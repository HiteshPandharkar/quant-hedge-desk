"""Programmatic facade for hedge-mandate assessment.

This module performs no command-line parsing or output. Call
:func:`assess_mandate` from Python and consume the returned immutable
:class:`MandateAssessment`.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from quant_hedge_desk.application.assessment_service import MandateAssessmentService
from quant_hedge_desk.application.enums import StageStatus
from quant_hedge_desk.application.errors import AssessmentInputError
from quant_hedge_desk.application.models import (
    HorizonRiskMetrics,
    IndexExposureMetrics,
    InputValidationSummary,
    MandateAssessment,
    MandateRiskComparison,
    MarketDataSummary,
    PendingStage,
    PortfolioSummary,
)


def assess_mandate(
    *,
    portfolio_path: str | Path,
    mandate_path: str | Path,
    desk_limits_path: str | Path,
    market_data_path: str | Path,
    supplied_total_market_value: Decimal | int | str | None = None,
) -> MandateAssessment:
    """Run an assessment through the default application service."""

    return MandateAssessmentService().assess(
        portfolio_path=portfolio_path,
        mandate_path=mandate_path,
        desk_limits_path=desk_limits_path,
        market_data_path=market_data_path,
        supplied_total_market_value=supplied_total_market_value,
    )


__all__ = [
    "AssessmentInputError",
    "HorizonRiskMetrics",
    "IndexExposureMetrics",
    "InputValidationSummary",
    "MandateAssessment",
    "MandateAssessmentService",
    "MandateRiskComparison",
    "MarketDataSummary",
    "PendingStage",
    "PortfolioSummary",
    "StageStatus",
    "assess_mandate",
]
