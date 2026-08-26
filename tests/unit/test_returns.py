import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.analytics.returns import (  # noqa: E402
    ReturnDataError,
    build_aligned_return_dataset,
    build_available_weight_portfolio_returns,
)


class AlignedReturnDatasetTests(unittest.TestCase):
    def test_aligns_prices_before_calculating_simple_returns(self) -> None:
        history = {
            "AAA": {
                "2026-01-01": 100,
                "2026-01-02": 110,
                "2026-01-03": 121,
            },
            "NIFTY": {
                "2026-01-01": 200,
                # Missing 2 January: the shared interval must be 1 -> 3 January.
                "2026-01-03": 220,
            },
        }

        result = build_aligned_return_dataset(history)

        self.assertEqual(result.price_dates, (date(2026, 1, 1), date(2026, 1, 3)))
        self.assertEqual(result.dates, (date(2026, 1, 3),))
        self.assertAlmostEqual(result.returns_for("aaa")[0], 0.21)
        self.assertAlmostEqual(result.returns_for("NIFTY")[0], 0.10)
        self.assertEqual(result.excluded_price_dates[0].date, date(2026, 1, 2))
        self.assertEqual(result.excluded_price_dates[0].missing_symbols, ("NIFTY",))

    def test_required_symbols_ignore_unneeded_series(self) -> None:
        history = {
            "AAA": {"2026-01-01": 100, "2026-01-02": 101},
            "NIFTY": {"2026-01-01": 200, "2026-01-02": 202},
            "UNUSED": {"2026-02-01": 1},
        }

        result = build_aligned_return_dataset(
            history, required_symbols=("AAA", "NIFTY")
        )

        self.assertEqual(result.symbols, ("AAA", "NIFTY"))
        self.assertEqual(result.observation_count, 1)

    def test_rejects_missing_required_history(self) -> None:
        history = {"AAA": {"2026-01-01": 100, "2026-01-02": 101}}

        with self.assertRaisesRegex(ReturnDataError, "missing required.*NIFTY"):
            build_aligned_return_dataset(history, required_symbols=("AAA", "NIFTY"))

    def test_rejects_non_positive_and_non_finite_prices(self) -> None:
        for invalid in (0, -1, float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                history = {"AAA": {"2026-01-01": 100, "2026-01-02": invalid}}
                with self.assertRaisesRegex(ReturnDataError, "finite and positive"):
                    build_aligned_return_dataset(history)

    def test_rejects_insufficient_overlap(self) -> None:
        history = {
            "AAA": {"2026-01-01": 100, "2026-01-02": 101},
            "NIFTY": {"2026-01-02": 200, "2026-01-03": 202},
        }

        with self.assertRaisesRegex(ReturnDataError, "fewer than two common"):
            build_aligned_return_dataset(history)

    def test_result_series_cannot_be_mutated(self) -> None:
        result = build_aligned_return_dataset(
            {"AAA": {"2026-01-01": 100, "2026-01-02": 101}}
        )

        with self.assertRaises(TypeError):
            result.returns["AAA"] = (0.5,)

    def test_available_weight_returns_include_pre_listing_history(self) -> None:
        result = build_available_weight_portfolio_returns(
            {
                "OLD": {
                    "2020-01-01": 100,
                    "2020-01-02": 90,
                    "2020-01-03": 99,
                },
                "IPO": {
                    "2020-01-02": 50,
                    "2020-01-03": 55,
                },
            },
            {"OLD": 0.8, "IPO": 0.2},
            price_dates=("2020-01-01", "2020-01-02", "2020-01-03"),
        )

        self.assertAlmostEqual(result.returns[0], -0.10)
        self.assertAlmostEqual(result.returns[1], 0.10)
        self.assertAlmostEqual(result.covered_weights[0], 0.8)
        self.assertAlmostEqual(result.covered_weights[1], 1.0)
        self.assertEqual(result.available_symbol_counts, (1, 2))
        self.assertEqual(result.incomplete_observation_count, 1)


if __name__ == "__main__":
    unittest.main()
