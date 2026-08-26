"""Immutable scenario records and their structural invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from quant_hedge_desk.domain.calculations.scenario_math import (
    compound_simple_returns,
    scenario_probability_weights,
)
from quant_hedge_desk.domain.constants import (
    MINIMUM_SIMPLE_RETURN,
    TOTAL_SCENARIO_PROBABILITY,
)
from quant_hedge_desk.domain.enums import ScenarioMethodology
from quant_hedge_desk.domain.errors import ScenarioValidationError
from quant_hedge_desk.domain.scenario_validation import (
    check_keys,
    decimal_number,
    numeric_mapping,
    required_text,
    scalar_parameters,
    scenario_date,
    scenario_methodology,
)


ScenarioParameter = str | int | float | Decimal | bool


@dataclass(frozen=True, slots=True)
class ScenarioStep:
    """One ordered market move within a scenario path."""

    step_number: int
    asset_returns: Mapping[str, Decimal]
    implied_volatility_shifts: Mapping[str, Decimal] = field(default_factory=dict)
    bid_ask_spread_multipliers: Mapping[str, Decimal] = field(default_factory=dict)
    rebalancing_allowed: bool = True
    observation_date: date | None = None
    market_volume_multipliers: Mapping[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            isinstance(self.step_number, bool)
            or not isinstance(self.step_number, int)
            or self.step_number <= 0
        ):
            raise ScenarioValidationError("step_number must be a positive integer")
        returns = numeric_mapping(
            self.asset_returns, "asset_returns", minimum=MINIMUM_SIMPLE_RETURN
        )
        if not returns:
            raise ScenarioValidationError("asset_returns must be non-empty")
        object.__setattr__(self, "asset_returns", returns)
        object.__setattr__(
            self,
            "implied_volatility_shifts",
            numeric_mapping(
                self.implied_volatility_shifts, "implied_volatility_shifts"
            ),
        )
        object.__setattr__(
            self,
            "bid_ask_spread_multipliers",
            numeric_mapping(
                self.bid_ask_spread_multipliers,
                "bid_ask_spread_multipliers",
                strictly_positive=True,
            ),
        )
        object.__setattr__(
            self,
            "market_volume_multipliers",
            numeric_mapping(
                self.market_volume_multipliers,
                "market_volume_multipliers",
                strictly_positive=True,
            ),
        )
        if not isinstance(self.rebalancing_allowed, bool):
            raise ScenarioValidationError("rebalancing_allowed must be boolean")
        if self.observation_date is not None:
            object.__setattr__(
                self,
                "observation_date",
                scenario_date(self.observation_date, "observation_date"),
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ScenarioStep:
        if not isinstance(value, Mapping):
            raise ScenarioValidationError("scenario_step must be a mapping")
        check_keys(
            value,
            {"step_number", "asset_returns"},
            {
                "implied_volatility_shifts",
                "bid_ask_spread_multipliers",
                "market_volume_multipliers",
                "rebalancing_allowed",
                "observation_date",
            },
            "scenario_step",
        )
        return cls(
            step_number=value["step_number"],
            asset_returns=value["asset_returns"],
            implied_volatility_shifts=value.get("implied_volatility_shifts", {}),
            bid_ask_spread_multipliers=value.get(
                "bid_ask_spread_multipliers", {}
            ),
            market_volume_multipliers=value.get("market_volume_multipliers", {}),
            rebalancing_allowed=value.get("rebalancing_allowed", True),
            observation_date=value.get("observation_date"),
        )


@dataclass(frozen=True, slots=True)
class ScenarioPath:
    """A uniquely named, ordered path of market-state changes."""

    scenario_id: str
    name: str
    steps: tuple[ScenarioStep, ...]
    probability: Decimal | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "scenario_id", required_text(self.scenario_id, "scenario_id")
        )
        object.__setattr__(self, "name", required_text(self.name, "name"))
        steps = tuple(self.steps)
        if not steps:
            raise ScenarioValidationError("steps must be non-empty")
        if any(not isinstance(step, ScenarioStep) for step in steps):
            raise ScenarioValidationError("steps must contain only ScenarioStep objects")
        expected_numbers = tuple(range(1, len(steps) + 1))
        if tuple(step.step_number for step in steps) != expected_numbers:
            raise ScenarioValidationError("step_numbers must be consecutive and start at 1")
        symbols = tuple(steps[0].asset_returns)
        if any(tuple(step.asset_returns) != symbols for step in steps[1:]):
            raise ScenarioValidationError(
                "every step in a scenario must contain the same asset return symbols"
            )
        dates = [step.observation_date for step in steps]
        supplied_dates = [item for item in dates if item is not None]
        if supplied_dates and len(supplied_dates) != len(dates):
            raise ScenarioValidationError(
                "observation_date must be supplied for every step or no steps"
            )
        if any(left >= right for left, right in zip(supplied_dates, supplied_dates[1:])):
            raise ScenarioValidationError("observation_dates must be increasing")
        object.__setattr__(self, "steps", steps)
        if self.probability is not None:
            probability = decimal_number(self.probability, "probability")
            if probability <= 0 or probability > TOTAL_SCENARIO_PROBABILITY:
                raise ScenarioValidationError("probability must be in (0, 1]")
            object.__setattr__(self, "probability", probability)
        if self.description is not None:
            object.__setattr__(
                self, "description", required_text(self.description, "description")
            )

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(self.steps[0].asset_returns)

    def terminal_return(self, symbol: str) -> Decimal:
        """Return the compounded result for one asset across the path."""

        normalized = required_text(symbol, "symbol").upper()
        if normalized not in self.steps[0].asset_returns:
            raise KeyError(normalized)
        return compound_simple_returns(
            step.asset_returns[normalized] for step in self.steps
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ScenarioPath:
        if not isinstance(value, Mapping):
            raise ScenarioValidationError("scenario must be a mapping")
        check_keys(
            value,
            {"scenario_id", "name", "steps"},
            {"probability", "description"},
            "scenario",
        )
        raw_steps = value["steps"]
        if isinstance(raw_steps, (str, bytes)) or not isinstance(
            raw_steps, (list, tuple)
        ):
            raise ScenarioValidationError("scenario.steps must be a sequence")
        return cls(
            scenario_id=value["scenario_id"],
            name=value["name"],
            steps=tuple(
                item if isinstance(item, ScenarioStep) else ScenarioStep.from_mapping(item)
                for item in raw_steps
            ),
            probability=value.get("probability"),
            description=value.get("description"),
        )


@dataclass(frozen=True, slots=True)
class ScenarioSet:
    """Versioned generator output passed to risk and hedge evaluation."""

    scenario_set_id: str
    version: str
    methodology: ScenarioMethodology
    as_of_date: date
    horizon_trading_days: int
    scenarios: tuple[ScenarioPath, ...]
    model_version: str
    parameters: Mapping[str, ScenarioParameter] = field(default_factory=dict)
    source_snapshot_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scenario_set_id",
            required_text(self.scenario_set_id, "scenario_set_id"),
        )
        object.__setattr__(self, "version", required_text(self.version, "version"))
        object.__setattr__(
            self,
            "methodology",
            scenario_methodology(self.methodology, "methodology"),
        )
        object.__setattr__(
            self, "as_of_date", scenario_date(self.as_of_date, "as_of_date")
        )
        if (
            isinstance(self.horizon_trading_days, bool)
            or not isinstance(self.horizon_trading_days, int)
            or self.horizon_trading_days <= 0
        ):
            raise ScenarioValidationError(
                "horizon_trading_days must be a positive integer"
            )
        scenarios = tuple(self.scenarios)
        if not scenarios:
            raise ScenarioValidationError("scenarios must be non-empty")
        if any(not isinstance(item, ScenarioPath) for item in scenarios):
            raise ScenarioValidationError(
                "scenarios must contain only ScenarioPath objects"
            )
        ids = [item.scenario_id for item in scenarios]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ScenarioValidationError(
                f"duplicate scenario_ids: {', '.join(duplicates)}"
            )
        symbols = scenarios[0].symbols
        if any(item.symbols != symbols for item in scenarios[1:]):
            raise ScenarioValidationError(
                "every scenario in a set must contain the same asset return symbols"
            )
        probabilities = [item.probability for item in scenarios]
        supplied = [item for item in probabilities if item is not None]
        if supplied and len(supplied) != len(probabilities):
            raise ScenarioValidationError(
                "probability must be supplied for every scenario or no scenarios"
            )
        if supplied and sum(supplied, Decimal("0")) != TOTAL_SCENARIO_PROBABILITY:
            raise ScenarioValidationError("scenario probabilities must sum to 1")
        object.__setattr__(self, "scenarios", scenarios)
        object.__setattr__(
            self, "model_version", required_text(self.model_version, "model_version")
        )
        object.__setattr__(
            self, "parameters", scalar_parameters(self.parameters, "parameters")
        )
        sources = tuple(
            required_text(item, "source_snapshot_ids item")
            for item in self.source_snapshot_ids
        )
        if len(set(sources)) != len(sources):
            raise ScenarioValidationError("source_snapshot_ids must be unique")
        object.__setattr__(self, "source_snapshot_ids", sources)

    @property
    def symbols(self) -> tuple[str, ...]:
        return self.scenarios[0].symbols

    @property
    def scenario_count(self) -> int:
        return len(self.scenarios)

    @property
    def probability_weights(self) -> tuple[Decimal, ...]:
        return scenario_probability_weights(
            item.probability for item in self.scenarios
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ScenarioSet:
        if not isinstance(value, Mapping):
            raise ScenarioValidationError("scenario_set must be a mapping")
        check_keys(
            value,
            {
                "scenario_set_id",
                "version",
                "methodology",
                "as_of_date",
                "horizon_trading_days",
                "scenarios",
                "model_version",
            },
            {"parameters", "source_snapshot_ids"},
            "scenario_set",
        )
        raw_scenarios = value["scenarios"]
        if isinstance(raw_scenarios, (str, bytes)) or not isinstance(
            raw_scenarios, (list, tuple)
        ):
            raise ScenarioValidationError("scenario_set.scenarios must be a sequence")
        raw_sources = value.get("source_snapshot_ids", ())
        if isinstance(raw_sources, (str, bytes)) or not isinstance(
            raw_sources, (list, tuple)
        ):
            raise ScenarioValidationError(
                "scenario_set.source_snapshot_ids must be a sequence"
            )
        return cls(
            scenario_set_id=value["scenario_set_id"],
            version=value["version"],
            methodology=value["methodology"],
            as_of_date=value["as_of_date"],
            horizon_trading_days=value["horizon_trading_days"],
            scenarios=tuple(
                item if isinstance(item, ScenarioPath) else ScenarioPath.from_mapping(item)
                for item in raw_scenarios
            ),
            model_version=value["model_version"],
            parameters=value.get("parameters", {}),
            source_snapshot_ids=tuple(raw_sources),
        )


Scenario = ScenarioPath


__all__ = [
    "Scenario",
    "ScenarioParameter",
    "ScenarioPath",
    "ScenarioSet",
    "ScenarioStep",
]
