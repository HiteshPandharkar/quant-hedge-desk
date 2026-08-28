# Quant Hedge Desk

A research-grade Python toolkit for diagnosing an equity portfolio, designing
and stress-testing derivative hedges, enforcing client and dealer constraints,
and producing a deterministic pre-trade decision.

The repository includes a fictional Indian equity mandate for **Asteria
Capital**. Its checked-in market data, option quotes, hedge candidates, desk
inventory, and limits make the workflow reproducible without a live market-data
connection. The examples are analytical fixtures, not executable investment
recommendations or live quotes.

## What the project covers

- Portfolio validation, return construction, concentration analysis, beta,
  tracking error, VaR, expected shortfall, and downside-risk metrics.
- Historical rolling-window, moving-block bootstrap, manual, and correlated
  factor-simulation scenario generation.
- Explicit option and futures legs with terminal payoff evaluation.
- Hedge feasibility against eligibility, premium, upside-sacrifice, liquidity,
  and protection constraints.
- Named stress tests with basis-correlation gaps, spread-adjusted execution
  costs, volume-adjusted unwind horizons, and stressed hedged returns.
- Dealer inventory aggregation and post-trade delta, vega, crash-loss,
  liquidity, and model-reserve limit checks.
- Deterministic ranking of feasible candidates and one final pre-trade action:
  `QUOTE`, `QUOTE_WITH_ADDITIONAL_RESERVE`, `REDUCE_NOTIONAL`, `RESTRUCTURE`, or
  `DECLINE`.

## Requirements

- Python 3.11 or newer
- Dependencies listed in `requirements/runtime.txt`
- `pytest` to run the test suite

The repository currently uses a `src` layout without installable package
metadata, so set `PYTHONPATH` to `src` when running it locally.

## Quick start

From the repository root in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements/runtime.txt pytest
$env:PYTHONPATH = "src"
python -m pytest -q
```

On macOS or Linux, activate with `source .venv/bin/activate` and run
`export PYTHONPATH=src` instead.

## Run the EOD hedge-tracking notebook

The checked-in notebook replays the Asteria portfolio and its NIFTY vertical
put spread from 30 January 2026 through 30 July 2026. It reconstructs daily
portfolio and hedge P&L, calibrates inception option volatility, and displays
performance and drawdown charts using the dedicated POC market dataset.

Install the notebook-only dependencies and launch JupyterLab from the
repository root:

```powershell
python -m pip install -r requirements/notebook.txt
python -m jupyter lab notebooks/eod_hedge_tracking_poc.ipynb
```

The notebook locates and adds `src` to its import path automatically. Its final
export cell is disabled by default; enable it to write
`reports/asteria_eod_hedge_tracking_poc.csv`. The replay uses static holdings
and analytical option marks, so it is reconstructed performance rather than
actual client P&L.

## Run the reference assessment

The public application layer is programmatic rather than a CLI. This example
validates the reference portfolio and mandate, then calculates its baseline
risk assessment:

```python
from quant_hedge_desk.application.assess_mandate import assess_mandate

assessment = assess_mandate(
    portfolio_path="cases/asteria_capital/portfolio.csv",
    mandate_path="cases/asteria_capital/mandate.yaml",
    desk_limits_path="cases/asteria_capital/desk_limits.yaml",
    market_data_path="data/market/eod_prices.csv",
)

print(assessment.to_dict())
```

Assess a configured hedge candidate against every hard client constraint:

```python
from quant_hedge_desk.application.assess_candidate_hedge import (
    assess_candidate_hedge,
)

result = assess_candidate_hedge(
    portfolio_path="cases/asteria_capital/portfolio.csv",
    mandate_path="cases/asteria_capital/mandate.yaml",
    candidate_path=(
        "cases/asteria_capital/"
        "candidate_02_nifty_vertical_put_spread.yaml"
    ),
    market_data_path="data/market/eod_prices.csv",
)

print(result.to_dict())
```

Each feasibility result contains a top-level `FEASIBLE` or `INFEASIBLE`
status, derived risk and cost metrics, individual diagnostics, and the binding
hard rules in `failed_constraints`. Infeasible results also include
parameter-level relaxation estimates in `infeasibility_diagnosis`.

## Reference case

The `cases/asteria_capital` directory contains:

| File | Purpose |
| --- | --- |
| `portfolio.csv` | Fictional equity holdings and portfolio weights |
| `mandate.yaml` | Client eligibility, protection, cost, upside, and liquidity rules |
| `candidate_*.yaml` | Hybrid puts, a NIFTY vertical put spread, and a protective put |
| `instrument_quotes.csv` | Reproducible executable and fallback quote inputs |
| `named_stress_correlation_liquidity.yaml` | Versioned stress scenarios and liquidity shocks |
| `desk_limits.yaml` | Dealer hard limits and warning thresholds |
| `desk_portfolio_capacity_*.yaml` | Available- and constrained-capacity inventory snapshots |

Supporting inputs and outputs live in:

- `data/market/eod_prices.csv` — checked-in adjusted-close history.
- `data/market/eod_prices.manifest.json` — data source and coverage lineage.
- `data/market/eod_prices_poc_2026-01-30_2026-07-30.csv` — notebook replay
  prices, with its adjacent manifest.
- `data/market/pricing_snapshot_2026-01-30.yaml` — reproducible pricing inputs.
- `notebooks/eod_hedge_tracking_poc.ipynb` — executable daily hedge replay.
- `reports/` — portfolio diagnosis and limitation disclosures.
- `methodology/` — scenario-method documentation.

## Core workflow

```text
portfolio + mandate + market data
                |
                v
       diagnose portfolio risk
                |
                v
     generate/evaluate scenarios
                |
                v
 assess and rank hedge candidates
                |
                v
 add desk inventory + dealer limits
                |
                v
 reconcile quote and make decision
```

A hedge is feasible only when every hard mandate diagnostic passes. Ranking
then excludes infeasible candidates and compares survivors lexicographically in
the mandate's declared objective order, with candidate ID as the final stable
tie-break.

The pre-trade calculator fails closed when client feasibility, dealer approval,
quote reconciliation, or executable all-in cost evidence is missing. Requested
trades are considered before reduced-notional and restructured alternatives.
`QUOTE_WITH_ADDITIONAL_RESERVE` requires both an explicit justification and a
positive, reconciled model reserve.

## Architecture

```text
src/quant_hedge_desk/
|-- analytics/       Portfolio returns, exposure, concentration, and risk
|-- application/     End-to-end assessment and decision facades
|-- data/            CSV/YAML loaders, repositories, and validation
|-- domain/          Immutable models, mandate rules, limits, and decisions
|-- hedge_design/    Candidate payoff, feasibility, stress, and ranking logic
|-- pricing/         Pricing port, CSV adapter, quotes, and waterfall models
|-- reports/         Structured diagnostic-report helpers
`-- scenarios/       Historical, bootstrap, factor, and manual generators
```

The design keeps immutable contracts separate from pure calculations and
application orchestration. Shared scenario, premium, and terminal-level math is
reused across feasibility and stress flows. Historical compatibility imports
remain available where modules have been split into narrower responsibilities.

## Scenario methodologies

Historical rolling windows are the primary empirical method. Moving-block
bootstrap scenarios retain short-run serial dependence, while factor simulation
estimates correlated factor log returns and OLS asset exposures before creating
reproducible paths with an optional local seed. Generated sets retain method,
parameter, and source-snapshot lineage.

See:

- `methodology/historical_rolling_scenarios.md`
- `methodology/factor_simulation_scenarios.md`

## Rebalancing stress contracts

The first rebalancing-stress increment adds strict, immutable interfaces without
changing existing static stress behavior. Scenario steps may optionally include
dated option marks, forward levels, a risk-free rate, and additive volatility
shifts. Existing scenario YAML needs no migration.

`load_rebalancing_stress_policy(...)` loads a versioned policy for either
`EXPLICIT_MARKS` or `BLACK_76` pricing. The checked-in Asteria policy uses a 5%
exceptional coverage-drift threshold, a five-trading-day routine interval,
contract-level indicative volatilities, and release gating for failed required
rebalances.

The Sprint 2 proposal layer is available in
`quant_hedge_desk.hedge_design.rebalancing`. It resolves explicit marks by
canonical contract identity or calculates Black-76 marks from dated scenario
state using an actual-calendar-days/365 year fraction. Targets preserve
inception per-underlying coverage and whole-structure
leg ratios, using decimal half-up contract rounding. `propose_rebalance(...)`
returns an immutable, JSON-ready request for routine or exceptional triggers;
missing pricing inputs produce a rejected request, while terminal steps and
rounded no-ops produce no request.

## Refresh market data

The checked-in dataset is sufficient for the tests and examples. To explicitly
refresh it from Yahoo Finance:

```powershell
python scripts/download_eod_prices.py `
  --portfolio cases/asteria_capital/portfolio.csv `
  --output data/market/eod_prices.csv `
  --start 2023-01-01 `
  --end 2026-01-30
```

This operation requires network access and replaces the requested output plus
its adjacent manifest. Review the resulting coverage and lineage before using
the refreshed data in comparisons.

## Important limitations

- The reference case is fictional and its option/liquidity assumptions are
  synthetic.
- The code is a research and decision-support project, not an order-management,
  execution, or production risk system.
- Stored desk snapshots are approved risk-system inputs; the pricing adapter
  does not derive their Greeks or crash P&L.
- Scenario results are model-dependent and do not predict future performance.

For case-specific caveats, see
`reports/asteria_capital_limitation_disclosures.md`.
