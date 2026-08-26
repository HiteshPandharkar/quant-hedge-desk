"""Mandate dataclasses for the hedge-design workflow.

Rates and currency amounts use :class:`~decimal.Decimal`: mandate thresholds are
policy inputs and must not acquire binary floating-point rounding noise.  The
models are deliberately independent of a serialization library; JSON objects
(and YAML mappings loaded by an adapter) can be passed to ``from_mapping``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from quant_hedge_desk.domain.enums import (
    InstrumentType,
    OptionStyle,
    RebalanceFrequency,
    SoftObjective,
    Underlying,
)
from quant_hedge_desk.domain.models._validation import ModelValidator


class MandateValidationError(ValueError):
    """Raised when a mandate is internally inconsistent or out of range."""


_validate = ModelValidator(MandateValidationError, percentages_allowed=True)


def _enum(value: Any, enum_type: type[Any], path: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise MandateValidationError(f"{path} must be one of: {allowed}") from exc


@dataclass(frozen=True, slots=True)
class RequirementInterpretation:
    """Original client wording and the desk's machine-evaluable interpretation."""

    original: str
    interpretation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "original", _validate.required_text(self.original, "original"))
        object.__setattr__(
            self, "interpretation", _validate.required_text(self.interpretation, "interpretation")
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RequirementInterpretation:
        value = _validate.mapping(value, "requirement interpretation")
        _validate.keys(value, {"original", "interpretation"}, "requirement interpretation")
        return cls(original=value["original"], interpretation=value["interpretation"])


@dataclass(frozen=True, slots=True)
class ProtectionConstraint:
    horizon_months: int
    expected_shortfall_confidence: Decimal
    max_expected_shortfall_loss: Decimal
    tail_loss_threshold: Decimal
    tail_breach_reduction_must_be_reported: bool
    assessment_basis: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon_months", _validate.positive_int(self.horizon_months, "protection.horizon_months"))
        object.__setattr__(self, "expected_shortfall_confidence", _validate.fraction(self.expected_shortfall_confidence, "protection.expected_shortfall_confidence", include_zero=False))
        object.__setattr__(self, "max_expected_shortfall_loss", _validate.fraction(self.max_expected_shortfall_loss, "protection.max_expected_shortfall_loss", include_zero=False))
        object.__setattr__(self, "tail_loss_threshold", _validate.fraction(self.tail_loss_threshold, "protection.tail_loss_threshold", include_zero=False))
        if not isinstance(self.tail_breach_reduction_must_be_reported, bool):
            raise MandateValidationError("protection.tail_breach_reduction_must_be_reported must be boolean")
        object.__setattr__(self, "assessment_basis", _validate.required_text(self.assessment_basis, "protection.assessment_basis"))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ProtectionConstraint:
        value = _validate.mapping(value, "protection")
        required = {"horizon_months", "expected_shortfall_confidence", "max_expected_shortfall_loss", "tail_loss_threshold", "tail_breach_reduction_must_be_reported", "assessment_basis"}
        _validate.keys(value, required, "protection")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class CostConstraint:
    max_all_in_premium_fraction: Decimal
    includes_execution_cost: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_all_in_premium_fraction", _validate.fraction(self.max_all_in_premium_fraction, "cost.max_all_in_premium_fraction", include_zero=True))
        if not isinstance(self.includes_execution_cost, bool):
            raise MandateValidationError("cost.includes_execution_cost must be boolean")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CostConstraint:
        value = _validate.mapping(value, "cost")
        _validate.keys(value, {"max_all_in_premium_fraction", "includes_execution_cost"}, "cost")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class UpsideConstraint:
    max_sacrifice_percentage_points: Decimal
    scenario_set_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_sacrifice_percentage_points", _validate.fraction(self.max_sacrifice_percentage_points, "upside.max_sacrifice_percentage_points", include_zero=True))
        object.__setattr__(self, "scenario_set_id", _validate.required_text(self.scenario_set_id, "upside.scenario_set_id"))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> UpsideConstraint:
        value = _validate.mapping(value, "upside")
        _validate.keys(value, {"max_sacrifice_percentage_points", "scenario_set_id"}, "upside")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class EligibilityConstraint:
    underlyings: tuple[Underlying, ...]
    instrument_types: tuple[InstrumentType, ...]
    option_style: OptionStyle
    approved_expiry_months: tuple[int, ...]

    def __post_init__(self) -> None:
        underlyings = tuple(_enum(v, Underlying, "eligibility.underlyings") for v in self.underlyings)
        instruments = tuple(_enum(v, InstrumentType, "eligibility.instrument_types") for v in self.instrument_types)
        expiries = tuple(_validate.positive_int(v, "eligibility.approved_expiry_months") for v in self.approved_expiry_months)
        if not underlyings or len(set(underlyings)) != len(underlyings):
            raise MandateValidationError("eligibility.underlyings must be non-empty and unique")
        if not instruments or len(set(instruments)) != len(instruments):
            raise MandateValidationError("eligibility.instrument_types must be non-empty and unique")
        if not expiries or len(set(expiries)) != len(expiries):
            raise MandateValidationError("eligibility.approved_expiry_months must be non-empty and unique")
        object.__setattr__(self, "underlyings", underlyings)
        object.__setattr__(self, "instrument_types", instruments)
        object.__setattr__(self, "option_style", _enum(self.option_style, OptionStyle, "eligibility.option_style"))
        object.__setattr__(self, "approved_expiry_months", expiries)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EligibilityConstraint:
        value = _validate.mapping(value, "eligibility")
        required = {"underlyings", "instrument_types", "option_style", "approved_expiry_months"}
        _validate.keys(value, required, "eligibility")
        return cls(
            underlyings=tuple(_validate.sequence(value["underlyings"], "eligibility.underlyings")),
            instrument_types=tuple(_validate.sequence(value["instrument_types"], "eligibility.instrument_types")),
            option_style=value["option_style"],
            approved_expiry_months=tuple(_validate.sequence(value["approved_expiry_months"], "eligibility.approved_expiry_months")),
        )


@dataclass(frozen=True, slots=True)
class LiquidityConstraint:
    max_unwind_trading_days: int
    max_market_participation: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_unwind_trading_days", _validate.positive_int(self.max_unwind_trading_days, "liquidity.max_unwind_trading_days"))
        object.__setattr__(self, "max_market_participation", _validate.fraction(self.max_market_participation, "liquidity.max_market_participation", include_zero=False))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> LiquidityConstraint:
        value = _validate.mapping(value, "liquidity")
        _validate.keys(value, {"max_unwind_trading_days", "max_market_participation"}, "liquidity")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class RebalancingPolicy:
    style: str
    routine_frequency: RebalanceFrequency
    exceptional_rebalance_enabled: bool
    trigger_set_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "style", _validate.required_text(self.style, "rebalancing.style"))
        object.__setattr__(self, "routine_frequency", _enum(self.routine_frequency, RebalanceFrequency, "rebalancing.routine_frequency"))
        if not isinstance(self.exceptional_rebalance_enabled, bool):
            raise MandateValidationError("rebalancing.exceptional_rebalance_enabled must be boolean")
        object.__setattr__(self, "trigger_set_id", _validate.required_text(self.trigger_set_id, "rebalancing.trigger_set_id"))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RebalancingPolicy:
        value = _validate.mapping(value, "rebalancing")
        required = {"style", "routine_frequency", "exceptional_rebalance_enabled", "trigger_set_id"}
        _validate.keys(value, required, "rebalancing")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ClientMandate:
    client_name: str
    client_type: str
    benchmark: str
    reporting_currency: str
    protection: ProtectionConstraint
    cost: CostConstraint
    upside: UpsideConstraint
    eligibility: EligibilityConstraint
    liquidity: LiquidityConstraint
    rebalancing: RebalancingPolicy
    interpretations: Mapping[str, RequirementInterpretation]
    soft_objectives: tuple[SoftObjective, ...] = field(default_factory=lambda: tuple(SoftObjective))

    def __post_init__(self) -> None:
        for name in ("client_name", "client_type", "benchmark"):
            object.__setattr__(self, name, _validate.required_text(getattr(self, name), f"client.{name}"))
        currency = _validate.required_text(self.reporting_currency, "client.reporting_currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise MandateValidationError("client.reporting_currency must be a three-letter currency code")
        object.__setattr__(self, "reporting_currency", currency)
        nested_types = {
            "protection": ProtectionConstraint,
            "cost": CostConstraint,
            "upside": UpsideConstraint,
            "eligibility": EligibilityConstraint,
            "liquidity": LiquidityConstraint,
            "rebalancing": RebalancingPolicy,
        }
        for name, expected_type in nested_types.items():
            if not isinstance(getattr(self, name), expected_type):
                raise MandateValidationError(f"client.{name} must be a {expected_type.__name__}")
        interpretations = _validate.mapping(self.interpretations, "client.interpretations")
        required_interpretations = {"protection", "upside", "maintenance", "liquidity", "affordability"}
        if set(interpretations) != required_interpretations:
            raise MandateValidationError("client.interpretations must contain exactly: " + ", ".join(sorted(required_interpretations)))
        parsed_interpretations = {
            key: value if isinstance(value, RequirementInterpretation) else RequirementInterpretation.from_mapping(value)
            for key, value in interpretations.items()
        }
        object.__setattr__(self, "interpretations", MappingProxyType(parsed_interpretations))
        objectives = tuple(_enum(v, SoftObjective, "client.soft_objectives") for v in self.soft_objectives)
        if not objectives or len(set(objectives)) != len(objectives):
            raise MandateValidationError("client.soft_objectives must be non-empty and unique")
        object.__setattr__(self, "soft_objectives", objectives)
        if self.protection.horizon_months not in self.eligibility.approved_expiry_months:
            raise MandateValidationError("the hedge horizon must be one of eligibility.approved_expiry_months")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ClientMandate:
        value = _validate.mapping(value, "client")
        required = {"client_name", "client_type", "benchmark", "reporting_currency", "protection", "cost", "upside", "eligibility", "liquidity", "rebalancing", "interpretations", "soft_objectives"}
        _validate.keys(value, required, "client")
        return cls(
            client_name=value["client_name"], client_type=value["client_type"], benchmark=value["benchmark"], reporting_currency=value["reporting_currency"],
            protection=ProtectionConstraint.from_mapping(value["protection"]), cost=CostConstraint.from_mapping(value["cost"]),
            upside=UpsideConstraint.from_mapping(value["upside"]), eligibility=EligibilityConstraint.from_mapping(value["eligibility"]),
            liquidity=LiquidityConstraint.from_mapping(value["liquidity"]), rebalancing=RebalancingPolicy.from_mapping(value["rebalancing"]),
            interpretations=value["interpretations"], soft_objectives=tuple(_validate.sequence(value["soft_objectives"], "client.soft_objectives")),
        )


@dataclass(frozen=True, slots=True)
class Mandate:
    """Versioned client policy used to assess hedge suitability."""

    mandate_id: str
    schema_version: str
    client: ClientMandate

    def __post_init__(self) -> None:
        object.__setattr__(self, "mandate_id", _validate.required_text(self.mandate_id, "mandate_id"))
        object.__setattr__(self, "schema_version", _validate.required_text(self.schema_version, "schema_version"))
        if not isinstance(self.client, ClientMandate):
            raise MandateValidationError("client must be a ClientMandate")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Mandate:
        value = _validate.mapping(value, "mandate")
        _validate.keys(value, {"mandate_id", "schema_version", "client"}, "mandate")
        return cls(
            mandate_id=value["mandate_id"],
            schema_version=value["schema_version"],
            client=ClientMandate.from_mapping(value["client"]),
        )


__all__ = [
    "ClientMandate", "CostConstraint", "EligibilityConstraint",
    "InstrumentType", "LiquidityConstraint", "Mandate", "MandateValidationError",
    "OptionStyle", "ProtectionConstraint", "RebalanceFrequency", "RebalancingPolicy",
    "RequirementInterpretation", "SoftObjective", "Underlying", "UpsideConstraint",
]
