"""Stable facade for client hard-constraint assessment.

Enums, result dataclasses, and calculations live in focused modules. Imports
from this historical module remain supported for existing callers.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from quant_hedge_desk.domain.models.mandate import Mandate
from quant_hedge_desk.domain.models.portfolio import Portfolio
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.constraint_calculator import (
    CandidateConstraintCalculator,
)
from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus
from quant_hedge_desk.hedge_design.constraint_models import (
    CandidateFeasibilityAssessment,
    ConstraintDiagnostic,
    ConstraintRelaxation,
    InfeasibilityDiagnosis,
)


def assess_candidate_constraints(
    *,
    candidate: HedgeCandidate,
    mandate: Mandate,
    portfolio: Portfolio,
    portfolio_horizon_returns: Sequence[float],
    underlying_horizon_returns: Mapping[str, Sequence[float]],
) -> CandidateFeasibilityAssessment:
    """Evaluate every hard client rule and return explainable diagnostics."""

    return CandidateConstraintCalculator(
        candidate=candidate,
        mandate=mandate,
        portfolio=portfolio,
        portfolio_horizon_returns=portfolio_horizon_returns,
        underlying_horizon_returns=underlying_horizon_returns,
    ).assess()


__all__ = [
    "CandidateConstraintCalculator",
    "CandidateFeasibilityAssessment",
    "ConstraintDiagnostic",
    "ConstraintRelaxation",
    "FeasibilityStatus",
    "InfeasibilityDiagnosis",
    "assess_candidate_constraints",
]
