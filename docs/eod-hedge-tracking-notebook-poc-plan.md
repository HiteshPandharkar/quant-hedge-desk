# Notebook-First POC: EOD Hedge Performance Replay

## Summary

Create one Jupyter notebook that proves the essential calculations before introducing production modules, constants, dataclasses, lifecycle services, or storage.

The notebook will replay the Asteria portfolio and NIFTY vertical put spread from **30 January 2026 through 30 July 2026**, using real equity/index EOD prices and simple model-derived option marks. It will produce daily performance tables, two charts, a summary, and an optional CSV export.

## Sprint 1 — Data and Notebook Foundation

### 1. Add notebook dependencies

Create a notebook-only requirements file containing:

- JupyterLab
- pandas
- matplotlib
- Existing runtime requirements

Do not add these dependencies to the production runtime requirements yet.

### 2. Download a separate POC dataset

Use the existing downloader to create:

```text
data/market/eod_prices_poc_2026-01-30_2026-07-30.csv
data/market/eod_prices_poc_2026-01-30_2026-07-30.manifest.json
```

Include:

- All 50 portfolio holdings.
- NIFTY.
- BANKNIFTY.
- Adjusted close, raw close, volume, ticker mapping, and source lineage.

Keep the existing historical dataset unchanged.

### 3. Create the notebook

Create:

```text
notebooks/eod_hedge_tracking_poc.ipynb
```

The notebook will use the existing project loaders for:

- `portfolio.csv`
- `candidate_02_nifty_vertical_put_spread.yaml`
- `pricing_snapshot_2026-01-30.yaml`

Set `PYTHONPATH` from the notebook so it runs from the repository root without installing the package.

### 4. Input and assumption cell

Use one visible dictionary for all POC choices:

```python
settings = {
    "inception_date": "2026-01-30",
    "end_date": "2026-07-30",
    "day_count": 365,
    "volatility_lower_bound": 0.0001,
    "volatility_upper_bound": 5.0,
    "calibration_tolerance": 1e-8,
    "calibration_iterations": 200,
}
```

Display prominently that:

- Portfolio holdings are static.
- Candidate quantities and multipliers are used as configured.
- Volatility is calibrated at inception and then held constant.
- Option marks are analytical rather than observed settlement prices.
- Results are reconstructed performance, not actual client P&L.

### 5. Load and validate data

Build pandas tables for portfolio, market prices, candidate legs, and pricing assumptions.

Validate:

- Portfolio and candidate inception dates match.
- Requested inception and expiry exist in the EOD data.
- Required symbols are present.
- Prices are finite and positive.
- Dates are unique per symbol.
- Candidate contains only supported European options or futures.
- Pricing snapshot supplies inception spots, forwards, and rate.
- Candidate expiry is not before inception.

Use NIFTY trading dates as the replay calendar. Retain only dates with complete portfolio and required-underlying observations, and display any excluded dates and missing symbols. Fail if inception or expiry would be excluded.

### Sprint 1 acceptance

- The notebook loads every input without copying domain data manually.
- The POC dataset covers inception through expiry.
- The initial portfolio reconciles to ₹5 billion.
- Missing or inconsistent data produces a readable assertion failure.
- No calculation code is added to `src/`.

## Sprint 2 — Essential Calculations

### 1. Reconstruct daily portfolio value

For each holding:

```text
holding_value_t =
    initial_market_value
    × adjusted_close_t
    ÷ adjusted_close_inception
```

Then calculate:

```text
portfolio_value_t = sum(holding_value_t)
portfolio_pnl_t = portfolio_value_t - portfolio_value_0
unhedged_return_t = portfolio_pnl_t / portfolio_value_0
```

This preserves the supplied inception value and uses adjusted-close total returns without creating corporate-action logic.

### 2. Add minimal pricing helpers in notebook cells

Define only the calculation functions needed by the notebook:

- `normal_cdf`
- `black76_option_value`
- `implied_volatility`
- `option_leg_value`
- `future_leg_value`
- `running_drawdown`

Do not create reusable package modules, classes, enums, or dataclasses.

### 3. Derive market assumptions

Read the interpolated T-bill rate, inception spots, and inception forwards from the pricing snapshot.

For each underlying:

```text
initial_time =
    (expiry - inception).days / 365

carry =
    ln(inception_forward / inception_spot) / initial_time

forward_t =
    spot_t × exp(carry × time_to_expiry)

discount_factor_t =
    1 / (1 + rate × time_to_expiry)
```

Use index `close` for option-underlying levels and adjusted close for portfolio holding performance.

### 4. Calibrate inception volatility

For each option leg:

- Calculate its configured unit premium.
- Check that the premium lies within Black-76 bounds.
- Solve for implied volatility using bounded bisection.
- Reprice at inception.
- Assert that repriced premium matches configured premium within tolerance.
- Display a calibration table containing contract, premium, calibrated volatility, and reconciliation difference.

This avoids an unexplained day-one valuation jump.

### 5. Calculate daily hedge values

Before expiry:

```text
signed_leg_value_t =
    model_unit_value_t
    × quantity
    × contract_multiplier
    × direction_sign
```

At expiry:

```text
put_payoff = max(strike - spot, 0)
call_payoff = max(spot - strike, 0)
```

Aggregate all legs into the daily hedge value.

For the reference vertical spread, correctly account for:

- Long 24,000 NIFTY put.
- Short 22,800 NIFTY put.
- Quantity and multiplier on each leg.
- Protection capped below the lower strike.

### 6. Calculate hedge and combined P&L

Calculate the signed inception hedge value:

```text
inception_hedge_value =
    sum(signed premium × quantity × multiplier)
```

Then:

```text
hedge_gross_pnl_t =
    hedge_value_t - inception_hedge_value

hedge_net_pnl_t =
    hedge_gross_pnl_t - estimated_execution_cost

combined_pnl_t =
    portfolio_pnl_t + hedge_net_pnl_t

combined_return_t =
    combined_pnl_t / initial_portfolio_value

hedge_benefit_t =
    combined_pnl_t - portfolio_pnl_t
```

Premium is treated as the derivative’s cost basis, not as an immediate loss. Execution cost is charged once.

### 7. Calculate drawdowns

Build wealth indices:

```text
unhedged_wealth_t = portfolio_value_t
hedged_wealth_t = initial_portfolio_value + combined_pnl_t
```

Calculate running peak and drawdown for both series.

### Sprint 2 acceptance

- Inception gross hedge P&L equals zero.
- Inception net hedge P&L equals negative execution cost.
- Every leg reconciles to its configured inception premium.
- Expiry hedge value equals the terminal payoff calculation.
- The short-put sign is handled correctly.
- No NaN or infinite values remain in the final daily table.
- Daily accounting identities reconcile within monetary tolerance.

## Sprint 3 — Results, Charts, and Verification

### 1. Produce the daily results table

Create one pandas DataFrame with:

- Date
- Portfolio value
- Portfolio daily and cumulative P&L
- Unhedged return
- Unhedged drawdown
- Hedge value
- Hedge daily P&L
- Hedge gross and net cumulative P&L
- Execution cost
- Combined P&L
- Combined return
- Hedged drawdown
- Hedge benefit
- NIFTY close
- Days to expiry

Display inception, worst portfolio day, maximum drawdown date, and expiry rows separately for review.

### 2. Produce a compact summary

Show:

- Initial and expiry portfolio values.
- Initial net premium.
- Execution cost.
- Unhedged expiry return.
- Hedged expiry return.
- Final hedge gross and net P&L.
- Hedge benefit in INR and percentage points.
- Unhedged and hedged maximum drawdown.
- Drawdown reduction.
- Calibrated volatility for each option leg.

### 3. Add two charts

Chart 1 — performance:

- Unhedged cumulative return.
- Hedged cumulative return.
- Vertical expiry marker.
- Percentage y-axis.

Chart 2 — drawdown:

- Unhedged drawdown.
- Hedged drawdown.
- Shared date axis.
- Percentage y-axis.

Use restrained formatting and no dashboard framework.

### 4. Add optional CSV export

Provide a final cell that writes:

```text
reports/asteria_eod_hedge_tracking_poc.csv
```

Export the aggregate daily results with deterministic column ordering, ISO dates, and explicit decimal formatting.

The export cell must be easy to disable so rerunning calculations does not require writing a file.

### 5. Add notebook assertions

At the end of the notebook, assert:

- First date equals inception.
- Last date equals expiry.
- Dates are strictly increasing and unique.
- Initial portfolio value reconciles to the source portfolio.
- Inception model marks reconcile to premiums.
- Gross and net hedge P&L identities hold.
- Combined P&L equals portfolio plus hedge P&L.
- Hedge benefit equals net hedge P&L.
- Expiry option marks equal intrinsic payoff.
- Drawdowns are never positive.
- Results contain no missing numeric values.

### 6. Execute and verify

Run the notebook from a clean kernel from top to bottom.

Verify it using Jupyter’s execution tooling so hidden cell state cannot affect the result. Keep only compact tables and charts in saved outputs; do not render the full 50-holding daily panel.

### Sprint 3 acceptance

- A new user can run the notebook top-to-bottom from the repository root.
- The notebook produces the same results from a clean kernel.
- The daily table, summary, and both charts render successfully.
- The optional CSV matches the displayed aggregate results.
- All notebook assertions pass.
- The existing pytest suite remains green.

## Deferred Until the Notebook Is Validated

Only after the notebook calculations and accounting conventions are approved should the work be extracted into:

- Shared constants and enums.
- Immutable dataclasses.
- Pricing and calibration modules.
- Portfolio and market-data repositories.
- Lifecycle and settlement services.
- A formal Python tracking API.
- Unit and integration test modules.
- Scheduled EOD runs, databases, rebalancing, live option marks, and dashboards.

The notebook will therefore be the executable specification for the later production implementation.
