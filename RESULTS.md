# Results

> **Synthetic data.** Generated from the capital market assumptions in
> `src/config.py` because a live price feed was unavailable. Mechanics are
> real, numbers are not history.

Period: **11 Aug 2011 – 11 Aug 2026** (15.5 years). Initial capital €2,000,000, income need €70,000 p.a. indexed at 2%, rebalanced Q.

## Headline metrics

|                     | 60/40      | Mean-variance   | Risk parity   |
|:--------------------|:-----------|:----------------|:--------------|
| CAGR                | 6.26%      | 0.83%           | 2.57%         |
| Volatility          | 10.75%     | 8.65%           | 6.00%         |
| Sharpe              | 0.48       | -0.04           | 0.20          |
| Sortino             | 0.76       | -0.05           | 0.32          |
| Max drawdown        | -21.63%    | -27.59%         | -21.14%       |
| Calmar              | 0.29       | 0.03            | 0.12          |
| Ulcer index         | 9.01%      | 12.00%          | 8.81%         |
| VaR 95% (daily)     | -1.03%     | -0.87%          | -0.61%        |
| CVaR 95% (daily)    | -1.40%     | -1.21%          | -0.80%        |
| Turnover p.a.       | 3.99%      | 53.90%          | 1.94%         |
| Rebalances          | 42         | 42              | 42            |
| Terminal value      | €2,822,725 | €1,308,824      | €1,717,453    |
| Terminal real value | €2,291,542 | €1,062,528      | €1,394,261    |
| Income paid         | €815,836   | €815,836        | €815,836      |
| Transaction cost    | €1,791     | €13,845         | €645          |
| Ongoing charge      | €55,602    | €34,497         | €40,384       |
| Capital gains tax   | €115,008   | €7,144          | €17,347       |
| Imposta di bollo    | €58,028    | €35,184         | €41,585       |

## Attribution by asset class

|                             | 60/40 — €   | 60/40 — avg w   | Mean-variance — €   | Mean-variance — avg w   | Risk parity — €   | Risk parity — avg w   |
|:----------------------------|:------------|:----------------|:--------------------|:------------------------|:------------------|:----------------------|
| Developed world equity      | €1,094,979  | 36.6%           | €191,271            | 18.3%                   | €156,699          | 7.2%                  |
| Eurozone equity             | €379,915    | 12.3%           | €50,753             | 7.3%                    | €132,868          | 5.8%                  |
| Emerging market equity      | €430,968    | 12.5%           | €60,596             | 3.4%                    | €126,175          | 5.2%                  |
| Euro government bonds       | €-15,247    | 19.5%           | €-12,496            | 14.2%                   | €-5,360           | 21.7%                 |
| Euro IG corporate bonds     | €-1,493     | 11.6%           | €-131,328           | 23.4%                   | €-5,489           | 19.1%                 |
| Global aggregate, EUR-hgd   | €14,322     | 7.6%            | €51,032             | 16.9%                   | €15,957           | 24.4%                 |
| European listed real estate | €0          | 0.0%            | €-73,280            | 10.1%                   | €100,198          | 6.6%                  |
| Gold                        | €0          | 0.0%            | €71,197             | 6.3%                    | €135,984          | 10.0%                 |

## Worst drawdowns

**60/40**

| start      | trough     | end        | depth   |   days | recovered   |
|:-----------|:-----------|:-----------|:--------|-------:|:------------|
| 2022-08-30 | 2024-08-06 | 2026-03-25 | -21.63% |   1303 | True        |
| 2018-12-05 | 2020-11-16 | 2022-02-15 | -17.96% |   1168 | True        |
| 2016-07-21 | 2016-10-19 | 2017-01-17 | -8.12%  |    180 | True        |

**Mean-variance**

| start      | trough     | end           | depth   |   days | recovered   |
|:-----------|:-----------|:--------------|:--------|-------:|:------------|
| 2022-06-16 | 2025-05-21 | not recovered | -27.59% |   1517 | False       |
| 2017-03-09 | 2020-11-16 | 2021-10-14    | -13.94% |   1680 | True        |
| 2016-07-11 | 2016-11-08 | 2017-03-06    | -4.81%  |    238 | True        |

**Risk parity**

| start      | trough     | end           | depth   |   days | recovered   |
|:-----------|:-----------|:--------------|:--------|-------:|:------------|
| 2022-06-16 | 2024-08-06 | not recovered | -21.14% |   1517 | False       |
| 2018-11-05 | 2020-08-10 | 2021-08-24    | -10.42% |   1023 | True        |
| 2016-07-21 | 2016-10-11 | 2017-02-28    | -5.98%  |    222 | True        |

## Charts

![Portfolio value](equity_curves.png)

![Time-weighted growth](twr_index.png)

![Drawdowns](drawdowns.png)

![Weights](weights.png)
