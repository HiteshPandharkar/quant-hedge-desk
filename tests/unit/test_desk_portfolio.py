import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402
from quant_hedge_desk.domain.models.desk_portfolio import (  # noqa: E402
    DeskPortfolio,
    DeskPortfolioValidationError,
)
from quant_hedge_desk.domain.enums import InstrumentType, Underlying  # noqa: E402


class DeskPortfolioSchemaTests(unittest.TestCase):
    def load_state(self, name: str) -> DeskPortfolio:
        raw = load_yaml_mapping(
            ROOT / "cases" / "asteria_capital" / f"desk_portfolio_{name}.yaml"
        )
        return DeskPortfolio.from_mapping(raw)

    def test_available_capacity_snapshot_aggregates_signed_risk(self) -> None:
        portfolio = self.load_state("capacity_available")

        self.assertEqual(len(portfolio.positions), 2)
        self.assertEqual(portfolio.positions[0].underlying, Underlying.NIFTY)
        self.assertEqual(portfolio.positions[0].instrument_type, InstrumentType.OPTION)
        self.assertEqual(
            portfolio.aggregate_risk.net_index_delta_inr, Decimal("-15000000")
        )
        self.assertEqual(
            portfolio.aggregate_risk.six_month_vega_inr_per_vol_point,
            Decimal("600000"),
        )
        self.assertEqual(
            portfolio.aggregate_risk.crash_stress_pnl_inr, Decimal("5000000")
        )

    def test_constrained_state_has_less_available_capacity(self) -> None:
        portfolio = self.load_state("capacity_constrained")

        self.assertEqual(
            portfolio.aggregate_risk.net_index_delta_inr, Decimal("125000000")
        )
        self.assertEqual(
            portfolio.aggregate_risk.six_month_vega_inr_per_vol_point,
            Decimal("5300000"),
        )
        self.assertEqual(
            portfolio.aggregate_risk.crash_stress_pnl_inr, Decimal("-45000000")
        )

    def test_models_are_immutable(self) -> None:
        portfolio = self.load_state("capacity_available")
        with self.assertRaises(FrozenInstanceError):
            portfolio.market_snapshot_id = "other"
        with self.assertRaises(FrozenInstanceError):
            portfolio.positions[0].risk.net_index_delta_inr = Decimal("0")

    def test_duplicate_position_ids_are_rejected(self) -> None:
        raw = load_yaml_mapping(
            ROOT
            / "cases"
            / "asteria_capital"
            / "desk_portfolio_capacity_available.yaml"
        )
        raw["positions"][1]["position_id"] = raw["positions"][0]["position_id"]

        with self.assertRaisesRegex(
            DeskPortfolioValidationError, "duplicate position ids"
        ):
            DeskPortfolio.from_mapping(raw)

    def test_naive_valuation_timestamp_is_rejected(self) -> None:
        raw = load_yaml_mapping(
            ROOT
            / "cases"
            / "asteria_capital"
            / "desk_portfolio_capacity_available.yaml"
        )
        raw["valuation_timestamp"] = "2026-01-30T15:30:00"

        with self.assertRaisesRegex(DeskPortfolioValidationError, "UTC offset"):
            DeskPortfolio.from_mapping(raw)

    def test_unknown_position_fields_are_rejected(self) -> None:
        raw = load_yaml_mapping(
            ROOT
            / "cases"
            / "asteria_capital"
            / "desk_portfolio_capacity_available.yaml"
        )
        raw["positions"][0]["unexpected"] = True

        with self.assertRaisesRegex(DeskPortfolioValidationError, "unexpected"):
            DeskPortfolio.from_mapping(raw)


if __name__ == "__main__":
    unittest.main()
