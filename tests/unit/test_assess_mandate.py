import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.application.assess_mandate import (  # noqa: E402
    StageStatus,
    assess_mandate,
)
from quant_hedge_desk.application.assessment_service import (  # noqa: E402
    MandateAssessmentService,
)


class AsteriaMandateAssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        case = ROOT / "cases" / "asteria_capital"
        cls.assessment = MandateAssessmentService().assess(
            portfolio_path=case / "portfolio.csv",
            mandate_path=case / "mandate.yaml",
            desk_limits_path=case / "desk_limits.yaml",
            market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
            supplied_total_market_value=5_000_000_000,
        )

    def test_runs_implemented_workflow_against_reference_case(self) -> None:
        result = self.assessment

        self.assertEqual(result.input_validation.status, StageStatus.COMPLETE)
        self.assertEqual(result.input_validation.error_count, 0)
        self.assertEqual(result.input_validation.warning_count, 0)
        self.assertEqual(result.portfolio.portfolio_id, "ASTERIA-001")
        self.assertEqual(result.portfolio.holding_count, 50)
        self.assertEqual(result.market_data.return_observation_count, 1504)
        self.assertEqual(
            result.market_data.portfolio_return_method,
            "AVAILABLE_HOLDINGS_RENORMALIZED",
        )
        self.assertAlmostEqual(result.market_data.minimum_covered_weight, 0.9822)
        self.assertEqual(
            result.market_data.incomplete_weight_observation_count, 717
        )
        self.assertEqual(result.horizon_risk.horizon_trading_days, 126)
        self.assertEqual(result.horizon_risk.overlapping_window_count, 1379)

        primary = next(
            exposure
            for exposure in result.index_exposures
            if exposure.is_primary_benchmark
        )
        self.assertEqual(primary.symbol, "NIFTY")
        self.assertAlmostEqual(primary.beta, 1.012026, places=6)
        self.assertAlmostEqual(primary.downside_beta, 1.057045, places=6)
        self.assertAlmostEqual(
            result.horizon_risk.expected_shortfall, -0.11374235, places=7
        )
        self.assertTrue(result.mandate_comparison.point_estimate_within_limit)

    def test_unimplemented_stages_are_explicitly_not_assessed(self) -> None:
        result = self.assessment

        self.assertEqual(result.scenario_assessment.status, StageStatus.NOT_ASSESSED)
        self.assertEqual(result.hedge_assessment.status, StageStatus.NOT_ASSESSED)
        self.assertEqual(
            result.feasibility_assessment.status, StageStatus.NOT_ASSESSED
        )

    def test_service_rejects_invalid_trading_calendar_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            MandateAssessmentService(trading_days_per_month=0)

    def test_result_supports_structured_serialization(self) -> None:
        payload = self.assessment.to_dict()

        self.assertEqual(payload["portfolio"]["as_of_date"], "2026-01-30")
        self.assertEqual(payload["portfolio"]["total_market_value"], "5000000000")
        self.assertEqual(payload["scenario_assessment"]["status"], "NOT_ASSESSED")
        json.dumps(payload)

    def test_public_facade_returns_assessment_without_cli(self) -> None:
        case = ROOT / "cases" / "asteria_capital"

        result = assess_mandate(
            portfolio_path=case / "portfolio.csv",
            mandate_path=case / "mandate.yaml",
            desk_limits_path=case / "desk_limits.yaml",
            market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
            supplied_total_market_value=5_000_000_000,
        )

        self.assertEqual(result.mandate_id, "asteria-capital-v1")


if __name__ == "__main__":
    unittest.main()
