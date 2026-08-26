import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.desk_limits import (  # noqa: E402
    DeskLimitSet,
    DeskLimitsValidationError,
)
from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402


class DeskLimitsSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        path = ROOT / "cases" / "asteria_capital" / "desk_limits.yaml"
        self.raw = load_yaml_mapping(path)

    def test_reference_limits_match_business_requirements(self) -> None:
        desk = DeskLimitSet.from_mapping(self.raw)

        self.assertEqual(desk.limits.max_absolute_net_index_delta_inr, Decimal("150000000"))
        self.assertEqual(desk.limits.max_one_month_vega_inr_per_vol_point, Decimal("2500000"))
        self.assertEqual(desk.limits.max_six_month_vega_inr_per_vol_point, Decimal("6000000"))
        self.assertEqual(desk.limits.max_crash_stress_loss_inr, Decimal("50000000"))
        self.assertEqual(desk.limits.warning_utilization, Decimal("0.80"))

    def test_limits_are_immutable(self) -> None:
        desk = DeskLimitSet.from_mapping(self.raw)
        with self.assertRaises(FrozenInstanceError):
            desk.limits.max_liquidation_trading_days = 5

    def test_unknown_fields_are_rejected(self) -> None:
        self.raw["limits"]["unexpected"] = True
        with self.assertRaisesRegex(DeskLimitsValidationError, "unknown fields: unexpected"):
            DeskLimitSet.from_mapping(self.raw)

    def test_invalid_warning_utilization_is_rejected(self) -> None:
        self.raw["limits"]["warning_utilization"] = "1.01"
        with self.assertRaisesRegex(DeskLimitsValidationError, r"\(0, 1\]"):
            DeskLimitSet.from_mapping(self.raw)


if __name__ == "__main__":
    unittest.main()
