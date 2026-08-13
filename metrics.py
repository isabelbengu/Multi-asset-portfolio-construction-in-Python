"""Performance, risk and cost metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .backtest import BacktestResult

TRADING_DAYS = 252


# --------------------------------------------------------------------------
# Core metrics
# --------------------------------------------------------------------------

def cagr(returns: pd.Series) -> float:
    years = len(returns) / TRADING_DAYS
    if years <= 0:
        return np.nan
    return float((1 + returns).prod() ** (1 / years) - 1)


def volatility(returns: pd.Series) -> float:
    return float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _excess(returns: pd.Series, rf: pd.Series | float | None) -> pd.Series:
    """
    Excess return over the risk-free rate.

    `rf` may be a daily series (preferred — euro cash went from -0.5% to +4%
    over this sample, and a constant would make every Sharpe ratio wrong in a
    direction that changes sign mid-study) or a scalar annual rate.
    """
    if rf is None:
        rf = config.CASH_RATE_PROXY
    if isinstance(rf, pd.Series):
        return returns - rf.reindex(returns.index).fillna(0.0)
    return returns - rf / TRADING_DAYS


def sharpe(returns: pd.Series, rf: pd.Series | float | None = None) -> float:
    excess = _excess(returns, rf)
    sd = excess.std(ddof=1)
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else np.nan


def sortino(returns: pd.Series, rf: pd.Series | float | None = None) -> float:
    excess = _excess(returns, rf)
    downside = excess[excess < 0].std(ddof=1)
    return float(excess.mean() / downside * np.sqrt(TRADING_DAYS)) if downside > 0 else np.nan


def wealth_index(res: "BacktestResult") -> pd.Series:
    """
    Time-weighted growth index, base 1.0.

    Built by compounding the withdrawal-adjusted return series rather than by
    adding cumulative withdrawals back onto the wealth path. The naive version
    understates the peak, because cash paid out in year 2 is credited at face
    value in year 14 instead of being allowed to compound -- which quietly turns
    a scheduled income payment into a permanent 'drawdown' the portfolio can
    never recover from.
    """
    return (1.0 + res.returns).cumprod()


def drawdown_series(index: pd.Series) -> pd.Series:
    """Drawdown of a growth index. Pass wealth_index(res), not res.equity."""
    peak = index.cummax()
    return index / peak - 1.0


def max_drawdown(index: pd.Series) -> float:
    return float(drawdown_series(index).min())


def drawdown_table(index: pd.Series, top: int = 5) -> pd.DataFrame:
    """The `top` worst peak-to-trough episodes, with recovery dates."""
    dd = drawdown_series(index)
    rows, in_dd, peak_date = [], False, None

    for dt, v in dd.items():
        if not in_dd and v < 0:
            in_dd, peak_date = True, dt
        elif in_dd and v >= 0:
            seg = dd.loc[peak_date:dt]
            rows.append({"start": peak_date, "trough": seg.idxmin(), "end": dt,
                         "depth": seg.min(), "days": (dt - peak_date).days,
                         "recovered": True})
            in_dd = False
    if in_dd:
        seg = dd.loc[peak_date:]
        rows.append({"start": peak_date, "trough": seg.idxmin(), "end": pd.NaT,
                     "depth": seg.min(), "days": (dd.index[-1] - peak_date).days,
                     "recovered": False})

    if not rows:
        return pd.DataFrame(columns=["start", "trough", "end", "depth", "days", "recovered"])
    out = pd.DataFrame(rows).sort_values("depth").head(top).reset_index(drop=True)
    for col in ("start", "trough", "end"):
        out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d").fillna("not recovered")
    return out


def value_at_risk(returns: pd.Series, level: float = 0.95) -> float:
    return float(np.percentile(returns, (1 - level) * 100))


def conditional_var(returns: pd.Series, level: float = 0.95) -> float:
    var = value_at_risk(returns, level)
    tail = returns[returns <= var]
    return float(tail.mean()) if len(tail) else var


def ulcer_index(index: pd.Series) -> float:
    dd = drawdown_series(index)
    return float(np.sqrt((dd**2).mean()))


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

def summarise(res: BacktestResult) -> dict:
    r = res.returns
    idx = wealth_index(res)
    ann_turnover = float(res.turnover.sum() / (len(r) / TRADING_DAYS)) if len(res.turnover) else 0.0
    total_costs = res.costs.sum()
    mdd = max_drawdown(idx)

    return {
        "Strategy": res.name,
        "CAGR": cagr(r),
        "Volatility": volatility(r),
        "Sharpe": sharpe(r, res.cash),
        "Sortino": sortino(r, res.cash),
        "Max drawdown": mdd,
        "Calmar": cagr(r) / abs(mdd) if mdd else np.nan,
        "Ulcer index": ulcer_index(idx),
        "VaR 95% (daily)": value_at_risk(r),
        "CVaR 95% (daily)": conditional_var(r),
        "Turnover p.a.": ann_turnover,
        "Rebalances": len(res.turnover),
        "Terminal value": float(res.equity.iloc[-1]),
        "Terminal real value": float(res.equity.iloc[-1]) / (1 + config.ASSUMED_INFLATION) ** (len(r) / TRADING_DAYS),
        "Income paid": float(res.withdrawals.sum()),
        "Transaction cost": float(total_costs["transaction"]),
        "Ongoing charge": float(total_costs["ongoing"]),
        "Capital gains tax": float(total_costs["capital_gains_tax"]),
        "Imposta di bollo": float(total_costs["imposta_di_bollo"]),
    }


def comparison_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    df = pd.DataFrame([summarise(r) for r in results.values()]).set_index("Strategy").T
    return df


def attribution_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """
    EUR contribution to P&L by asset, and the average weight that earned it.

    Contribution is sum over days of (asset value at open x asset return), so
    the column adds up to total gross P&L before withdrawals, costs and tax.
    """
    frames = {}
    for name, res in results.items():
        frames[f"{name} — €"] = res.attribution
        frames[f"{name} — avg w"] = res.weights.mean()
    out = pd.DataFrame(frames)
    names = {a.key: a.name for a in config.UNIVERSE}
    return out.rename(index=names)


def format_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """€ columns as thousands, weight columns as percentages."""
    out = df.copy().astype(object)
    for col in df.columns:
        if col.endswith("avg w"):
            out[col] = df[col].map(lambda v: f"{v:.1%}")
        else:
            out[col] = df[col].map(lambda v: f"€{v:,.0f}")
    return out


def format_table(df: pd.DataFrame) -> pd.DataFrame:
    """Human-readable formatting for the console and README."""
    pct_rows = ["CAGR", "Volatility", "Max drawdown", "Turnover p.a.",
                "VaR 95% (daily)", "CVaR 95% (daily)", "Ulcer index"]
    eur_rows = ["Terminal value", "Terminal real value", "Income paid",
                "Transaction cost", "Ongoing charge", "Capital gains tax",
                "Imposta di bollo"]
    ratio_rows = ["Sharpe", "Sortino", "Calmar"]

    out = df.copy().astype(object)
    for idx in df.index:
        for col in df.columns:
            v = df.loc[idx, col]
            if idx in pct_rows:
                out.loc[idx, col] = f"{v:.2%}"
            elif idx in eur_rows:
                out.loc[idx, col] = f"€{v:,.0f}"
            elif idx in ratio_rows:
                out.loc[idx, col] = f"{v:.2f}"
            else:
                out.loc[idx, col] = f"{v:,.0f}"
    return out
