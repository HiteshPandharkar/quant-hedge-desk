# Historical rolling scenarios

The historical engine replays aligned daily simple returns as complete paths.
For the Asteria mandate, each path contains **126 trading days** and a new path
starts **one trading day** after the previous path. All complete windows through
the scenario set's as-of date are retained and receive equal empirical weight.

## Window decisions

- **Length: 126 trading days.** The mandate protects a six-month horizon and
  the project convention is 21 trading days per month, so `6 × 21 = 126`.
- **Stride: one trading day.** This produces overlapping rolling windows and
  uses every observable six-month historical outcome. With the reference data's
  1,504 benchmark-calendar daily returns, the count is
  `1,504 - 126 + 1 = 1,379` scenarios.
- **Boundaries: same-interval return observations.** NIFTY and BANKNIFTY define
  the common price calendar. For each interval, a portfolio holding contributes
  only when it has adjusted prices at both endpoints. Current snapshot weights
  are renormalized across those available holdings; prices are never
  forward-filled. A window starting at return index `i` therefore runs from
  price date `i` through price date `i + 126` and contains the 126 intervening
  daily returns.
- **Weights: equal.** Historical windows have no explicit probabilities, so the
  scenario contract assigns each path weight `1 / window_count`.

The one-day stride is the primary specification because it maximizes use of the
available history, including the 2020 COVID crash, and matches the six-month VaR and expected-
shortfall calculations. Overlapping paths are not independent, so their count
must not be interpreted as an effective independent sample size. For sensitivity
testing, `window_stride` is configurable; setting it to 126 produces
non-overlapping windows (with any incomplete trailing period excluded).

Each scenario retains all 126 dated daily steps rather than only a terminal
return. This preserves path ordering for interim drawdown, delayed rebalancing,
and path-dependent hedge valuation. Data after `as_of_date` is rejected to
prevent look-ahead.

For the reference portfolio, coverage is at least 98.22% of snapshot weight
(48 of 50 names) on every retained interval. MAXHEALTH and KAYNES are omitted
before their listings and their weights are redistributed proportionally. This
is a transparent historical reconstruction, not actual client P&L, and retains
look-ahead and survivorship bias from applying 2026 holdings to earlier dates.
