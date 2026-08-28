import json
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.analytics.returns import (  # noqa: E402
    build_aligned_return_dataset,
    build_available_weight_portfolio_returns,
)
from quant_hedge_desk.application.assess_candidate_hedge import _rolling_returns  # noqa: E402
from quant_hedge_desk.data.loaders import load_portfolio_csv, load_yaml_mapping  # noqa: E402
from quant_hedge_desk.data.repositories import AdjustedCloseCSVRepository  # noqa: E402
from quant_hedge_desk.domain.mandate import Mandate  # noqa: E402
from quant_hedge_desk.domain.models.rebalancing import RebalancingStressPolicy  # noqa: E402
from quant_hedge_desk.domain.models.scenario_contracts import (  # noqa: E402
    OptionMark,
    ScenarioPath,
    ScenarioSet,
    ScenarioStep,
)
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate  # noqa: E402
from quant_hedge_desk.hedge_design.rebalancing_stress import (  # noqa: E402
    evaluate_rebalancing_path,
)
from quant_hedge_desk.hedge_design.stress_evaluator import (  # noqa: E402
    evaluate_candidate_stresses,
)


CASE = ROOT / "cases" / "asteria_capital"


class SequentialRebalancingStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = HedgeCandidate.from_mapping(
            load_yaml_mapping(CASE / "candidate_03_nifty_protective_put.yaml")
        )
        cls.portfolio = load_portfolio_csv(
            CASE / "portfolio.csv", supplied_total_market_value=5_000_000_000
        )
        cls.mandate = Mandate.from_mapping(load_yaml_mapping(CASE / "mandate.yaml"))
        eligible = tuple(
            item.value for item in cls.mandate.client.eligibility.underlyings
        )
        holdings = tuple(item.symbol for item in cls.portfolio.holdings)
        history = AdjustedCloseCSVRepository().load(
            ROOT / "data" / "market" / "eod_prices.csv",
            required_symbols=(*holdings, *eligible),
            end_date=cls.portfolio.as_of_date,
        )
        dataset = build_aligned_return_dataset(history, required_symbols=eligible)
        portfolio_history = build_available_weight_portfolio_returns(
            history,
            {
                holding.symbol: holding.portfolio_weight
                for holding in cls.portfolio.holdings
            },
            price_dates=dataset.price_dates,
        )
        horizon = cls.mandate.client.protection.horizon_months * 21
        cls.portfolio_returns = _rolling_returns(
            portfolio_history.returns, horizon
        )
        cls.underlying_returns = {
            "NIFTY": _rolling_returns(dataset.returns_for("NIFTY"), horizon)
        }
        cls.policy = RebalancingStressPolicy(
            "sequential-explicit-test", "1", "0.01", 5, "EXPLICIT_MARKS"
        )
        leg = cls.candidate.legs[0]
        cls.mark = OptionMark(
            leg.underlying,
            leg.expiry,
            leg.strike_or_level,
            leg.option_type,
            "686.03",
        )

    def path(self, allowed: tuple[bool, ...]) -> ScenarioPath:
        steps = []
        for index, is_allowed in enumerate(allowed, start=1):
            steps.append(
                ScenarioStep(
                    index,
                    {
                        "NIFTY": "0",
                        "PORTFOLIO": "-0.02" if index == 1 else "0",
                    },
                    rebalancing_allowed=is_allowed,
                    option_marks=(self.mark,),
                )
            )
        return ScenarioPath("sequential", "Sequential resize", tuple(steps))

    def evaluate_path(self, allowed: tuple[bool, ...]):
        return evaluate_rebalancing_path(
            scenario=self.path(allowed),
            portfolio=self.portfolio,
            candidate=self.candidate,
            mandate=self.mandate,
            policy=self.policy,
            portfolio_horizon_returns=self.portfolio_returns,
            underlying_horizon_returns=self.underlying_returns,
        )

    def test_immediate_fill_reconciles_terminal_return_and_cash_flows(self) -> None:
        result = self.evaluate_path((True, True))

        self.assertTrue(result.passed)
        self.assertEqual(len(result.events), 1)
        self.assertIsNone(result.events[0].failure_reason)
        self.assertEqual(result.maximum_delay_trading_days, 0)
        expected_return = (
            self.portfolio.total_market_value * Decimal("0.98")
            + result.terminal_payoff
            + result.cash_ledger.net_cash_flow
        ) / self.portfolio.total_market_value - 1
        self.assertEqual(result.hedged_return, expected_return)

    def test_deferred_fill_completes_late_but_remains_a_failure(self) -> None:
        first, second, terminal = self.path((False, True, True)).steps
        scenario = ScenarioPath(
            "deferred",
            "Deferred without a blocked-step mark",
            (replace(first, option_marks=()), second, terminal),
        )
        result = evaluate_rebalancing_path(
            scenario=scenario,
            portfolio=self.portfolio,
            candidate=self.candidate,
            mandate=self.mandate,
            policy=self.policy,
            portfolio_horizon_returns=self.portfolio_returns,
            underlying_horizon_returns=self.underlying_returns,
        )

        self.assertFalse(result.passed)
        self.assertEqual(len(result.events), 2)
        self.assertEqual(result.events[0].failure_reason, "REBALANCING_NOT_ALLOWED")
        self.assertEqual(result.events[1].delay_trading_days, 1)
        self.assertIsNone(result.events[1].failure_reason)
        self.assertTrue(any("after 1 trading days" in item for item in result.failure_reasons))

    def test_pending_target_and_price_are_recalculated_when_trading_resumes(self) -> None:
        first, second, terminal = self.path((False, True, True)).steps
        second = replace(
            second,
            asset_returns={"NIFTY": Decimal("0"), "PORTFOLIO": Decimal("-0.02")},
            option_marks=(replace(self.mark, mark=Decimal("650")),),
        )
        scenario = ScenarioPath(
            "recalculated", "Recalculated pending target", (first, second, terminal)
        )

        result = evaluate_rebalancing_path(
            scenario=scenario,
            portfolio=self.portfolio,
            candidate=self.candidate,
            mandate=self.mandate,
            policy=self.policy,
            portfolio_horizon_returns=self.portfolio_returns,
            underlying_horizon_returns=self.underlying_returns,
        )

        self.assertNotEqual(
            result.events[0].target_quantities, result.events[1].target_quantities
        )
        self.assertNotEqual(result.events[1].premium_cash_flow, Decimal("0"))

    def test_pricing_failure_is_carried_forward_and_recorded(self) -> None:
        first, second, terminal = self.path((True, True, True)).steps
        scenario = ScenarioPath(
            "repriced",
            "Missing then available price",
            (replace(first, option_marks=()), second, terminal),
        )

        result = evaluate_rebalancing_path(
            scenario=scenario,
            portfolio=self.portfolio,
            candidate=self.candidate,
            mandate=self.mandate,
            policy=self.policy,
            portfolio_horizon_returns=self.portfolio_returns,
            underlying_horizon_returns=self.underlying_returns,
        )

        self.assertIn("PRICING_REJECTED", result.events[0].failure_reason)
        self.assertEqual(result.events[1].delay_trading_days, 1)
        self.assertFalse(result.passed)

    def test_blocked_request_is_reported_unresolved_at_terminal_step(self) -> None:
        result = self.evaluate_path((False, False, True))

        self.assertFalse(result.passed)
        self.assertEqual(result.maximum_delay_trading_days, 2)
        self.assertTrue(
            any("UNRESOLVED_REBALANCE" in item for item in result.failure_reasons)
        )

    def test_capacity_limited_request_remains_incomplete(self) -> None:
        first, terminal = self.path((True, True)).steps
        constrained = replace(
            first, market_volume_multipliers={"NIFTY": Decimal("0.001")}
        )
        scenario = ScenarioPath(
            "incomplete", "Capacity-limited resize", (constrained, terminal)
        )

        result = evaluate_rebalancing_path(
            scenario=scenario,
            portfolio=self.portfolio,
            candidate=self.candidate,
            mandate=self.mandate,
            policy=self.policy,
            portfolio_horizon_returns=self.portfolio_returns,
            underlying_horizon_returns=self.underlying_returns,
        )

        self.assertFalse(result.passed)
        self.assertIn("FEASIBILITY_REJECTED", result.events[0].failure_reason)
        self.assertTrue(
            any("UNRESOLVED_REBALANCE" in item for item in result.failure_reasons)
        )

    def test_release_gate_changes_result_while_diagnostic_mode_does_not(self) -> None:
        scenario_set = ScenarioSet(
            "sequential-set",
            "1",
            "NAMED_STRESS",
            self.portfolio.as_of_date,
            3,
            (self.path((False, True, True)),),
            "test/1",
        )
        common = {
            "scenario_set": scenario_set,
            "portfolio": self.portfolio,
            "candidate": self.candidate,
            "mandate": self.mandate,
            "maximum_correlation_basis_gap": "1",
            "portfolio_horizon_returns": self.portfolio_returns,
            "underlying_horizon_returns": self.underlying_returns,
        }

        gated = evaluate_candidate_stresses(
            **common, rebalancing_policy=self.policy
        )
        diagnostic = evaluate_candidate_stresses(
            **common,
            rebalancing_policy=replace(
                self.policy, rebalancing_failure_is_release_gate=False
            ),
        )

        self.assertFalse(gated.passed)
        self.assertTrue(diagnostic.passed)
        self.assertFalse(diagnostic.rebalancing_pass)
        self.assertIn("Diagnostic only", diagnostic.usage_restrictions[-1])
        json.dumps(gated.to_dict())


if __name__ == "__main__":
    unittest.main()
