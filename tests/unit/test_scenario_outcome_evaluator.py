import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.models.portfolio import Portfolio, PortfolioHolding  # noqa: E402
from quant_hedge_desk.domain.models.scenario_contracts import (  # noqa: E402
    ScenarioPath,
    ScenarioSet,
    ScenarioStep,
)
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate  # noqa: E402
from quant_hedge_desk.hedge_design.scenario_evaluator import (  # noqa: E402
    evaluate_scenario_outcomes,
)


class ScenarioOutcomeEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        holding = PortfolioHolding(
            portfolio_id="portfolio-1",
            as_of_date="2026-08-20",
            symbol="ABC",
            quantity="100",
            price="100",
            market_value="10000",
            portfolio_weight="1",
            sector="Industrials",
            benchmark_weight="0",
            liquidity_bucket="LARGE",
            hedging_restriction="NONE",
            data_source="TEST",
        )
        self.portfolio = Portfolio("portfolio-1", "2026-08-20", (holding,))
        self.candidate = HedgeCandidate.from_mapping(
            {
                "candidate_id": "put-1",
                "schema_version": "1.0",
                "family": "NIFTY_PROTECTIVE_PUT",
                "description": "One protective put.",
                "quote_timestamp": "2026-08-21T10:00:00+05:30",
                "estimated_execution_cost": "50",
                "initial_levels": {"NIFTY": "100"},
                "legs": [
                    {
                        "underlying": "NIFTY",
                        "instrument_type": "OPTION",
                        "direction": "LONG",
                        "option_type": "PUT",
                        "option_style": "EUROPEAN",
                        "strike_or_level": "95",
                        "expiry": "2027-02-25",
                        "quantity": 10,
                        "contract_multiplier": "1",
                        "premium": "2",
                        "quote_timestamp": "2026-08-21T10:00:00+05:30",
                        "liquidity_attributes": {},
                    }
                ],
                "upside_scenario_set_id": "upside-v1",
                "upside_scenarios": [
                    {
                        "scenario_id": "up",
                        "portfolio_return": "0.10",
                        "terminal_levels": {"NIFTY": "110"},
                    }
                ],
            }
        )

    def _scenario_set(self, *, include_nifty: bool = True) -> ScenarioSet:
        down_returns = {"PORTFOLIO": "-0.20"}
        up_returns = {"PORTFOLIO": "0.10"}
        if include_nifty:
            down_returns["NIFTY"] = "-0.20"
            up_returns["NIFTY"] = "0.10"
        return ScenarioSet(
            scenario_set_id="stress-v1",
            version="1.2",
            methodology="NAMED_STRESS",
            as_of_date="2026-08-20",
            horizon_trading_days=126,
            model_version="stress-model/2",
            scenarios=(
                ScenarioPath(
                    "down",
                    "Market down",
                    (ScenarioStep(1, down_returns),),
                    probability="0.25",
                ),
                ScenarioPath(
                    "up",
                    "Market up",
                    (ScenarioStep(1, up_returns),),
                    probability="0.75",
                ),
            ),
        )

    def test_values_each_path_and_probability_weighted_breaches(self) -> None:
        result = evaluate_scenario_outcomes(
            scenario_set=self._scenario_set(),
            portfolio=self.portfolio,
            candidate=self.candidate,
            tail_loss_threshold="0.10",
        )

        down, up = result.outcomes
        self.assertEqual(result.all_in_hedge_cost, Decimal("70"))
        self.assertEqual(down.unhedged_terminal_value, Decimal("8000.00"))
        self.assertEqual(down.hedge_payoff, Decimal("150.0"))
        self.assertEqual(down.hedged_terminal_value, Decimal("8080.00"))
        self.assertEqual(down.hedged_return, Decimal("-0.192"))
        self.assertEqual(down.return_improvement, Decimal("0.008"))
        self.assertEqual(up.hedge_payoff, Decimal("0"))
        self.assertEqual(result.unhedged_tail_breach_probability, Decimal("0.25"))
        self.assertEqual(result.hedged_tail_breach_probability, Decimal("0.25"))
        self.assertEqual(result.scenario_set_version, "1.2")
        self.assertEqual(result.model_version, "stress-model/2")

    def test_compounds_multistep_returns_and_assigns_equal_weights(self) -> None:
        scenario = ScenarioPath(
            "two-step",
            "Two-step decline",
            (
                ScenarioStep(1, {"PORTFOLIO": "-0.10", "NIFTY": "-0.10"}),
                ScenarioStep(2, {"PORTFOLIO": "-0.10", "NIFTY": "-0.10"}),
            ),
        )
        scenario_set = ScenarioSet(
            "compound-v1",
            "1",
            "HISTORICAL",
            "2026-08-20",
            2,
            (scenario,),
            "historical/1",
        )

        result = evaluate_scenario_outcomes(
            scenario_set=scenario_set,
            portfolio=self.portfolio,
            candidate=self.candidate,
        )

        self.assertEqual(result.outcomes[0].portfolio_return, Decimal("-0.19"))
        self.assertEqual(result.outcomes[0].probability, Decimal("1"))

    def test_rejects_missing_required_scenario_symbols(self) -> None:
        with self.assertRaisesRegex(ValueError, "NIFTY"):
            evaluate_scenario_outcomes(
                scenario_set=self._scenario_set(include_nifty=False),
                portfolio=self.portfolio,
                candidate=self.candidate,
            )

    def test_derives_portfolio_return_from_holding_scenarios(self) -> None:
        scenario_set = ScenarioSet(
            "holding-paths-v1",
            "1",
            "BLOCK_BOOTSTRAP",
            "2026-08-20",
            1,
            (
                ScenarioPath(
                    "holding-down",
                    "Holding and index decline",
                    (ScenarioStep(1, {"ABC": "-0.15", "NIFTY": "-0.20"}),),
                ),
            ),
            "bootstrap/1",
        )

        result = evaluate_scenario_outcomes(
            scenario_set=scenario_set,
            portfolio=self.portfolio,
            candidate=self.candidate,
        )

        self.assertEqual(result.outcomes[0].portfolio_return, Decimal("-0.15"))

    def test_requires_portfolio_or_every_holding_symbol(self) -> None:
        scenario_set = ScenarioSet(
            "index-only-v1",
            "1",
            "NAMED_STRESS",
            "2026-08-20",
            1,
            (
                ScenarioPath(
                    "index-down",
                    "Index only",
                    (ScenarioStep(1, {"NIFTY": "-0.20"}),),
                ),
            ),
            "stress/1",
        )

        with self.assertRaisesRegex(ValueError, "missing holdings: ABC"):
            evaluate_scenario_outcomes(
                scenario_set=scenario_set,
                portfolio=self.portfolio,
                candidate=self.candidate,
            )

    def test_json_output_preserves_decimal_values_as_strings(self) -> None:
        payload = evaluate_scenario_outcomes(
            scenario_set=self._scenario_set(),
            portfolio=self.portfolio,
            candidate=self.candidate,
        ).to_dict()

        self.assertEqual(payload["all_in_hedge_cost"], "70")
        self.assertEqual(payload["outcomes"][0]["hedge_payoff"], "150.00")


if __name__ == "__main__":
    unittest.main()
