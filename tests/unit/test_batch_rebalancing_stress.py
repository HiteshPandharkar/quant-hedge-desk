import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.application.stress_candidate_hedge import (  # noqa: E402
    stress_candidate_hedge,
    stress_candidate_hedges,
)


CASE = ROOT / "cases" / "asteria_capital"
MARKET_DATA = ROOT / "data" / "market" / "eod_prices.csv"
CANDIDATES = tuple(sorted(CASE.glob("candidate_*.yaml")))


class BatchRebalancingStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.common = {
            "portfolio_path": CASE / "portfolio.csv",
            "mandate_path": CASE / "mandate.yaml",
            "candidate_paths": CANDIDATES,
            "market_data_path": MARKET_DATA,
            "supplied_total_market_value": 5_000_000_000,
        }
        cls.black76 = stress_candidate_hedges(
            **cls.common,
            stress_scenario_path=(
                CASE / "rebalancing_stress_delayed_black76.yaml"
            ),
            rebalancing_policy_path=CASE / "rebalancing_stress_policy.yaml",
        )
        cls.explicit = stress_candidate_hedges(
            **cls.common,
            stress_scenario_path=CASE / "rebalancing_stress_explicit_marks.yaml",
            rebalancing_policy_path=(
                CASE / "rebalancing_stress_explicit_policy.yaml"
            ),
        )

    def test_all_asteria_candidates_are_classified_and_json_ready(self) -> None:
        expected_ids = {
            "asteria-hybrid-protective-puts-v1",
            "asteria-nifty-vertical-put-spread-v1",
            "asteria-nifty-protective-put-v1",
        }

        self.assertEqual(
            {item.candidate_id for item in self.black76.evaluations}, expected_ids
        )
        self.assertEqual(
            set(self.black76.releasable_candidate_ids)
            | set(self.black76.rejected_candidate_ids),
            expected_ids,
        )
        payload = self.black76.to_dict()
        self.assertEqual(payload["policy_id"], "asteria-rebalancing-stress-v1")
        self.assertEqual(
            payload["scenario_set_id"], "asteria-delayed-rebalancing-black76-v1"
        )
        json.dumps(payload)

    def test_delayed_rebalance_is_an_ordinary_structured_failure(self) -> None:
        self.assertEqual(len(self.black76.rejected_candidate_ids), 3)
        for evaluation in self.black76.evaluations:
            self.assertFalse(evaluation.rebalancing_pass)
            events = evaluation.outcomes[0].rebalance_events
            self.assertEqual(events[0].failure_reason, "REBALANCING_NOT_ALLOWED")
            self.assertEqual(events[1].delay_trading_days, 1)
            self.assertNotIn("PRICING_REJECTED", events[1].failure_reason or "")

    def test_explicit_marks_price_every_candidate_without_pricing_rejection(self) -> None:
        self.assertEqual(len(self.explicit.evaluations), 3)
        for evaluation in self.explicit.evaluations:
            events = evaluation.outcomes[0].rebalance_events
            self.assertEqual(events[0].failure_reason, "REBALANCING_NOT_ALLOWED")
            self.assertIsNone(events[1].failure_reason)
            self.assertNotEqual(events[1].premium_cash_flow, 0)

    def test_batch_and_single_candidate_results_agree(self) -> None:
        candidate_path = CANDIDATES[2]
        single = stress_candidate_hedge(
            portfolio_path=self.common["portfolio_path"],
            mandate_path=self.common["mandate_path"],
            candidate_path=candidate_path,
            stress_scenario_path=(
                CASE / "rebalancing_stress_delayed_black76.yaml"
            ),
            rebalancing_policy_path=CASE / "rebalancing_stress_policy.yaml",
            market_data_path=MARKET_DATA,
            supplied_total_market_value=5_000_000_000,
        )
        batch_item = next(
            item
            for item in self.black76.evaluations
            if item.candidate_id == single.candidate_id
        )

        self.assertEqual(batch_item, single)

    def test_candidate_evaluation_state_is_isolated(self) -> None:
        evaluations = self.explicit.evaluations
        self.assertEqual(len({id(item) for item in evaluations}), len(evaluations))
        self.assertEqual(
            len({id(item.outcomes[0].final_position) for item in evaluations}),
            len(evaluations),
        )
        for evaluation in evaluations:
            self.assertEqual(
                evaluation.candidate_id,
                evaluation.outcomes[0].final_position.candidate_id,
            )

    def test_duplicate_candidate_ids_fail_before_shared_inputs_are_loaded(self) -> None:
        with patch(
            "quant_hedge_desk.application.stress_candidate_hedge.load_portfolio_csv"
        ) as portfolio_loader:
            with self.assertRaisesRegex(ValueError, "duplicate candidate_ids"):
                stress_candidate_hedges(
                    **{
                        **self.common,
                        "candidate_paths": (CANDIDATES[0], CANDIDATES[0]),
                    },
                    stress_scenario_path=(
                        CASE / "rebalancing_stress_delayed_black76.yaml"
                    ),
                    rebalancing_policy_path=(
                        CASE / "rebalancing_stress_policy.yaml"
                    ),
                )
        portfolio_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
