import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402
from quant_hedge_desk.domain.dealer_risk import (  # noqa: E402
    ProposedTradeRisk,
    RiskLimitStatus,
    assess_dealer_risk,
)
from quant_hedge_desk.domain.desk_limits import DeskLimitSet  # noqa: E402
from quant_hedge_desk.domain.models.desk_portfolio import (  # noqa: E402
    DeskPortfolio,
    DeskRiskExposure,
)


class DealerRiskMandateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        case = ROOT / "cases" / "asteria_capital"
        cls.mandate = DeskLimitSet.from_mapping(
            load_yaml_mapping(case / "desk_limits.yaml")
        )
        cls.available = DeskPortfolio.from_mapping(
            load_yaml_mapping(case / "desk_portfolio_capacity_available.yaml")
        )
        cls.constrained = DeskPortfolio.from_mapping(
            load_yaml_mapping(case / "desk_portfolio_capacity_constrained.yaml")
        )

    @staticmethod
    def trade(**overrides: object) -> ProposedTradeRisk:
        values = {
            "exposure": DeskRiskExposure(
                "50000000", "500000", "500000", "-10000000"
            ),
            "market_participation": "5%",
            "liquidation_trading_days": 2,
            "model_reserve_inr": "1000000",
            "clean_value_inr": "10000000",
        }
        values.update(overrides)
        return ProposedTradeRisk(**values)

    def test_available_capacity_approves_and_reports_post_trade_risk(self) -> None:
        result = assess_dealer_risk(self.available, self.trade(), self.mandate)

        self.assertTrue(result.approved)
        self.assertEqual(
            result.post_trade_risk.net_index_delta_inr, Decimal("35000000")
        )
        self.assertEqual(len(result.diagnostics), 7)
        self.assertFalse(result.breaches)

    def test_constrained_inventory_is_included_in_limit_enforcement(self) -> None:
        result = assess_dealer_risk(self.constrained, self.trade(), self.mandate)

        self.assertFalse(result.approved)
        breached = {item.measure for item in result.breaches}
        self.assertIn("absolute_net_index_delta_inr", breached)
        self.assertIn("crash_stress_loss_inr", breached)

    def test_warning_level_is_inclusive(self) -> None:
        trade = self.trade(
            exposure=DeskRiskExposure("135000000", "0", "0", "0")
        )
        result = assess_dealer_risk(self.available, trade, self.mandate)
        delta = next(
            item
            for item in result.diagnostics
            if item.measure == "absolute_net_index_delta_inr"
        )

        self.assertEqual(delta.after_utilization, Decimal("0.8"))
        self.assertEqual(delta.status, RiskLimitStatus.WARNING)
        self.assertTrue(result.approved)

    def test_netting_can_release_risk_capacity(self) -> None:
        trade = self.trade(
            exposure=DeskRiskExposure("-50000000", "0", "0", "10000000")
        )
        result = assess_dealer_risk(self.constrained, trade, self.mandate)
        delta = next(
            item
            for item in result.diagnostics
            if item.measure == "absolute_net_index_delta_inr"
        )

        self.assertEqual(delta.incremental, Decimal("-50000000"))
        self.assertEqual(delta.after, Decimal("75000000"))

    def test_trade_specific_liquidity_and_reserve_limits_are_enforced(self) -> None:
        result = assess_dealer_risk(
            self.available,
            self.trade(
                market_participation="11%",
                liquidation_trading_days=4,
                model_reserve_inr="1600000",
            ),
            self.mandate,
        )

        self.assertEqual(
            {item.measure for item in result.breaches},
            {"market_participation", "liquidation_trading_days", "model_reserve_inr"},
        )


if __name__ == "__main__":
    unittest.main()
