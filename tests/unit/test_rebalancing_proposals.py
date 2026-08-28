import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402
from quant_hedge_desk.domain.enums import RebalanceTriggerType  # noqa: E402
from quant_hedge_desk.domain.errors import RebalancePricingError  # noqa: E402
from quant_hedge_desk.domain.models.rebalancing import (  # noqa: E402
    RebalanceProposal,
    RebalancingStressPolicy,
)
from quant_hedge_desk.domain.models.scenario_contracts import (  # noqa: E402
    OptionMark,
    ScenarioStep,
)
from quant_hedge_desk.hedge_design.candidate_generator import (  # noqa: E402
    HedgeCandidate,
)
from quant_hedge_desk.hedge_design.rebalancing import (  # noqa: E402
    black_76_option_price,
    contract_id_for_leg,
    initial_position,
    propose_rebalance,
    resolve_option_prices,
    target_quantities,
)


INITIAL_PORTFOLIO_VALUE = Decimal("5000000000")


def candidate(number: int) -> HedgeCandidate:
    names = {
        1: "candidate_01_hybrid_protective_puts.yaml",
        2: "candidate_02_nifty_vertical_put_spread.yaml",
        3: "candidate_03_nifty_protective_put.yaml",
    }
    return HedgeCandidate.from_mapping(
        load_yaml_mapping(ROOT / "cases" / "asteria_capital" / names[number])
    )


def explicit_policy(threshold: str = "0.05") -> RebalancingStressPolicy:
    return RebalancingStressPolicy(
        policy_id="explicit-test",
        version="1",
        exceptional_coverage_drift_threshold=threshold,
        routine_interval_trading_days=5,
        pricing_mode="EXPLICIT_MARKS",
    )


class RebalancePricingTests(unittest.TestCase):
    def test_black_76_matches_at_the_money_reference_case(self) -> None:
        call = black_76_option_price(
            forward="100",
            strike="100",
            risk_free_rate="0.05",
            volatility="0.20",
            time_to_expiry_years="1",
            option_type="CALL",
        )
        put = black_76_option_price(
            forward="100",
            strike="100",
            risk_free_rate="0.05",
            volatility="0.20",
            time_to_expiry_years="1",
            option_type="PUT",
        )

        self.assertAlmostEqual(float(call), 7.5770821464, places=9)
        self.assertAlmostEqual(float(put), 7.5770821464, places=9)

    def test_explicit_marks_resolve_by_stable_contract_identity(self) -> None:
        hedge = candidate(3)
        leg = hedge.legs[0]
        step = ScenarioStep(
            1,
            {"NIFTY": "0", "PORTFOLIO": "0"},
            option_marks=(
                OptionMark(
                    leg.underlying,
                    leg.expiry,
                    leg.strike_or_level,
                    leg.option_type,
                    "712.50",
                ),
            ),
        )

        prices = resolve_option_prices(hedge, step, explicit_policy())

        self.assertEqual(
            prices["NIFTY|2026-07-30|PUT|24000"], Decimal("712.50")
        )
        self.assertEqual(contract_id_for_leg(leg), step.option_marks[0].contract_id)

    def test_black_76_reports_missing_inputs_with_contract_context(self) -> None:
        hedge = candidate(3)
        policy = RebalancingStressPolicy(
            "black-test",
            "1",
            "0.05",
            5,
            "BLACK_76",
            {contract_id_for_leg(hedge.legs[0]): "0.15"},
        )

        with self.assertRaisesRegex(RebalancePricingError, "observation_date"):
            resolve_option_prices(
                hedge,
                ScenarioStep(1, {"NIFTY": "0", "PORTFOLIO": "0"}),
                policy,
            )


class RebalanceTargetTests(unittest.TestCase):
    def test_vertical_spread_preserves_matched_leg_ratio(self) -> None:
        hedge = candidate(2)

        targets = target_quantities(
            hedge,
            inception_portfolio_value=INITIAL_PORTFOLIO_VALUE,
            current_portfolio_value="4750000000",
            current_underlying_levels={"NIFTY": "24700"},
        )

        self.assertEqual(len(set(targets.values())), 1)
        self.assertNotEqual(next(iter(targets.values())), hedge.legs[0].quantity)

    def test_hybrid_preserves_inception_underlying_allocation_after_rounding(self) -> None:
        hedge = candidate(1)
        levels = {"NIFTY": Decimal("24000"), "BANKNIFTY": Decimal("57000")}

        targets = target_quantities(
            hedge,
            inception_portfolio_value=INITIAL_PORTFOLIO_VALUE,
            current_portfolio_value="4500000000",
            current_underlying_levels=levels,
        )
        target_notionals = {
            leg.underlying.value: (
                levels[leg.underlying.value]
                * targets[contract_id_for_leg(leg)]
                * leg.contract_multiplier
            )
            for leg in hedge.legs
        }
        inception_notionals = {
            leg.underlying.value: (
                hedge.initial_levels[leg.underlying.value]
                * leg.quantity
                * leg.contract_multiplier
            )
            for leg in hedge.legs
        }

        target_mix = target_notionals["NIFTY"] / target_notionals["BANKNIFTY"]
        inception_mix = inception_notionals["NIFTY"] / inception_notionals["BANKNIFTY"]
        self.assertLess(abs(target_mix / inception_mix - 1), Decimal("0.001"))


class RebalanceProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = candidate(3)
        self.position = initial_position(self.candidate)

    def test_exceptional_trigger_returns_deterministic_pricing_rejection(self) -> None:
        proposal = propose_rebalance(
            self.candidate,
            self.position,
            ScenarioStep(1, {"NIFTY": "0", "PORTFOLIO": "-0.10"}),
            explicit_policy(),
            inception_portfolio_value=INITIAL_PORTFOLIO_VALUE,
            current_portfolio_value="4500000000",
            current_underlying_levels={"NIFTY": self.candidate.initial_levels["NIFTY"]},
            is_terminal_step=False,
        )

        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertIs(proposal.trigger_type, RebalanceTriggerType.EXCEPTIONAL)
        self.assertTrue(proposal.is_rejected)
        self.assertIn("missing explicit option marks", proposal.rejection_reason)
        self.assertEqual(proposal.current_quantities, self.position.quantities)
        self.assertEqual(RebalanceProposal.from_mapping(proposal.to_dict()), proposal)
        json.dumps(proposal.to_dict())

    def test_five_day_schedule_creates_routine_proposal_below_drift_threshold(self) -> None:
        leg = self.candidate.legs[0]
        proposal = propose_rebalance(
            self.candidate,
            self.position,
            ScenarioStep(
                5,
                {"NIFTY": "-0.01", "PORTFOLIO": "-0.02"},
                option_marks=(
                    OptionMark(
                        leg.underlying,
                        leg.expiry,
                        leg.strike_or_level,
                        leg.option_type,
                        "800",
                    ),
                ),
            ),
            explicit_policy(),
            inception_portfolio_value=INITIAL_PORTFOLIO_VALUE,
            current_portfolio_value="4900000000",
            current_underlying_levels={"NIFTY": "25067.4435"},
            is_terminal_step=False,
        )

        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertIs(proposal.trigger_type, RebalanceTriggerType.ROUTINE)
        self.assertFalse(proposal.is_rejected)

    def test_rounded_no_op_and_terminal_step_do_not_create_proposals(self) -> None:
        no_op = propose_rebalance(
            self.candidate,
            self.position,
            ScenarioStep(5, {"NIFTY": "0", "PORTFOLIO": "0"}),
            explicit_policy(),
            inception_portfolio_value=INITIAL_PORTFOLIO_VALUE,
            current_portfolio_value=INITIAL_PORTFOLIO_VALUE,
            current_underlying_levels={"NIFTY": self.candidate.initial_levels["NIFTY"]},
            is_terminal_step=False,
        )
        terminal = propose_rebalance(
            self.candidate,
            self.position,
            ScenarioStep(1, {"NIFTY": "0", "PORTFOLIO": "-0.10"}),
            explicit_policy(),
            inception_portfolio_value=INITIAL_PORTFOLIO_VALUE,
            current_portfolio_value="4500000000",
            current_underlying_levels={"NIFTY": self.candidate.initial_levels["NIFTY"]},
            is_terminal_step=True,
        )

        self.assertIsNone(no_op)
        self.assertIsNone(terminal)


if __name__ == "__main__":
    unittest.main()
