import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.enums import ScenarioMethodology  # noqa: E402
from quant_hedge_desk.domain.errors import ScenarioValidationError  # noqa: E402
from quant_hedge_desk.domain.scenario_protocols import ScenarioGenerator  # noqa: E402
from quant_hedge_desk.scenarios.manual_generator import (  # noqa: E402
    DEFAULT_MANUAL_MODEL_VERSION,
    ManualScenarioGenerator,
)


class ManualScenarioGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "scenario_set_id": "asteria-manual-stress-v1",
            "version": "1.0",
            "methodology": "NAMED_STRESS",
            "as_of_date": "2026-08-20",
            "horizon_trading_days": 126,
            "model_version": "asteria-manual/1.0",
            "parameters": {
                "owner": "risk-desk",
                "approved": True,
            },
            "source_snapshot_ids": ["portfolio-2026-08-20"],
            "scenarios": [
                {
                    "scenario_id": "market-crash",
                    "name": "Broad market crash",
                    "description": "Equity selloff with a volatility jump.",
                    "steps": [
                        {
                            "step_number": 1,
                            "asset_returns": {
                                "PORTFOLIO": "-0.22",
                                "NIFTY": "-0.18",
                                "BANKNIFTY": "-0.25",
                            },
                            "implied_volatility_shifts": {
                                "NIFTY": "0.15",
                                "BANKNIFTY": "0.18",
                            },
                        }
                    ],
                },
                {
                    "scenario_id": "wider-spreads",
                    "name": "Wider bid-ask spreads",
                    "steps": [
                        {
                            "step_number": 1,
                            "asset_returns": {
                                "PORTFOLIO": "-0.03",
                                "NIFTY": "-0.03",
                                "BANKNIFTY": "-0.04",
                            },
                            "bid_ask_spread_multipliers": {
                                "NIFTY": "3",
                                "BANKNIFTY": "4",
                            },
                            "market_volume_multipliers": {
                                "NIFTY": "0.25",
                                "BANKNIFTY": "0.20",
                            },
                        }
                    ],
                },
                {
                    "scenario_id": "delayed-rebalancing",
                    "name": "Two-day rebalance delay",
                    "steps": [
                        {
                            "step_number": 1,
                            "observation_date": "2026-08-21",
                            "asset_returns": {
                                "PORTFOLIO": "-0.08",
                                "NIFTY": "-0.06",
                                "BANKNIFTY": "-0.09",
                            },
                            "rebalancing_allowed": False,
                        },
                        {
                            "step_number": 2,
                            "observation_date": "2026-08-24",
                            "asset_returns": {
                                "PORTFOLIO": "-0.04",
                                "NIFTY": "-0.03",
                                "BANKNIFTY": "-0.05",
                            },
                            "rebalancing_allowed": False,
                        },
                    ],
                },
            ],
        }

    def test_generates_multiple_configurable_scenario_types(self) -> None:
        generator = ManualScenarioGenerator.from_mapping(self.config)

        result = generator.generate()

        self.assertIsInstance(generator, ScenarioGenerator)
        self.assertIs(result.methodology, ScenarioMethodology.NAMED_STRESS)
        self.assertEqual(result.scenario_count, 3)
        self.assertEqual(
            result.scenarios[0].steps[0].implied_volatility_shifts["NIFTY"],
            Decimal("0.15"),
        )
        self.assertEqual(
            result.scenarios[1].steps[0].bid_ask_spread_multipliers["BANKNIFTY"],
            Decimal("4"),
        )
        self.assertEqual(
            result.scenarios[1].steps[0].market_volume_multipliers["NIFTY"],
            Decimal("0.25"),
        )
        self.assertFalse(result.scenarios[2].steps[1].rebalancing_allowed)
        self.assertEqual(
            result.scenarios[2].terminal_return("PORTFOLIO"), Decimal("-0.1168")
        )

    def test_configuration_is_normalized_and_detached_from_input(self) -> None:
        generator = ManualScenarioGenerator.from_mapping(self.config)
        self.config["scenarios"][0]["steps"][0]["asset_returns"]["NIFTY"] = 0

        result = generator.configuration

        self.assertEqual(
            result.scenarios[0].steps[0].asset_returns["NIFTY"], Decimal("-0.18")
        )
        self.assertEqual(result.parameters["owner"], "risk-desk")

    def test_defaults_model_version_and_methodology(self) -> None:
        self.config.pop("methodology")
        self.config.pop("model_version")

        result = ManualScenarioGenerator.from_mapping(self.config).generate()

        self.assertIs(result.methodology, ScenarioMethodology.NAMED_STRESS)
        self.assertEqual(result.model_version, DEFAULT_MANUAL_MODEL_VERSION)

    def test_rejects_non_manual_methodology_and_unknown_fields(self) -> None:
        self.config["methodology"] = "HISTORICAL"
        with self.assertRaisesRegex(ScenarioValidationError, "NAMED_STRESS"):
            ManualScenarioGenerator.from_mapping(self.config)

        self.config["methodology"] = "NAMED_STRESS"
        self.config["unexpected"] = True
        with self.assertRaisesRegex(ScenarioValidationError, "unknown fields"):
            ManualScenarioGenerator.from_mapping(self.config)

    def test_underlying_contract_rejects_invalid_manual_shocks(self) -> None:
        self.config["scenarios"][0]["steps"][0]["asset_returns"]["NIFTY"] = "-1.1"

        with self.assertRaisesRegex(ScenarioValidationError, "at least -1"):
            ManualScenarioGenerator.from_mapping(self.config)

    def test_market_volume_multiplier_must_be_positive(self) -> None:
        self.config["scenarios"][1]["steps"][0]["market_volume_multipliers"][
            "NIFTY"
        ] = "0"

        with self.assertRaisesRegex(ScenarioValidationError, "must be positive"):
            ManualScenarioGenerator.from_mapping(self.config)


if __name__ == "__main__":
    unittest.main()
