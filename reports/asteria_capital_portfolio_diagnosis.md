# Asteria Capital — Unhedged Portfolio Diagnosis

**Portfolio:** ASTERIA-001  
**Portfolio snapshot:** 2026-01-30  
**Report produced:** 2026-08-23  
**Reporting currency:** INR  
**Benchmark:** NIFTY 50 (`NIFTY`)  
**Status:** Diagnostic baseline; not a hedge recommendation

## Executive diagnosis

The ₹5.00 billion (₹500 crore), 50-name long-only equity portfolio is economically close to a one-for-one NIFTY exposure, but it is not a NIFTY replica. Full-sample beta is 1.01 and correlation is 0.97, while downside beta rises to 1.06, rolling 126-day beta ranges from 0.85 to 1.11, and annualized tracking error is 4.54%. A static NIFTY hedge would therefore leave material sector, stock-specific, and changing-beta basis risk.

The principal structural risks are sector concentration and bank/industrial tilts. Financials represent 37.30% of the portfolio and Industrials 18.54%; together they account for 55.84%. The five largest holdings account for 35.00%. No holding breaches the diagnostic 10% single-name limit, but the holding HHI implies only 26.9 equally weighted effective names despite 50 legal names, and the sector HHI implies only 4.8 equally weighted effective sectors.

Using overlapping 126-trading-day historical windows from the reconstructed adjusted-price history, including the COVID crash, the unhedged portfolio has a 99% six-month VaR of −10.61%, expected shortfall of −11.37%, and a 1.67% probability of losing more than 10%. The worst observed six-month outcome is −12.13%. The expected-shortfall estimate is only 0.63 percentage points inside the mandate's **post-hedge** limit of −12%, leaving limited empirical margin and not eliminating the need for scenario and stress testing.

**Diagnosis:** a hedge problem is substantiated. NIFTY is the natural primary hedge, but BANKNIFTY should be evaluated as a supplementary basis-risk hedge because of the 37.30% Financials allocation. No hedge should be selected from this report alone.

## Portfolio and data validation

| Check | Result | Assessment |
|---|---:|---|
| Total market value | ₹5,000,000,000 | Reconciles to supplied ₹5.00bn total |
| Holdings | 50 | Within the case baseline of 40–60 |
| Portfolio weights | 100.00% | Reconciled within configured tolerance |
| CSV validation warnings | 0 | Pass |
| Existing derivatives | None in baseline | Unhedged diagnosis |
| Price history | 2020-01-01 to 2026-01-30 | Common NIFTY and BANKNIFTY calendar |
| Aligned prices / daily returns | 1,505 / 1,504 | Same-endpoint returns; no forward filling |
| Six-month windows | 1,379 | Overlapping 126-trading-day terminal returns |
| Minimum represented weight | 98.22% | At least 48 of 50 current holdings on every interval |
| Partial-coverage returns | 717 | Snapshot weights renormalized across available holdings |

NIFTY and BANKNIFTY define the return calendar. A holding contributes only when it has an adjusted price at both interval endpoints; the 2026-01-30 snapshot weights are then renormalized across the contributing names. MAXHEALTH and KAYNES enter only after listing. This incorporates the COVID crash without inventing pre-IPO prices, but it remains a reconstructed portfolio rather than actual client P&L.

## Concentration and sector exposure

| Measure | Result |
|---|---:|
| Largest holding | HDFCBANK, 8.00% |
| Top-five concentration | 35.00% |
| Holdings above 10% | None |
| Holding HHI | 0.03715 |
| Effective holding count | 26.9 |
| Largest sector | Financials, 37.30% |
| Second-largest sector | Industrials, 18.54% |
| Top-two sectors | 55.84% |
| Sector HHI | 0.20988 |
| Effective sector count | 4.8 |

| Sector | Portfolio weight | Supplied benchmark weight | Difference on supplied coverage |
|---|---:|---:|---:|
| Financials | 37.30% | 32.70% | +4.60 pp |
| Industrials | 18.54% | 5.00% | +13.54 pp |
| Consumer Discretionary | 12.30% | 7.50% | +4.80 pp |
| Information Technology | 8.80% | 9.60% | −0.80 pp |
| Health Care | 7.38% | 4.10% | +3.28 pp |
| Energy | 7.00% | 9.00% | −2.00 pp |
| Materials | 4.78% | 1.20% | +3.58 pp |
| Communication Services | 2.70% | 4.00% | −1.30 pp |
| Consumer Staples | 1.20% | 2.00% | −0.80 pp |

The holding-level benchmark weights supplied in the portfolio file total only 75.10%, so the differences above are diagnostic comparisons on covered constituents, not a complete benchmark-sector active-weight decomposition. The missing 24.90% must be classified before final hedge sizing.

## Benchmark exposure and basis risk

| Measure | Result | Interpretation |
|---|---:|---|
| NIFTY beta | 1.012 | Near one-for-one full-sample market sensitivity |
| NIFTY downside beta | 1.057 | Sensitivity increases when NIFTY daily returns are negative |
| NIFTY correlation | 0.970 | Strong, but imperfect, hedge relationship |
| Annualized tracking error | 4.54% | Material residual risk versus a simple NIFTY position |
| 126-day rolling NIFTY beta | 0.850–1.113 | Static hedge ratio can become stale |
| BANKNIFTY beta | 0.715 | Meaningful banking-factor exposure |
| BANKNIFTY correlation | 0.912 | Supports testing a supplementary bank-index leg |
| Worst six-month active return vs NIFTY | −1.61 pp | Basis loss remains after broad-index matching |

For context, reconstructed annualized portfolio volatility is 18.79% versus 18.01% for NIFTY over the aligned sample. Historical annualized returns were 23.44% and 13.04%, respectively; these are backward-looking sample statistics, not return forecasts and are strongly affected by using current holdings retrospectively.

## Unhedged risk baseline

| Measure | Result |
|---|---:|
| Daily 99% VaR | −3.39% |
| Daily 99% expected shortfall | −5.65% |
| Historical maximum drawdown | −40.06% (trough 2020-03-23) |
| Six-month 99% VaR | −10.61% |
| Six-month 99% expected shortfall | −11.37% |
| Probability of six-month loss worse than 10% | 1.67% |
| Worst / median / best six-month return | −12.13% / +14.41% / +59.83% |

At ₹5.00bn, the six-month 99% expected-shortfall estimate corresponds to approximately ₹568.7m of loss, and the worst historical window to approximately ₹606.3m. These currency translations assume the initial portfolio value is unchanged and do not model flows, taxes, trading costs, or dynamic holdings.

The mandate requires the **hedged** six-month 99% expected shortfall to be no worse than −12%. The unhedged point estimate passes by a limited margin even after adding COVID-period evidence. It should not be interpreted as evidence that no hedge is required: the observed worst window breaches −12%, the mandate separately targets losses beyond 10%, and the required named and simulated stress scenarios are not yet available in the repository.

## Liquidity and hedge-design implications

81.10% of the portfolio is classified `HIGH` liquidity and 18.90% `MEDIUM`; no holding carries an explicit hedging restriction. These portfolio classifications do not prove that a proposed derivative hedge can be unwound within the mandated three trading days at no more than 10% participation. Contract-level volume, open interest, bid–ask spread, and market-impact inputs must be applied to each candidate.

The diagnosis supports the following design tests:

1. Use NIFTY as the primary broad-market hedge and size from scenario loss reduction, not beta alone.
2. Compare a NIFTY-only hedge with a NIFTY plus BANKNIFTY structure to determine whether reduced Financials basis risk justifies incremental premium, liquidity use, and complexity.
3. Re-estimate hedge ratios weekly and trigger exceptional review when beta, sector weights, or tail metrics move beyond approved thresholds.
4. Require historical crisis, block-bootstrap, factor-simulation, and named stress results before client feasibility is determined.

## Limitations and decision boundary

- The portfolio history is reconstructed with 2026-01-30 weights. On each interval, weights are renormalized across holdings with prices at both endpoints. It is not the client's actual historical P&L and is subject to look-ahead and survivorship bias.
- The 1,379 six-month observations overlap heavily and are not statistically independent. At a 1% tail, the expected-shortfall estimate is driven by roughly 13.79 observation-equivalents.
- The sample includes the 2020 COVID crash. MAXHEALTH and KAYNES are absent before listing, so their weights are redistributed across available holdings; minimum represented snapshot weight is 98.22%.
- No named stress definitions or populated scenario outputs exist in the repository, so crash, correlation-breakdown, volatility-skew, wider-spread, and delayed-rebalancing results cannot be reported yet.
- Benchmark weights cover only 75.10% of the benchmark. Complete benchmark classification is required for a definitive active-sector report.
- Historical VaR and expected shortfall measure empirical sample loss; they do not create a guaranteed floor.
- Index hedges leave stock-specific risk, sector mismatch, liquidity risk, gap risk, model risk, and changing-beta risk. Statistical protection is not a guaranteed portfolio floor.

## Reproducibility lineage

| Item | Identifier |
|---|---|
| Portfolio input | `cases/asteria_capital/portfolio.csv`; SHA-256 `AA619C7AAE76EDE48F4502BF7972C4BF785E5D0A06514B9D7BCA5D63417D674F` |
| Mandate input | `cases/asteria_capital/mandate.yaml`; `asteria-capital-v1`; SHA-256 `DFC937AD467ACD2D706FBB98F812314C734FA2582C810A1BFE963E49F7F7EDF6` |
| Market data | `data/market/eod_prices.csv`; SHA-256 `754EEE5FE63AA8954AE4AD71039D6C4122506A97255844EC5762E5403AA7C918` |
| Market-data manifest | Yahoo Finance via yfinance 0.2.66; downloaded 2026-08-23T12:06:49.681279Z |
| Price field | `adjusted_close` |
| Return convention | Simple close-to-close return on common NIFTY and BANKNIFTY endpoints |
| Portfolio-return convention | Current snapshot weights renormalized daily across holdings priced at both endpoints |
| Six-month horizon | 126 trading days, overlapping rolling windows |
| Tail convention | Signed empirical lower-tail nearest-rank VaR; fractional-boundary empirical ES |
| Confidence | 99% |
| Code revision | Git commit `343e7d56a0dac416dfa59ada4f12e0c20bb55f2d` plus uncommitted workspace files |
| Verification | 137 tests and 52 subtests passed on 2026-08-23 |
