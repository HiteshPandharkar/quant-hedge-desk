import sys
import unittest
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
from quant_hedge_desk.domain.models.rebalancing import (  # noqa: E402
    CashLedger,
    PositionState,
    RebalanceProposal,
)
from quant_hedge_desk.domain.models.scenario_contracts import ScenarioStep  # noqa: E402
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate  # noqa: E402
from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus  # noqa: E402
from quant_hedge_desk.hedge_design.constraints import assess_candidate_constraints  # noqa: E402
from quant_hedge_desk.hedge_design.rebalancing import (  # noqa: E402
    contract_id_for_leg,
    execute_rebalance_proposal,
    initial_cash_ledger,
    initial_position,
    stressed_execution_cost,
    structure_preserving_fill,
)


CASE = ROOT / "cases" / "asteria_capital"


class RebalancingExecutionTests(unittest.TestCase):
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
        holding_symbols = tuple(item.symbol for item in cls.portfolio.holdings)
        history = AdjustedCloseCSVRepository().load(
            ROOT / "data" / "market" / "eod_prices.csv",
            required_symbols=(*holding_symbols, *eligible),
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
        cls.portfolio_returns = _rolling_returns(portfolio_history.returns, horizon)
        cls.underlying_returns = {
            "NIFTY": _rolling_returns(dataset.returns_for("NIFTY"), horizon)
        }

    def proposal(self, change: int, price: str = "800") -> RebalanceProposal:
        position = initial_position(self.candidate)
        contract_id = next(iter(position.quantities))
        current = position.quantities[contract_id]
        return RebalanceProposal(
            candidate_id=self.candidate.candidate_id,
            step_number=1,
            trigger_type="EXCEPTIONAL",
            current_quantities=position.quantities,
            target_quantities={contract_id: current + change},
            requested_changes={contract_id: change},
            option_prices={contract_id: price},
        )

    def execute(self, proposal: RebalanceProposal, step: ScenarioStep):
        return execute_rebalance_proposal(
            self.candidate,
            initial_position(self.candidate),
            initial_cash_ledger(self.candidate),
            proposal,
            step,
            scenario_id="sprint-3-test",
            mandate=self.mandate,
            portfolio=self.portfolio,
            current_underlying_levels=self.candidate.initial_levels,
            portfolio_horizon_returns=self.portfolio_returns,
            underlying_horizon_returns=self.underlying_returns,
        )

    def test_in_memory_assessment_uses_position_and_cumulative_cost_basis(self) -> None:
        position = initial_position(self.candidate)
        contract_id = next(iter(position.quantities))
        smaller = PositionState(
            self.candidate.candidate_id,
            {contract_id: position.quantities[contract_id] // 2},
        )
        ledger = CashLedger(premium_paid="50000000", execution_cost="6000000")

        result = assess_candidate_constraints(
            candidate=self.candidate,
            mandate=self.mandate,
            portfolio=self.portfolio,
            portfolio_horizon_returns=self.portfolio_returns,
            underlying_horizon_returns=self.underlying_returns,
            position=smaller,
            cumulative_cost_basis=ledger,
        )

        self.assertEqual(result.net_option_premium, Decimal("50000000"))
        self.assertEqual(result.estimated_execution_cost, Decimal("6000000"))
        self.assertLess(result.protected_reference_notional, Decimal("3000000000"))

    def test_stressed_cost_scales_inception_rate_and_spread(self) -> None:
        contract_id = contract_id_for_leg(self.candidate.legs[0])
        normal = stressed_execution_cost(
            self.candidate,
            {contract_id: 100},
            current_underlying_levels=self.candidate.initial_levels,
            spread_multipliers={},
        )
        stressed = stressed_execution_cost(
            self.candidate,
            {contract_id: 100},
            current_underlying_levels=self.candidate.initial_levels,
            spread_multipliers={"NIFTY": "2.5"},
        )

        self.assertEqual(stressed, normal * Decimal("2.5"))

    def test_capacity_returns_full_partial_and_zero_common_bundles(self) -> None:
        contract_id = contract_id_for_leg(self.candidate.legs[0])
        full, full_ratio = structure_preserving_fill(
            self.candidate,
            {contract_id: 100},
            mandate=self.mandate,
            market_volume_multipliers={},
        )
        partial, partial_ratio = structure_preserving_fill(
            self.candidate,
            {contract_id: 40_000},
            mandate=self.mandate,
            market_volume_multipliers={},
        )
        zero, zero_ratio = structure_preserving_fill(
            self.candidate,
            {contract_id: 100},
            mandate=self.mandate,
            market_volume_multipliers={"NIFTY": "0.000001"},
        )

        self.assertEqual(full[contract_id], 100)
        self.assertEqual(full_ratio, Decimal("1"))
        self.assertGreater(partial[contract_id], 0)
        self.assertLess(partial_ratio, Decimal("1"))
        self.assertEqual(zero[contract_id], 0)
        self.assertEqual(zero_ratio, Decimal("0"))

    def test_feasible_full_fill_commits_position_and_cash_ledger(self) -> None:
        proposal = self.proposal(10)
        result = self.execute(
            proposal,
            ScenarioStep(
                1,
                {"NIFTY": "0", "PORTFOLIO": "0"},
                bid_ask_spread_multipliers={"NIFTY": "1.5"},
            ),
        )

        self.assertTrue(result.committed)
        self.assertEqual(result.fill_ratio, Decimal("1"))
        self.assertEqual(result.feasibility.status, FeasibilityStatus.FEASIBLE)
        self.assertGreater(
            result.cash_ledger.premium_paid,
            initial_cash_ledger(self.candidate).premium_paid,
        )
        self.assertIsNone(result.event.failure_reason)

    def test_infeasible_fill_leaves_position_and_ledger_unchanged(self) -> None:
        position = initial_position(self.candidate)
        ledger = initial_cash_ledger(self.candidate)
        result = self.execute(
            self.proposal(10, price="1000000"),
            ScenarioStep(1, {"NIFTY": "0", "PORTFOLIO": "0"}),
        )

        self.assertFalse(result.committed)
        self.assertEqual(result.position, position)
        self.assertEqual(result.cash_ledger, ledger)
        self.assertEqual(result.feasibility.status, FeasibilityStatus.INFEASIBLE)
        self.assertIn("FEASIBILITY_REJECTED", result.event.failure_reason)

    def test_capacity_limited_partial_fill_is_rejected_when_position_is_infeasible(self) -> None:
        position = initial_position(self.candidate)
        ledger = initial_cash_ledger(self.candidate)
        result = self.execute(
            self.proposal(40_000),
            ScenarioStep(1, {"NIFTY": "0", "PORTFOLIO": "0"}),
        )

        self.assertFalse(result.committed)
        self.assertEqual(result.position, position)
        self.assertEqual(result.cash_ledger, ledger)
        self.assertEqual(result.feasibility.status, FeasibilityStatus.INFEASIBLE)
        self.assertIn("LIQUIDITY", result.feasibility.failed_constraints)
        self.assertEqual(set(result.event.filled_changes.values()), {0})

    def test_zero_capacity_leaves_position_and_ledger_unchanged(self) -> None:
        position = initial_position(self.candidate)
        ledger = initial_cash_ledger(self.candidate)
        result = self.execute(
            self.proposal(100),
            ScenarioStep(
                1,
                {"NIFTY": "0", "PORTFOLIO": "0"},
                market_volume_multipliers={"NIFTY": "0.000001"},
            ),
        )

        self.assertFalse(result.committed)
        self.assertEqual(result.position, position)
        self.assertEqual(result.cash_ledger, ledger)
        self.assertEqual(result.event.failure_reason, "ZERO_CAPACITY")


if __name__ == "__main__":
    unittest.main()
