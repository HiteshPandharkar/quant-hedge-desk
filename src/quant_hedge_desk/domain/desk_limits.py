"""Compatibility imports for dealer desk-limit domain types."""

from quant_hedge_desk.domain.models.desk_limits import (
    DealerRiskLimits,
    DeskLimitSet,
    DeskLimitsValidationError,
)

__all__ = ["DealerRiskLimits", "DeskLimitSet", "DeskLimitsValidationError"]
