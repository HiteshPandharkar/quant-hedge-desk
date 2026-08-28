import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.application.stress_candidate_hedge import (  # noqa: E402
    stress_candidate_hedge,
)
from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402
from quant_hedge_desk.scenarios.manual_generator import ManualScenarioGenerator  # noqa: E402


class CandidateStressEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        case = ROOT / "cases" / "asteria_capital"
        cls.result = stress_candidate_hedge(
            portfolio_path=case / "portfolio.csv",
            mandate_path=case / "mandate.yaml",
            candidate_path=case / "candidate_01_hybrid_protective_puts.yaml",
            stress_scenario_path=case / "named_stress_correlation_liquidity.yaml",
            supplied_total_market_value=5_000_000_000,
        )

    def test_market_volume_multiplier_is_a_valid_scenario_input(self) -> None:
        case = ROOT / "cases" / "asteria_capital"
        scenario_set = ManualScenarioGenerator.from_mapping(
            load_yaml_mapping(case / "named_stress_correlation_liquidity.yaml")
        ).generate()

        self.assertEqual(
            scenario_set.scenarios[1].steps[0].market_volume_multipliers["NIFTY"],
            Decimal("0.15"),
        )

    def test_correlation_breakdown_is_measured_against_protective_proxy(self) -> None:
        outcome = self.result.outcomes[0]

        self.assertEqual(outcome.scenario_id, "correlation-breakdown")
        self.assertGreater(outcome.absolute_correlation_basis_gap, Decimal("0.05"))
        self.assertFalse(outcome.correlation_pass)

    def test_stressed_liquidity_recalculates_cost_and_unwind(self) -> None:
        outcome = self.result.outcomes[1]

        self.assertGreater(outcome.stressed_execution_cost, outcome.baseline_execution_cost)
        self.assertGreater(outcome.stressed_unwind_days, Decimal("3"))
        self.assertFalse(outcome.liquidity_pass)
        self.assertFalse(outcome.cost_budget_pass)
        self.assertLess(outcome.stressed_hedged_return, outcome.baseline_hedged_return)

    def test_failures_create_explicit_usage_restrictions(self) -> None:
        self.assertFalse(self.result.passed)
        self.assertEqual(len(self.result.usage_restrictions), 3)
        self.assertIn("portfolio floor", self.result.usage_restrictions[0])
        self.assertIn("three-day full unwind", self.result.usage_restrictions[1])
        self.assertIn("Reprice", self.result.usage_restrictions[2])
        payload = self.result.to_dict()
        self.assertNotIn("rebalancing_policy_id", payload)
        self.assertNotIn("rebalanced_hedged_return", payload["outcomes"][0])
        json.dumps(payload)

    def test_single_candidate_facade_accepts_optional_rebalancing_inputs(self) -> None:
        case = ROOT / "cases" / "asteria_capital"

        result = stress_candidate_hedge(
            portfolio_path=case / "portfolio.csv",
            mandate_path=case / "mandate.yaml",
            candidate_path=case / "candidate_03_nifty_protective_put.yaml",
            stress_scenario_path=case / "named_stress_correlation_liquidity.yaml",
            supplied_total_market_value=5_000_000_000,
            rebalancing_policy_path=case / "rebalancing_stress_policy.yaml",
            market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
        )

        self.assertEqual(
            result.rebalancing_policy_id, "asteria-rebalancing-stress-v1"
        )
        self.assertIsNotNone(result.outcomes[0].rebalanced_hedged_return)

    def test_single_candidate_facade_requires_policy_and_history_together(self) -> None:
        case = ROOT / "cases" / "asteria_capital"

        with self.assertRaisesRegex(ValueError, "supplied together"):
            stress_candidate_hedge(
                portfolio_path=case / "portfolio.csv",
                mandate_path=case / "mandate.yaml",
                candidate_path=case / "candidate_03_nifty_protective_put.yaml",
                stress_scenario_path=case / "named_stress_correlation_liquidity.yaml",
                rebalancing_policy_path=case / "rebalancing_stress_policy.yaml",
            )


if __name__ == "__main__":
    unittest.main()
