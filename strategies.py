"""
Three allocators, each exposing the same interface:

    allocator(returns_window: pd.DataFrame) -> pd.Series of target weights

`returns_window` is the trailing daily return history available at the
rebalance date. Nothing downstream of the rebalance date is passed in, which
is what keeps the backtest free of look-ahead bias.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import config

TRADING_DAYS = 252


# --------------------------------------------------------------------------
# Estimation helpers
# --------------------------------------------------------------------------

def annualised_moments(window: pd.DataFrame, shrinkage: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """
    Sample mean/covariance, annualised, optionally shrunk toward the capital
    market assumptions in config. Sample means over a 3-5 year window are a
    notoriously noisy input to MVO; shrinkage is the cheapest available fix.
    """
    keys = list(window.columns)
    mu_s = window.mean().values * TRADING_DAYS
    cov_s = window.cov().values * TRADING_DAYS

    if shrinkage <= 0:
        return mu_s, cov_s

    prior = {a.key: a for a in config.UNIVERSE}
    mu_p = np.array([prior[k].cma_return for k in keys])

    # shrink covariance toward a constant-correlation target (Ledoit-Wolf style)
    vol = np.sqrt(np.diag(cov_s))
    corr = cov_s / np.outer(vol, vol)
    n = len(keys)
    off = corr[~np.eye(n, dtype=bool)]
    rho_bar = off.mean()
    target = np.full((n, n), rho_bar)
    np.fill_diagonal(target, 1.0)
    cov_p = np.outer(vol, vol) * target

    mu = (1 - shrinkage) * mu_s + shrinkage * mu_p
    cov = (1 - shrinkage) * cov_s + shrinkage * cov_p
    return mu, cov


def _constraints(keys: list[str]) -> list[dict]:
    growth_mask = np.array([k in config.GROWTH_KEYS for k in keys], dtype=float)
    defensive_mask = np.array([k in config.DEFENSIVE_KEYS for k in keys], dtype=float)
    return [
        {"type": "eq", "fun": lambda w: w.sum() - 1.0},
        {"type": "ineq", "fun": lambda w: config.MAX_GROWTH - w @ growth_mask},
        {"type": "ineq", "fun": lambda w: w @ defensive_mask - config.MIN_DEFENSIVE},
    ]


# --------------------------------------------------------------------------
# 1. Strategic 60/40
# --------------------------------------------------------------------------

def static_6040(window: pd.DataFrame) -> pd.Series:
    """Fixed policy weights. The benchmark every other strategy has to beat."""
    w = pd.Series(config.POLICY_6040, dtype=float).reindex(window.columns).fillna(0.0)
    return w / w.sum()


# --------------------------------------------------------------------------
# 2. Mean-variance
# --------------------------------------------------------------------------

def mean_variance(window: pd.DataFrame) -> pd.Series:
    keys = list(window.columns)
    n = len(keys)
    mu, cov = annualised_moments(window, shrinkage=config.MVO_SHRINKAGE)
    rf = config.CASH_RATE_PROXY

    def neg_sharpe(w):
        r = w @ mu
        s = np.sqrt(max(w @ cov @ w, 1e-12))
        return -(r - rf) / s

    def variance(w):
        return w @ cov @ w

    obj = {"max_sharpe": neg_sharpe, "min_vol": variance, "target_vol": variance}[config.MVO_OBJECTIVE]

    cons = _constraints(keys)
    if config.MVO_OBJECTIVE == "target_vol":
        cons.append({"type": "ineq", "fun": lambda w: config.MVO_TARGET_VOL**2 - w @ cov @ w})
        obj = lambda w: -(w @ mu)                                    # noqa: E731

    bounds = [(config.MIN_WEIGHT, config.MAX_WEIGHT)] * n
    x0 = np.full(n, 1.0 / n)

    res = minimize(obj, x0, method="SLSQP", bounds=bounds, constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-10})

    w = res.x if res.success else x0
    w = np.clip(w, 0, None)
    return pd.Series(w / w.sum(), index=keys)


# --------------------------------------------------------------------------
# 3. Risk parity (equal risk contribution)
# --------------------------------------------------------------------------

def risk_parity(window: pd.DataFrame) -> pd.Series:
    """
    Solve for weights where each asset contributes the same share of portfolio
    variance: w_i * (Sigma w)_i equal for all i. Long-only, fully invested.
    Covariance only -- no expected-return input, which is the whole point.
    """
    keys = list(window.columns)
    n = len(keys)
    _, cov = annualised_moments(window, shrinkage=0.0)
    cov = cov + np.eye(n) * 1e-10

    target = np.full(n, 1.0 / n)

    def risk_budget_error(w):
        port_var = w @ cov @ w
        mrc = cov @ w                        # marginal risk contribution
        rc = w * mrc / max(port_var, 1e-12)  # % contribution to variance
        return np.sum((rc - target) ** 2)

    bounds = [(1e-6, config.MAX_WEIGHT)] * n
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]

    # inverse-vol start point gets SLSQP close before it begins
    inv_vol = 1.0 / np.sqrt(np.diag(cov))
    x0 = inv_vol / inv_vol.sum()

    res = minimize(risk_budget_error, x0, method="SLSQP", bounds=bounds,
                   constraints=cons, options={"maxiter": config.RP_MAX_ITER, "ftol": config.RP_TOLERANCE})

    w = res.x if res.success else x0
    w = np.clip(w, 0, None)
    return pd.Series(w / w.sum(), index=keys)


def risk_contributions(weights: pd.Series, cov: np.ndarray) -> pd.Series:
    """Diagnostic: % of portfolio variance contributed by each asset."""
    w = weights.values
    port_var = w @ cov @ w
    rc = w * (cov @ w) / max(port_var, 1e-12)
    return pd.Series(rc, index=weights.index)


STRATEGIES = {
    "60/40": static_6040,
    "Mean-variance": mean_variance,
    "Risk parity": risk_parity,
}

LOOKBACK_YEARS = {
    "60/40": 1,                                  # unused, but keeps the loop uniform
    "Mean-variance": config.MVO_LOOKBACK_YEARS,
    "Risk parity": config.RP_LOOKBACK_YEARS,
}
