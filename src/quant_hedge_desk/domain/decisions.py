"""Class-based calculation of deterministic pre-trade decisions.

The calculator combines already-approved client-feasibility, dealer-risk, and
quote-waterfall results. It deliberately does not manufacture missing risk or
pricing evidence: a candidate without all required approvals cannot be quoted.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from quant_hedge_desk.domain.enums import CandidateRelationship, PreTradeDecision
from quant_hedge_desk.domain.errors import DecisionValidationError
from quant_hedge_desk.domain.models.decision_models import (
    CandidateDecisionDiagnostic,
    CandidateDecisionInput,
    PreTradeDecisionResult,
    positive_decimal,
    required_text,
)
from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus


class PreTradeDecisionCalculator:
    """Validate decision evidence and apply the mandated selection precedence."""

    def __init__(
        self,
        *,
        requested_candidate_id: str,
        requested_notional: Decimal | int | str,
        candidates: Iterable[CandidateDecisionInput],
    ) -> None:
        self.requested_candidate_id = required_text(
            requested_candidate_id, "requested_candidate_id"
        )
        self.requested_notional = positive_decimal(
            requested_notional, "requested_notional"
        )
        self.candidates = tuple(candidates)
        self._validate_inputs()

    def calculate(self) -> PreTradeDecisionResult:
        """Return one auditable full/reduce/restructure/decline decision."""

        diagnostics = tuple(self._diagnose(item) for item in self.candidates)
        eligible_ids = {
            item.candidate_id for item in diagnostics if item.eligible_for_selection
        }

        selected: CandidateDecisionInput | None
        requested = self._eligible(CandidateRelationship.REQUESTED, eligible_ids)
        if requested:
            selected = requested[0]
            decision = (
                PreTradeDecision.QUOTE_WITH_ADDITIONAL_RESERVE
                if selected.additional_reserve_required
                else PreTradeDecision.QUOTE
            )
            reason = (
                "The requested transaction passes all client and dealer hard "
                "constraints with an explicitly justified additional reserve."
                if selected.additional_reserve_required
                else "The requested transaction passes all client and dealer hard constraints."
            )
        else:
            reduced = self._eligible(
                CandidateRelationship.REDUCED_NOTIONAL, eligible_ids
            )
            if reduced:
                selected = reduced[0]
                decision = PreTradeDecision.REDUCE_NOTIONAL
                reason = (
                    "The requested transaction does not pass at full notional; the "
                    "selected lower-notional version passes all client and dealer "
                    "hard constraints."
                )
            else:
                restructured = self._eligible(
                    CandidateRelationship.RESTRUCTURED, eligible_ids
                )
                if restructured:
                    selected = restructured[0]
                    decision = PreTradeDecision.RESTRUCTURE
                    reason = (
                        "The requested transaction and lower-notional alternatives do "
                        "not pass; the selected alternative payoff passes all client "
                        "and dealer hard constraints."
                    )
                else:
                    selected = None
                    decision = PreTradeDecision.DECLINE
                    reason = (
                        "No candidate has complete evidence showing that client "
                        "constraints, dealer limits, and quote reconciliation all pass."
                    )

        return self._result(
            decision=decision,
            selected=selected,
            reason=reason,
            diagnostics=diagnostics,
        )

    def _validate_inputs(self) -> None:
        if not self.candidates:
            raise DecisionValidationError("candidates must be non-empty")
        if any(
            not isinstance(item, CandidateDecisionInput) for item in self.candidates
        ):
            raise DecisionValidationError(
                "candidates must contain only CandidateDecisionInput values"
            )
        identifiers = tuple(item.candidate_id for item in self.candidates)
        if len(identifiers) != len(set(identifiers)):
            raise DecisionValidationError("candidate IDs must be unique")

        requested = tuple(
            item
            for item in self.candidates
            if item.relationship is CandidateRelationship.REQUESTED
        )
        if len(requested) != 1:
            raise DecisionValidationError("exactly one candidate must be REQUESTED")
        if requested[0].candidate_id != self.requested_candidate_id:
            raise DecisionValidationError(
                "requested_candidate_id must identify the REQUESTED candidate"
            )
        if requested[0].proposed_notional != self.requested_notional:
            raise DecisionValidationError(
                "the REQUESTED candidate proposed_notional must equal requested_notional"
            )
        if any(
            item.relationship is CandidateRelationship.REDUCED_NOTIONAL
            and item.proposed_notional >= self.requested_notional
            for item in self.candidates
        ):
            raise DecisionValidationError(
                "REDUCED_NOTIONAL candidates must be below requested_notional"
            )

    @staticmethod
    def _diagnose(candidate: CandidateDecisionInput) -> CandidateDecisionDiagnostic:
        reasons: list[str] = []
        client_feasible = (
            candidate.assessment.status is FeasibilityStatus.FEASIBLE
        )
        if not client_feasible:
            failures = ", ".join(candidate.assessment.failed_constraints) or "unknown"
            reasons.append(f"client constraints failed: {failures}")

        dealer_approved: bool | None = None
        if candidate.dealer_risk is None:
            reasons.append("dealer risk assessment missing")
        else:
            dealer_approved = candidate.dealer_risk.approved
            if not dealer_approved:
                failures = ", ".join(
                    item.measure for item in candidate.dealer_risk.breaches
                )
                reasons.append(f"dealer limits breached: {failures}")

        quote_reconciled: bool | None = None
        quote_within_client_budget: bool | None = None
        if candidate.quote_waterfall is None:
            reasons.append("quote waterfall missing")
        else:
            quote_reconciled = candidate.quote_waterfall.reconciled
            if not quote_reconciled:
                reasons.append("quote waterfall does not reconcile")
            assert candidate.quote_waterfall.quoted_client_premium_inr is not None
            quote_within_client_budget = (
                candidate.quote_waterfall.quoted_client_premium_inr
                <= candidate.maximum_client_premium_inr
            )
            if not quote_within_client_budget:
                reasons.append(
                    "reconciled quote exceeds the client's all-in premium budget"
                )

        eligible = bool(
            client_feasible
            and dealer_approved
            and quote_reconciled
            and quote_within_client_budget
        )
        if eligible:
            reasons.append(
                "client constraints, dealer limits, and quote reconciliation pass"
            )
            if candidate.additional_reserve_required:
                reasons.append("additional reserve is explicitly justified")
        return CandidateDecisionDiagnostic(
            candidate_id=candidate.candidate_id,
            relationship=candidate.relationship,
            proposed_notional=candidate.proposed_notional,
            priority=candidate.priority,
            client_feasible=client_feasible,
            dealer_approved=dealer_approved,
            quote_reconciled=quote_reconciled,
            quote_within_client_budget=quote_within_client_budget,
            eligible_for_selection=eligible,
            reasons=tuple(reasons),
        )

    def _eligible(
        self,
        relationship: CandidateRelationship,
        eligible_ids: set[str],
    ) -> tuple[CandidateDecisionInput, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self.candidates
                    if item.relationship is relationship
                    and item.candidate_id in eligible_ids
                ),
                key=lambda item: (item.priority, item.candidate_id),
            )
        )

    def _result(
        self,
        *,
        decision: PreTradeDecision,
        selected: CandidateDecisionInput | None,
        reason: str,
        diagnostics: tuple[CandidateDecisionDiagnostic, ...],
    ) -> PreTradeDecisionResult:
        return PreTradeDecisionResult(
            requested_candidate_id=self.requested_candidate_id,
            requested_notional=self.requested_notional,
            decision=decision,
            selected_candidate_id=None if selected is None else selected.candidate_id,
            selected_family=None if selected is None else selected.assessment.family,
            approved_notional=None if selected is None else selected.proposed_notional,
            additional_reserve_required=(
                False if selected is None else selected.additional_reserve_required
            ),
            additional_reserve_justification=(
                None if selected is None else selected.additional_reserve_justification
            ),
            primary_reason=reason,
            diagnostics=diagnostics,
            quote_waterfall=None if selected is None else selected.quote_waterfall,
        )


__all__ = [
    "CandidateDecisionDiagnostic",
    "CandidateDecisionInput",
    "CandidateRelationship",
    "DecisionValidationError",
    "PreTradeDecision",
    "PreTradeDecisionCalculator",
    "PreTradeDecisionResult",
]
