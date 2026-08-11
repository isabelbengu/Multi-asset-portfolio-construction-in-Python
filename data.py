"""
Price data acquisition.

Primary path: download adjusted daily closes from Yahoo Finance and cache them
to data/raw/prices.csv so the backtest is reproducible offline.

Fallback path: if yfinance is unavailable or the download fails (no network,
delisted ticker, rate limit), generate a correlated synthetic price history
from the capital market assumptions in config.py. The fallback exists so the
repo runs end-to-end for anyone who clones it; results produced this way are
clearly flagged and must not be read as historical fact.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "prices.csv"


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def load_prices(
    start: str | None = None,
    end: str | None = None,
    use_cache: bool = True,
    allow_synthetic: bool = True,
) -> tuple[pd.DataFrame, bool]:
    """
    Return (prices, is_synthetic).

    prices: DataFrame indexed by date, one column per asset key in config.UNIVERSE.
    """
    end = end or pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
    if start is None:
        start = (pd.Timestamp(end) - pd.DateOffset(years=config.HORIZON_YEARS)).strftime("%Y-%m-%d")

    if use_cache and CACHE.exists():
        px = pd.read_csv(CACHE, index_col=0, parse_dates=True)
        missing = set(config.ASSET_KEYS) - set(px.columns)
        if not missing:
            px = px.loc[start:end]
            if len(px) > 250:
                return px, bool(os.environ.get("HNW_CACHE_IS_SYNTHETIC"))

    px = _download(start, end)
    if px is not None and not px.empty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        px.to_csv(CACHE)
        return px, False

    if not allow_synthetic:
        raise RuntimeError(
            "Price download failed and allow_synthetic=False. "
            "Check your network, or drop a prices.csv into data/raw/."
        )

    px = synthetic_prices(start, end)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    px.to_csv(CACHE)
    os.environ["HNW_CACHE_IS_SYNTHETIC"] = "1"
    return px, True


# --------------------------------------------------------------------------
# Yahoo Finance
# --------------------------------------------------------------------------

def _download(start: str, end: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
    except ImportError:
        print("[data] yfinance not installed -> falling back to synthetic history.")
        return None

    try:
        raw = yf.download(
            list(config.TICKERS.values()),
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:                      # noqa: BLE001
        print(f"[data] download failed ({exc}) -> falling back to synthetic history.")
        return None

    if raw is None or raw.empty:
        print("[data] download returned nothing -> falling back to synthetic history.")
        return None

    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    inv = {v: k for k, v in config.TICKERS.items()}
    close = close.rename(columns=inv)

    missing = set(config.ASSET_KEYS) - set(close.columns)
    if missing:
        print(f"[data] missing tickers {sorted(missing)} -> falling back to synthetic history.")
        return None

    close = close[config.ASSET_KEYS].ffill().dropna(how="any")
    if len(close) < 250:
        print("[data] too little overlapping history -> falling back to synthetic history.")
        return None
    return close


# --------------------------------------------------------------------------
# Synthetic fallback
# --------------------------------------------------------------------------

def _prior_correlation() -> np.ndarray:
    """Hand-set block correlation matrix consistent with the sleeve structure."""
    keys = config.ASSET_KEYS
    n = len(keys)
    c = np.eye(n)
    sleeve = {a.key: a.sleeve for a in config.UNIVERSE}
    base = {
        ("growth", "growth"): 0.80,
        ("defensive", "defensive"): 0.75,
        ("diversifier", "diversifier"): 0.15,
        ("growth", "defensive"): 0.05,
        ("growth", "diversifier"): 0.35,
        ("defensive", "diversifier"): 0.15,
    }
    for i in range(n):
        for j in range(i + 1, n):
            a, b = sleeve[keys[i]], sleeve[keys[j]]
            rho = base.get((a, b), base.get((b, a), 0.0))
            c[i, j] = c[j, i] = rho
    # gold is the genuine diversifier: pull its equity correlation down
    if "gold" in keys:
        g = keys.index("gold")
        for i in range(n):
            if i != g:
                c[g, i] = c[i, g] = 0.05 if sleeve[keys[i]] == "growth" else 0.20
    return _nearest_psd(c)


def _nearest_psd(mat: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh((mat + mat.T) / 2)
    vals = np.clip(vals, 1e-8, None)
    out = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.diag(out))
    return out / np.outer(d, d)


def synthetic_prices(start: str, end: str, seed: int | None = None) -> pd.DataFrame:
    """
    Correlated fat-tailed returns with a regime overlay, calibrated so the
    realised long-run moments match the capital market assumptions in config.

    Two design choices matter:

    1. Innovations are Student-t (df=5), standardised to unit variance, so the
       tails are fatter than Gaussian. A backtest that only ever sees normal
       returns flatters every risk model in it.
    2. The regime overlay is de-meaned before it is applied. It redistributes
       return through time -- a bear market, a recovery, a rate shock -- without
       secretly changing the long-run drift. Without this the "crisis" silently
       becomes a permanent haircut and the whole study measures an artefact.
    """
    rng = np.random.default_rng(config.SEED if seed is None else seed)
    dates = pd.bdate_range(start, end)
    n_days, keys = len(dates), config.ASSET_KEYS
    n = len(keys)

    mu = np.array([a.cma_return for a in config.UNIVERSE])
    vol = np.array([a.cma_vol for a in config.UNIVERSE])
    corr = _prior_correlation()
    chol = np.linalg.cholesky(corr)

    # fat-tailed, unit-variance innovations
    df = 5.0
    z = rng.standard_t(df, size=(n_days, n)) / np.sqrt(df / (df - 2.0))
    z = (z - z.mean(axis=0)) / z.std(axis=0, ddof=1)      # exact sample moments
    shocks = (z @ chol.T) * (vol / np.sqrt(252.0))

    drift = (mu - 0.5 * vol**2) / 252.0

    # ---- regime overlay ---------------------------------------------------
    is_growth = np.array([a.sleeve in ("growth", "diversifier") for a in config.UNIVERSE])
    is_bond = np.array([a.sleeve == "defensive" for a in config.UNIVERSE])

    shift = np.zeros((n_days, n))
    scale = np.ones((n_days, n))

    def _window(frac: float, days: int) -> slice:
        a = int(n_days * frac)
        return slice(a, min(a + days, n_days))

    # equity bear market: ~-25% over nine months, vol doubles
    bear = _window(0.28, 190)
    shift[bear] += np.where(is_growth, -0.0015, 0.0002)
    scale[bear] *= np.where(is_growth, 2.0, 1.15)

    # recovery: the mirror image, slower and calmer
    rebound = _window(0.36, 380)
    shift[rebound] += np.where(is_growth, 0.0009, -0.0001)

    # rate shock: bonds and equities fall together, the 60/40 nightmare
    rates = _window(0.72, 300)
    shift[rates] += np.where(is_bond, -0.00035, -0.00020)
    scale[rates] *= 1.30

    # normalisation after the rate shock
    after = _window(0.85, 300)
    shift[after] += np.where(is_bond, 0.00035, 0.00020)

    # de-mean the overlay: shape without a hidden change in drift
    shift -= shift.mean(axis=0, keepdims=True)

    rets = drift + shift + shocks * scale
    px = pd.DataFrame(100.0 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=keys)
    return px


def to_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna(how="all").fillna(0.0)
