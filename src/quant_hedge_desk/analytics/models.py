"""Immutable input and result records used by analytics calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from quant_hedge_desk.analytics.errors import ReturnDataError


@dataclass(frozen=True, slots=True)
class MissingPriceDate:
    """A union-calendar date excluded because one or more prices are absent."""

    date: date
    missing_symbols: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlignedReturnDataset:
    """Simple returns for every required symbol over identical intervals."""

    price_dates: tuple[date, ...]
    returns: Mapping[str, tuple[float, ...]]
    excluded_price_dates: tuple[MissingPriceDate, ...] = ()

    def __post_init__(self) -> None:
        price_dates = tuple(self.price_dates)
        if len(price_dates) < 2:
            raise ReturnDataError("at least two aligned price dates are required")
        if any(left >= right for left, right in zip(price_dates, price_dates[1:])):
            raise ReturnDataError("aligned price dates must be unique and increasing")

        series: dict[str, tuple[float, ...]] = {}
        for raw_symbol, values in self.returns.items():
            symbol = str(raw_symbol).strip().upper()
            if symbol in series:
                raise ReturnDataError(
                    f"duplicate return symbol after normalization: {symbol}"
                )
            series[symbol] = tuple(values)
        if not series:
            raise ReturnDataError("at least one return series is required")

        expected_length = len(price_dates) - 1
        for symbol, values in series.items():
            if not symbol:
                raise ReturnDataError("return symbols must be non-empty")
            if len(values) != expected_length:
                raise ReturnDataError(
                    f"{symbol} has {len(values)} returns; expected {expected_length}"
                )
            if any(not isfinite(value) for value in values):
                raise ReturnDataError(f"{symbol} returns must be finite")

        object.__setattr__(self, "price_dates", price_dates)
        object.__setattr__(self, "returns", MappingProxyType(series))
        object.__setattr__(self, "excluded_price_dates", tuple(self.excluded_price_dates))

    @property
    def dates(self) -> tuple[date, ...]:
        return self.price_dates[1:]

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(self.returns)

    @property
    def observation_count(self) -> int:
        return len(self.dates)

    def returns_for(self, symbol: str) -> tuple[float, ...]:
        normalized = symbol.strip().upper()
        try:
            return self.returns[normalized]
        except KeyError as exc:
            raise KeyError(normalized) from exc


@dataclass(frozen=True, slots=True)
class AvailableWeightPortfolioReturns:
    """Portfolio returns with snapshot weights renormalized over available names."""

    price_dates: tuple[date, ...]
    returns: tuple[float, ...]
    covered_weights: tuple[float, ...]
    available_symbol_counts: tuple[int, ...]

    def __post_init__(self) -> None:
        price_dates = tuple(self.price_dates)
        returns = tuple(self.returns)
        covered_weights = tuple(self.covered_weights)
        counts = tuple(self.available_symbol_counts)
        expected = len(price_dates) - 1
        if len(price_dates) < 2 or any(
            left >= right for left, right in zip(price_dates, price_dates[1:])
        ):
            raise ReturnDataError(
                "portfolio price dates must contain at least two unique increasing dates"
            )
        if not (len(returns) == len(covered_weights) == len(counts) == expected):
            raise ReturnDataError("portfolio return coverage lengths are inconsistent")
        if any(not isfinite(value) or value <= -1.0 for value in returns):
            raise ReturnDataError("portfolio returns must be finite and greater than -1")
        if any(not isfinite(value) or not 0.0 < value <= 1.0 for value in covered_weights):
            raise ReturnDataError("covered portfolio weights must be in (0, 1]")
        if any(isinstance(value, bool) or value <= 0 for value in counts):
            raise ReturnDataError("available symbol counts must be positive integers")
        object.__setattr__(self, "price_dates", price_dates)
        object.__setattr__(self, "returns", returns)
        object.__setattr__(self, "covered_weights", covered_weights)
        object.__setattr__(self, "available_symbol_counts", counts)

    @property
    def dates(self) -> tuple[date, ...]:
        return self.price_dates[1:]

    @property
    def observation_count(self) -> int:
        return len(self.returns)

    @property
    def minimum_covered_weight(self) -> float:
        return min(self.covered_weights)

    @property
    def incomplete_observation_count(self) -> int:
        return sum(weight < 1.0 - 1e-12 for weight in self.covered_weights)


@dataclass(frozen=True, slots=True)
class HistoricalRiskMetrics:
    confidence_level: float
    observation_count: int
    value_at_risk: float
    expected_shortfall: float
    maximum_drawdown: float


@dataclass(frozen=True, slots=True)
class HoldingWeight:
    rank: int
    symbol: str
    weight: Decimal


@dataclass(frozen=True, slots=True)
class SectorWeight:
    rank: int
    sector: str
    weight: Decimal
    holding_count: int


@dataclass(frozen=True, slots=True)
class ConcentrationMetrics:
    holding_count: int
    sector_count: int
    ranked_holdings: tuple[HoldingWeight, ...]
    ranked_sectors: tuple[SectorWeight, ...]
    top_n: int
    top_n_weight: Decimal
    single_name_limit: Decimal
    single_name_breaches: tuple[HoldingWeight, ...]
    holding_hhi: Decimal
    effective_holding_count: Decimal
    sector_hhi: Decimal
    effective_sector_count: Decimal
    top_n_minimum: Decimal | None = None
    top_n_maximum: Decimal | None = None

    @property
    def largest_holding(self) -> HoldingWeight:
        return self.ranked_holdings[0]

    @property
    def largest_sector(self) -> SectorWeight:
        return self.ranked_sectors[0]

    @property
    def single_name_limit_passed(self) -> bool:
        return not self.single_name_breaches

    @property
    def top_n_range_passed(self) -> bool | None:
        if self.top_n_minimum is None and self.top_n_maximum is None:
            return None
        if self.top_n_minimum is not None and self.top_n_weight < self.top_n_minimum:
            return False
        if self.top_n_maximum is not None and self.top_n_weight > self.top_n_maximum:
            return False
        return True


__all__ = [
    "AlignedReturnDataset",
    "AvailableWeightPortfolioReturns",
    "ConcentrationMetrics",
    "HistoricalRiskMetrics",
    "HoldingWeight",
    "MissingPriceDate",
    "SectorWeight",
]
