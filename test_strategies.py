"""
Tests for the allocators, the tax helper and the backtest invariants.

These are the checks that catch the errors which would otherwise look like
results: weights that don't sum to one, a risk parity solution that isn't
actually equal-risk, a lookback window that peeks at the future.

    pytest -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import config, data
from src.backtest import _tax_on_gains, run_backtest
from src.strategies import (
    STRATEGIES,
    mean_variance,
    risk_contributions,
    risk_parity,
    static_6040,
    annualised_moments,
)


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return data.synthetic_prices("2012-01-01", "2022-01-01", seed=7)


@pytest.fixture(scope="module")
def window(prices) -> pd.DataFrame:
    return prices.pct_change().dropna()


# --------------------------------------------------------------------------
# Allocators
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(STRATEGIES))
def test_weights_sum_to_one_and_are_long_only(window, name):
    w = STRATEGIES[name](window)
    assert np.isclose(w.sum(), 1.0, atol=1e-8)
    assert (w >= -1e-9).all()
    assert set(w.index) == set(window.columns)


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_concentration_cap_respected(window, name):
    w = STRATEGIES[name](window)
    assert w.max() <= config.MAX_WEIGHT + 1e-6


def test_static_6040_matches_policy(window):
    w = static_6040(window)
    assert np.isclose(w["dm_equity"], config.POLICY_6040["dm_equity"], atol=1e-9)
    growth = w[[k for k in config.GROWTH_KEYS]].sum()
    assert np.isclose(growth, 0.60, atol=1e-9)


def test_risk_parity_equalises_risk_contributions(window):
    w = risk_parity(window)
    _, cov = annualised_moments(window, shrinkage=0.0)
    rc = risk_contributions(w, cov)
    # every asset should carry the same share of portfolio variance
    assert rc.std() < 0.02, f"risk contributions not equal: {rc.to_dict()}"
    assert np.isclose(rc.sum(), 1.0, atol=1e-6)


def test_risk_parity_beats_equal_weight_on_concentration(window):
    """The whole point: risk parity should hold less of the volatile assets."""
    w = risk_parity(window)
    vols = window.std() * np.sqrt(252)
    # weight and volatility should be inversely related
    assert np.corrcoef(w.values, vols.values)[0, 1] < 0


def test_mean_variance_respects_ips_constraints(window):
    w = mean_variance(window)
    growth = w[[k for k in config.GROWTH_KEYS]].sum()
    defensive = w[[k for k in config.DEFENSIVE_KEYS]].sum()
    assert growth <= config.MAX_GROWTH + 1e-6
    assert defensive >= config.MIN_DEFENSIVE - 1e-6


def test_shrinkage_pulls_estimates_toward_the_prior(window):
    mu_sample, _ = annualised_moments(window, shrinkage=0.0)
    mu_shrunk, _ = annualised_moments(window, shrinkage=1.0)
    prior = np.array([a.cma_return for a in config.UNIVERSE])
    assert np.allclose(mu_shrunk, prior, atol=1e-9)
    assert not np.allclose(mu_sample, prior, atol=1e-3)


# --------------------------------------------------------------------------
# Tax
# --------------------------------------------------------------------------

def test_whitelist_government_bonds_taxed_at_lower_rate():
    gains = np.array([1000.0, 1000.0])
    rates = np.array([config.CGT_RATE_STANDARD, config.CGT_RATE_WHITELIST_GOVT])
    tax, pool = _tax_on_gains(gains, rates, loss_pool=0.0)
    assert np.isclose(tax, 1000 * 0.26 + 1000 * 0.125)
    assert pool == 0.0


def test_losses_carry_forward_and_offset_later_gains():
    # realise a 500 loss, then a 500 gain: net tax should be zero
    _, pool = _tax_on_gains(np.array([-500.0]), np.array([0.26]), 0.0)
    assert np.isclose(pool, 500.0)
    tax, pool = _tax_on_gains(np.array([500.0]), np.array([0.26]), pool)
    assert np.isclose(tax, 0.0)
    assert np.isclose(pool, 0.0)


def test_partial_loss_offset():
    tax, pool = _tax_on_gains(np.array([1000.0]), np.array([0.26]), loss_pool=400.0)
    assert np.isclose(tax, 600 * 0.26)
    assert np.isclose(pool, 0.0)


# --------------------------------------------------------------------------
# Backtest invariants
# --------------------------------------------------------------------------

def test_no_lookahead_in_estimation_window(prices, monkeypatch):
    """
    The allocator must never see a return dated on or after the rebalance date.
    We assert it by spying on every window the engine passes in.
    """
    seen: list[pd.Timestamp] = []

    def spy(window: pd.DataFrame) -> pd.Series:
        if len(window):
            seen.append(window.index[-1])
        return static_6040(window)

    monkeypatch.setitem(STRATEGIES, "60/40", spy)
    res = run_backtest(prices, "60/40")
    reb_dates = list(res.turnover.index)

    for w_end, reb in zip(seen[1:], reb_dates):
        assert w_end < reb, f"window ending {w_end} used at rebalance {reb}"


def test_all_strategies_share_a_start_date(prices):
    results = {n: run_backtest(prices, n) for n in ("60/40", "Risk parity")}
    starts = {r.equity.index[0] for r in results.values()}
    assert len(starts) == 1, "strategies compared over different windows"


def test_portfolio_stays_fully_invested(prices):
    res = run_backtest(prices, "60/40")
    assert np.allclose(res.weights.sum(axis=1), 1.0, atol=1e-6)


def test_income_is_paid_and_indexed(prices):
    res = run_backtest(prices, "60/40")
    wd = res.withdrawals
    assert len(wd) > 0
    # later payments exceed earlier ones because they are inflation-indexed
    assert wd.iloc[-1] > wd.iloc[0]


def test_tax_toggle_changes_the_outcome(prices):
    gross = run_backtest(prices, "60/40", apply_tax=False)
    net = run_backtest(prices, "60/40", apply_tax=True)
    assert net.equity.iloc[-1] < gross.equity.iloc[-1]
    assert net.costs["capital_gains_tax"].sum() > 0
    assert np.isclose(gross.costs["capital_gains_tax"].sum(), 0.0)


def test_no_trade_band_reduces_turnover(prices, monkeypatch):
    monkeypatch.setattr(config, "REBALANCE_BAND", 0.0)
    unbanded = run_backtest(prices, "60/40").turnover.sum()
    monkeypatch.setattr(config, "REBALANCE_BAND", 0.015)
    banded = run_backtest(prices, "60/40").turnover.sum()
    assert banded < unbanded
