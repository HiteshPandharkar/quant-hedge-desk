"""Programmatic facade for the deterministic pre-trade decision engine."""

from decimal import Decimal
from typing import Iterable

from quant_hedge_desk.domain.decisions import (
    CandidateDecisionDiagnostic,
    CandidateDecisionInput,
    CandidateRelationship,
    DecisionValidationError,
    PreTradeDecision,
    PreTradeDecisionCalculator,
    PreTradeDecisionResult,
)


def decide_pre_trade(
    *,
    requested_candidate_id: str,
    requested_notional: Decimal | int | str,
    candidates: Iterable[CandidateDecisionInput],
) -> PreTradeDecisionResult:
    """Run the domain calculator through the application-level facade."""

    return PreTradeDecisionCalculator(
        requested_candidate_id=requested_candidate_id,
        requested_notional=requested_notional,
        candidates=candidates,
    ).calculate()


__all__ = [
    "CandidateDecisionDiagnostic",
    "CandidateDecisionInput",
    "CandidateRelationship",
    "DecisionValidationError",
    "PreTradeDecision",
    "PreTradeDecisionCalculator",
    "PreTradeDecisionResult",
    "decide_pre_trade",
]
