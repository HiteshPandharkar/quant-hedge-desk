"""Configuration contract for user-supplied hedge candidates.

Despite the historical module name, this module does not optimize or invent a
trade.  It turns an explicit, auditable YAML mapping into immutable derivative
legs that can be assessed by the application service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from quant_hedge_desk.domain.enums import InstrumentType, Underlying
from quant_hedge_desk.domain.errors import HedgeCandidateValidationError
from quant_hedge_desk.domain.instrument_leg_validation import quote_datetime
from quant_hedge_desk.domain.models._validation import ModelValidator
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg


DerivativeLeg = FutureLeg | VanillaOptionLeg
_validate = ModelValidator(HedgeCandidateValidationError, percentages_allowed=True)


class HedgeFamily(StrEnum):
    NIFTY_FUTURES_BETA_HEDGE = "NIFTY_FUTURES_BETA_HEDGE"
    NIFTY_PROTECTIVE_PUT = "NIFTY_PROTECTIVE_PUT"
    NIFTY_VERTICAL_PUT_SPREAD = "NIFTY_VERTICAL_PUT_SPREAD"
    NIFTY_COLLAR = "NIFTY_COLLAR"
    HYBRID_NIFTY_BANKNIFTY_PUT_HEDGE = "HYBRID_NIFTY_BANKNIFTY_PUT_HEDGE"


@dataclass(frozen=True, slots=True)
class UpsideScenario:
    scenario_id: str
    portfolio_return: Decimal
    terminal_levels: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _validate.required_text(self.scenario_id, "scenario_id"))
        portfolio_return = _validate.decimal(
            self.portfolio_return, "portfolio_return", percentage_allowed=True
        )
        if portfolio_return <= 0:
            raise HedgeCandidateValidationError("portfolio_return must be positive for an upside scenario")
        object.__setattr__(self, "portfolio_return", portfolio_return)
        raw_levels = _validate.mapping(self.terminal_levels, "terminal_levels")
        levels: dict[str, Decimal] = {}
        for raw_symbol, raw_level in raw_levels.items():
            try:
                symbol = Underlying(str(raw_symbol).strip().upper()).value
            except ValueError as exc:
                raise HedgeCandidateValidationError(
                    f"terminal_levels contains unsupported underlying {raw_symbol!r}"
                ) from exc
            levels[symbol] = _validate.positive_decimal(
                raw_level, f"terminal_levels.{symbol}"
            )
        object.__setattr__(self, "terminal_levels", MappingProxyType(levels))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "UpsideScenario":
        mapping = _validate.mapping(value, "upside scenario")
        _validate.keys(
            mapping,
            {"scenario_id", "portfolio_return", "terminal_levels"},
            "upside scenario",
        )
        return cls(**mapping)


@dataclass(frozen=True, slots=True)
class HedgeCandidate:
    candidate_id: str
    schema_version: str
    family: HedgeFamily
    description: str
    quote_timestamp: datetime
    estimated_execution_cost: Decimal
    initial_levels: Mapping[str, Decimal]
    legs: tuple[DerivativeLeg, ...]
    upside_scenario_set_id: str
    upside_scenarios: tuple[UpsideScenario, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _validate.required_text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "schema_version", _validate.required_text(self.schema_version, "schema_version"))
        try:
            family = HedgeFamily(self.family)
        except (TypeError, ValueError) as exc:
            raise HedgeCandidateValidationError(
                "family must be one of: " + ", ".join(item.value for item in HedgeFamily)
            ) from exc
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "description", _validate.required_text(self.description, "description"))
        timestamp = quote_datetime(self.quote_timestamp, "quote_timestamp")
        object.__setattr__(self, "quote_timestamp", timestamp)
        execution_cost = _validate.decimal(self.estimated_execution_cost, "estimated_execution_cost")
        if execution_cost < 0:
            raise HedgeCandidateValidationError("estimated_execution_cost must be non-negative")
        object.__setattr__(self, "estimated_execution_cost", execution_cost)

        raw_levels = _validate.mapping(self.initial_levels, "initial_levels")
        levels: dict[str, Decimal] = {}
        for raw_symbol, raw_level in raw_levels.items():
            try:
                symbol = Underlying(str(raw_symbol).strip().upper()).value
            except ValueError as exc:
                raise HedgeCandidateValidationError(
                    f"initial_levels contains unsupported underlying {raw_symbol!r}"
                ) from exc
            levels[symbol] = _validate.positive_decimal(raw_level, f"initial_levels.{symbol}")
        object.__setattr__(self, "initial_levels", MappingProxyType(levels))

        legs = tuple(self.legs)
        if not legs:
            raise HedgeCandidateValidationError("legs must be non-empty")
        if any(not isinstance(leg, (FutureLeg, VanillaOptionLeg)) for leg in legs):
            raise HedgeCandidateValidationError("legs contain an unsupported derivative type")
        if any(leg.quote_timestamp != timestamp for leg in legs):
            raise HedgeCandidateValidationError("every leg must use the candidate quote_timestamp")
        if any(leg.underlying.value not in levels for leg in legs):
            raise HedgeCandidateValidationError("initial_levels must cover every leg underlying")
        structure_error = _family_structure_error(family, legs)
        if structure_error:
            raise HedgeCandidateValidationError(
                f"legs do not match family {family.value}: {structure_error}"
            )
        object.__setattr__(self, "legs", legs)

        object.__setattr__(
            self,
            "upside_scenario_set_id",
            _validate.required_text(self.upside_scenario_set_id, "upside_scenario_set_id"),
        )
        scenarios = tuple(self.upside_scenarios)
        if not scenarios:
            raise HedgeCandidateValidationError("upside_scenarios must be non-empty")
        ids = [item.scenario_id for item in scenarios]
        if len(ids) != len(set(ids)):
            raise HedgeCandidateValidationError("upside scenario ids must be unique")
        required_symbols = {leg.underlying.value for leg in legs}
        if any(not required_symbols.issubset(item.terminal_levels) for item in scenarios):
            raise HedgeCandidateValidationError(
                "every upside scenario must contain terminal levels for all leg underlyings"
            )
        object.__setattr__(self, "upside_scenarios", scenarios)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HedgeCandidate":
        mapping = _validate.mapping(value, "hedge candidate")
        required = {
            "candidate_id", "schema_version", "family", "description",
            "quote_timestamp", "estimated_execution_cost", "initial_levels",
            "legs", "upside_scenario_set_id", "upside_scenarios",
        }
        _validate.keys(mapping, required, "hedge candidate")
        raw_legs = mapping["legs"]
        if isinstance(raw_legs, (str, bytes)) or not isinstance(raw_legs, (list, tuple)):
            raise HedgeCandidateValidationError("legs must be a sequence")
        legs: list[DerivativeLeg] = []
        for number, raw_leg in enumerate(raw_legs, start=1):
            if not isinstance(raw_leg, Mapping):
                raise HedgeCandidateValidationError(f"leg {number} must be a mapping")
            try:
                instrument_type = InstrumentType(raw_leg.get("instrument_type"))
                leg = (
                    FutureLeg.from_mapping(raw_leg)
                    if instrument_type is InstrumentType.FUTURE
                    else VanillaOptionLeg.from_mapping(raw_leg)
                )
            except (TypeError, ValueError) as exc:
                raise HedgeCandidateValidationError(f"invalid leg {number}: {exc}") from exc
            legs.append(leg)
        raw_scenarios = mapping["upside_scenarios"]
        if isinstance(raw_scenarios, (str, bytes)) or not isinstance(raw_scenarios, (list, tuple)):
            raise HedgeCandidateValidationError("upside_scenarios must be a sequence")
        return cls(
            **{key: mapping[key] for key in required - {"legs", "upside_scenarios"}},
            legs=tuple(legs),
            upside_scenarios=tuple(UpsideScenario.from_mapping(item) for item in raw_scenarios),
        )


def _same_contract_terms(left: DerivativeLeg, right: DerivativeLeg) -> bool:
    return (
        left.expiry == right.expiry
        and left.quantity == right.quantity
        and left.contract_multiplier == right.contract_multiplier
    )


def _family_structure_error(
    family: HedgeFamily, legs: tuple[DerivativeLeg, ...]
) -> str | None:
    """Return why explicit legs do not implement their declared family."""

    if family is HedgeFamily.NIFTY_FUTURES_BETA_HEDGE:
        if all(
            isinstance(leg, FutureLeg)
            and leg.underlying is Underlying.NIFTY
            and leg.direction.value == "SHORT"
            for leg in legs
        ):
            return None
        return "requires only short NIFTY futures"

    options = tuple(leg for leg in legs if isinstance(leg, VanillaOptionLeg))
    if len(options) != len(legs):
        return "this family requires option legs only"

    if family is HedgeFamily.NIFTY_PROTECTIVE_PUT:
        if len(options) == 1 and _is_option(options[0], "NIFTY", "LONG", "PUT"):
            return None
        return "requires exactly one long NIFTY put"

    if family is HedgeFamily.NIFTY_VERTICAL_PUT_SPREAD:
        if len(options) != 2:
            return "requires exactly two NIFTY put legs"
        long_puts = [leg for leg in options if _is_option(leg, "NIFTY", "LONG", "PUT")]
        short_puts = [leg for leg in options if _is_option(leg, "NIFTY", "SHORT", "PUT")]
        if (
            len(long_puts) == len(short_puts) == 1
            and long_puts[0].strike_or_level > short_puts[0].strike_or_level
            and _same_contract_terms(long_puts[0], short_puts[0])
        ):
            return None
        return "requires matched long-higher-strike and short-lower-strike NIFTY puts"

    if family is HedgeFamily.NIFTY_COLLAR:
        if len(options) != 2:
            return "requires exactly two NIFTY option legs"
        puts = [leg for leg in options if _is_option(leg, "NIFTY", "LONG", "PUT")]
        calls = [leg for leg in options if _is_option(leg, "NIFTY", "SHORT", "CALL")]
        if len(puts) == len(calls) == 1 and _same_contract_terms(puts[0], calls[0]):
            return None
        return "requires matched long NIFTY put and short NIFTY call legs"

    # The hybrid can contain one protective put or one matched put spread per
    # underlying. Reuse the strict single-underlying shapes above.
    groups = {
        symbol: tuple(leg for leg in options if leg.underlying.value == symbol)
        for symbol in ("NIFTY", "BANKNIFTY")
    }
    if any(not group or len(group) > 2 for group in groups.values()):
        return "requires one put or one put spread on both NIFTY and BANKNIFTY"
    for symbol, group in groups.items():
        long_puts = [leg for leg in group if _is_option(leg, symbol, "LONG", "PUT")]
        short_puts = [leg for leg in group if _is_option(leg, symbol, "SHORT", "PUT")]
        valid_protective = len(group) == 1 and len(long_puts) == 1
        valid_spread = (
            len(group) == 2
            and len(long_puts) == len(short_puts) == 1
            and long_puts[0].strike_or_level > short_puts[0].strike_or_level
            and _same_contract_terms(long_puts[0], short_puts[0])
        )
        if not (valid_protective or valid_spread):
            return f"{symbol} component is not a protective put or matched put spread"
    return None


def _is_option(
    leg: VanillaOptionLeg, underlying: str, direction: str, option_type: str
) -> bool:
    return (
        leg.underlying.value == underlying
        and leg.direction.value == direction
        and leg.option_type.value == option_type
    )


__all__ = ["DerivativeLeg", "HedgeCandidate", "HedgeFamily", "UpsideScenario"]
