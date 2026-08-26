# Asteria Capital — Limitation Disclosures

**Portfolio:** ASTERIA-001  
**Portfolio snapshot:** 2026-01-30  
**Disclosure produced:** 2026-08-23  
**Scope:** Research and pre-trade decision support  
**Release status:** Restricted; no checked-in candidate passes all named stress gates

## Required headline disclosure

The analysis is a reproducible project case study based on a fictional client and
fictional dealer limits. It is not an executable quote, a promise of hedge
performance, or evidence of suitability for any real client. An index hedge does
not create a guaranteed portfolio floor. Stock-specific losses, sector mismatch,
correlation breakdown, changing beta, market gaps, volatility-skew changes,
liquidity deterioration, model error, and delayed rebalancing can cause the
portfolio to lose materially more than the hedge proxy indicates.

No checked-in Asteria candidate is cleared for an unrestricted recommendation.
Each candidate fails at least one release-gate named stress. Any later report or
commercial decision must carry forward the applicable restrictions below and
must use refreshed, executable market inputs.

## Candidate-specific restrictions

| Candidate | Correlation-breakdown result | Stressed-liquidity result | Required restriction |
|---|---|---|---|
| Hybrid NIFTY/BANKNIFTY protective puts | 7.10 pp absolute basis gap versus 5.00 pp limit; fail | 3.13-day unwind; stressed cost 2.984% versus 2.5% budget; fail | Do not describe as a portfolio floor. Do not assume a three-day full unwind. Reprice, resize, or reserve before quoting. |
| NIFTY vertical put spread | 8.00 pp absolute basis gap versus 5.00 pp limit; fail | 6.20-day unwind; fail | Do not describe as a portfolio floor. Do not assume a three-day full unwind. Protection is capped below the short-put strike. |
| NIFTY protective put | 8.00 pp absolute basis gap versus 5.00 pp limit; fail | 4.48-day unwind; stressed cost 2.703% versus 2.5% budget; fail | Do not describe as a portfolio floor. Do not assume a three-day full unwind. Reprice, resize, or reserve before quoting. |

The stress results use scenario set
`asteria-correlation-liquidity-stress-v1`, version `1.0`, and the configured
5.00 percentage-point maximum correlation-basis gap. Passing an individual
cost, liquidity, or basis check does not override a failure of another hard
gate.

## Residual basis and protection risk

- NIFTY and BANKNIFTY options settle on index levels, not on the value of the
  client portfolio. The portfolio's stock and sector composition can diverge
  from both indices before or at expiry.
- The reconstructed portfolio has 37.30% in Financials and 18.54% in
  Industrials. A broad-index overlay does not directly neutralize these active
  concentrations.
- Full-sample relationships are not stable protection ratios. Observed NIFTY
  beta is 1.012, downside beta is 1.057, and rolling 126-day beta ranges from
  0.850 to 1.113.
- Correlation breakdown is a demonstrated failure mode. In the named stress,
  the portfolio falls 20% while the NIFTY and BANKNIFTY proxies fall only 12%
  and 15%, respectively. All three candidates breach the configured basis-gap
  tolerance.
- Option protection is strike-, expiry-, quantity-, and settlement-dependent.
  Losses above the strike attachment point remain with the client; protection
  ends at expiry. A vertical put spread additionally caps protection below its
  short strike.
- Premium and execution cost reduce net protection. Early exit, rebalancing,
  taxes, funding, margin, and path-dependent trading costs are not fully
  represented by terminal payoff results.

## Market data and portfolio-history limitations

- Historical portfolio returns are reconstructed using the 2026-01-30 holdings
  and snapshot weights. They are not actual client P&L and contain look-ahead
  and survivorship bias.
- A holding contributes only when adjusted prices exist at both interval
  endpoints. Available weights are then renormalized. MAXHEALTH and KAYNES are
  omitted before listing; represented snapshot weight is no lower than 98.22%.
- The 1,379 six-month historical windows overlap and are not statistically
  independent. The nominal observation count must not be interpreted as an
  effective independent sample size.
- The sample contains the 2020 COVID crash but cannot cover every future regime,
  policy event, market closure, gap, or joint tail dependency.
- Holding-level benchmark weights cover only 75.10% of the benchmark. Active
  sector comparisons are diagnostic on the supplied coverage, not a complete
  benchmark attribution.
- Source errors, corporate-action adjustments, stale prices, and differences
  between end-of-day settlement and executable prices can affect results.

## Pricing and model limitations

- The configured option premiums, execution costs, reference levels, and normal
  daily volumes are user-supplied assumptions. The candidate files label option
  and liquidity inputs as synthetic scaled proxies.
- The target 2026-07-30 contracts were not listed on the 2026-01-30 NSE snapshot.
  Values in the pricing snapshot are indicative Black-76 interpolations from
  bracketing expiries, not executable broker quotes.
- NIFTY 22800 volatility extrapolates the observed 23000/24000 skew.
  BANKNIFTY 56600 uses the nearest listed 57000 strike, whose bracketing rows had
  zero volume and zero open interest. Some call settlements used to infer
  forwards were theoretical.
- Candidate multipliers do not match the exchange snapshot: candidate NIFTY
  uses 25 versus reported lot size 65, and candidate BANKNIFTY uses 15 versus
  reported lot size 30. Candidates must be rebuilt with valid contract
  specifications before execution analysis.
- Historical VaR and expected shortfall are empirical sample statistics, not
  guarantees or maximum-loss bounds. Tail estimates are especially sensitive
  to the short, dependent lower-tail sample.
- Factor simulation assumes stable exposures, multivariate-normal factor and
  residual innovations, and independent residuals across non-factor assets. It
  can understate skew, fat tails, volatility clustering, and idiosyncratic
  co-movement.
- Terminal payoff calculations do not by themselves validate an executable
  hedge. Interim mark-to-market, Greeks, American-style exercise where relevant,
  collateral, counterparty exposure, funding, and operational events require
  separate treatment when applicable.

## Liquidity and execution limitations

- Normal daily volume and baseline execution cost are assumptions rather than
  independently verified executable market observations. A calculated unwind
  horizon is therefore conditional on those inputs.
- The three-day unwind test assumes participation up to the mandate's 10% limit.
  Actual accessible liquidity may be lower, fragmented across strikes and
  expiries, or unavailable at modeled spreads.
- Under the named liquidity stress, usable NIFTY and BANKNIFTY volume falls to
  15% and 10% of baseline and spreads widen four and five times. Every candidate
  breaches at least one stressed liquidity or cost gate.
- Execution may move implied volatility, skew, the underlying index, and quoted
  spreads. The current model scales aggregate baseline execution cost and does
  not simulate an order book, intraday timing, partial fills, or market impact.
- A position that can be entered may not be capable of being exited, rolled, or
  rebalanced on the same terms. Gap moves and market disruption can prevent
  timely adjustment.

## Scenario and methodology boundary

- Historical replay, block bootstrap, factor simulation, and named stresses are
  complementary views. Agreement does not prove completeness; disagreement or
  a material ranking reversal requires review.
- The current named set directly tests correlation breakdown and stressed
  liquidity. It does not separately isolate every volatility-skew shock or a
  multi-step delayed-rebalancing path. Those challenges remain required before
  final release under AC-16.
- Scenario weights are modeling conventions, not forecasts. Named stresses are
  hypothetical and their severity is not an estimate of probability.
- The mandate assessment service does not yet orchestrate scenario valuation,
  candidate pricing, hedge feasibility, and pre-trade decisions end to end.
  Evidence produced by separate services must be reconciled before a final
  recommendation.

## Dealer, governance, and use limitations

- Desk limits, inventory snapshots, risk measures, reserves, and approval rules
  are fictional project assumptions and are not claims about any bank or actual
  trading desk.
- A client-feasible hedge is not automatically dealer-approved or executable.
  Dealer limits, quote reconciliation, approvals, and the executable client
  budget must pass independently.
- A theoretical price or successful model run must not be used alone to return
  `QUOTE`. Missing feasibility, dealer approval, or quote-reconciliation
  evidence requires the decision process to fail closed.
- Results are point-in-time. A material change in portfolio composition, market
  level, volatility surface, rates, dividends, liquidity, contract terms, desk
  inventory, limits, or mandate requires reassessment.
- Real client data must be handled as confidential and excluded from public
  repositories and demonstrations. This checked-in case contains no real client
  information.

## Minimum disclosure language by output

### Client-facing suitability output

> This index-based hedge does not guarantee a portfolio floor. Stock-specific
> losses, sector mismatch, changing beta, correlation breakdown, market gaps,
> liquidity deterioration, model error, premium, and delayed rebalancing may
> cause realized protection to be materially less than illustrated. Results are
> scenario estimates based on point-in-time assumptions, not forecasts.

### Indicative price or term-sheet output

> Indicative and non-executable. The configured contract expiry was not listed
> on the valuation snapshot, premiums and liquidity are synthetic or
> interpolated inputs, and candidate multipliers differ from the exchange
> snapshot. Obtain executable quotes, validate contract terms, and rerun all
> client, stress, liquidity, and dealer checks before use.

### Dealer decision output

> Dealer limits and inventory are fictional project assumptions. Client
> feasibility does not constitute dealer approval. Quote reconciliation,
> post-trade limit capacity, liquidity, reserves, and required approvals must be
> evidenced independently at the decision timestamp.

## Release conditions

These disclosures may accompany research output now, but an unrestricted hedge
recommendation or quote requires all of the following:

1. Replace synthetic/interpolated premiums, spreads, volumes, and contract terms
   with timestamped executable inputs and valid exchange multipliers.
2. Recalculate candidate sizing, cost, expected shortfall, liquidity, and dealer
   risk using the refreshed portfolio and market snapshots.
3. Pass the primary methodology, an alternative scenario methodology, and every
   named release-gate stress, including explicit volatility-skew and delayed-
   rebalancing challenges.
4. Resolve or formally approve every usage restriction and material ranking
   reversal.
5. Reconcile the executable quote waterfall and obtain all required client,
   trading, risk, and model approvals.

## Evidence lineage

| Evidence | Identifier |
|---|---|
| Portfolio | `cases/asteria_capital/portfolio.csv`; ASTERIA-001; 2026-01-30 |
| Mandate | `cases/asteria_capital/mandate.yaml`; `asteria-capital-v1` |
| Candidate inputs | `candidate_01_hybrid_protective_puts.yaml`; `candidate_02_nifty_vertical_put_spread.yaml`; `candidate_03_nifty_protective_put.yaml` |
| Pricing snapshot | `data/market/pricing_snapshot_2026-01-30.yaml`; `nse-fo-2026-01-30-eod`; status `INDICATIVE_NON_EXECUTABLE` |
| Named stresses | `asteria-correlation-liquidity-stress-v1`; version `1.0` |
| Historical method | 126 trading days; one-day stride; equal-weighted overlapping windows |
| Factor method | `methodology/factor_simulation_scenarios.md` |
| Governing requirements | BR-15, NFR-03, AC-15, AC-16 |
