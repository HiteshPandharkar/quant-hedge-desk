import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.enums import ScenarioMethodology  # noqa: E402
from quant_hedge_desk.domain.errors import ScenarioValidationError  # noqa: E402
from quant_hedge_desk.domain.models.scenario_contracts import (  # noqa: E402
    ScenarioPath,
    ScenarioSet,
    ScenarioStep,
)
from quant_hedge_desk.domain.scenario_protocols import ScenarioGenerator  # noqa: E402


class ScenarioContractTests(unittest.TestCase):
    @staticmethod
    def _path(
        scenario_id: str = "window-001", probability: str | None = None
    ) -> ScenarioPath:
        return ScenarioPath(
            scenario_id=scenario_id,
            name=f"Historical {scenario_id}",
            probability=probability,
            steps=(
                ScenarioStep(
                    step_number=1,
                    observation_date="2026-01-02",
                    asset_returns={"nifty": "-0.10", "portfolio": "-0.15"},
                ),
                ScenarioStep(
                    step_number=2,
                    observation_date="2026-01-03",
                    asset_returns={"nifty": "0.05", "portfolio": "0.10"},
                    implied_volatility_shifts={"nifty": "0.03"},
                    bid_ask_spread_multipliers={"nifty": "1.5"},
                    rebalancing_allowed=False,
                ),
            ),
        )

    def test_contract_normalizes_and_freezes_market_data(self) -> None:
        path = self._path()

        self.assertEqual(path.symbols, ("NIFTY", "PORTFOLIO"))
        self.assertEqual(path.terminal_return("nifty"), Decimal("-0.055"))
        self.assertEqual(
            path.steps[1].implied_volatility_shifts["NIFTY"], Decimal("0.03")
        )
        with self.assertRaises(TypeError):
            path.steps[0].asset_returns["NIFTY"] = Decimal("0")
        with self.assertRaises(FrozenInstanceError):
            path.name = "Changed"

    def test_scenario_set_records_lineage_and_supplies_equal_weights(self) -> None:
        scenario_set = ScenarioSet(
            scenario_set_id="asteria-historical-v1",
            version="1.0",
            methodology="historical",
            as_of_date="2026-01-03",
            horizon_trading_days=126,
            scenarios=(self._path("one"), self._path("two")),
            model_version="historical-windows/1.0",
            parameters={"window_length": 126, "overlapping": True},
            source_snapshot_ids=("prices-2026-01-03", "portfolio-2026-01-03"),
        )

        self.assertIs(scenario_set.methodology, ScenarioMethodology.HISTORICAL)
        self.assertEqual(scenario_set.scenario_count, 2)
        self.assertEqual(
            scenario_set.probability_weights,
            (Decimal("0.5"), Decimal("0.5")),
        )
        with self.assertRaises(TypeError):
            scenario_set.parameters["window_length"] = 100

    def test_mapping_factory_builds_nested_contract(self) -> None:
        scenario_set = ScenarioSet.from_mapping(
            {
                "scenario_set_id": "stress-v1",
                "version": "1",
                "methodology": "NAMED_STRESS",
                "as_of_date": "2026-08-20",
                "horizon_trading_days": 1,
                "model_version": "named-stress/1",
                "scenarios": [
                    {
                        "scenario_id": "correlation-breakdown",
                        "name": "Correlation breakdown",
                        "description": "Portfolio falls while the hedge basis weakens.",
                        "steps": [
                            {
                                "step_number": 1,
                                "asset_returns": {
                                    "PORTFOLIO": "-0.18",
                                    "NIFTY": "-0.10",
                                },
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(scenario_set.scenarios[0].scenario_id, "correlation-breakdown")
        self.assertEqual(
            scenario_set.scenarios[0].terminal_return("PORTFOLIO"), Decimal("-0.18")
        )

    def test_rejects_inconsistent_paths_and_probabilities(self) -> None:
        with self.assertRaisesRegex(ScenarioValidationError, "same asset return symbols"):
            ScenarioPath(
                scenario_id="bad-path",
                name="Bad path",
                steps=(
                    ScenarioStep(1, {"NIFTY": 0}),
                    ScenarioStep(2, {"BANKNIFTY": 0}),
                ),
            )

        with self.assertRaisesRegex(ScenarioValidationError, "sum to 1"):
            ScenarioSet(
                scenario_set_id="bad-weights",
                version="1",
                methodology=ScenarioMethodology.BLOCK_BOOTSTRAP,
                as_of_date="2026-08-20",
                horizon_trading_days=126,
                scenarios=(self._path("one", "0.4"), self._path("two", "0.4")),
                model_version="bootstrap/1",
            )

    def test_rejects_impossible_returns_and_nonpositive_spread_multiplier(self) -> None:
        with self.assertRaisesRegex(ScenarioValidationError, "at least -1"):
            ScenarioStep(1, {"NIFTY": "-1.01"})
        with self.assertRaisesRegex(ScenarioValidationError, "positive"):
            ScenarioStep(
                1,
                {"NIFTY": 0},
                bid_ask_spread_multipliers={"NIFTY": 0},
            )

    def test_generator_protocol_is_runtime_checkable(self) -> None:
        class Generator:
            def generate(self) -> ScenarioSet:
                raise NotImplementedError

        self.assertIsInstance(Generator(), ScenarioGenerator)


if __name__ == "__main__":
    unittest.main()
