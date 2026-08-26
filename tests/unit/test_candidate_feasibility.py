import json
import sys
import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.application.assess_candidate_hedge import assess_candidate_hedge  # noqa: E402
from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402
from quant_hedge_desk.domain.errors import HedgeCandidateValidationError  # noqa: E402
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate  # noqa: E402
from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus  # noqa: E402
from quant_hedge_desk.hedge_design.constraints import (  # noqa: E402
    FeasibilityStatus as CompatibilityFeasibilityStatus,
)


class CandidateFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        case = ROOT / "cases" / "asteria_capital"
        cls.candidate_path = case / "candidate_01_hybrid_protective_puts.yaml"
        cls.result = assess_candidate_hedge(
            portfolio_path=case / "portfolio.csv",
            mandate_path=case / "mandate.yaml",
            candidate_path=cls.candidate_path,
            market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
            supplied_total_market_value=5_000_000_000,
        )

    def test_yaml_loads_as_explicit_candidate(self) -> None:
        candidate = HedgeCandidate.from_mapping(load_yaml_mapping(self.candidate_path))
        self.assertEqual(candidate.candidate_id, "asteria-hybrid-protective-puts-v1")
        self.assertEqual(len(candidate.legs), 2)
        self.assertEqual(len(candidate.upside_scenarios), 2)

    def test_historical_constraint_import_remains_compatible(self) -> None:
        self.assertIs(CompatibilityFeasibilityStatus, FeasibilityStatus)

    def test_assessment_returns_decision_and_diagnostics(self) -> None:
        self.assertIn(self.result.status, tuple(FeasibilityStatus))
        self.assertEqual(
            {item.constraint for item in self.result.diagnostics},
            {"ELIGIBILITY", "ALL_IN_PREMIUM", "UPSIDE_SACRIFICE", "LIQUIDITY", "EXPECTED_SHORTFALL"},
        )
        self.assertEqual(self.result.net_option_premium, Decimal("116960616.10"))
        self.assertEqual(self.result.all_in_client_cost, Decimal("124460616.10"))
        self.assertEqual(
            self.result.premium_constraint_cost,
            self.result.all_in_client_cost,
        )
        self.assertEqual(self.result.failed_constraints, ())
        self.assertIsNone(self.result.infeasibility_diagnosis)
        self.assertLessEqual(float(self.result.maximum_upside_sacrifice), 0.06)
        json.dumps(self.result.to_dict())

    def test_invalid_candidate_leg_is_rejected_with_context(self) -> None:
        raw = dict(load_yaml_mapping(self.candidate_path))
        raw["legs"] = [dict(raw["legs"][0], underlying="SENSEX")]
        with self.assertRaisesRegex(HedgeCandidateValidationError, "invalid leg 1"):
            HedgeCandidate.from_mapping(raw)

    def test_declared_family_must_match_leg_structure(self) -> None:
        raw = dict(load_yaml_mapping(self.candidate_path))
        raw["family"] = "NIFTY_PROTECTIVE_PUT"
        with self.assertRaisesRegex(HedgeCandidateValidationError, "do not match family"):
            HedgeCandidate.from_mapping(raw)

    def test_failed_hard_rule_returns_infeasible_with_diagnostic(self) -> None:
        raw = dict(load_yaml_mapping(self.candidate_path))
        raw["estimated_execution_cost"] = "10000000"
        with tempfile.TemporaryDirectory() as directory:
            candidate_path = Path(directory) / "over_budget.yaml"
            candidate_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
            case = ROOT / "cases" / "asteria_capital"
            result = assess_candidate_hedge(
                portfolio_path=case / "portfolio.csv",
                mandate_path=case / "mandate.yaml",
                candidate_path=candidate_path,
                market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
                supplied_total_market_value=5_000_000_000,
            )

        premium = next(item for item in result.diagnostics if item.constraint == "ALL_IN_PREMIUM")
        self.assertEqual(result.status, FeasibilityStatus.INFEASIBLE)
        self.assertFalse(premium.passed)
        self.assertIn("ALL_IN_PREMIUM", result.failed_constraints)
        diagnosis = result.infeasibility_diagnosis
        self.assertIsNotNone(diagnosis)
        self.assertEqual(diagnosis.binding_constraints, result.failed_constraints)
        budget = next(
            item for item in diagnosis.relaxations
            if item.constraint == "ALL_IN_PREMIUM"
        )
        self.assertEqual(
            Decimal(budget.required_limit), result.premium_constraint_fraction
        )
        self.assertEqual(
            Decimal(budget.relaxation_amount),
            result.premium_constraint_fraction - Decimal(budget.current_limit),
        )
        json.dumps(result.to_dict())

    def test_execution_cost_policy_controls_premium_constraint(self) -> None:
        raw_candidate = dict(load_yaml_mapping(self.candidate_path))
        raw_candidate["estimated_execution_cost"] = "10000000"
        case = ROOT / "cases" / "asteria_capital"
        raw_mandate = deepcopy(load_yaml_mapping(case / "mandate.yaml"))
        raw_mandate["client"]["cost"]["includes_execution_cost"] = False

        with tempfile.TemporaryDirectory() as directory:
            candidate_path = Path(directory) / "candidate.yaml"
            mandate_path = Path(directory) / "mandate.yaml"
            candidate_path.write_text(yaml.safe_dump(raw_candidate), encoding="utf-8")
            mandate_path.write_text(yaml.safe_dump(raw_mandate), encoding="utf-8")
            result = assess_candidate_hedge(
                portfolio_path=case / "portfolio.csv",
                mandate_path=mandate_path,
                candidate_path=candidate_path,
                market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
                supplied_total_market_value=5_000_000_000,
            )

        premium = next(
            item for item in result.diagnostics
            if item.constraint == "ALL_IN_PREMIUM"
        )
        self.assertGreater(result.all_in_cost_fraction, Decimal("0.025"))
        self.assertEqual(
            result.premium_constraint_fraction,
            result.net_option_premium / Decimal("5000000000"),
        )
        self.assertTrue(premium.passed)
        self.assertIn("excluded by mandate", premium.detail)

    def test_missing_liquidity_input_produces_an_input_remedy(self) -> None:
        raw = deepcopy(load_yaml_mapping(self.candidate_path))
        raw["legs"][0]["liquidity_attributes"]["normal_daily_volume"] = 0
        with tempfile.TemporaryDirectory() as directory:
            candidate_path = Path(directory) / "missing_volume.yaml"
            candidate_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
            case = ROOT / "cases" / "asteria_capital"
            result = assess_candidate_hedge(
                portfolio_path=case / "portfolio.csv",
                mandate_path=case / "mandate.yaml",
                candidate_path=candidate_path,
                market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
                supplied_total_market_value=5_000_000_000,
            )

        diagnosis = result.infeasibility_diagnosis
        self.assertIsNotNone(diagnosis)
        liquidity = next(
            item for item in diagnosis.relaxations
            if item.constraint == "LIQUIDITY"
        )
        self.assertEqual(liquidity.unit, "contracts_per_day")
        self.assertEqual(
            liquidity.required_limit,
            "positive normal_daily_volume for every leg",
        )

    def test_expiry_must_cover_the_full_approved_horizon(self) -> None:
        raw = dict(load_yaml_mapping(self.candidate_path))
        raw["legs"] = [
            dict(leg, expiry="2026-07-29") for leg in raw["legs"]
        ]
        with tempfile.TemporaryDirectory() as directory:
            candidate_path = Path(directory) / "short_expiry.yaml"
            candidate_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
            case = ROOT / "cases" / "asteria_capital"
            result = assess_candidate_hedge(
                portfolio_path=case / "portfolio.csv",
                mandate_path=case / "mandate.yaml",
                candidate_path=candidate_path,
                market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
                supplied_total_market_value=5_000_000_000,
            )

        eligibility = next(
            item for item in result.diagnostics
            if item.constraint == "ELIGIBILITY"
        )
        self.assertFalse(eligibility.passed)
        self.assertEqual(eligibility.detail, "expiry month offsets: 5")
        self.assertIn("ELIGIBILITY", result.failed_constraints)

    def test_second_candidate_is_a_valid_vertical_put_spread(self) -> None:
        path = (
            ROOT
            / "cases"
            / "asteria_capital"
            / "candidate_02_nifty_vertical_put_spread.yaml"
        )
        candidate = HedgeCandidate.from_mapping(load_yaml_mapping(path))

        self.assertEqual(candidate.family.value, "NIFTY_VERTICAL_PUT_SPREAD")
        self.assertEqual(len(candidate.legs), 2)
        self.assertGreater(
            candidate.legs[0].strike_or_level,
            candidate.legs[1].strike_or_level,
        )

    def test_spread_coverage_counts_protective_leg_once(self) -> None:
        case = ROOT / "cases" / "asteria_capital"
        result = assess_candidate_hedge(
            portfolio_path=case / "portfolio.csv",
            mandate_path=case / "mandate.yaml",
            candidate_path=case / "candidate_02_nifty_vertical_put_spread.yaml",
            market_data_path=ROOT / "data" / "market" / "eod_prices.csv",
            supplied_total_market_value=5_000_000_000,
        )

        self.assertEqual(
            result.gross_reference_notional, Decimal("10000390717.50")
        )
        self.assertEqual(
            result.protected_reference_notional, Decimal("5000195358.75")
        )
        self.assertEqual(
            result.notional_coverage_fraction, Decimal("1.00003907175")
        )
        self.assertAlmostEqual(
            result.unhedged_expected_shortfall, -0.11374235, places=7
        )

    def test_third_candidate_is_a_valid_protective_put(self) -> None:
        path = (
            ROOT
            / "cases"
            / "asteria_capital"
            / "candidate_03_nifty_protective_put.yaml"
        )
        candidate = HedgeCandidate.from_mapping(load_yaml_mapping(path))

        self.assertEqual(candidate.family.value, "NIFTY_PROTECTIVE_PUT")
        self.assertEqual(len(candidate.legs), 1)
        self.assertEqual(candidate.legs[0].quantity, 6714)


if __name__ == "__main__":
    unittest.main()
