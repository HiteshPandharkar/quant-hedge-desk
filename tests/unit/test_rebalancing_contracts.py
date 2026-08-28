import json
import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.data.loaders import load_rebalancing_stress_policy  # noqa: E402
from quant_hedge_desk.domain.enums import (  # noqa: E402
    RebalancingPricingMode,
    RebalanceTriggerType,
)
from quant_hedge_desk.domain.errors import RebalancingValidationError  # noqa: E402
from quant_hedge_desk.domain.models.rebalancing import (  # noqa: E402
    CandidateStressBatchResult,
    CashLedger,
    PositionState,
    RebalanceEvent,
    RebalancingStressPolicy,
)


class RebalancingPolicyTests(unittest.TestCase):
    def test_loads_asteria_policy_with_required_release_controls(self) -> None:
        policy = load_rebalancing_stress_policy(
            ROOT / "cases" / "asteria_capital" / "rebalancing_stress_policy.yaml"
        )

        self.assertEqual(
            policy.exceptional_coverage_drift_threshold, Decimal("0.05")
        )
        self.assertEqual(policy.routine_interval_trading_days, 5)
        self.assertIs(policy.pricing_mode, RebalancingPricingMode.BLACK_76)
        self.assertTrue(policy.rebalancing_failure_is_release_gate)
        self.assertEqual(len(policy.base_volatilities), 3)
        self.assertEqual(
            RebalancingStressPolicy.from_mapping(policy.to_dict()), policy
        )
        json.dumps(policy.to_dict())

    def test_rejects_invalid_policy_fields_with_context(self) -> None:
        valid = {
            "policy_id": "test-policy",
            "version": "1.0",
            "exceptional_coverage_drift_threshold": "0.05",
            "routine_interval_trading_days": 5,
            "pricing_mode": "BLACK_76",
            "base_volatilities": {"NIFTY|2026-07-30|PUT|24000": "0.13"},
            "rebalancing_failure_is_release_gate": True,
        }
        cases = (
            ({**valid, "exceptional_coverage_drift_threshold": "1.01"}, "drift"),
            ({**valid, "routine_interval_trading_days": 0}, "routine_interval"),
            ({**valid, "pricing_mode": "SPOT"}, "pricing_mode"),
            ({**valid, "base_volatilities": {"contract": "0"}}, "base_volatilities.contract"),
            ({**valid, "rebalancing_failure_is_release_gate": "yes"}, "release_gate"),
        )
        for mapping, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(RebalancingValidationError, message):
                    RebalancingStressPolicy.from_mapping(mapping)

    def test_explicit_marks_policy_does_not_require_base_volatilities(self) -> None:
        policy = RebalancingStressPolicy(
            policy_id="explicit",
            version="1",
            exceptional_coverage_drift_threshold="0.05",
            routine_interval_trading_days=5,
            pricing_mode="EXPLICIT_MARKS",
            base_volatilities={},
        )

        self.assertIs(policy.pricing_mode, RebalancingPricingMode.EXPLICIT_MARKS)


class RebalancingStateContractTests(unittest.TestCase):
    def test_position_ledger_event_and_batch_are_immutable_and_json_ready(self) -> None:
        position = PositionState("candidate-1", {"contract-1": 10})
        ledger = CashLedger("25", "10", "2")
        event = RebalanceEvent(
            scenario_id="path-1",
            step_number=5,
            trigger_type=RebalanceTriggerType.ROUTINE,
            current_quantities={"contract-1": 10},
            target_quantities={"contract-1": 12},
            requested_changes={"contract-1": 2},
            filled_changes={"contract-1": 2},
            delay_trading_days=0,
            turnover="1000",
            premium_cash_flow="-25",
            execution_cost="2",
            constraint_result="FEASIBLE",
        )
        batch = CandidateStressBatchResult(
            scenario_set_id="set-1",
            scenario_set_version="1",
            policy_id="policy-1",
            policy_version="1",
            evaluations=(),
            releasable_candidate_ids=("candidate-1",),
            rejected_candidate_ids=(),
        )

        self.assertEqual(PositionState.from_mapping(position.to_dict()), position)
        self.assertEqual(CashLedger.from_mapping(ledger.to_dict()), ledger)
        self.assertEqual(RebalanceEvent.from_mapping(event.to_dict()), event)
        self.assertEqual(ledger.premium_cash_flow, Decimal("-15"))
        self.assertEqual(ledger.net_cash_flow, Decimal("-17"))
        json.dumps(batch.to_dict())
        with self.assertRaises(TypeError):
            position.quantities["contract-1"] = 11
        with self.assertRaises(FrozenInstanceError):
            ledger.execution_cost = Decimal("3")

    def test_batch_rejects_overlapping_release_classifications(self) -> None:
        with self.assertRaisesRegex(RebalancingValidationError, "both"):
            CandidateStressBatchResult(
                "set", "1", "policy", "1", (), ("candidate",), ("candidate",)
            )


if __name__ == "__main__":
    unittest.main()
