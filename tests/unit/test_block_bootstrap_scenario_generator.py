import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.analytics.models import AlignedReturnDataset  # noqa: E402
from quant_hedge_desk.domain.enums import ScenarioMethodology  # noqa: E402
from quant_hedge_desk.domain.errors import ScenarioValidationError  # noqa: E402
from quant_hedge_desk.domain.scenario_protocols import ScenarioGenerator  # noqa: E402
from quant_hedge_desk.scenarios.bootstrap import (  # noqa: E402
    BlockBootstrapScenarioGenerator,
)


class BlockBootstrapScenarioGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = AlignedReturnDataset(
            price_dates=tuple(date(2026, 1, day) for day in range(1, 8)),
            returns={
                "PORTFOLIO": (0.01, 0.02, 0.03, 0.04, 0.05, 0.06),
                "NIFTY": (0.11, 0.12, 0.13, 0.14, 0.15, 0.16),
            },
        )

    def _generator(self, **overrides: object) -> BlockBootstrapScenarioGenerator:
        arguments = {
            "scenario_set_id": "bootstrap-v1",
            "version": "1.0",
            "as_of_date": "2026-01-07",
            "horizon_trading_days": 5,
            "dataset": self.dataset,
            "scenario_count": 3,
            "block_length": 2,
            "random_seed": 42,
            "source_snapshot_ids": ("prices-2026-01-07",),
        }
        arguments.update(overrides)
        return BlockBootstrapScenarioGenerator(**arguments)

    def test_generates_aligned_contiguous_blocks_and_truncates_final_block(self) -> None:
        generator = self._generator()
        result = generator.generate()

        self.assertIsInstance(generator, ScenarioGenerator)
        self.assertIs(result.methodology, ScenarioMethodology.BLOCK_BOOTSTRAP)
        self.assertEqual(result.scenario_count, 3)
        self.assertEqual(len(result.scenarios[0].steps), 5)
        self.assertEqual(result.parameters["blocks_per_scenario"], 3)
        self.assertEqual(result.parameters["eligible_block_count"], 5)

        for path in result.scenarios:
            portfolio = [float(step.asset_returns["PORTFOLIO"]) for step in path.steps]
            nifty = [float(step.asset_returns["NIFTY"]) for step in path.steps]
            self.assertEqual([round(value + 0.10, 10) for value in portfolio], nifty)
            self.assertAlmostEqual(portfolio[1] - portfolio[0], 0.01)
            self.assertAlmostEqual(portfolio[3] - portfolio[2], 0.01)

    def test_seed_makes_repeated_generation_reproducible(self) -> None:
        generator = self._generator()

        self.assertEqual(generator.generate(), generator.generate())
        self.assertNotEqual(
            generator.generate().scenarios,
            self._generator(random_seed=43).generate().scenarios,
        )

    def test_rejects_invalid_configuration_and_lookahead(self) -> None:
        for field in ("horizon_trading_days", "scenario_count", "block_length"):
            with self.subTest(field=field), self.assertRaisesRegex(
                ScenarioValidationError, "positive integer"
            ):
                self._generator(**{field: 0})
        with self.assertRaisesRegex(ScenarioValidationError, "cannot exceed"):
            self._generator(block_length=7)
        with self.assertRaisesRegex(ScenarioValidationError, "after as_of_date"):
            self._generator(as_of_date="2026-01-06")
        with self.assertRaisesRegex(ScenarioValidationError, "integer or None"):
            self._generator(random_seed=True)


if __name__ == "__main__":
    unittest.main()
