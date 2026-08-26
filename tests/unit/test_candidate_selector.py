import json
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.application.assess_candidate_hedge import assess_candidate_hedge  # noqa: E402
from quant_hedge_desk.domain.enums import SoftObjective  # noqa: E402
from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus  # noqa: E402
from quant_hedge_desk.hedge_design.selector import (  # noqa: E402
    CandidateRankingInput,
    rank_feasible_candidates,
)


class CandidateSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        case = ROOT / "cases" / "asteria_capital"
        cls.assessments = tuple(
            assess_candidate_hedge(
                portfolio_path=case / "portfolio.csv",
                mandate_path=case / "mandate.yaml",
                candidate_path=path,
                market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
                supplied_total_market_value=5_000_000_000,
            )
            for path in sorted(case.glob("candidate_*.yaml"))
        )

    @staticmethod
    def ranking_input(assessment, **overrides):
        values = {
            "basis_risk": Decimal("0.03"),
            "estimated_turnover": Decimal("0.80"),
            "cross_methodology_robustness_penalty": Decimal("0.01"),
            "complexity": 2,
        }
        values.update(overrides)
        return CandidateRankingInput(assessment=assessment, **values)

    def test_ranks_only_feasible_candidates_by_mandate_priority(self) -> None:
        first, second, third = self.assessments
        ranked = rank_feasible_candidates(
            (
                self.ranking_input(first, basis_risk="0.001"),
                self.ranking_input(second, basis_risk="0.10"),
                self.ranking_input(third, basis_risk="0.0001"),
            )
        )

        self.assertEqual([item.rank for item in ranked], [1, 2, 3])
        # Residual ES precedes basis risk, so candidate 2 wins despite its
        # deliberately worse basis-risk input.
        self.assertEqual(ranked[0].candidate_id, second.candidate_id)
        self.assertEqual(ranked[1].candidate_id, third.candidate_id)
        self.assertEqual(ranked[2].candidate_id, first.candidate_id)
        json.dumps([item.to_dict() for item in ranked])

    def test_excludes_infeasible_before_soft_ranking(self) -> None:
        feasible = self.assessments[0]
        infeasible = replace(
            self.assessments[1],
            status=FeasibilityStatus.INFEASIBLE,
            failed_constraints=("ALL_IN_PREMIUM",),
        )
        ranked = rank_feasible_candidates(
            (
                self.ranking_input(feasible, basis_risk="1"),
                self.ranking_input(infeasible, basis_risk="0"),
            ),
            (SoftObjective.BASIS_RISK,),
        )

        self.assertEqual([item.candidate_id for item in ranked], [feasible.candidate_id])

    def test_declared_objective_order_controls_result(self) -> None:
        left, right = self.assessments[:2]
        inputs = (
            self.ranking_input(left, basis_risk="0.01", complexity=5),
            self.ranking_input(right, basis_risk="0.10", complexity=1),
        )

        by_basis = rank_feasible_candidates(
            inputs,
            (SoftObjective.BASIS_RISK, SoftObjective.SIMPLICITY),
        )
        by_simplicity = rank_feasible_candidates(
            inputs,
            (SoftObjective.SIMPLICITY, SoftObjective.BASIS_RISK),
        )

        self.assertEqual(by_basis[0].candidate_id, left.candidate_id)
        self.assertEqual(by_simplicity[0].candidate_id, right.candidate_id)

    def test_exact_ties_use_candidate_id_not_input_order(self) -> None:
        left = replace(self.assessments[0], candidate_id="candidate-a")
        right = replace(self.assessments[0], candidate_id="candidate-b")
        ranked = rank_feasible_candidates(
            (self.ranking_input(right), self.ranking_input(left))
        )
        self.assertEqual(
            [item.candidate_id for item in ranked],
            ["candidate-a", "candidate-b"],
        )

    def test_rejects_duplicate_ids_and_invalid_metrics(self) -> None:
        assessment = self.assessments[0]
        item = self.ranking_input(assessment)
        with self.assertRaisesRegex(ValueError, "candidate IDs must be unique"):
            rank_feasible_candidates((item, item))
        with self.assertRaisesRegex(ValueError, "basis_risk"):
            self.ranking_input(assessment, basis_risk="NaN")
        with self.assertRaisesRegex(ValueError, "soft_objectives must be unique"):
            rank_feasible_candidates(
                (item,),
                (SoftObjective.BASIS_RISK, SoftObjective.BASIS_RISK),
            )


if __name__ == "__main__":
    unittest.main()
