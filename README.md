# HNW Portfolio Construction — IPS and Allocation Study

A portfolio construction case study for a hypothetical €2,000,000 high-net-worth
mandate: 15-year horizon, ongoing income need, Italian tax residency. It
contains a two-page [Investment Policy Statement](docs/IPS.md) defining
objectives, constraints and risk limits, and a Python backtesting engine
comparing three allocation methods: strategic 60/40, mean-variance
optimisation, and equal-risk-contribution risk parity, with quarterly
rebalancing, net of transaction costs, ongoing charges, Italian capital gains
tax and *imposta di bollo*.

The point of the exercise is the part most backtests leave out: what an
allocation does **after** an income schedule, a turnover budget and a 26% tax
rate are applied to it.

## Run it

```bash
git clone https://github.com/<your-handle>/hnw-portfolio-construction.git
cd hnw-portfolio-construction
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m src.fetch_macro     # Italian HICP + ticker coverage audit
python -m src.run --no-cache  # download prices, run the study
python -m pytest -q           # 20 tests
```

`src/run.py` writes every table and chart into `outputs/`, including
[`RESULTS.md`](outputs/RESULTS.md).

Useful flags: `--no-tax` (gross of Italian tax), `--rebalance M` (monthly),
`--start 2012-01-01`, `--allow-synthetic` (simulate prices when offline).

## Data

| Input | Source | Coverage |
|---|---|---|
| Prices | Yahoo Finance via `yfinance`, adjusted close, EUR | see below |
| Risk-free rate | XEON.DE overnight-rate tracker total return | 2008– |
| €STR cross-check | ECB Data Portal (committed, `data/macro/`) | 2019-10– |
| Inflation | Italian HICP, Eurostat via FRED `CP0000ITM086NEST` | 1996-01– |

**Universe.** Seven EUR-denominated UCITS ETFs. Inception dates were verified
before selection, because they are what actually determines the study window:

| Asset | Ticker | From |
|---|---|---|
| Developed world equity | IWDA.AS | 2009-09 |
| Emerging market equity | EUNM.DE | 2009-10 |
| Euro government bonds | EUNH.DE | 2009-04 |
| Euro IG corporates | IEAC.AS | 2009-05 |
| Euro aggregate | IEAG.AS | 2009-03 |
| European listed property | IQQP.DE | 2008-12 |
| Gold | 4GLD.DE | 2009-11 |

Common window ≈ **December 2009 onward, about 16.5 years**. With a three-year
estimation window burned in for the optimiser, roughly **13.5 years are
measured** — short of fifteen, and the README says so rather than rounding up.
Run `python -m src.fetch_macro --coverage` to re-audit; ETF listings change.

Three data decisions worth stating, since each changes results:

**Adjusted close, not close.** IEAC, IEAG and IQQP are distributing funds.
Their raw price excludes coupons, so a bond fund yielding 3% shows as roughly
flat over a decade. `auto_adjust=True` reinvests distributions.

**The risk-free rate is a series, not a constant.** Euro cash went from −0.5%
to +4% across this sample. A flat assumption doesn't just add noise to Sharpe
ratios, it gets them wrong in a direction that reverses partway through the
study. The rate is taken from an overnight-rate ETF's total return (available
from 2008, unlike €STR which starts in 2019) and cross-checked against the
ECB's published €STR over the overlap.

**Income is indexed to realised HICP.** Euro inflation exceeded 8% in 2022.
Indexing the client's withdrawal at a smooth 2% would understate the real
withdrawal burden in the year the portfolio was also falling — which is exactly
the sequence risk the mandate exists to survive.

## Method notes

**Drawdown is computed on a time-weighted index, not the wealth path.** With
€70k a year leaving the portfolio, account value falls for reasons unrelated to
markets. Measuring drawdown on raw wealth turns a scheduled income payment into
a permanent, unrecoverable loss. `metrics.wealth_index()` compounds the
withdrawal-adjusted return series instead; the wealth path is reported
separately, because funding the income *is* the objective. Two questions, two
series.

**All three strategies start on the same date.** Mean-variance needs an
estimation window, 60/40 needs none. Letting each start when ready compares
start dates, not strategies. `common_start_index()` burns in the longest
lookback for all of them.

**No look-ahead.** Allocators receive only the trailing window available at the
rebalance date. `test_no_lookahead_in_estimation_window` spies on every window
the engine passes in and asserts it ends strictly before the rebalance date.

**Italian tax.** Realised gains at 26%, or 12.5% for white-list government
issuers; losses carried forward four years; 0.20% *imposta di bollo* annually
on statement value; accumulating share classes where available.

The model is deliberately optimistic in one place, and the IPS says so: gains
on UCITS funds are *redditi di capitale* while losses are *redditi diversi*, so
an ETF loss cannot offset an ETF gain. The carry-forward pool implemented here
is more generous than reality. Modelling that asymmetry is the first item on
the to-do list.

## Repository layout

```
├── docs/IPS.md              Investment Policy Statement (the mandate)
├── src/
│   ├── config.py            Mandate, universe, tax constants, constraints
│   ├── data.py              Prices, cash rate, inflation; synthetic fallback
│   ├── fetch_macro.py       Macro download + ticker coverage audit
│   ├── strategies.py        The three allocators
│   ├── backtest.py          Daily engine: costs, income, tax, rebalancing
│   ├── metrics.py           Risk, return, cost and attribution metrics
│   └── run.py               Entry point, charts, results write-up
├── tests/test_strategies.py 20 tests: constraints, tax, no-look-ahead
├── data/macro/              ECB €STR export (committed)
└── outputs/                 Generated by src/run.py
```

Everything about the mandate lives in `src/config.py` — capital, horizon,
income need, tax rates, universe, constraints. Change it there and re-run.

## Known limitations

- The window is ~13.5 measured years, not 15. Extending it requires splicing
  index series onto the front of the ETF histories, which is not implemented.
- The *redditi di capitale* / *redditi diversi* asymmetry is not modelled.
- IWDA and EUNM are USD-denominated funds with EUR listings: the EUR price
  embeds FX, but there is no explicit currency model or hedging decision.
- Mean-variance uses constant-correlation shrinkage rather than Ledoit-Wolf
  with an estimated intensity.
- No glidepath, the allocation does not de-risk as the horizon shortens,
  which a real 15-year drawdown mandate would.
- Transaction costs are a flat 8bp.
- Survivorship: these tickers were chosen in 2026 partly *because* they still
  exist with long histories.

## Licence

MIT — see [LICENSE](LICENSE).

Price data © Yahoo Finance. €STR © European Central Bank. HICP © Eurostat,
retrieved via FRED, St. Louis Fed.

Built by Isabel Bengu.

*Fictitious client, illustrative figures. Not investment or tax advice.*
