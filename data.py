"""
Data acquisition.

Three sources, three different reliability profiles, handled separately:

  prices     yfinance, EUR-denominated UCITS ETFs, cached to data/raw/prices.csv
  cash rate  XEON.DE total return (an overnight-rate tracker), cross-checked
             against the ECB's published €STR series in data/macro/
  inflation  Italian HICP from FRED (Eurostat series), data/macro/

A note on the cash rate, because the choice is not obvious. The ECB publishes
€STR only from October 2019. A backtest starting in 2010 that uses it directly
has no risk-free rate for its first decade, and splicing EONIA onto the front
is fiddly. Instead the risk-free rate is taken from the *total return of an
overnight-rate ETF* (XEON.DE, which tracks €STR and tracked EONIA before it).
That series runs from 2008, is denominated in EUR, and is net of the frictions
a real investor actually pays to hold cash. The ECB file is then used to verify
the tracker behaves as advertised, rather than as the primary input.

Synthetic prices remain available for tests and for anyone cloning the repo
without network access. They are never used silently.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MACRO = ROOT / "data" / "macro"

PRICE_CACHE = RAW / "prices.csv"
CASH_CACHE = RAW / "cash.csv"

FRED_HICP_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + config.HICP_FRED_SERIES
)


# --------------------------------------------------------------------------
# Prices
# --------------------------------------------------------------------------

def load_prices(
    start: str | None = None,
    end: str | None = None,
    use_cache: bool = True,
    allow_synthetic: bool = False,
) -> tuple[pd.DataFrame, bool]:
    """
    Return (prices, is_synthetic) for the investable universe, EUR, adjusted
    for distributions.

    The frame is trimmed to the window where every asset has data. That common
    start date is reported loudly, because it is usually later than the date
    asked for, and quietly shortening the study is how a backtest ends up
    measuring something other than what its title claims.
    """
    if use_cache and PRICE_CACHE.exists():
        px = pd.read_csv(PRICE_CACHE, index_col=0, parse_dates=True)
        if not set(config.ASSET_KEYS) - set(px.columns):
            px = _trim(px[config.ASSET_KEYS], start, end)
            if len(px) > 250:
                return px, False

    px = _download(list(config.TICKERS.values()), start, end)
    if px is not None:
        px = px.rename(columns={v: k for k, v in config.TICKERS.items()})[config.ASSET_KEYS]
        px = _trim(px, start, end)
        RAW.mkdir(parents=True, exist_ok=True)
        px.to_csv(PRICE_CACHE)
        return px, False

    if not allow_synthetic:
        raise RuntimeError(
            "Price download failed and allow_synthetic=False.\n"
            "  - pip install yfinance\n"
            "  - check network access to query1.finance.yahoo.com\n"
            "  - or place a prices.csv (dates x asset keys) in data/raw/"
        )

    warnings.warn("Falling back to SYNTHETIC prices. Results are not history.", stacklevel=2)
    return synthetic_prices(start or "2010-01-01", end or "2026-01-01"), True


def load_cash_rate(index: pd.DatetimeIndex, use_cache: bool = True) -> tuple[pd.Series, str]:
    """
    Daily risk-free return aligned to `index`, as a decimal daily rate.

    Returns (series, provenance) so the write-up can state which source was
    actually used instead of assuming.
    """
    s = None
    if use_cache and CASH_CACHE.exists():
        s = pd.read_csv(CASH_CACHE, index_col=0, parse_dates=True).iloc[:, 0]

    if s is None:
        px = _download([config.CASH_TICKER], None, None)
        if px is None:
            rate = config.CASH_RATE_FALLBACK
            warnings.warn(
                f"Cash tracker {config.CASH_TICKER} unavailable; using a flat "
                f"{rate:.2%} risk-free rate. Sharpe ratios are indicative only.",
                stacklevel=2,
            )
            return pd.Series(rate / 252.0, index=index), f"flat {rate:.2%} (fallback)"
        s = px.iloc[:, 0]
        RAW.mkdir(parents=True, exist_ok=True)
        s.to_frame("cash").to_csv(CASH_CACHE)

    daily = s.reindex(s.index.union(index)).ffill().reindex(index).pct_change()
    daily = daily.fillna(0.0).clip(-0.01, 0.01)      # guard against data artefacts
    return daily, f"{config.CASH_TICKER} total return"


def verify_cash_tracker(daily_cash: pd.Series) -> pd.DataFrame | None:
    """
    Cross-check the ETF-derived cash return against the ECB's published €STR.

    A tracker that drifts materially from the rate it claims to track is worth
    knowing about before it silently sets every Sharpe ratio in the study.
    Returns None when the ECB file is absent or the overlap is too short.
    """
    ecb = load_estr()
    if ecb is None:
        return None
    overlap = daily_cash.index.intersection(ecb.index)
    if len(overlap) < 250:
        return None

    tracker = (1 + daily_cash.loc[overlap]).prod() ** (252 / len(overlap)) - 1
    published = ecb.loc[overlap].mean() / 100.0
    return pd.DataFrame(
        {"annualised": [tracker, published, tracker - published]},
        index=[f"{config.CASH_TICKER} realised", "ECB €STR published", "difference"],
    )


# --------------------------------------------------------------------------
# Macro series
# --------------------------------------------------------------------------

def load_estr() -> pd.Series | None:
    """
    ECB Data Portal export of the euro short-term rate, in percent.

    Handles the portal's actual export shape: quoted fields, a redundant
    human-readable date column, and a value column whose name embeds the whole
    series key. Any data/macro/estr*.csv is accepted.
    """
    hits = sorted(MACRO.glob("estr*.csv"))
    if not hits:
        return None
    df = pd.read_csv(hits[0])
    date_col = df.columns[0]
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    val_col = num_cols[-1] if num_cols else df.columns[-1]
    s = pd.Series(
        pd.to_numeric(df[val_col], errors="coerce").values,
        index=pd.to_datetime(df[date_col], errors="coerce"),
        name="estr",
    ).dropna()
    return s[~s.index.duplicated()].sort_index()


def load_hicp() -> pd.Series | None:
    """
    Italian HICP, monthly index level, from a FRED CSV export.

    Fetch once with `python -m src.fetch_macro`, or download by hand from
    FRED_HICP_URL into data/macro/.
    """
    hits = sorted(MACRO.glob("hicp*.csv"))
    if not hits:
        return None
    df = pd.read_csv(hits[0])
    s = pd.Series(
        pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
        index=pd.to_datetime(df.iloc[:, 0], errors="coerce"),
        name="hicp",
    ).dropna()
    return s[~s.index.duplicated()].sort_index()


def inflation_factor(index: pd.DatetimeIndex) -> tuple[pd.Series, str]:
    """
    Cumulative inflation factor aligned to `index`, base 1.0 at the start,
    used to index the client's income need.

    Falls back to the flat assumption in config when HICP is missing, and
    reports which was used. The difference is not cosmetic: 2021-23 euro area
    inflation ran far above any 2% assumption, and a study that indexes income
    at 2% through that period understates the real withdrawal burden.
    """
    hicp = load_hicp()
    if hicp is None or len(hicp) < 24:
        years = (index - index[0]).days / 365.25
        return (pd.Series((1 + config.ASSUMED_INFLATION) ** years, index=index),
                f"assumed {config.ASSUMED_INFLATION:.1%} p.a.")

    aligned = hicp.reindex(hicp.index.union(index)).ffill().reindex(index).bfill()
    return aligned / aligned.iloc[0], "Italian HICP (Eurostat via FRED)"


# --------------------------------------------------------------------------
# yfinance
# --------------------------------------------------------------------------

def _download(tickers: list[str], start: str | None, end: str | None) -> pd.DataFrame | None:
    try:
        import yfinance as yf
    except ImportError:
        print("[data] yfinance not installed (pip install yfinance)")
        return None

    try:
        raw = yf.download(tickers, start=start, end=end, auto_adjust=True,
                          progress=False, threads=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[data] download failed: {exc}")
        return None

    if raw is None or raw.empty:
        print("[data] download returned no rows")
        return None

    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])

    missing = set(tickers) - set(close.columns)
    if missing:
        print(f"[data] no data for {sorted(missing)}")
        return None

    return close.ffill().dropna(how="all")


def _trim(px: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    px = px.dropna(how="any")
    if start:
        px = px.loc[px.index >= pd.Timestamp(start)]
    if end:
        px = px.loc[px.index <= pd.Timestamp(end)]
    return px


def coverage_report(tickers: dict[str, str] | None = None) -> pd.DataFrame:
    """
    First and last available date per ticker, and the resulting common window.

    Run this before trusting any result. European UCITS ETFs have wildly
    different inception dates, and one 2017 launch silently truncates a study
    that claims fifteen years.
    """
    tickers = tickers or config.TICKERS
    px = _download(list(tickers.values()), None, None)
    if px is None:
        return pd.DataFrame()
    inv = {v: k for k, v in tickers.items()}
    rows = []
    for tk in tickers.values():
        s = px[tk].dropna()
        rows.append({"asset": inv[tk], "ticker": tk,
                     "first": s.index[0].date() if len(s) else None,
                     "last": s.index[-1].date() if len(s) else None,
                     "obs": len(s)})
    common = px.dropna(how="any")
    if len(common):
        print(f"Common window: {common.index[0].date()} to {common.index[-1].date()} "
              f"({len(common) / 252:.1f} years)")
    return pd.DataFrame(rows).sort_values("first").reset_index(drop=True)


# --------------------------------------------------------------------------
# Synthetic fallback (tests and offline clones only)
# --------------------------------------------------------------------------

def _prior_correlation() -> np.ndarray:
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
            c[i, j] = c[j, i] = base.get((a, b), base.get((b, a), 0.0))
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
    Correlated fat-tailed returns with a de-meaned regime overlay, calibrated
    to the capital market assumptions in config. Tests only, never reported.
    """
    rng = np.random.default_rng(config.SEED if seed is None else seed)
    dates = pd.bdate_range(start, end)
    n_days, keys = len(dates), config.ASSET_KEYS
    n = len(keys)

    mu = np.array([a.cma_return for a in config.UNIVERSE])
    vol = np.array([a.cma_vol for a in config.UNIVERSE])
    chol = np.linalg.cholesky(_prior_correlation())

    df = 5.0
    z = rng.standard_t(df, size=(n_days, n)) / np.sqrt(df / (df - 2.0))
    z = (z - z.mean(axis=0)) / z.std(axis=0, ddof=1)
    shocks = (z @ chol.T) * (vol / np.sqrt(252.0))
    drift = (mu - 0.5 * vol**2) / 252.0

    is_growth = np.array([a.sleeve in ("growth", "diversifier") for a in config.UNIVERSE])
    is_bond = np.array([a.sleeve == "defensive" for a in config.UNIVERSE])
    shift = np.zeros((n_days, n))
    scale = np.ones((n_days, n))

    def _win(frac, days):
        a = int(n_days * frac)
        return slice(a, min(a + days, n_days))

    bear = _win(0.28, 190)
    shift[bear] += np.where(is_growth, -0.0015, 0.0002)
    scale[bear] *= np.where(is_growth, 2.0, 1.15)
    shift[_win(0.36, 380)] += np.where(is_growth, 0.0009, -0.0001)
    rates = _win(0.72, 300)
    shift[rates] += np.where(is_bond, -0.00035, -0.00020)
    scale[rates] *= 1.30
    shift[_win(0.85, 300)] += np.where(is_bond, 0.00035, 0.00020)

    shift -= shift.mean(axis=0, keepdims=True)

    rets = drift + shift + shocks * scale
    return pd.DataFrame(100.0 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=keys)


def to_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna(how="all").fillna(0.0)
