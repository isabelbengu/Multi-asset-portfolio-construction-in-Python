"""
Backtest engine.

Daily loop over asset values in EUR. On each date, in order:

  1. mark to market
  2. accrue the ongoing charge (TER) pro rata
  3. on withdrawal dates, raise the income payment
  4. on rebalance dates, trade toward the allocator's target weights,
     paying transaction costs and realising capital gains tax
  5. on 31 December, pay the 0.20% imposta di bollo (IVAFE)

Tax model (simplified, see IPS section 6):
  - realised gains taxed on sale at 26%, or 12.5% for whitelist government bonds
  - realised losses go into a carry-forward pool (Italy allows 4 years) and
    offset later gains before tax is charged
  - accumulating UCITS ETFs are assumed, so no annual dividend leakage
  - the ETF 'redditi di capitale vs redditi diversi' asymmetry is NOT modelled;
    in reality ETF gains cannot be offset by ETF losses, which makes the real
    tax drag somewhat worse than shown here
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .strategies import LOOKBACK_YEARS, STRATEGIES

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series                 # portfolio value, EUR
    weights: pd.DataFrame             # daily end-of-day weights
    target_weights: pd.DataFrame      # weights set at each rebalance
    turnover: pd.Series               # one-way turnover per rebalance
    withdrawals: pd.Series
    costs: pd.DataFrame               # transaction, ongoing, tax, bollo
    attribution: pd.Series            # EUR contribution by asset
    is_synthetic: bool = False
    meta: dict = field(default_factory=dict)

    @property
    def returns(self) -> pd.Series:
        """
        Time-weighted returns: withdrawals are added back so the return series
        measures the manager, not the cash flow schedule.
        """
        v = self.equity
        w = self.withdrawals.reindex(v.index).fillna(0.0)
        return ((v + w) / v.shift(1) - 1.0).iloc[1:]


# --------------------------------------------------------------------------
# Schedule helpers
# --------------------------------------------------------------------------

def common_start_index(n_obs: int) -> int:
    """Longest estimation window required by any strategy, in trading days."""
    need = int(max(LOOKBACK_YEARS.values()) * TRADING_DAYS)
    if need >= n_obs - TRADING_DAYS * 2:
        need = max(1, n_obs // 5)
    return need


def _period_ends(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    if freq not in {"M", "Q", "A"}:
        raise ValueError(f"unsupported frequency {freq!r}")
    alias = {"M": "ME", "Q": "QE", "A": "YE"}[freq]
    marks = pd.Series(index=index, data=1).resample(alias).last().index
    out = [index[index <= m][-1] for m in marks if len(index[index <= m])]
    return pd.DatetimeIndex(sorted(set(out)))


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

def run_backtest(
    prices: pd.DataFrame,
    strategy_name: str,
    initial_capital: float = config.INITIAL_CAPITAL,
    income_annual: float = config.INCOME_NEED_ANNUAL,
    apply_tax: bool | None = None,
    is_synthetic: bool = False,
    start_i: int | None = None,
) -> BacktestResult:

    apply_tax = config.APPLY_TAX_DRAG if apply_tax is None else apply_tax
    allocator = STRATEGIES[strategy_name]
    lookback_days = int(LOOKBACK_YEARS[strategy_name] * TRADING_DAYS)

    rets = prices.pct_change().fillna(0.0)
    keys = list(prices.columns)
    n = len(keys)
    tax_rate = np.array([
        config.CGT_RATE_WHITELIST_GOVT if a.whitelist_govt else config.CGT_RATE_STANDARD
        for a in config.UNIVERSE if a.key in keys
    ])

    # The first `start_i` observations are burned in as the estimation window.
    # It defaults to the longest lookback of ANY strategy, not just this one, so
    # every strategy is measured over an identical window. Comparing a 60/40 that
    # starts on day 1 against an MVO that starts five years later is not a
    # comparison of strategies, it is a comparison of start dates.
    if start_i is None:
        start_i = common_start_index(len(prices))
    dates = prices.index[start_i:]

    reb_dates = set(_period_ends(dates, config.REBALANCE_FREQ))
    wd_dates = sorted(_period_ends(dates, config.WITHDRAWAL_FREQ))
    wd_per_year = {"M": 12, "Q": 4, "A": 1}[config.WITHDRAWAL_FREQ]
    bollo_dates = set(_period_ends(dates, "A"))

    # state
    values = np.zeros(n)
    basis = np.zeros(n)               # tax cost basis per asset, EUR
    loss_pool = 0.0                   # minusvalenze carry-forward
    daily_ter = config.ONGOING_CHARGE_BPS / 1e4 / TRADING_DAYS
    tc_rate = config.TRANSACTION_COST_BPS / 1e4

    equity, w_hist, tgt_hist, turn_hist = [], [], {}, {}
    wd_hist, cost_rows, attrib = {}, [], np.zeros(n)

    # seed the portfolio on day one
    w0 = allocator(rets.iloc[max(0, start_i - lookback_days):start_i])
    w0 = w0.reindex(keys).fillna(0.0).values
    values = initial_capital * w0
    basis = values.copy()
    last_target = w0.copy()
    tgt_hist[dates[0]] = pd.Series(w0, index=keys)

    for i, dt in enumerate(dates):
        r = rets.loc[dt].values
        prev_total = values.sum()

        # 1-2. mark to market, net of the ongoing charge
        if i > 0 and prev_total > 0:
            attrib += (values / prev_total) * r * prev_total
        values = values * (1.0 + r) * (1.0 - daily_ter)
        ongoing_cost = prev_total * daily_ter

        tx_cost = tax_paid = bollo = wd_amt = 0.0
        total = values.sum()

        # 3. income withdrawal.
        # Sourced from positions that are overweight against the standing
        # target, so the withdrawal does part of the rebalancing work for free
        # (IPS section 7). Falls back to pro rata when nothing is overweight.
        if dt in wd_dates and total > 0:
            years_elapsed = (dt - dates[0]).days / 365.25
            infl = (1 + config.ASSUMED_INFLATION) ** years_elapsed if config.INCOME_INDEXED_TO_INFLATION else 1.0
            wd_amt = min(income_annual / wd_per_year * infl, total * 0.9)

            over = np.maximum(values / total - last_target, 0.0)
            share = over / over.sum() if over.sum() > 1e-8 else values / total
            share = np.minimum(share, values / max(wd_amt, 1e-9))    # never oversell a line
            if share.sum() < 1.0:                                    # top up pro rata
                gap = 1.0 - share.sum()
                pro = values / total
                share = share + pro * gap / max(pro.sum(), 1e-9)
            sold = share * wd_amt
            gains = sold - basis * (sold / np.maximum(values, 1e-9))
            basis -= basis * (sold / np.maximum(values, 1e-9))
            values -= sold
            if apply_tax:
                tax_paid, loss_pool = _tax_on_gains(gains, tax_rate, loss_pool)
                values -= (values / max(values.sum(), 1e-9)) * tax_paid
            wd_hist[dt] = wd_amt
            total = values.sum()

        # 4. rebalance
        if dt in reb_dates and total > 0:
            window = rets.iloc[max(0, i + start_i - lookback_days): i + start_i]
            if len(window) >= 60:
                tgt = allocator(window).reindex(keys).fillna(0.0).values
                tgt = tgt / tgt.sum()
                last_target = tgt.copy()

                # no-trade band: leave lines that are close enough alone, then
                # renormalise so the traded lines absorb the residual. Trading a
                # 40bp deviation costs more in spread and realised tax than the
                # tracking error it removes.
                cur_w = values / total
                hold = np.abs(tgt - cur_w) < config.REBALANCE_BAND
                eff = np.where(hold, cur_w, tgt)
                eff = eff / eff.sum()

                target_vals = total * eff
                trades = target_vals - values

                one_way = np.abs(trades).sum() / 2.0
                tx_cost = one_way * 2 * tc_rate
                turn_hist[dt] = one_way / total

                sells = np.minimum(trades, 0.0)
                sold = -sells
                gains = sold - basis * (sold / np.maximum(values, 1e-9))
                basis -= basis * (sold / np.maximum(values, 1e-9))
                if apply_tax:
                    tax_paid, loss_pool = _tax_on_gains(gains, tax_rate, loss_pool)

                buys = np.maximum(trades, 0.0)
                basis += buys

                values = target_vals
                drag = tx_cost + tax_paid
                values -= (values / max(values.sum(), 1e-9)) * drag
                tgt_hist[dt] = pd.Series(tgt, index=keys)
                total = values.sum()

        # 5. imposta di bollo
        if dt in bollo_dates and total > 0:
            bollo = total * config.IVAFE_RATE
            values -= (values / total) * bollo
            total = values.sum()

        equity.append(total)
        w_hist.append(values / total if total > 0 else np.zeros(n))
        cost_rows.append((dt, tx_cost, ongoing_cost, tax_paid, bollo))

    idx = pd.DatetimeIndex(dates)
    costs = pd.DataFrame(
        [c[1:] for c in cost_rows], index=idx,
        columns=["transaction", "ongoing", "capital_gains_tax", "imposta_di_bollo"],
    )

    return BacktestResult(
        name=strategy_name,
        equity=pd.Series(equity, index=idx, name=strategy_name),
        weights=pd.DataFrame(w_hist, index=idx, columns=keys),
        target_weights=pd.DataFrame(tgt_hist).T.reindex(columns=keys),
        turnover=pd.Series(turn_hist, name="turnover").sort_index(),
        withdrawals=pd.Series(wd_hist, name="withdrawals").sort_index(),
        costs=costs,
        attribution=pd.Series(attrib, index=keys, name="attribution_eur"),
        is_synthetic=is_synthetic,
        meta={"initial_capital": initial_capital, "income_annual": income_annual,
              "tax_applied": apply_tax, "rebalance": config.REBALANCE_FREQ},
    )


def _tax_on_gains(gains: np.ndarray, rates: np.ndarray, loss_pool: float) -> tuple[float, float]:
    """Apply the loss carry-forward pool, then tax what's left."""
    losses = -gains[gains < 0].sum()
    loss_pool += losses

    tax = 0.0
    for g, rate in zip(gains, rates):
        if g <= 0:
            continue
        offset = min(g, loss_pool)
        loss_pool -= offset
        tax += (g - offset) * rate
    return tax, loss_pool


def run_all(prices: pd.DataFrame, is_synthetic: bool = False, **kw) -> dict[str, BacktestResult]:
    si = common_start_index(len(prices))
    return {name: run_backtest(prices, name, is_synthetic=is_synthetic, start_i=si, **kw)
            for name in STRATEGIES}
