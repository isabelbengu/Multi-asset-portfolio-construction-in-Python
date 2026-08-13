"""
One-off data setup: fetch the macro series and audit ticker coverage.

    python -m src.fetch_macro            # download HICP, report ETF coverage
    python -m src.fetch_macro --coverage # coverage audit only

The ECB €STR export is committed under data/macro/ already. Italian HICP is
downloaded from FRED rather than committed, because it is Eurostat data whose
licence requires attribution on redistribution; fetching it keeps the repo
clean and the provenance obvious.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

from . import config, data

MACRO = Path(__file__).resolve().parents[1] / "data" / "macro"


def fetch_hicp() -> Path | None:
    """Download Italian HICP from FRED into data/macro/hicp_italy.csv."""
    MACRO.mkdir(parents=True, exist_ok=True)
    dest = MACRO / "hicp_italy.csv"
    try:
        with urllib.request.urlopen(data.FRED_HICP_URL, timeout=30) as r:
            body = r.read().decode("utf-8")
    except Exception as exc:                                   # noqa: BLE001
        print(f"[macro] HICP download failed: {exc}")
        print(f"[macro] download by hand from:\n         {data.FRED_HICP_URL}")
        print(f"[macro] and save it to {dest}")
        return None

    dest.write_text(body, encoding="utf-8")
    series = data.load_hicp()
    if series is None or series.empty:
        print("[macro] downloaded file did not parse as a HICP series")
        return None

    print(f"[macro] HICP: {len(series)} obs, {series.index[0]:%Y-%m} to "
          f"{series.index[-1]:%Y-%m} -> {dest}")
    yrs = (series.index[-1] - series.index[0]).days / 365.25
    print(f"[macro] realised Italian inflation over the file: "
          f"{(series.iloc[-1] / series.iloc[0]) ** (1 / yrs) - 1:.2%} p.a.")
    return dest


def audit_coverage() -> None:
    """Print inception dates per ticker and the resulting common window."""
    print("\nTicker coverage (Yahoo Finance):")
    df = data.coverage_report()
    if df.empty:
        print("  unavailable — is yfinance installed and the network reachable?")
        return
    print(df.to_string(index=False))

    cash = data._download([config.CASH_TICKER], None, None)
    if cash is not None and not cash.empty:
        s = cash.iloc[:, 0].dropna()
        print(f"\nCash benchmark {config.CASH_TICKER}: "
              f"{s.index[0].date()} to {s.index[-1].date()} ({len(s)} obs)")


def main() -> None:
    ap = argparse.ArgumentParser(description="fetch macro data and audit coverage")
    ap.add_argument("--coverage", action="store_true", help="skip the download")
    args = ap.parse_args()

    if not args.coverage:
        fetch_hicp()

    estr = data.load_estr()
    if estr is not None:
        print(f"[macro] €STR: {len(estr)} obs, {estr.index[0]:%Y-%m-%d} to "
              f"{estr.index[-1]:%Y-%m-%d}, currently {estr.iloc[-1]:.3f}%")
    else:
        print("[macro] no €STR file found in data/macro/ (estr*.csv)")

    audit_coverage()


if __name__ == "__main__":
    main()
