# Factor simulation scenarios

The factor-simulation engine is the alternative parametric methodology used to
challenge results from historical rolling windows. It fits only observations on
or before the scenario set's as-of date and generates equally weighted daily
paths over the configured horizon.

## Model

Daily simple returns are converted to log returns. The configured factor series
(for example, NIFTY) are modeled jointly with their historical sample mean and
covariance. Each remaining asset is estimated by ordinary least squares:

`asset log return = intercept + factor exposures * factor log returns + residual`

For every simulated day, correlated factor returns are drawn from a multivariate
normal distribution. Asset returns are reconstructed from their fitted factor
exposures and independent Gaussian residuals with the estimated sample residual
volatility. Simulated log returns are converted back with `expm1`, ensuring that
simple returns remain above -100%.

## Reproducibility and lineage

The generator creates a local random-number generator on every call. Supplying
`random_seed` produces identical paths across repeated calls and does not alter
global random state. The scenario set records the seed, distribution,
estimation method, factor symbols, source observation count, model version, and
source snapshot identifiers.

## Validation and limitations

The engine rejects look-ahead data, missing or duplicated factors, insufficient
observations, factor design matrices without full rank, and returns that cannot
be log transformed. It assumes stable exposures, normally distributed factor
and residual innovations, and independent residuals across non-factor assets.
Consequently it can understate skew, fat tails, volatility clustering, and
idiosyncratic co-movement. It is a robustness comparison, not a replacement for
historical replay, block bootstrap, or named stress scenarios.
