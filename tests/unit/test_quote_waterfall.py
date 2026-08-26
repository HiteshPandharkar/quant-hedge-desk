import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.pricing import QuoteWaterfall, QuoteWaterfallError  # noqa: E402


class QuoteWaterfallTests(unittest.TestCase):
    @staticmethod
    def values(**overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "clean_value_inr": "10000000",
            "initial_hedge_execution_cost_inr": "100000",
            "expected_rehedging_cost_inr": "200000",
            "liquidity_reserve_inr": "300000",
            "model_reserve_inr": "400000",
            "capital_funding_estimate_inr": "500000",
            "dealer_margin_inr": "600000",
        }
        values.update(overrides)
        return values

    def test_derives_client_premium_from_all_seven_components(self) -> None:
        waterfall = QuoteWaterfall(**self.values())

        self.assertEqual(waterfall.total_adjustments_inr, Decimal("2100000"))
        self.assertEqual(
            waterfall.calculated_client_premium_inr, Decimal("12100000")
        )
        self.assertEqual(waterfall.quoted_client_premium_inr, Decimal("12100000"))
        self.assertEqual(waterfall.reconciliation_difference_inr, Decimal("0"))
        self.assertTrue(waterfall.reconciled)

    def test_accepts_only_currency_rounding_difference(self) -> None:
        waterfall = QuoteWaterfall(
            **self.values(quoted_client_premium_inr="12100000.01")
        )
        self.assertEqual(waterfall.reconciliation_difference_inr, Decimal("0.01"))

        with self.assertRaisesRegex(QuoteWaterfallError, "does not reconcile"):
            QuoteWaterfall(
                **self.values(quoted_client_premium_inr="12100000.02")
            )

    def test_rejects_negative_or_non_finite_amounts(self) -> None:
        for value in ("-0.01", "NaN", "Infinity", True):
            with self.subTest(value=value):
                with self.assertRaises(QuoteWaterfallError):
                    QuoteWaterfall(**self.values(dealer_margin_inr=value))

    def test_mapping_and_serialization_preserve_reconciliation(self) -> None:
        waterfall = QuoteWaterfall.from_mapping(self.values())

        result = waterfall.to_dict()
        self.assertEqual(result["clean_value_inr"], "10000000")
        self.assertEqual(result["calculated_client_premium_inr"], "12100000")
        self.assertEqual(result["reconciliation_difference_inr"], "0")
        self.assertTrue(result["reconciled"])

    def test_mapping_rejects_unknown_fields(self) -> None:
        with self.assertRaisesRegex(QuoteWaterfallError, "unknown fields"):
            QuoteWaterfall.from_mapping(self.values(unexplained_charge_inr="1"))


if __name__ == "__main__":
    unittest.main()
