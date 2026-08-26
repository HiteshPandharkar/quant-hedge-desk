import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.calculations.scenario_math import (  # noqa: E402
    compound_simple_returns,
    scenario_probability_weights,
)


class ScenarioCalculationTests(unittest.TestCase):
    def test_compounds_simple_returns(self) -> None:
        self.assertEqual(
            compound_simple_returns((Decimal("-0.10"), Decimal("0.05"))),
            Decimal("-0.055"),
        )

    def test_uses_explicit_or_equal_probability_weights(self) -> None:
        self.assertEqual(
            scenario_probability_weights((Decimal("0.25"), Decimal("0.75"))),
            (Decimal("0.25"), Decimal("0.75")),
        )
        self.assertEqual(
            scenario_probability_weights((None, None)),
            (Decimal("0.5"), Decimal("0.5")),
        )

    def test_rejects_empty_probability_collection(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            scenario_probability_weights(())

    def test_rejects_partially_supplied_probabilities(self) -> None:
        with self.assertRaisesRegex(ValueError, "every scenario or none"):
            scenario_probability_weights((Decimal("0.5"), None))


if __name__ == "__main__":
    unittest.main()
