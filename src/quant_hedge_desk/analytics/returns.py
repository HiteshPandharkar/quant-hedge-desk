"""Construction of date-aligned simple-return datasets.

Prices are aligned *before* returns are calculated.  This is important: if a
symbol is missing a trading date, calculating each series first would compare
returns measured over different intervals and create misleading beta and
tracking-error estimates.
"""

from __future__ import annotations

from datetime import date, datetime
from math import isfinite
from typing import Any, Mapping, Sequence

import numpy as np

from quant_hedge_desk.analytics.errors import ReturnDataError
from quant_hedge_desk.analytics.models import (
    AlignedReturnDataset,
    AvailableWeightPortfolioReturns,
    MissingPriceDate,
)


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        raise ReturnDataError("price dates must be dates, not datetimes")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ReturnDataError(f"invalid ISO price date: {value!r}") from exc
    raise ReturnDataError(f"price date must be an ISO date or date: {value!r}")


def _price(value: Any, symbol: str, observation_date: date) -> float:
    if isinstance(value, bool):
        raise ReturnDataError(f"{symbol} price on {observation_date} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ReturnDataError(
            f"{symbol} price on {observation_date} must be numeric"
        ) from exc
    if not isfinite(result) or result <= 0:
        raise ReturnDataError(f"{symbol} price on {observation_date} must be finite and positive")
    return result


def build_aligned_return_dataset(
    price_history: Mapping[str, Mapping[date | str, Any]],
    *,
    required_symbols: Sequence[str] | None = None,
) -> AlignedReturnDataset:
    """Build simple returns on the intersection of all required price dates.

    The input is ``{symbol: {date: adjusted_price}}``.  Adjusted or total-return
    prices should be supplied so dividends and corporate actions are treated
    consistently.  Missing observations are never forward-filled; excluded
    union-calendar dates are retained as diagnostics.
    """

    if not isinstance(price_history, Mapping) or not price_history:
        raise ReturnDataError("price_history must be a non-empty mapping")

    normalized_history: dict[str, dict[date, float]] = {}
    for raw_symbol, observations in price_history.items():
        symbol = str(raw_symbol).strip().upper()
        if not symbol:
            raise ReturnDataError("price-history symbols must be non-empty")
        if symbol in normalized_history:
            raise ReturnDataError(f"duplicate symbol after normalization: {symbol}")
        if not isinstance(observations, Mapping) or not observations:
            raise ReturnDataError(f"{symbol} price history must be a non-empty mapping")
        parsed: dict[date, float] = {}
        for raw_date, raw_price in observations.items():
            observation_date = _date(raw_date)
            if observation_date in parsed:
                raise ReturnDataError(f"duplicate {symbol} price date: {observation_date}")
            parsed[observation_date] = _price(raw_price, symbol, observation_date)
        normalized_history[symbol] = parsed

    if required_symbols is None:
        symbols = tuple(normalized_history)
    else:
        if isinstance(required_symbols, (str, bytes)):
            raise ReturnDataError("required_symbols must be a sequence of symbols")
        symbols = tuple(str(symbol).strip().upper() for symbol in required_symbols)
        if not symbols or any(not symbol for symbol in symbols):
            raise ReturnDataError("required_symbols must contain non-empty symbols")
        if len(symbols) != len(set(symbols)):
            raise ReturnDataError("required_symbols contains duplicates")
        missing = sorted(set(symbols) - normalized_history.keys())
        if missing:
            raise ReturnDataError(f"missing required price histories: {', '.join(missing)}")

    date_sets = [set(normalized_history[symbol]) for symbol in symbols]
    common_dates = tuple(sorted(set.intersection(*date_sets)))
    if len(common_dates) < 2:
        raise ReturnDataError(
            "fewer than two common price dates remain after aligning required symbols"
        )

    union_dates = sorted(set.union(*date_sets))
    common_date_set = set(common_dates)
    excluded = tuple(
        MissingPriceDate(
            observation_date,
            tuple(symbol for symbol in symbols if observation_date not in normalized_history[symbol]),
        )
        for observation_date in union_dates
        if observation_date not in common_date_set
    )

    aligned_returns: dict[str, tuple[float, ...]] = {}
    for symbol in symbols:
        prices = normalized_history[symbol]
        aligned_prices = np.fromiter(
            (prices[observation_date] for observation_date in common_dates),
            dtype=np.float64,
            count=len(common_dates),
        )
        aligned_returns[symbol] = tuple(
            (aligned_prices[1:] / aligned_prices[:-1] - 1.0).tolist()
        )

    return AlignedReturnDataset(common_dates, aligned_returns, excluded)


def build_available_weight_portfolio_returns(
    price_history: Mapping[str, Mapping[date | str, Any]],
    holding_weights: Mapping[str, Any],
    *,
    price_dates: Sequence[date | str],
) -> AvailableWeightPortfolioReturns:
    """Build same-interval portfolio returns without inventing pre-listing prices.

    For each consecutive pair of supplied calendar dates, a holding contributes
    only when it has a price at both endpoints. Snapshot weights are renormalized
    over the contributing holdings for that interval. This permits crisis-period
    reconstruction when a small part of the current portfolio listed later,
    while retaining explicit coverage diagnostics and never forward-filling.
    """

    if not isinstance(price_history, Mapping) or not price_history:
        raise ReturnDataError("price_history must be a non-empty mapping")
    if not isinstance(holding_weights, Mapping) or not holding_weights:
        raise ReturnDataError("holding_weights must be a non-empty mapping")

    calendar = tuple(_date(value) for value in price_dates)
    if len(calendar) < 2 or any(
        left >= right for left, right in zip(calendar, calendar[1:])
    ):
        raise ReturnDataError(
            "price_dates must contain at least two unique increasing dates"
        )

    normalized_history: dict[str, dict[date, float]] = {}
    normalized_weights: dict[str, float] = {}
    for raw_symbol, raw_weight in holding_weights.items():
        symbol = str(raw_symbol).strip().upper()
        if not symbol or symbol in normalized_weights:
            raise ReturnDataError("holding-weight symbols must be unique and non-empty")
        if symbol not in price_history:
            raise ReturnDataError(f"missing required price history: {symbol}")
        if isinstance(raw_weight, bool):
            raise ReturnDataError(f"{symbol} weight must be numeric")
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as exc:
            raise ReturnDataError(f"{symbol} weight must be numeric") from exc
        if not isfinite(weight) or weight <= 0.0:
            raise ReturnDataError(f"{symbol} weight must be finite and positive")
        observations = price_history[symbol]
        normalized_history[symbol] = {
            _date(raw_date): _price(raw_price, symbol, _date(raw_date))
            for raw_date, raw_price in observations.items()
        }
        normalized_weights[symbol] = weight

    total_weight = sum(normalized_weights.values())
    if not np.isclose(total_weight, 1.0, rtol=0.0, atol=1e-8):
        raise ReturnDataError("holding_weights must sum to 1")

    portfolio_returns: list[float] = []
    covered_weights: list[float] = []
    available_counts: list[int] = []
    for start, end in zip(calendar, calendar[1:]):
        contributors = tuple(
            symbol
            for symbol, observations in normalized_history.items()
            if start in observations and end in observations
        )
        if not contributors:
            raise ReturnDataError(
                f"no holdings have prices at both endpoints {start} and {end}"
            )
        covered = sum(normalized_weights[symbol] for symbol in contributors)
        result = sum(
            normalized_weights[symbol]
            * (normalized_history[symbol][end] / normalized_history[symbol][start] - 1.0)
            for symbol in contributors
        ) / covered
        portfolio_returns.append(result)
        covered_weights.append(covered)
        available_counts.append(len(contributors))

    return AvailableWeightPortfolioReturns(
        calendar,
        tuple(portfolio_returns),
        tuple(covered_weights),
        tuple(available_counts),
    )


__all__ = [
    "AlignedReturnDataset",
    "AvailableWeightPortfolioReturns",
    "MissingPriceDate",
    "ReturnDataError",
    "build_aligned_return_dataset",
    "build_available_weight_portfolio_returns",
]
