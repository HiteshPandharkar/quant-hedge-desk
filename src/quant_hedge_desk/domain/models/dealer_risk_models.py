"""Dealer risk-mandate assessment contracts.

The models in this module describe a pre-trade comparison.  Risk measures are
kept as approved inputs: valuation and Greek production remain responsibilities
of the pricing and risk adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quant_hedge_desk.domain.enums import RiskLimitStatus
from quant_hedge_desk.domain.errors import DealerRiskValidationError
from quant_hedge_desk.domain.models._validation import ModelValidator
from quant_hedge_desk.domain.models.desk_portfolio import DeskRiskExposure


_validate = ModelValidator(DealerRiskValidationError, percentages_allowed=True)


@dataclass(frozen=True, slots=True)
class ProposedTradeRisk:
    """Approved incremental risk and trade-specific control measures."""

    exposure: DeskRiskExposure
    market_participation: Decimal
    liquidation_trading_days: int
    model_reserve_inr: Decimal
    clean_value_inr: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.exposure, DeskRiskExposure):
            raise DealerRiskValidationError("exposure must be a DeskRiskExposure")
        participation = _validate.fraction(
            self.market_participation,
            "market_participation",
            include_zero=True,
        )
        if (
            isinstance(self.liquidation_trading_days, bool)
            or not isinstance(self.liquidation_trading_days, int)
            or self.liquidation_trading_days <= 0
        ):
            raise DealerRiskValidationError(
                "liquidation_trading_days must be a positive integer"
            )
        reserve = _validate.decimal(self.model_reserve_inr, "model_reserve_inr")
        clean_value = _validate.decimal(self.clean_value_inr, "clean_value_inr")
        if reserve < 0:
            raise DealerRiskValidationError("model_reserve_inr must be non-negative")
        if clean_value <= 0:
            raise DealerRiskValidationError("clean_value_inr must be positive")
        object.__setattr__(self, "market_participation", participation)
        object.__setattr__(self, "model_reserve_inr", reserve)
        object.__setattr__(self, "clean_value_inr", clean_value)


@dataclass(frozen=True, slots=True)
class RiskLimitDiagnostic:
    """Utilization of one hard limit before and after a proposed trade."""

    measure: str
    before: Decimal
    incremental: Decimal
    after: Decimal
    limit: Decimal
    before_utilization: Decimal
    after_utilization: Decimal
    status: RiskLimitStatus


@dataclass(frozen=True, slots=True)
class DealerRiskAssessment:
    """Complete result of applying a versioned dealer mandate."""

    desk_limits_id: str
    desk_portfolio_id: str
    existing_risk: DeskRiskExposure
    incremental_risk: DeskRiskExposure
    post_trade_risk: DeskRiskExposure
    diagnostics: tuple[RiskLimitDiagnostic, ...]

    @property
    def approved(self) -> bool:
        return not any(item.status is RiskLimitStatus.BREACH for item in self.diagnostics)

    @property
    def warnings(self) -> tuple[RiskLimitDiagnostic, ...]:
        return tuple(
            item for item in self.diagnostics if item.status is RiskLimitStatus.WARNING
        )

    @property
    def breaches(self) -> tuple[RiskLimitDiagnostic, ...]:
        return tuple(
            item for item in self.diagnostics if item.status is RiskLimitStatus.BREACH
        )


__all__ = [
    "DealerRiskAssessment",
    "ProposedTradeRisk",
    "RiskLimitDiagnostic",
]
