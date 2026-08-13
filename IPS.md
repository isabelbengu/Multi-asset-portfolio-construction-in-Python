# Investment Policy Statement

**Client:** "Cliente Rossi" — hypothetical private client, sole account holder
**Portfolio:** €2,000,000 discretionary mandate
**Tax residency:** Italy
**Date:** Draft, v1.0
**Review cycle:** Annual, or on any material change in circumstances

> This is a teaching document written around a fictitious client. It is not
> advice, and the tax treatment described is a simplification — see §8.

---

## 1. Purpose

This statement sets out the objectives, constraints, permitted allocations and
governance for the mandate. It exists so that decisions taken during a
drawdown are decisions that were already agreed before the drawdown began. Any
deviation from it should be documented and countersigned rather than
improvised.

## 2. Client circumstances

The client is 58, retired following the sale of a minority stake in an
operating company. The proceeds constitute the portfolio. The primary
residence in Lombardy is owned outright and is excluded from this mandate, as
is a cash buffer of €150,000 held separately at a retail bank.

The client has no dependants requiring support, two adult children as eventual
beneficiaries, and no debt. Investment experience is moderate: familiar with
equity and bond markets, unfamiliar with derivatives, structured products and
private markets. The client has stated a strong preference for transparent,
liquid, daily-priced instruments and an explicit dislike of lock-ups.

## 3. Objectives

**Return objective.** The portfolio must fund a real income need and preserve
purchasing power over the horizon. Building the required return from the
bottom up:

| Component | Rate |
|---|---|
| Initial withdrawal rate (€70,000 on €2,000,000) | 3.50% |
| Inflation (realised Italian HICP in the backtest; 2.0% assumed forward) | 2.00% |
| Ongoing charges, transaction costs | 0.30% |
| Imposta di bollo | 0.20% |
| **Required nominal return, before capital gains tax** | **≈ 6.00%** |

This is a demanding target for a portfolio that must also respect the risk
limits in §4. The client accepts that meeting it requires meaningful equity
exposure, and that in adverse sequences the real value of capital may decline
even where the income is maintained. Capital preservation in nominal terms is
**not** the objective; funding the income stream for fifteen years is.

**Income objective.** €70,000 per annum, indexed to inflation, distributed
quarterly. Indexation in the backtest uses realised Italian HICP rather than a
flat assumption. This matters more than it sounds: euro area inflation ran
above 8% in 2022, and a study that indexes income at a smooth 2% through that
period understates the real withdrawal burden in precisely the year the
portfolio was also falling. Income is raised by selling assets pro rata rather than
by targeting a natural dividend yield. Manufacturing income from total return
avoids the concentration and value-tilt that a yield-seeking portfolio
imposes, and in Italy accumulating funds defer the taxable event rather than
forcing it each distribution date.

## 4. Risk tolerance and risk limits

**Ability to take risk:** above average. Fifteen-year horizon, no debt, income
need is 3.5% of capital, separate cash buffer covers two years of spending
without touching the portfolio.

**Willingness to take risk:** moderate. In discussion the client indicated
that a decline beyond roughly 25% would prompt a request to de-risk. That
figure, not the theoretical capacity, is the binding constraint. The IPS is
written to the lower of the two.

Formal limits:

| Limit | Value |
|---|---|
| Maximum drawdown tolerance (time-weighted, peak to trough) | −25% |
| Target volatility, annualised | 8–12% |
| Maximum single line | 40% |
| Maximum growth assets (equity, listed real estate) | 75% |
| Minimum defensive assets (government and IG credit) | 20% |
| Minimum liquidity: assets realisable within 5 business days | 100% |

Breach of the drawdown tolerance triggers a documented review, **not** an
automatic sale. The distinction is deliberate: the limit exists to force a
conversation, not to institutionalise selling at the bottom.

## 5. Constraints

**Time horizon.** Fifteen years, treated as a single stage. The client should
expect the defensive sleeve to grow as the horizon shortens; that glidepath is
out of scope for v1.0 and is flagged for the year-5 review.

**Liquidity.** Quarterly income of €17,500 (indexed) plus a €50,000 annual
allowance for irregular spending. No illiquid holdings permitted.

**Legal and regulatory.** UCITS-eligible instruments only. US-domiciled ETFs
are not available to EU retail clients under PRIIPs; Irish- and
Luxembourg-domiciled UCITS are used instead. Foreign-held assets are subject
to *quadro RW* monitoring obligations in the annual return.

**Unique circumstances.** No holdings in the client's former sector
(industrial machinery) beyond incidental index exposure. No tobacco or
controversial weapons. No leverage, no securities lending preference expressed.

## 6. Strategic asset allocation

The policy portfolio is a 60/40 growth/defensive split, implemented in
EUR-denominated or EUR-hedged accumulating UCITS ETFs:

| Asset class | Instrument | Policy | Permitted range |
|---|---|---|---|
| Developed world equity | IWDA.AS | 40% | 25–40% |
| Emerging market equity | EUNM.DE | 12% | 5–20% |
| European listed real estate | IQQP.DE | 8% | 0–12% |
| Euro government bonds | EUNH.DE | 18% | 10–35% |
| Euro IG corporate bonds | IEAC.AS | 12% | 5–25% |
| Euro aggregate bonds | IEAG.AS | 10% | 0–20% |
| Gold | 4GLD.DE | 0% | 0–10% |

The 60/40 label refers to risk assets against defensive assets: 60% across
equity and listed real estate, 40% across the three bond sleeves. Gold is
permitted but not held at policy weight; it is available to the optimiser and
to risk parity, which is part of what the study tests.

Euro aggregate replaces the EUR-hedged global aggregate originally
contemplated. Every hedged global bond UCITS with adequate liquidity launched
after 2017, and including one would have truncated the measurement window by
seven years. The substitution costs some geographic diversification in the
defensive sleeve and is flagged for review if a longer-history instrument
becomes available.

Two alternative construction methods are evaluated against this policy
portfolio in the accompanying study: unconstrained-by-priors **mean-variance
optimisation** on a rolling five-year window with shrinkage toward long-run
capital market assumptions, and **equal risk contribution (risk parity)** on a
rolling three-year covariance estimate. Both are subject to the same limits in
§4. The policy portfolio is the default; an alternative is adopted only if it
demonstrates a superior risk-adjusted outcome *after* costs, turnover and
Italian tax.

## 7. Rebalancing policy

- **Frequency:** quarterly, on the last business day of March, June, September
  and December.
- **Method:** trade back to target weights. Income withdrawals are raised at
  the same time and, where possible, sourced from overweight positions so that
  the withdrawal itself performs part of the rebalance.
- **No-trade band:** positions within ±1.5% of target are left alone. Trading
  a 40bp deviation costs more in spread and realised tax than the tracking
  error it removes.
- **Turnover budget:** 25% one-way per annum. Sustained breach requires
  written justification, because in this jurisdiction turnover is not merely a
  cost — it accelerates the realisation of taxable gains.

## 8. Tax policy

Modelled as an Italian-resident private investor under the *regime
amministrato*, with the intermediary acting as withholding agent:

- **26%** substitute tax on most capital gains and investment income.
- **12.5%** on income and gains from Italian government bonds and *white-list*
  sovereign issuers, applied via the pro-rata mechanism.
- **0.20% per annum** *imposta di bollo* on the statement value of financial
  assets, charged annually.
- **Realised losses** (*minusvalenze*) carry forward four years.

One asymmetry deserves emphasis because it materially changes portfolio
construction here: gains on UCITS funds are *redditi di capitale*, while
losses are *redditi diversi*. A loss realised on an ETF therefore **cannot** be
offset against a gain realised on another ETF. Tax-loss harvesting, the
standard answer elsewhere, is largely unavailable in a pure ETF portfolio. The
practical consequences accepted in this IPS: prefer accumulating share classes
to defer the taxable event, prefer wide rebalancing bands to lower realisation
frequency, and retain the option to hold a sleeve of direct bonds or ETCs
against which losses can be used.

*The backtest implements a simplified version of the above and does not model
the redditi di capitale asymmetry, which makes the reported tax drag mildly
optimistic. This is a portfolio construction exercise, not tax advice; the
client's commercialista should review any implementation.*

## 9. Monitoring and review

| Item | Frequency |
|---|---|
| Valuation and income statement | Quarterly |
| Full performance and attribution report | Semi-annual |
| IPS review | Annual, or on material change |
| Capital market assumption refresh | Annual |

Performance is assessed against the policy portfolio in §6, net of all costs
and tax, over rolling three-year periods. Judging a fifteen-year mandate on
twelve-month numbers is the single most common way a sound policy gets
abandoned prematurely, and both parties agree in advance not to do it.

## 10. Responsibilities

**Adviser:** construct and maintain the portfolio within these limits, execute
rebalances, report as above, and escalate any breach within five business days.
**Client:** notify material changes in circumstances, objectives or risk
tolerance, and confirm income requirements annually in advance.

---

*Prepared by Isabel Bengu as a portfolio-construction exercise. Fictitious client, illustrative
figures, not investment or tax advice.*
