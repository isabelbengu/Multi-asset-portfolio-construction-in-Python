"""
Mandate parameters, asset universe and Italian tax constants.

All monetary amounts are in EUR. All rates are decimals (0.26 == 26%).
Edit this file to re-run the whole study under a different mandate.
"""

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Mandate
# --------------------------------------------------------------------------

INITIAL_CAPITAL = 2_000_000.0      # EUR
HORIZON_YEARS = 15
INCOME_NEED_ANNUAL = 70_000.0      # EUR, ~3.5% initial withdrawal rate
INCOME_INDEXED_TO_INFLATION = True
ASSUMED_INFLATION = 0.02           # used only if no CPI series is supplied

REBALANCE_FREQ = "Q"               # 'M', 'Q', 'A'
REBALANCE_BAND = 0.015             # no-trade band, absolute weight (IPS section 7)
TURNOVER_BUDGET = 0.25             # one-way p.a., soft limit, reported not enforced
WITHDRAWAL_FREQ = "Q"              # income is drawn quarterly

# --------------------------------------------------------------------------
# Costs and taxes (Italian resident private investor)
# --------------------------------------------------------------------------
# NOTE: simplified model. Real treatment depends on regime (amministrato /
# gestito / dichiarativo), instrument type, and the redditi diversi vs redditi
# di capitale distinction. See docs/IPS.md, section 6. Not tax advice.

TRANSACTION_COST_BPS = 8.0         # round-trip spread + commission, per unit traded
ONGOING_CHARGE_BPS = 20.0          # blended TER of the UCITS ETF sleeve, annual

IVAFE_RATE = 0.002                 # 'imposta di bollo' on financial assets, 0.20% p.a.
CGT_RATE_STANDARD = 0.26           # 26% on most capital gains and dividends
CGT_RATE_WHITELIST_GOVT = 0.125    # 12.5% on EU / whitelist government bonds
APPLY_TAX_DRAG = True              # if False, results are gross of tax

# --------------------------------------------------------------------------
# Asset universe
# --------------------------------------------------------------------------
# UCITS ETFs, EUR-denominated or EUR-hedged, accumulating where possible.
# Tickers are Yahoo Finance symbols (.AS = Euronext Amsterdam, .MI = Milan,
# .DE = Xetra). Swap these for your own data vendor in src/data.py.


@dataclass(frozen=True)
class Asset:
    key: str
    name: str
    ticker: str
    sleeve: str                    # 'growth' | 'defensive' | 'diversifier'
    whitelist_govt: bool = False   # drives the 12.5% vs 26% tax rate
    # Long-run capital market assumptions, EUR nominal. Used only for the
    # synthetic-data fallback and as MVO priors under shrinkage.
    cma_return: float = 0.05
    cma_vol: float = 0.15


# Inception dates verified against Yahoo Finance, August 2026. The binding
# constraint is EUNM.DE (Oct 2009) and 4GLD.DE (Nov 2009), which set the common
# window at roughly Dec 2009. Stooq was rejected as a source: its European ETF
# coverage starts whenever Stooq began tracking the listing, not at inception
# (IWDA.NL begins Jan 2026 there), which silently truncates the study.

UNIVERSE: list[Asset] = [
    Asset("dm_equity", "Developed world equity",      "IWDA.AS", "growth",
          cma_return=0.068, cma_vol=0.155),
    Asset("em_equity", "Emerging market equity",      "EUNM.DE", "growth",
          cma_return=0.075, cma_vol=0.210),
    Asset("eu_govt",   "Euro government bonds",       "EUNH.DE", "defensive",
          whitelist_govt=True, cma_return=0.028, cma_vol=0.055),
    Asset("eu_corp",   "Euro IG corporate bonds",     "IEAC.AS", "defensive",
          cma_return=0.035, cma_vol=0.065),
    Asset("eu_agg",    "Euro aggregate bonds",        "IEAG.AS", "defensive",
          cma_return=0.032, cma_vol=0.050),
    Asset("eu_reits",  "European listed real estate", "IQQP.DE", "diversifier",
          cma_return=0.060, cma_vol=0.190),
    Asset("gold",      "Gold",                        "4GLD.DE", "diversifier",
          cma_return=0.040, cma_vol=0.145),
]

# Not part of the investable universe: an overnight-rate tracker used as the
# risk-free benchmark. See src/data.py for why this beats splicing EONIA.
CASH_TICKER = "XEON.DE"
CASH_RATE_FALLBACK = 0.015          # flat rate, used only if XEON.DE is unavailable

# Italian HICP, Eurostat series mirrored by FRED. Indexes the income need.
HICP_FRED_SERIES = "CP0000ITM086NEST"

TICKERS = {a.key: a.ticker for a in UNIVERSE}
ASSET_KEYS = [a.key for a in UNIVERSE]
GROWTH_KEYS = [a.key for a in UNIVERSE if a.sleeve == "growth"]
DEFENSIVE_KEYS = [a.key for a in UNIVERSE if a.sleeve == "defensive"]

CASH_RATE_PROXY = 0.015            # legacy constant, superseded by the XEON.DE series

# --------------------------------------------------------------------------
# Strategy constraints (IPS section 4)
# --------------------------------------------------------------------------

MIN_WEIGHT = 0.00
MAX_WEIGHT = 0.40                  # single-line concentration cap (IPS section 4)
MAX_GROWTH = 0.75                  # equity + equity-like ceiling
MIN_DEFENSIVE = 0.20               # liquidity floor for the income need

# Strategic 60/40 policy weights
POLICY_6040 = {
    "dm_equity": 0.40,
    "em_equity": 0.12,
    "eu_reits": 0.08,
    "eu_govt": 0.18,
    "eu_corp": 0.12,
    "eu_agg": 0.10,
    "gold": 0.00,
}

# Mean-variance settings
MVO_LOOKBACK_YEARS = 3             # rolling estimation window (see README: 5y
                                   # would cost 2 more years of measured results)
MVO_SHRINKAGE = 0.5                # 0 = pure sample estimates, 1 = pure CMA priors
MVO_OBJECTIVE = "max_sharpe"       # 'max_sharpe' | 'min_vol' | 'target_vol'
MVO_TARGET_VOL = 0.10

# Risk parity settings
RP_LOOKBACK_YEARS = 3
RP_TOLERANCE = 1e-10
RP_MAX_ITER = 10_000

SEED = 42
