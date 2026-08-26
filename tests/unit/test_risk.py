import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.analytics.risk import (  # noqa: E402
    RiskMetricError,
    calculate_historical_risk_metrics,
    drawdown_series,
    expected_shortfall,
    historical_risk_metrics_from_dataset,
    maximum_drawdown,
    value_at_risk,
)
from quant_hedge_desk.analytics.returns import (  # noqa: E402
    build_aligned_return_dataset,
)


class HistoricalRiskMetricTests(unittest.TestCase):
    def test_var_uses_non_interpolated_lower_empirical_quantile(self) -> None:
        returns = (-0.30, -0.20, -0.10, 0.00, 0.10)

        self.assertEqual(value_at_risk(returns, confidence_level=0.60), -0.20)
        self.assertEqual(value_at_risk(returns, confidence_level=0.99), -0.30)

    def test_exact_quantile_cutoff_is_not_shifted_by_float_rounding(self) -> None:
        returns = tuple(float(value) for value in range(100))

        # The 5% empirical quantile is the fifth ordered observation (index 4).
        self.assertEqual(value_at_risk(returns, confidence_level=0.95), 4.0)
        self.assertEqual(expected_shortfall(returns, confidence_level=0.95), 2.0)

    def test_expected_shortfall_weights_fractional_boundary_observation(self) -> None:
        returns = (-0.40, -0.20, 0.00, 0.10)

        # A 37.5% tail contains the worst return and half of the next one.
        self.assertAlmostEqual(
            expected_shortfall(returns, confidence_level=0.625),
            (-0.40 - 0.5 * 0.20) / 1.5,
        )
        # With a tail smaller than one empirical observation, ES is the worst.
        self.assertEqual(
            expected_shortfall(returns, confidence_level=0.99), -0.40
        )

    def test_drawdown_compounds_returns_and_includes_initial_wealth(self) -> None:
        returns = (-0.10, 0.20, -0.25, 0.50)

        result = drawdown_series(returns)

        self.assertAlmostEqual(result[0], -0.10)
        self.assertAlmostEqual(result[1], 0.0)
        self.assertAlmostEqual(result[2], -0.25)
        self.assertAlmostEqual(result[3], 0.0)
        self.assertAlmostEqual(maximum_drawdown(returns), 0.25)

    def test_combined_result_records_parameters_and_metrics(self) -> None:
        returns = (-0.20, -0.10, 0.10, 0.20)

        result = calculate_historical_risk_metrics(
            returns, confidence_level=0.50
        )

        self.assertEqual(result.confidence_level, 0.50)
        self.assertEqual(result.observation_count, 4)
        self.assertEqual(result.value_at_risk, -0.10)
        self.assertAlmostEqual(result.expected_shortfall, -0.15)
        self.assertAlmostEqual(result.maximum_drawdown, 0.28)

    def test_dataset_helper_uses_named_aligned_series(self) -> None:
        dataset = build_aligned_return_dataset(
            {
                "PORTFOLIO": {
                    "2026-01-01": 100,
                    "2026-01-02": 80,
                    "2026-01-03": 88,
                },
                "NIFTY": {
                    "2026-01-01": 100,
                    "2026-01-02": 90,
                    "2026-01-03": 99,
                },
            }
        )

        result = historical_risk_metrics_from_dataset(
            dataset, "portfolio", confidence_level=0.50
        )

        self.assertEqual(result.observation_count, 2)
        self.assertAlmostEqual(result.value_at_risk, -0.20)
        self.assertAlmostEqual(result.expected_shortfall, -0.20)
        self.assertAlmostEqual(result.maximum_drawdown, 0.20)

    def test_rejects_invalid_returns_and_confidence_levels(self) -> None:
        for invalid in ((), (0.1, float("nan")), (0.1, -1.01), "0.1"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RiskMetricError):
                    maximum_drawdown(invalid)

        for invalid in (0, 1, -0.1, 1.1, float("inf"), True):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(RiskMetricError, "confidence_level"):
                    value_at_risk((0.1,), confidence_level=invalid)


if __name__ == "__main__":
    unittest.main()
