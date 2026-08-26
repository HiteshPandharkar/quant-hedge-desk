import csv
import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.portfolio import (  # noqa: E402
    Portfolio,
    PortfolioHolding,
    PortfolioValidationError,
)


def holding(symbol: str, quantity: str, price: str, market_value: str, weight: str):
    return {
        "portfolio_id": "ASTERIA-001",
        "as_of_date": "2026-01-30",
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "market_value": market_value,
        "portfolio_weight": weight,
        "sector": "Financials",
        "benchmark_weight": "0.20",
        "liquidity_bucket": "HIGH",
        "hedging_restriction": "NONE",
        "data_source": "TEST",
    }


class PortfolioDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            holding("AAA", "60", "10", "600", "60%"),
            holding("BBB", "20", "20", "400", "40%"),
        ]

    def test_valid_snapshot_reconciles(self) -> None:
        portfolio = Portfolio.from_holdings(self.rows, supplied_total_market_value="1000")

        self.assertEqual(portfolio.total_market_value, Decimal("1000"))
        self.assertEqual(portfolio.calculated_total_market_value, Decimal("1000"))
        self.assertEqual(portfolio.holding("aaa").symbol, "AAA")

    def test_models_are_immutable(self) -> None:
        portfolio = Portfolio.from_holdings(self.rows)
        with self.assertRaises(FrozenInstanceError):
            portfolio.portfolio_id = "OTHER"
        with self.assertRaises(FrozenInstanceError):
            portfolio.holdings[0].price = Decimal("11")

    def test_duplicate_symbols_are_rejected_after_normalization(self) -> None:
        self.rows[1]["symbol"] = "aaa"
        with self.assertRaisesRegex(PortfolioValidationError, "duplicate holdings: AAA"):
            Portfolio.from_holdings(self.rows)

    def test_position_market_value_must_reconcile(self) -> None:
        self.rows[0]["market_value"] = "500"
        with self.assertRaisesRegex(PortfolioValidationError, "quantity \\* price"):
            Portfolio.from_holdings(self.rows)

    def test_weights_must_sum_to_one(self) -> None:
        self.rows[1]["portfolio_weight"] = "30%"
        with self.assertRaisesRegex(PortfolioValidationError, "weights must sum"):
            Portfolio.from_holdings(self.rows)

    def test_each_weight_must_match_market_value(self) -> None:
        self.rows[0]["portfolio_weight"] = "50%"
        self.rows[1]["portfolio_weight"] = "50%"
        with self.assertRaisesRegex(PortfolioValidationError, "AAA portfolio_weight"):
            Portfolio.from_holdings(self.rows)

    def test_supplied_total_must_reconcile(self) -> None:
        with self.assertRaisesRegex(PortfolioValidationError, "supplied total"):
            Portfolio.from_holdings(self.rows, supplied_total_market_value="900")

    def test_unknown_or_missing_fields_are_rejected(self) -> None:
        row = self.rows[0].copy()
        row["unexpected"] = True
        with self.assertRaisesRegex(PortfolioValidationError, "unknown fields: unexpected"):
            PortfolioHolding.from_mapping(row)

        del self.rows[0]["sector"]
        with self.assertRaisesRegex(PortfolioValidationError, "missing: sector"):
            PortfolioHolding.from_mapping(self.rows[0])


class AsteriaPortfolioFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        path = ROOT / "cases" / "asteria_capital" / "portfolio.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            self.rows = list(csv.DictReader(stream))
        self.portfolio = Portfolio.from_holdings(
            self.rows,
            supplied_total_market_value="5000000000",
        )

    def test_reference_portfolio_matches_business_requirements(self) -> None:
        weights = sorted(
            (holding.portfolio_weight for holding in self.portfolio.holdings),
            reverse=True,
        )

        self.assertEqual(self.portfolio.portfolio_id, "ASTERIA-001")
        self.assertEqual(self.portfolio.as_of_date.isoformat(), "2026-01-30")
        self.assertGreaterEqual(len(self.portfolio.holdings), 40)
        self.assertLessEqual(len(self.portfolio.holdings), 60)
        self.assertEqual(self.portfolio.total_market_value, Decimal("5000000000"))
        self.assertLessEqual(weights[0], Decimal("0.10"))
        self.assertGreaterEqual(sum(weights[:5]), Decimal("0.30"))
        self.assertLessEqual(sum(weights[:5]), Decimal("0.40"))

    def test_reference_portfolio_has_intended_basis_risk(self) -> None:
        financials = sum(
            holding.portfolio_weight
            for holding in self.portfolio.holdings
            if holding.sector == "Financials"
        )
        industrials = sum(
            holding.portfolio_weight
            for holding in self.portfolio.holdings
            if holding.sector == "Industrials"
        )
        non_core_index = sum(
            holding.portfolio_weight
            for holding in self.portfolio.holdings
            if holding.benchmark_weight == 0
        )

        self.assertGreater(financials, Decimal("0.30"))
        self.assertGreater(industrials, Decimal("0.15"))
        self.assertGreaterEqual(non_core_index, Decimal("0.15"))


if __name__ == "__main__":
    unittest.main()
