# HNW Portfolio Construction — IPS and Allocation Study

A full portfolio construction case study built around a hypothetical €2,000,000
high-net-worth mandate: 15-year horizon, ongoing income need, Italian tax
residency. It contains a two-page [Investment Policy Statement](docs/IPS.md)
defining objectives, constraints and risk limits, and a Python backtesting
engine comparing three allocation methods — strategic 60/40, mean-variance
optimisation, and equal-risk-contribution risk parity — over a 15-year window
with quarterly rebalancing, net of transaction costs, ongoing charges, Italian
capital gains tax and *imposta di bollo*.

The point of the exercise is the part most backtests leave out: what the
allocation does **after** an income schedule, a turnover budget and a 26% tax
rate are applied to it.

---

> ### ⚠️ Read this before quoting any number
> The results committed here were produced from **synthetic prices**, generated
> from the capital market assumptions in `src/config.py`, because the machine
> used to build the repo had no market data access. The mechanics are real; the
> numbers are not history.
>
> To reproduce with real data: `pip install yfinance` then
> `python -m src.run --no-cache`. Every table, chart and figure in
> `outputs/` regenerates. **Do this before showing the repo to anyone.**

---

## Headline results

Synthetic 15-year window, €2m initial, €70k p.a. income indexed at 2%,
quarterly rebalancing, net of all costs and tax.

| | 60/40 | Mean-variance | Risk parity |
|---|---|---|---|
| CAGR | **6.26%** | 0.83% | 2.57% |
| Volatility | 10.75% | 8.65% | 6.00% |
| Sharpe | **0.48** | −0.04 | 0.20 |
| Max drawdown | −21.63% | −27.59% | **−21.14%** |
| Turnover p.a. (one-way) | 3.99% | 53.90% | **1.94%** |
| Terminal value | **€2,822,725** | €1,308,824 | €1,717,453 |
| Capital gains tax paid | €115,008 | €7,144 | €17,347 |
| *Imposta di bollo* paid | €58,028 | €35,184 | €41,585 |

Full tables, per-asset attribution and drawdown episodes: [`outputs/RESULTS.md`](outputs/RESULTS.md).

## What the study actually shows

**1. The optimiser breached the risk limit it was constrained to respect.**
Mean-variance was constrained *ex ante* on estimated volatility and still
delivered a −27.6% drawdown against the IPS tolerance of −25%. Constraining a
portfolio on an estimate is not the same as constraining it on an outcome. This
is the argument for stating drawdown limits in the IPS as review triggers
rather than as optimiser inputs.

**2. Mean-variance bought the asset that was about to break.** Attribution puts
the damage in Euro IG corporate bonds: an average 23.4% weight losing €131,328.
The rolling five-year window rated credit attractive on trailing data
immediately before the rate shock. Shrinkage toward long-run assumptions
(`MVO_SHRINKAGE = 0.5`) reduced but did not remove the effect. Estimation error
in expected returns is not a detail of the method, it is the method's dominant
risk.

**3. Turnover is a tax event, not just a cost.** Mean-variance turned over 53.9%
p.a. against 4.0% for the policy portfolio. The direct transaction cost
difference is €12,054. But in Italy each rebalance realises gains
taxed at 26%, and turnover compounds into the tax base. Holding everything else
fixed and toggling only the no-trade band (§7 of the IPS,
`REBALANCE_BAND = 0.015`):

| 60/40 | No band | ±1.5% band |
|---|---|---|
| Turnover p.a. | 6.30% | 3.99% |
| Capital gains tax | €133,709 | €115,008 |
| Terminal value | €2,754,130 | €2,822,725 |

€68,595 of terminal value from one line of portfolio policy, and only €2,000 of
it is saved commission. The rest is deferred tax that stayed invested.

**4. Risk parity did what it promises and not more.** Lowest volatility (6.00%),
lowest drawdown, lowest turnover, and a return that, after a 3.5% withdrawal
rate, left the portfolio at €1.72m against a €2m start. Low risk is not free
when there is an income need: the mandate's binding problem is funding, and
risk parity solves for the wrong variable unless it is levered, which the IPS
prohibits.

## Method notes

**Drawdown is computed on a time-weighted index, not the wealth path.** With
€70k a year leaving the portfolio, the account value falls for reasons that
have nothing to do with markets. Measuring drawdown on the raw wealth path
turns a scheduled income payment into a permanent, unrecoverable loss and
produces figures like −55% on a 60/40 portfolio. `metrics.wealth_index()`
compounds the withdrawal-adjusted return series instead. The wealth path is
still reported separately, because funding the income *is* the objective — the
two questions just need two different series.

**All three strategies start on the same date.** Mean-variance needs a
five-year estimation window; 60/40 needs none. Letting each start when it is
ready compares start dates, not strategies. `common_start_index()` burns in the
longest lookback of any strategy for all of them.

**No look-ahead.** Allocators receive only the trailing return window available
at the rebalance date. There is a test (`test_no_lookahead_in_estimation_window`)
that spies on every window the engine passes in and asserts it ends strictly
before the rebalance date.

**Italian tax model.** Realised gains taxed at 26%, or 12.5% for white-list
government issuers; losses carried forward four years and offset against later
gains; 0.20% *imposta di bollo* charged annually on statement value;
accumulating share classes assumed, so no annual dividend leakage.

The model is deliberately optimistic in one place, and the IPS says so: gains on
UCITS funds are *redditi di capitale* while losses are *redditi diversi*, so an
ETF loss **cannot** offset an ETF gain. The carry-forward pool implemented here
is more generous than reality. Modelling that asymmetry properly is the first
item on the to-do list.

## Repository layout

```
├── docs/
│   └── IPS.md               Investment Policy Statement (the mandate)
├── src/
│   ├── config.py            Mandate, universe, tax constants, constraints
│   ├── data.py              Yahoo Finance download + synthetic fallback
│   ├── strategies.py        The three allocators
│   ├── backtest.py          Daily engine: costs, income, tax, rebalancing
│   ├── metrics.py           Risk, return, cost and attribution metrics
│   └── run.py               Entry point, charts, results write-up
├── tests/
│   └── test_strategies.py   20 tests: constraints, tax, no-look-ahead
└── outputs/                 Generated: RESULTS.md, CSVs, charts
```

Everything about the mandate lives in `src/config.py`. Change the capital,
horizon, income need, tax rates, universe or constraints there and re-run; no
other file needs editing.

## Running it

```bash
git clone https://github.com/<you>/hnw-portfolio-construction.git
cd hnw-portfolio-construction
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m src.run --no-cache      # download real prices, full study
python -m pytest -q               # 20 tests
```

Useful flags:

```bash
python -m src.run --no-tax              # gross of Italian tax, for comparison
python -m src.run --rebalance M         # monthly instead of quarterly
python -m src.run --start 2008-01-01    # include the GFC
```

## Known limitations

- Tickers in `config.UNIVERSE` are Yahoo symbols for EUR-listed UCITS ETFs.
  Several have inception dates after 2010, so a true 15-year run will fall back
  to a shorter overlapping window or drop assets. Fix by substituting index
  series for the early years — not yet implemented.
- Currency is assumed EUR throughout. EUR-listed share classes of global funds
  still carry underlying currency risk; there is no explicit FX model.
- The *redditi di capitale* / *redditi diversi* asymmetry is not modelled (see
  above).
- Mean-variance uses a constant-correlation shrinkage target rather than
  Ledoit-Wolf with an estimated intensity.
- No glidepath: the allocation does not de-risk as the horizon shortens, which
  a real 15-year drawdown mandate would.
- Transaction costs are a flat 8bp. Real spreads widen exactly when the
  rebalance matters most.

## Licence

MIT — see [LICENSE](LICENSE).

*Fictitious client, illustrative figures. Not investment or tax advice.*
