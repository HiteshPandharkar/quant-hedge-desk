"""Immutable configuration and result contracts for rebalancing stresses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping

from quant_hedge_desk.domain.enums import RebalancingPricingMode, RebalanceTriggerType
from quant_hedge_desk.domain.errors import RebalancingValidationError
from quant_hedge_desk.serialization import json_ready


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RebalancingValidationError(f"{path} must be non-empty text")
    return value.strip()


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool):
        raise RebalancingValidationError(f"{path} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RebalancingValidationError(f"{path} must be numeric") from exc
    if not result.is_finite():
        raise RebalancingValidationError(f"{path} must be finite")
    return result


def _integer_mapping(value: object, path: str) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise RebalancingValidationError(f"{path} must be a mapping")
    result: dict[str, int] = {}
    for raw_key, quantity in value.items():
        key = _text(raw_key, f"{path} key")
        if key in result:
            raise RebalancingValidationError(f"{path} contains duplicate key: {key}")
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise RebalancingValidationError(f"{path}.{key} must be an integer")
        result[key] = quantity
    return MappingProxyType(dict(sorted(result.items())))


@dataclass(frozen=True, slots=True)
class RebalancingStressPolicy:
    """Versioned controls used by the sequential rebalancing stress engine."""

    policy_id: str
    version: str
    exceptional_coverage_drift_threshold: Decimal
    routine_interval_trading_days: int
    pricing_mode: RebalancingPricingMode
    base_volatilities: Mapping[str, Decimal] = field(default_factory=dict)
    rebalancing_failure_is_release_gate: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        object.__setattr__(self, "version", _text(self.version, "version"))
        threshold = _decimal(
            self.exceptional_coverage_drift_threshold,
            "exceptional_coverage_drift_threshold",
        )
        if threshold < 0 or threshold > 1:
            raise RebalancingValidationError(
                "exceptional_coverage_drift_threshold must be in [0, 1]"
            )
        object.__setattr__(self, "exceptional_coverage_drift_threshold", threshold)
        if (
            isinstance(self.routine_interval_trading_days, bool)
            or not isinstance(self.routine_interval_trading_days, int)
            or self.routine_interval_trading_days <= 0
        ):
            raise RebalancingValidationError(
                "routine_interval_trading_days must be a positive integer"
            )
        try:
            pricing_mode = RebalancingPricingMode(self.pricing_mode)
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(item.value for item in RebalancingPricingMode)
            raise RebalancingValidationError(
                f"pricing_mode must be one of: {allowed}"
            ) from exc
        object.__setattr__(self, "pricing_mode", pricing_mode)
        if not isinstance(self.base_volatilities, Mapping):
            raise RebalancingValidationError("base_volatilities must be a mapping")
        volatilities: dict[str, Decimal] = {}
        for raw_contract_id, raw_volatility in self.base_volatilities.items():
            contract_id = _text(raw_contract_id, "base_volatilities key")
            if contract_id in volatilities:
                raise RebalancingValidationError(
                    f"base_volatilities contains duplicate key: {contract_id}"
                )
            volatility = _decimal(
                raw_volatility, f"base_volatilities.{contract_id}"
            )
            if volatility <= 0 or volatility > 1:
                raise RebalancingValidationError(
                    f"base_volatilities.{contract_id} must be in (0, 1]"
                )
            volatilities[contract_id] = volatility
        if pricing_mode is RebalancingPricingMode.BLACK_76 and not volatilities:
            raise RebalancingValidationError(
                "base_volatilities must be non-empty for BLACK_76 pricing"
            )
        object.__setattr__(
            self,
            "base_volatilities",
            MappingProxyType(dict(sorted(volatilities.items()))),
        )
        if not isinstance(self.rebalancing_failure_is_release_gate, bool):
            raise RebalancingValidationError(
                "rebalancing_failure_is_release_gate must be boolean"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RebalancingStressPolicy:
        if not isinstance(value, Mapping):
            raise RebalancingValidationError(
                "rebalancing_stress_policy must be a mapping"
            )
        required = {
            "policy_id",
            "version",
            "exceptional_coverage_drift_threshold",
            "routine_interval_trading_days",
            "pricing_mode",
            "base_volatilities",
            "rebalancing_failure_is_release_gate",
        }
        missing = required - value.keys()
        extra = value.keys() - required
        if missing:
            raise RebalancingValidationError(
                "rebalancing_stress_policy is missing: " + ", ".join(sorted(missing))
            )
        if extra:
            raise RebalancingValidationError(
                "rebalancing_stress_policy has unknown fields: "
                + ", ".join(sorted(extra))
            )
        return cls(**{name: value[name] for name in required})

    def to_dict(self) -> dict[str, Any]:
        return json_ready(
            {
                "policy_id": self.policy_id,
                "version": self.version,
                "exceptional_coverage_drift_threshold": (
                    self.exceptional_coverage_drift_threshold
                ),
                "routine_interval_trading_days": self.routine_interval_trading_days,
                "pricing_mode": self.pricing_mode,
                "base_volatilities": self.base_volatilities,
                "rebalancing_failure_is_release_gate": self.rebalancing_failure_is_release_gate,
            }
        )


@dataclass(frozen=True, slots=True)
class PositionState:
    candidate_id: str
    quantities: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_id", _text(self.candidate_id, "candidate_id")
        )
        quantities = _integer_mapping(self.quantities, "quantities")
        if not quantities:
            raise RebalancingValidationError("quantities must be non-empty")
        if any(quantity < 0 for quantity in quantities.values()):
            raise RebalancingValidationError("quantities must be non-negative")
        object.__setattr__(self, "quantities", quantities)

    def to_dict(self) -> dict[str, Any]:
        return json_ready(
            {"candidate_id": self.candidate_id, "quantities": self.quantities}
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> PositionState:
        if not isinstance(value, Mapping) or set(value) != {
            "candidate_id",
            "quantities",
        }:
            raise RebalancingValidationError(
                "position_state must contain exactly candidate_id and quantities"
            )
        return cls(candidate_id=value["candidate_id"], quantities=value["quantities"])


@dataclass(frozen=True, slots=True)
class CashLedger:
    premium_paid: Decimal = Decimal("0")
    premium_received: Decimal = Decimal("0")
    execution_cost: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name in ("premium_paid", "premium_received", "execution_cost"):
            amount = _decimal(getattr(self, name), name)
            if amount < 0:
                raise RebalancingValidationError(f"{name} must be non-negative")
            object.__setattr__(self, name, amount)

    @property
    def premium_cash_flow(self) -> Decimal:
        return self.premium_received - self.premium_paid

    @property
    def net_cash_flow(self) -> Decimal:
        return self.premium_cash_flow - self.execution_cost

    def to_dict(self) -> dict[str, Any]:
        return json_ready(
            {
                "premium_paid": self.premium_paid,
                "premium_received": self.premium_received,
                "execution_cost": self.execution_cost,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CashLedger:
        required = {"premium_paid", "premium_received", "execution_cost"}
        if not isinstance(value, Mapping) or set(value) != required:
            raise RebalancingValidationError(
                "cash_ledger must contain exactly premium_paid, premium_received, and execution_cost"
            )
        return cls(**{name: value[name] for name in required})


@dataclass(frozen=True, slots=True)
class RebalanceEvent:
    scenario_id: str
    step_number: int
    trigger_type: RebalanceTriggerType
    current_quantities: Mapping[str, int]
    target_quantities: Mapping[str, int]
    requested_changes: Mapping[str, int]
    filled_changes: Mapping[str, int]
    delay_trading_days: int
    turnover: Decimal
    premium_cash_flow: Decimal
    execution_cost: Decimal
    constraint_result: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _text(self.scenario_id, "scenario_id"))
        if (
            isinstance(self.step_number, bool)
            or not isinstance(self.step_number, int)
            or self.step_number <= 0
        ):
            raise RebalancingValidationError("step_number must be a positive integer")
        try:
            trigger = RebalanceTriggerType(self.trigger_type)
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(item.value for item in RebalanceTriggerType)
            raise RebalancingValidationError(
                f"trigger_type must be one of: {allowed}"
            ) from exc
        object.__setattr__(self, "trigger_type", trigger)
        mappings = {}
        for name in (
            "current_quantities",
            "target_quantities",
            "requested_changes",
            "filled_changes",
        ):
            mappings[name] = _integer_mapping(getattr(self, name), name)
        keys = set(mappings["current_quantities"])
        if not keys or any(set(value) != keys for value in mappings.values()):
            raise RebalancingValidationError(
                "rebalance quantity mappings must contain the same non-empty contract ids"
            )
        if any(value < 0 for value in mappings["current_quantities"].values()) or any(
            value < 0 for value in mappings["target_quantities"].values()
        ):
            raise RebalancingValidationError(
                "current_quantities and target_quantities must be non-negative"
            )
        for name, value in mappings.items():
            object.__setattr__(self, name, value)
        if (
            isinstance(self.delay_trading_days, bool)
            or not isinstance(self.delay_trading_days, int)
            or self.delay_trading_days < 0
        ):
            raise RebalancingValidationError(
                "delay_trading_days must be a non-negative integer"
            )
        for name in ("turnover", "execution_cost"):
            number = _decimal(getattr(self, name), name)
            if number < 0:
                raise RebalancingValidationError(f"{name} must be non-negative")
            object.__setattr__(self, name, number)
        object.__setattr__(
            self,
            "premium_cash_flow",
            _decimal(self.premium_cash_flow, "premium_cash_flow"),
        )
        for name in ("constraint_result", "failure_reason"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(value, name))

    def to_dict(self) -> dict[str, Any]:
        return json_ready(
            {
                "scenario_id": self.scenario_id,
                "step_number": self.step_number,
                "trigger_type": self.trigger_type,
                "current_quantities": self.current_quantities,
                "target_quantities": self.target_quantities,
                "requested_changes": self.requested_changes,
                "filled_changes": self.filled_changes,
                "delay_trading_days": self.delay_trading_days,
                "turnover": self.turnover,
                "premium_cash_flow": self.premium_cash_flow,
                "execution_cost": self.execution_cost,
                "constraint_result": self.constraint_result,
                "failure_reason": self.failure_reason,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RebalanceEvent:
        required = {
            "scenario_id",
            "step_number",
            "trigger_type",
            "current_quantities",
            "target_quantities",
            "requested_changes",
            "filled_changes",
            "delay_trading_days",
            "turnover",
            "premium_cash_flow",
            "execution_cost",
            "constraint_result",
            "failure_reason",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise RebalancingValidationError(
                "rebalance_event fields are incomplete or unknown"
            )
        return cls(**{name: value[name] for name in required})


@dataclass(frozen=True, slots=True)
class RebalanceProposal:
    """A deterministic resize request; execution is deliberately out of scope."""

    candidate_id: str
    step_number: int
    trigger_type: RebalanceTriggerType
    current_quantities: Mapping[str, int]
    target_quantities: Mapping[str, int]
    requested_changes: Mapping[str, int]
    option_prices: Mapping[str, Decimal] = field(default_factory=dict)
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _text(self.candidate_id, "candidate_id"))
        if (
            isinstance(self.step_number, bool)
            or not isinstance(self.step_number, int)
            or self.step_number <= 0
        ):
            raise RebalancingValidationError("step_number must be a positive integer")
        try:
            trigger = RebalanceTriggerType(self.trigger_type)
        except (TypeError, ValueError) as exc:
            raise RebalancingValidationError("trigger_type is unsupported") from exc
        object.__setattr__(self, "trigger_type", trigger)
        quantity_mappings = {
            name: _integer_mapping(getattr(self, name), name)
            for name in ("current_quantities", "target_quantities", "requested_changes")
        }
        contract_ids = set(quantity_mappings["current_quantities"])
        if not contract_ids or any(
            set(value) != contract_ids for value in quantity_mappings.values()
        ):
            raise RebalancingValidationError(
                "proposal quantity mappings must contain the same non-empty contract ids"
            )
        if any(value < 0 for value in quantity_mappings["current_quantities"].values()):
            raise RebalancingValidationError("current_quantities must be non-negative")
        if any(value < 0 for value in quantity_mappings["target_quantities"].values()):
            raise RebalancingValidationError("target_quantities must be non-negative")
        if any(
            quantity_mappings["target_quantities"][key]
            - quantity_mappings["current_quantities"][key]
            != quantity_mappings["requested_changes"][key]
            for key in contract_ids
        ):
            raise RebalancingValidationError(
                "requested_changes must equal target minus current quantities"
            )
        for name, value in quantity_mappings.items():
            object.__setattr__(self, name, value)
        if not isinstance(self.option_prices, Mapping):
            raise RebalancingValidationError("option_prices must be a mapping")
        prices: dict[str, Decimal] = {}
        for raw_contract_id, raw_price in self.option_prices.items():
            contract_id = _text(raw_contract_id, "option_prices key")
            price = _decimal(raw_price, f"option_prices.{contract_id}")
            if price < 0:
                raise RebalancingValidationError(
                    f"option_prices.{contract_id} must be non-negative"
                )
            prices[contract_id] = price
        object.__setattr__(self, "option_prices", MappingProxyType(dict(sorted(prices.items()))))
        if self.rejection_reason is not None:
            object.__setattr__(
                self, "rejection_reason", _text(self.rejection_reason, "rejection_reason")
            )

    @property
    def is_rejected(self) -> bool:
        return self.rejection_reason is not None

    def to_dict(self) -> dict[str, Any]:
        return json_ready(
            {
                "candidate_id": self.candidate_id,
                "step_number": self.step_number,
                "trigger_type": self.trigger_type,
                "current_quantities": self.current_quantities,
                "target_quantities": self.target_quantities,
                "requested_changes": self.requested_changes,
                "option_prices": self.option_prices,
                "rejection_reason": self.rejection_reason,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RebalanceProposal:
        required = {
            "candidate_id",
            "step_number",
            "trigger_type",
            "current_quantities",
            "target_quantities",
            "requested_changes",
            "option_prices",
            "rejection_reason",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise RebalancingValidationError(
                "rebalance_proposal fields are incomplete or unknown"
            )
        return cls(**{name: value[name] for name in required})


@dataclass(frozen=True, slots=True)
class CandidateStressBatchResult:
    scenario_set_id: str
    scenario_set_version: str
    policy_id: str
    policy_version: str
    evaluations: tuple[Any, ...]
    releasable_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "scenario_set_id",
            "scenario_set_version",
            "policy_id",
            "policy_version",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "evaluations", tuple(self.evaluations))
        for name in ("releasable_candidate_ids", "rejected_candidate_ids"):
            values = tuple(_text(item, f"{name} item") for item in getattr(self, name))
            if len(values) != len(set(values)):
                raise RebalancingValidationError(f"{name} must be unique")
            object.__setattr__(self, name, values)
        overlap = set(self.releasable_candidate_ids) & set(self.rejected_candidate_ids)
        if overlap:
            raise RebalancingValidationError(
                "candidate ids cannot be both releasable and rejected: "
                + ", ".join(sorted(overlap))
            )

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))


BatchStressResult = CandidateStressBatchResult
PricingMode = RebalancingPricingMode


__all__ = [
    "BatchStressResult",
    "CandidateStressBatchResult",
    "CashLedger",
    "PositionState",
    "PricingMode",
    "RebalanceEvent",
    "RebalanceProposal",
    "RebalancingPricingMode",
    "RebalancingStressPolicy",
]
