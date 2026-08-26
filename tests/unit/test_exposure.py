import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.analytics.downside import (  # noqa: E402
    DownsideMetricError,
    downside_beta,
    downside_beta_from_dataset,
)
from quant_hedge_desk.analytics.exposure import (  # noqa: E402
    ExposureMetricError,
    market_beta,
    market_beta_from_dataset,
    tracking_error,
    tracking_error_from_dataset,
)
from quant_hedge_desk.analytics.returns import (  # noqa: E402
    build_aligned_return_dataset,
)


class BenchmarkExposureMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = (-0.02, -0.01, 0.0, 0.01, 0.02)
        self.portfolio = tuple(0.001 + 1.5 * value for value in self.benchmark)

    def test_market_beta_is_ols_slope_with_intercept(self) -> None:
        self.assertAlmostEqual(market_beta(self.portfolio, self.benchmark), 1.5)

    def test_downside_beta_uses_only_strictly_negative_benchmark_periods(self) -> None:
        portfolio = (-0.05, -0.015, 0.50, 0.60)
        benchmark = (-0.02, -0.01, 0.00, 0.01)

        self.assertAlmostEqual(downside_beta(portfolio, benchmark), 3.5)

    def test_tracking_error_is_annualized_sample_active_return_volatility(self) -> None:
        portfolio = (0.02, 0.00, 0.04)
        benchmark = (0.01, 0.01, 0.01)
        # Active returns are 1%, -1%, 3%; sample standard deviation is 2%.
        self.assertAlmostEqual(
            tracking_error(portfolio, benchmark, periods_per_year=12),
            0.02 * math.sqrt(12),
        )

    def test_dataset_helpers_use_named_aligned_series(self) -> None:
        dataset = build_aligned_return_dataset(
            {
                "PORTFOLIO": {
                    "2026-01-01": 100,
                    "2026-01-02": 98,
                    "2026-01-03": 97.02,
                    "2026-01-04": 98.9604,
                },
                "NIFTY": {
                    "2026-01-01": 100,
                    "2026-01-02": 99,
                    "2026-01-03": 98.505,
                    "2026-01-04": 99.49005,
                },
            }
        )

        self.assertAlmostEqual(
            market_beta_from_dataset(dataset, "portfolio", "nifty"), 2.0
        )
        self.assertAlmostEqual(
            downside_beta_from_dataset(dataset, "portfolio", "nifty"), 2.0
        )
        self.assertAlmostEqual(
            tracking_error_from_dataset(
                dataset, "portfolio", "nifty", periods_per_year=1
            ),
            0.010408329997330674,
        )

    def test_rejects_misaligned_non_finite_and_degenerate_inputs(self) -> None:
        with self.assertRaisesRegex(ExposureMetricError, "equal length"):
            market_beta((0.1, 0.2), (0.1, 0.2, 0.3))
        with self.assertRaisesRegex(ExposureMetricError, "finite"):
            tracking_error((0.1, float("nan")), (0.1, 0.2))
        with self.assertRaisesRegex(ExposureMetricError, "zero benchmark variance"):
            market_beta((0.1, 0.2), (0.1, 0.1))
        with self.assertRaisesRegex(DownsideMetricError, "at least two"):
            downside_beta((-0.1, 0.1), (-0.1, 0.1))

    def test_validates_annualization_and_downside_threshold(self) -> None:
        with self.assertRaisesRegex(ExposureMetricError, "positive integer"):
            tracking_error((0.1, 0.2), (0.1, 0.2), periods_per_year=0)
        with self.assertRaisesRegex(DownsideMetricError, "finite"):
            downside_beta((0.1, 0.2), (0.1, 0.2), threshold=float("inf"))


if __name__ == "__main__":
    unittest.main()
