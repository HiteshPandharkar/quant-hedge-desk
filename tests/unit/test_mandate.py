import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.mandate import (  # noqa: E402
    Mandate,
    MandateValidationError,
    SoftObjective,
)
from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402


class MandateSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        path = ROOT / "cases" / "asteria_capital" / "mandate.yaml"
        self.raw = load_yaml_mapping(path)

    def test_reference_mandate_matches_business_requirements(self) -> None:
        mandate = Mandate.from_mapping(self.raw)

        self.assertEqual(mandate.client.cost.max_all_in_premium_fraction, Decimal("0.025"))
        self.assertEqual(mandate.client.protection.expected_shortfall_confidence, Decimal("0.99"))
        self.assertEqual(mandate.client.protection.max_expected_shortfall_loss, Decimal("0.12"))
        self.assertEqual(mandate.client.upside.max_sacrifice_percentage_points, Decimal("0.06"))
        self.assertEqual(mandate.client.soft_objectives[0], SoftObjective.RESIDUAL_EXPECTED_SHORTFALL)

    def test_models_are_immutable(self) -> None:
        mandate = Mandate.from_mapping(self.raw)
        with self.assertRaises(FrozenInstanceError):
            mandate.client.reporting_currency = "USD"
        with self.assertRaises(TypeError):
            mandate.client.interpretations["protection"] = None

    def test_unknown_fields_are_rejected(self) -> None:
        self.raw["unexpected"] = True
        with self.assertRaisesRegex(MandateValidationError, "unknown fields: unexpected"):
            Mandate.from_mapping(self.raw)

    def test_horizon_requires_an_approved_expiry(self) -> None:
        self.raw["client"]["eligibility"]["approved_expiry_months"] = [3]
        with self.assertRaisesRegex(MandateValidationError, "hedge horizon"):
            Mandate.from_mapping(self.raw)

    def test_invalid_fraction_is_rejected(self) -> None:
        self.raw["client"]["cost"]["max_all_in_premium_fraction"] = "1.01"
        with self.assertRaisesRegex(MandateValidationError, r"\[0, 1\]"):
            Mandate.from_mapping(self.raw)


if __name__ == "__main__":
    unittest.main()
