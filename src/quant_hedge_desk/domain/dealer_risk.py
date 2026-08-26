"""Public façade for dealer risk-mandate assessment."""

from quant_hedge_desk.domain.calculations.dealer_risk_limits import (
    assess_dealer_risk,
    build_risk_limit_diagnostic,
)
from quant_hedge_desk.domain.enums import RiskLimitStatus
from quant_hedge_desk.domain.errors import DealerRiskValidationError
from quant_hedge_desk.domain.models.dealer_risk_models import (
    DealerRiskAssessment,
    ProposedTradeRisk,
    RiskLimitDiagnostic,
)


__all__ = [
    "DealerRiskAssessment",
    "DealerRiskValidationError",
    "ProposedTradeRisk",
    "RiskLimitDiagnostic",
    "RiskLimitStatus",
    "assess_dealer_risk",
    "build_risk_limit_diagnostic",
]
