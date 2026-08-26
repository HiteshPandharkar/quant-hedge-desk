"""Immutable inputs and outputs for pre-trade commercial decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from quant_hedge_desk.domain.enums import CandidateRelationship, PreTradeDecision
from quant_hedge_desk.domain.errors import DecisionValidationError
from quant_hedge_desk.domain.models.dealer_risk_models import DealerRiskAssessment
from quant_hedge_desk.hedge_design.constraint_models import (
    CandidateFeasibilityAssessment,
)
from quant_hedge_desk.pricing.models import QuoteWaterfall
from quant_hedge_desk.serialization import json_ready


def positive_decimal(value: Any, name: str) -> Decimal:
    """Normalize a positive finite decimal used by a decision contract."""

    if isinstance(value, bool):
        raise DecisionValidationError(f"{name} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DecisionValidationError(f"{name} must be numeric") from exc
    if not result.is_finite() or result <= 0:
        raise DecisionValidationError(f"{name} must be positive and finite")
    return result


def required_text(value: Any, name: str) -> str:
    """Normalize required text used by a decision contract."""

    if not isinstance(value, str) or not value.strip():
        raise DecisionValidationError(f"{name} must be non-empty text")
    return value.strip()


@dataclass(frozen=True, slots=True)
class CandidateDecisionInput:
    """All available pre-trade evidence for one candidate.

    ``additional_reserve_justification`` is explicit policy evidence. A risk
    warning or a non-zero ordinary model reserve is never silently interpreted
    as requiring the special reserve decision.
    """

    assessment: CandidateFeasibilityAssessment
    relationship: CandidateRelationship
    proposed_notional: Decimal
    maximum_client_premium_inr: Decimal
    priority: int
    dealer_risk: DealerRiskAssessment | None = None
    quote_waterfall: QuoteWaterfall | None = None
    additional_reserve_justification: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.assessment, CandidateFeasibilityAssessment):
            raise DecisionValidationError(
                "assessment must be a CandidateFeasibilityAssessment"
            )
        try:
            relationship = CandidateRelationship(self.relationship)
        except (TypeError, ValueError) as exc:
            raise DecisionValidationError(
                "relationship must be REQUESTED, REDUCED_NOTIONAL, or RESTRUCTURED"
            ) from exc
        object.__setattr__(self, "relationship", relationship)
        object.__setattr__(
            self,
            "proposed_notional",
            positive_decimal(self.proposed_notional, "proposed_notional"),
        )
        object.__setattr__(
            self,
            "maximum_client_premium_inr",
            positive_decimal(
                self.maximum_client_premium_inr, "maximum_client_premium_inr"
            ),
        )
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise DecisionValidationError("priority must be a positive integer")
        if self.priority <= 0:
            raise DecisionValidationError("priority must be a positive integer")
        if self.dealer_risk is not None and not isinstance(
            self.dealer_risk, DealerRiskAssessment
        ):
            raise DecisionValidationError(
                "dealer_risk must be a DealerRiskAssessment or None"
            )
        if self.quote_waterfall is not None and not isinstance(
            self.quote_waterfall, QuoteWaterfall
        ):
            raise DecisionValidationError(
                "quote_waterfall must be a QuoteWaterfall or None"
            )

        justification = self.additional_reserve_justification
        if justification is not None:
            justification = required_text(
                justification, "additional_reserve_justification"
            )
            if self.quote_waterfall is None:
                raise DecisionValidationError(
                    "additional reserve requires a quote waterfall"
                )
            if self.quote_waterfall.model_reserve_inr <= 0:
                raise DecisionValidationError(
                    "additional reserve requires a positive model reserve"
                )
            object.__setattr__(
                self, "additional_reserve_justification", justification
            )

        if self.dealer_risk is not None and self.quote_waterfall is not None:
            reserve = next(
                (
                    item.after
                    for item in self.dealer_risk.diagnostics
                    if item.measure == "model_reserve_inr"
                ),
                None,
            )
            if reserve is None:
                raise DecisionValidationError(
                    "dealer risk assessment lacks model_reserve_inr diagnostic"
                )
            if reserve != self.quote_waterfall.model_reserve_inr:
                raise DecisionValidationError(
                    "dealer risk and quote waterfall model reserves must agree"
                )

    @property
    def candidate_id(self) -> str:
        return self.assessment.candidate_id

    @property
    def additional_reserve_required(self) -> bool:
        return self.additional_reserve_justification is not None


@dataclass(frozen=True, slots=True)
class CandidateDecisionDiagnostic:
    candidate_id: str
    relationship: CandidateRelationship
    proposed_notional: Decimal
    priority: int
    client_feasible: bool
    dealer_approved: bool | None
    quote_reconciled: bool | None
    quote_within_client_budget: bool | None
    eligible_for_selection: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreTradeDecisionResult:
    """Auditable primary decision plus candidate-level selection evidence."""

    requested_candidate_id: str
    requested_notional: Decimal
    decision: PreTradeDecision
    selected_candidate_id: str | None
    selected_family: str | None
    approved_notional: Decimal | None
    additional_reserve_required: bool
    additional_reserve_justification: str | None
    primary_reason: str
    diagnostics: tuple[CandidateDecisionDiagnostic, ...]
    quote_waterfall: QuoteWaterfall | None

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))


__all__ = [
    "CandidateDecisionDiagnostic",
    "CandidateDecisionInput",
    "PreTradeDecisionResult",
    "positive_decimal",
    "required_text",
]
