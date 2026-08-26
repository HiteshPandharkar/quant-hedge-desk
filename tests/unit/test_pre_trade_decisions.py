import json
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.decisions import (  # noqa: E402
    CandidateDecisionInput,
    CandidateRelationship,
    DecisionValidationError,
    PreTradeDecision,
    PreTradeDecisionCalculator,
)
from quant_hedge_desk.application.decide_pre_trade import decide_pre_trade  # noqa: E402
from quant_hedge_desk.domain.enums import RiskLimitStatus  # noqa: E402
from quant_hedge_desk.domain.models.dealer_risk_models import (  # noqa: E402
    DealerRiskAssessment,
    RiskLimitDiagnostic,
)
from quant_hedge_desk.domain.models.desk_portfolio import (  # noqa: E402
    DeskRiskExposure,
)
from quant_hedge_desk.hedge_design.constraint_enums import (  # noqa: E402
    FeasibilityStatus,
)
from quant_hedge_desk.hedge_design.constraint_models import (  # noqa: E402
    CandidateFeasibilityAssessment,
)
from quant_hedge_desk.pricing.models import QuoteWaterfall  # noqa: E402


class PreTradeDecisionTests(unittest.TestCase):
    @staticmethod
    def assessment(
        candidate_id: str,
        *,
        feasible: bool = True,
        family: str = "NIFTY_PROTECTIVE_PUT",
    ) -> CandidateFeasibilityAssessment:
        return CandidateFeasibilityAssessment(
            candidate_id=candidate_id,
            family=family,
            status=(
                FeasibilityStatus.FEASIBLE
                if feasible
                else FeasibilityStatus.INFEASIBLE
            ),
            net_option_premium=Decimal("100"),
            estimated_execution_cost=Decimal("10"),
            all_in_client_cost=Decimal("110"),
            all_in_cost_fraction=Decimal("0.011"),
            premium_constraint_cost=Decimal("110"),
            premium_constraint_fraction=Decimal("0.011"),
            gross_reference_notional=Decimal("1000"),
            protected_reference_notional=Decimal("1000"),
            notional_coverage_fraction=Decimal("0.10"),
            unhedged_expected_shortfall=-0.15,
            hedged_expected_shortfall=-0.10,
            unhedged_tail_breach_probability=0.20,
            hedged_tail_breach_probability=0.10,
            tail_breach_reduction=0.10,
            maximum_upside_sacrifice=Decimal("0.01"),
            estimated_unwind_days=Decimal("1"),
            failed_constraints=() if feasible else ("EXPECTED_SHORTFALL",),
            diagnostics=(),
            infeasibility_diagnosis=None,
            limitations=(),
        )

    @staticmethod
    def quote(*, reserve: str = "10") -> QuoteWaterfall:
        return QuoteWaterfall(
            clean_value_inr="100",
            initial_hedge_execution_cost_inr="1",
            expected_rehedging_cost_inr="2",
            liquidity_reserve_inr="3",
            model_reserve_inr=reserve,
            capital_funding_estimate_inr="4",
            dealer_margin_inr="5",
        )

    @staticmethod
    def dealer(*, approved: bool = True, reserve: str = "10") -> DealerRiskAssessment:
        zero = DeskRiskExposure.zero()
        diagnostics = [
            RiskLimitDiagnostic(
                measure="model_reserve_inr",
                before=Decimal("0"),
                incremental=Decimal(reserve),
                after=Decimal(reserve),
                limit=Decimal("15"),
                before_utilization=Decimal("0"),
                after_utilization=Decimal(reserve) / Decimal("15"),
                status=RiskLimitStatus.PASS,
            )
        ]
        if not approved:
            diagnostics.append(
                RiskLimitDiagnostic(
                    measure="absolute_net_index_delta_inr",
                    before=Decimal("90"),
                    incremental=Decimal("20"),
                    after=Decimal("110"),
                    limit=Decimal("100"),
                    before_utilization=Decimal("0.9"),
                    after_utilization=Decimal("1.1"),
                    status=RiskLimitStatus.BREACH,
                )
            )
        return DealerRiskAssessment(
            desk_limits_id="limits-1",
            desk_portfolio_id="desk-1",
            existing_risk=zero,
            incremental_risk=zero,
            post_trade_risk=zero,
            diagnostics=tuple(diagnostics),
        )

    @classmethod
    def candidate(
        cls,
        candidate_id: str,
        relationship: CandidateRelationship,
        notional: str,
        *,
        feasible: bool = True,
        dealer_approved: bool = True,
        priority: int = 1,
        reserve_justification: str | None = None,
        family: str = "NIFTY_PROTECTIVE_PUT",
    ) -> CandidateDecisionInput:
        return CandidateDecisionInput(
            assessment=cls.assessment(
                candidate_id, feasible=feasible, family=family
            ),
            relationship=relationship,
            proposed_notional=notional,
            maximum_client_premium_inr="1000",
            priority=priority,
            dealer_risk=cls.dealer(approved=dealer_approved),
            quote_waterfall=cls.quote(),
            additional_reserve_justification=reserve_justification,
        )

    @staticmethod
    def decide(*candidates: CandidateDecisionInput):
        return decide_pre_trade(
            requested_candidate_id="requested",
            requested_notional="1000",
            candidates=candidates,
        )

    def test_quote_when_requested_trade_passes(self) -> None:
        result = self.decide(
            self.candidate("requested", CandidateRelationship.REQUESTED, "1000")
        )

        self.assertEqual(result.decision, PreTradeDecision.QUOTE)
        self.assertEqual(result.selected_candidate_id, "requested")
        self.assertEqual(result.approved_notional, Decimal("1000"))
        self.assertFalse(result.additional_reserve_required)
        json.dumps(result.to_dict())

    def test_class_calculator_exposes_same_decision_api(self) -> None:
        candidate = self.candidate(
            "requested", CandidateRelationship.REQUESTED, "1000"
        )
        result = PreTradeDecisionCalculator(
            requested_candidate_id="requested",
            requested_notional="1000",
            candidates=(candidate,),
        ).calculate()

        self.assertEqual(result.decision, PreTradeDecision.QUOTE)

    def test_quote_with_additional_reserve_requires_explicit_justification(self) -> None:
        result = self.decide(
            self.candidate(
                "requested",
                CandidateRelationship.REQUESTED,
                "1000",
                reserve_justification="Gap-risk model uncertainty",
            )
        )

        self.assertEqual(
            result.decision, PreTradeDecision.QUOTE_WITH_ADDITIONAL_RESERVE
        )
        self.assertEqual(
            result.additional_reserve_justification,
            "Gap-risk model uncertainty",
        )

    def test_reduce_notional_when_full_request_fails_and_lower_size_passes(self) -> None:
        result = self.decide(
            self.candidate(
                "requested",
                CandidateRelationship.REQUESTED,
                "1000",
                dealer_approved=False,
            ),
            self.candidate(
                "reduced", CandidateRelationship.REDUCED_NOTIONAL, "700"
            ),
        )

        self.assertEqual(result.decision, PreTradeDecision.REDUCE_NOTIONAL)
        self.assertEqual(result.selected_candidate_id, "reduced")
        self.assertEqual(result.approved_notional, Decimal("700"))

    def test_reduce_precedes_restructure_and_uses_declared_priority(self) -> None:
        result = self.decide(
            self.candidate(
                "requested",
                CandidateRelationship.REQUESTED,
                "1000",
                feasible=False,
            ),
            self.candidate(
                "reduced-low-priority",
                CandidateRelationship.REDUCED_NOTIONAL,
                "800",
                priority=2,
            ),
            self.candidate(
                "reduced-high-priority",
                CandidateRelationship.REDUCED_NOTIONAL,
                "750",
                priority=1,
            ),
            self.candidate(
                "alternative",
                CandidateRelationship.RESTRUCTURED,
                "1000",
                family="NIFTY_VERTICAL_PUT_SPREAD",
            ),
        )

        self.assertEqual(result.decision, PreTradeDecision.REDUCE_NOTIONAL)
        self.assertEqual(result.selected_candidate_id, "reduced-high-priority")

    def test_restructure_when_only_alternative_payoff_passes(self) -> None:
        result = self.decide(
            self.candidate(
                "requested",
                CandidateRelationship.REQUESTED,
                "1000",
                feasible=False,
            ),
            self.candidate(
                "alternative",
                CandidateRelationship.RESTRUCTURED,
                "1000",
                family="NIFTY_VERTICAL_PUT_SPREAD",
            ),
        )

        self.assertEqual(result.decision, PreTradeDecision.RESTRUCTURE)
        self.assertEqual(result.selected_candidate_id, "alternative")

    def test_decline_when_no_candidate_has_complete_approved_evidence(self) -> None:
        requested = self.candidate(
            "requested",
            CandidateRelationship.REQUESTED,
            "1000",
            feasible=False,
        )
        alternative = replace(
            self.candidate(
                "alternative", CandidateRelationship.RESTRUCTURED, "1000"
            ),
            dealer_risk=None,
        )
        result = self.decide(requested, alternative)

        self.assertEqual(result.decision, PreTradeDecision.DECLINE)
        self.assertIsNone(result.selected_candidate_id)
        diagnosis = next(
            item for item in result.diagnostics if item.candidate_id == "alternative"
        )
        self.assertFalse(diagnosis.eligible_for_selection)
        self.assertIn("dealer risk assessment missing", diagnosis.reasons)

    def test_rejects_ambiguous_request_and_invalid_reduced_notional(self) -> None:
        requested = self.candidate(
            "requested", CandidateRelationship.REQUESTED, "1000"
        )
        with self.assertRaisesRegex(DecisionValidationError, "exactly one"):
            decide_pre_trade(
                requested_candidate_id="requested",
                requested_notional="1000",
                candidates=(
                    requested,
                    self.candidate(
                        "second-request", CandidateRelationship.REQUESTED, "1000"
                    ),
                ),
            )
        with self.assertRaisesRegex(DecisionValidationError, "below"):
            self.decide(
                requested,
                self.candidate(
                    "not-reduced", CandidateRelationship.REDUCED_NOTIONAL, "1000"
                ),
            )

    def test_reserve_evidence_must_be_positive_and_consistent(self) -> None:
        with self.assertRaisesRegex(DecisionValidationError, "positive model reserve"):
            CandidateDecisionInput(
                assessment=self.assessment("requested"),
                relationship=CandidateRelationship.REQUESTED,
                proposed_notional="1000",
                maximum_client_premium_inr="1000",
                priority=1,
                dealer_risk=self.dealer(reserve="0"),
                quote_waterfall=self.quote(reserve="0"),
                additional_reserve_justification="Required",
            )
        with self.assertRaisesRegex(DecisionValidationError, "must agree"):
            CandidateDecisionInput(
                assessment=self.assessment("requested"),
                relationship=CandidateRelationship.REQUESTED,
                proposed_notional="1000",
                maximum_client_premium_inr="1000",
                priority=1,
                dealer_risk=self.dealer(reserve="9"),
                quote_waterfall=self.quote(reserve="10"),
            )

    def test_reconciled_quote_above_client_budget_is_not_selectable(self) -> None:
        requested = replace(
            self.candidate(
                "requested", CandidateRelationship.REQUESTED, "1000"
            ),
            maximum_client_premium_inr=Decimal("100"),
        )
        result = self.decide(requested)

        self.assertEqual(result.decision, PreTradeDecision.DECLINE)
        self.assertFalse(result.diagnostics[0].quote_within_client_budget)
        self.assertIn(
            "reconciled quote exceeds the client's all-in premium budget",
            result.diagnostics[0].reasons,
        )


if __name__ == "__main__":
    unittest.main()
