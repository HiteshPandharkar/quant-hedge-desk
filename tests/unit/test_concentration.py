import csv
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.analytics.concentration import (  # noqa: E402
    ConcentrationMetricError,
    calculate_concentration_metrics,
    concentration_ratio,
    herfindahl_hirschman_index,
)
from quant_hedge_desk.domain.portfolio import Portfolio  # noqa: E402


def holding(symbol: str, weight: str, sector: str):
    market_value = Decimal(weight) * 1000
    return {
        "portfolio_id": "TEST",
        "as_of_date": "2026-01-30",
        "symbol": symbol,
        "quantity": str(market_value),
        "price": "1",
        "market_value": str(market_value),
        "portfolio_weight": weight,
        "sector": sector,
        "benchmark_weight": "0",
        "liquidity_bucket": "HIGH",
        "hedging_restriction": "NONE",
        "data_source": "TEST",
    }


class ConcentrationMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.portfolio = Portfolio.from_holdings(
            (
                holding("AAA", "0.40", "Banks"),
                holding("BBB", "0.30", "Industrials"),
                holding("CCC", "0.20", "Banks"),
                holding("DDD", "0.10", "Technology"),
            )
        )

    def test_calculates_ranked_name_and_sector_metrics(self) -> None:
        result = calculate_concentration_metrics(
            self.portfolio,
            top_n=2,
            single_name_limit="30%",
            top_n_minimum=None,
            top_n_maximum="75%",
        )

        self.assertEqual(result.top_n_weight, Decimal("0.70"))
        self.assertEqual(result.largest_holding.symbol, "AAA")
        self.assertEqual(result.largest_sector.sector, "Banks")
        self.assertEqual(result.largest_sector.weight, Decimal("0.60"))
        self.assertEqual(result.holding_hhi, Decimal("0.30"))
        self.assertEqual(result.effective_holding_count, Decimal("1") / Decimal("0.30"))
        self.assertEqual(result.sector_hhi, Decimal("0.46"))
        self.assertEqual([item.symbol for item in result.single_name_breaches], ["AAA"])
        self.assertFalse(result.single_name_limit_passed)
        self.assertTrue(result.top_n_range_passed)

    def test_limit_is_inclusive_and_unbounded_range_is_not_assessed(self) -> None:
        result = calculate_concentration_metrics(
            self.portfolio,
            single_name_limit="40%",
            top_n_minimum=None,
            top_n_maximum=None,
        )

        self.assertTrue(result.single_name_limit_passed)
        self.assertIsNone(result.top_n_range_passed)

    def test_low_level_metrics_validate_parameters(self) -> None:
        self.assertEqual(concentration_ratio(self.portfolio, 99), Decimal("1.00"))
        self.assertEqual(
            herfindahl_hirschman_index((Decimal("0.5"), Decimal("0.5"))),
            Decimal("0.50"),
        )
        with self.assertRaisesRegex(ConcentrationMetricError, "positive integer"):
            concentration_ratio(self.portfolio, 0)
        with self.assertRaisesRegex(ConcentrationMetricError, "sum to 1"):
            herfindahl_hirschman_index((Decimal("0.4"), Decimal("0.5")))
        with self.assertRaisesRegex(ConcentrationMetricError, "cannot exceed"):
            calculate_concentration_metrics(
                self.portfolio, top_n_minimum="50%", top_n_maximum="40%"
            )

    def test_hhi_accepts_the_same_weight_tolerance_as_portfolio_reconciliation(self) -> None:
        result = herfindahl_hirschman_index([Decimal("0.5"), Decimal("0.49995")])

        self.assertEqual(result, Decimal("0.5") ** 2 + Decimal("0.49995") ** 2)


class AsteriaConcentrationTests(unittest.TestCase):
    def test_reference_portfolio_meets_week_one_design_limits(self) -> None:
        path = ROOT / "cases" / "asteria_capital" / "portfolio.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            portfolio = Portfolio.from_holdings(csv.DictReader(stream))

        result = calculate_concentration_metrics(portfolio)

        self.assertEqual(result.holding_count, len(portfolio.holdings))
        self.assertLessEqual(result.largest_holding.weight, Decimal("0.10"))
        self.assertTrue(result.single_name_limit_passed)
        self.assertTrue(result.top_n_range_passed)
        self.assertGreater(result.effective_holding_count, Decimal("1"))
        self.assertGreater(result.sector_count, 1)


if __name__ == "__main__":
    unittest.main()
