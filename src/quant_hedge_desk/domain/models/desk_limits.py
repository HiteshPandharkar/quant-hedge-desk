"""Dealer desk-limit dataclasses and their invariant checks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from quant_hedge_desk.domain.models._validation import ModelValidator


class DeskLimitsValidationError(ValueError):
    """Raised when a desk-limit configuration is invalid."""


_validate = ModelValidator(DeskLimitsValidationError, percentages_allowed=True)


@dataclass(frozen=True, slots=True)
class DealerRiskLimits:
    max_absolute_net_index_delta_inr: Decimal
    max_one_month_vega_inr_per_vol_point: Decimal
    max_six_month_vega_inr_per_vol_point: Decimal
    max_crash_stress_loss_inr: Decimal
    max_market_participation: Decimal
    max_liquidation_trading_days: int
    max_model_reserve_fraction_of_clean_value: Decimal
    warning_utilization: Decimal

    def __post_init__(self) -> None:
        amount_fields = (
            "max_absolute_net_index_delta_inr",
            "max_one_month_vega_inr_per_vol_point",
            "max_six_month_vega_inr_per_vol_point",
            "max_crash_stress_loss_inr",
        )
        for name in amount_fields:
            amount = _validate.decimal(getattr(self, name), f"limits.{name}")
            if amount <= 0:
                raise DeskLimitsValidationError(f"limits.{name} must be positive")
            object.__setattr__(self, name, amount)
        object.__setattr__(self, "max_market_participation", _validate.fraction(self.max_market_participation, "limits.max_market_participation", include_zero=False))
        object.__setattr__(self, "max_liquidation_trading_days", _validate.positive_int(self.max_liquidation_trading_days, "limits.max_liquidation_trading_days"))
        object.__setattr__(self, "max_model_reserve_fraction_of_clean_value", _validate.fraction(self.max_model_reserve_fraction_of_clean_value, "limits.max_model_reserve_fraction_of_clean_value", include_zero=False))
        object.__setattr__(self, "warning_utilization", _validate.fraction(self.warning_utilization, "limits.warning_utilization", include_zero=False))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DealerRiskLimits:
        value = _validate.mapping(value, "limits")
        required = {
            "max_absolute_net_index_delta_inr",
            "max_one_month_vega_inr_per_vol_point",
            "max_six_month_vega_inr_per_vol_point",
            "max_crash_stress_loss_inr",
            "max_market_participation",
            "max_liquidation_trading_days",
            "max_model_reserve_fraction_of_clean_value",
            "warning_utilization",
        }
        _validate.keys(value, required, "limits")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class DeskLimitSet:
    """Versioned set of fictional dealer limits used for pre-trade approval."""

    desk_limits_id: str
    schema_version: str
    limits: DealerRiskLimits

    def __post_init__(self) -> None:
        object.__setattr__(self, "desk_limits_id", _validate.required_text(self.desk_limits_id, "desk_limits_id"))
        object.__setattr__(self, "schema_version", _validate.required_text(self.schema_version, "schema_version"))
        if not isinstance(self.limits, DealerRiskLimits):
            raise DeskLimitsValidationError("limits must be DealerRiskLimits")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DeskLimitSet:
        value = _validate.mapping(value, "desk limits")
        _validate.keys(value, {"desk_limits_id", "schema_version", "limits"}, "desk limits")
        return cls(
            desk_limits_id=value["desk_limits_id"],
            schema_version=value["schema_version"],
            limits=DealerRiskLimits.from_mapping(value["limits"]),
        )


__all__ = ["DealerRiskLimits", "DeskLimitSet", "DeskLimitsValidationError"]
