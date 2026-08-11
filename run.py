"""
Entry point.

    python -m src.run                 # full study, writes to outputs/
    python -m src.run --no-tax        # gross of Italian tax, for comparison
    python -m src.run --rebalance M   # override the rebalancing frequency
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from . import config, data, metrics
from .backtest import run_backtest
from .metrics import drawdown_series, drawdown_table, wealth_index
from .strategies import STRATEGIES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

PALETTE = {"60/40": "#1f4e79", "Mean-variance": "#c0504d", "Risk parity": "#4f8a5b"}


def main() -> None:
    ap = argparse.ArgumentParser(description="HNW portfolio construction study")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--no-tax", action="store_true", help="run gross of Italian tax")
    ap.add_argument("--rebalance", default=None, choices=["M", "Q", "A"])
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    if args.rebalance:
        config.REBALANCE_FREQ = args.rebalance

    OUT.mkdir(exist_ok=True)

    prices, synthetic = data.load_prices(args.start, args.end, use_cache=not args.no_cache)
    if synthetic:
        print("\n" + "!" * 72)
        print("!  SYNTHETIC DATA. yfinance was unavailable, so prices were simulated")
        print("!  from the capital market assumptions in src/config.py. The mechanics")
        print("!  are real; the numbers are not history. Install yfinance and re-run")
        print("!  with --no-cache for the actual backtest.")
        print("!" * 72 + "\n")

    print(f"Period: {prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}  "
          f"({len(prices)} trading days, {len(prices.columns)} assets)\n")

    results = {}
    for name in STRATEGIES:
        print(f"  running {name} ...")
        results[name] = run_backtest(prices, name, apply_tax=not args.no_tax,
                                     is_synthetic=synthetic)

    table = metrics.comparison_table(results)
    pretty = metrics.format_table(table)

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(pretty.to_string())

    attrib = metrics.attribution_table(results)
    print("\n" + "=" * 72)
    print("ATTRIBUTION BY ASSET CLASS")
    print("=" * 72)
    print(metrics.format_attribution(attrib).to_string())

    for name, res in results.items():
        dd = drawdown_table(wealth_index(res), top=3)
        if not dd.empty:
            print(f"\nWorst drawdowns -- {name}")
            print(dd.assign(depth=lambda d: d["depth"].map("{:.2%}".format)).to_string(index=False))

    # ---- artefacts -------------------------------------------------------
    table.to_csv(OUT / "summary.csv")
    attrib.to_csv(OUT / "attribution.csv")
    pd.DataFrame({n: r.equity for n, r in results.items()}).to_csv(OUT / "equity_curves.csv")
    pd.DataFrame({n: r.turnover for n, r in results.items()}).to_csv(OUT / "turnover.csv")

    _plot_equity(results, synthetic)
    _plot_twr(results, synthetic)
    _plot_drawdown(results, synthetic)
    _plot_weights(results, synthetic)
    _write_results_md(table, attrib, results, prices, synthetic)

    print(f"\nWritten to {OUT}/  (summary.csv, attribution.csv, *.png, RESULTS.md)")


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def _stamp(fig, synthetic: bool) -> None:
    if synthetic:
        fig.text(0.5, 0.5, "SYNTHETIC DATA", fontsize=34, color="grey",
                 alpha=0.16, ha="center", va="center", rotation=25, zorder=10)


def _plot_equity(results, synthetic):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name, res in results.items():
        ax.plot(res.equity.index, res.equity / 1e6, label=name,
                color=PALETTE.get(name), lw=1.6)
    ax.axhline(config.INITIAL_CAPITAL / 1e6, color="grey", lw=0.8, ls="--")
    ax.set_title("Portfolio value after income withdrawals, net of costs and tax (€m)")
    ax.set_ylabel("€m")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    _stamp(fig, synthetic)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curves.png", dpi=140)
    plt.close(fig)


def _plot_twr(results, synthetic):
    """Growth of the strategy itself, before the income schedule."""
    fig, ax = plt.subplots(figsize=(11, 5.0))
    for name, res in results.items():
        idx = wealth_index(res)
        ax.plot(idx.index, idx, label=name, color=PALETTE.get(name), lw=1.6)
    ax.set_title("Time-weighted growth index, income added back (base 1.00)")
    ax.set_ylabel("index")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    _stamp(fig, synthetic)
    fig.tight_layout()
    fig.savefig(OUT / "twr_index.png", dpi=140)
    plt.close(fig)


def _plot_drawdown(results, synthetic):
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for name, res in results.items():
        dd = drawdown_series(wealth_index(res))
        ax.fill_between(dd.index, dd * 100, 0, alpha=0.22, color=PALETTE.get(name))
        ax.plot(dd.index, dd * 100, label=name, color=PALETTE.get(name), lw=1.2)
    ax.set_title("Drawdown, time-weighted (%)")
    ax.set_ylabel("%")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    _stamp(fig, synthetic)
    fig.tight_layout()
    fig.savefig(OUT / "drawdowns.png", dpi=140)
    plt.close(fig)


def _plot_weights(results, synthetic):
    fig, axes = plt.subplots(len(results), 1, figsize=(11, 3.1 * len(results)), sharex=True)
    names = {a.key: a.name for a in config.UNIVERSE}
    for ax, (name, res) in zip(axes, results.items()):
        w = res.weights.rename(columns=names)
        ax.stackplot(w.index, w.T.values * 100, labels=w.columns, alpha=0.9)
        ax.set_title(f"{name} — allocation through time (%)", fontsize=10)
        ax.set_ylim(0, 100)
        ax.margins(x=0)
    axes[-1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.18),
                    ncol=4, frameon=False, fontsize=8)
    _stamp(fig, synthetic)
    fig.tight_layout()
    fig.savefig(OUT / "weights.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------
# Results write-up
# --------------------------------------------------------------------------

def _write_results_md(table, attrib, results, prices, synthetic):
    lines = ["# Results", ""]
    if synthetic:
        lines += ["> **Synthetic data.** Generated from the capital market assumptions in",
                  "> `src/config.py` because a live price feed was unavailable. Mechanics are",
                  "> real, numbers are not history.", ""]
    lines += [
        f"Period: **{prices.index[0]:%d %b %Y} – {prices.index[-1]:%d %b %Y}** "
        f"({len(prices) / 252:.1f} years). Initial capital €{config.INITIAL_CAPITAL:,.0f}, "
        f"income need €{config.INCOME_NEED_ANNUAL:,.0f} p.a. indexed at "
        f"{config.ASSUMED_INFLATION:.0%}, rebalanced {config.REBALANCE_FREQ}.", "",
        "## Headline metrics", "",
        metrics.format_table(table).to_markdown(), "",
        "## Attribution by asset class", "",
        metrics.format_attribution(attrib).to_markdown(), "",
        "## Worst drawdowns", "",
    ]
    for name, res in results.items():
        dd = drawdown_table(wealth_index(res), top=3)
        lines += [f"**{name}**", ""]
        if dd.empty:
            lines += ["_No drawdown recorded._", ""]
        else:
            dd = dd.assign(depth=lambda d: d["depth"].map("{:.2%}".format))
            lines += [dd.to_markdown(index=False), ""]

    lines += ["## Charts", "",
              "![Portfolio value](equity_curves.png)", "",
              "![Time-weighted growth](twr_index.png)", "",
              "![Drawdowns](drawdowns.png)", "",
              "![Weights](weights.png)", ""]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
