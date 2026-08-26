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
from quant_hedge_desk.scenarios.factor import (  # noqa: E402
    FactorSimulationScenarioGenerator,
)


class FactorSimulationScenarioGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        factor = (-0.03, -0.01, 0.0, 0.01, 0.02, 0.04)
        self.dataset = AlignedReturnDataset(
            price_dates=tuple(date(2026, 1, day) for day in range(1, 8)),
            returns={
                "PORTFOLIO": tuple(0.001 + 1.2 * value for value in factor),
                "NIFTY": factor,
            },
        )

    def _generator(self, **overrides: object) -> FactorSimulationScenarioGenerator:
        arguments = {
            "scenario_set_id": "factor-v1",
            "version": "1.0",
            "as_of_date": "2026-01-07",
            "horizon_trading_days": 5,
            "dataset": self.dataset,
            "factor_symbols": ("nifty",),
            "scenario_count": 4,
            "random_seed": 42,
            "source_snapshot_ids": ("prices-2026-01-07",),
        }
        arguments.update(overrides)
        return FactorSimulationScenarioGenerator(**arguments)

    def test_generates_complete_valid_factor_paths_with_lineage(self) -> None:
        generator = self._generator()
        result = generator.generate()

        self.assertIsInstance(generator, ScenarioGenerator)
        self.assertIs(result.methodology, ScenarioMethodology.FACTOR_SIMULATION)
        self.assertEqual(result.scenario_count, 4)
        self.assertEqual(result.symbols, ("NIFTY", "PORTFOLIO"))
        self.assertTrue(all(len(path.steps) == 5 for path in result.scenarios))
        self.assertTrue(
            all(
                value > -1
                for path in result.scenarios
                for step in path.steps
                for value in step.asset_returns.values()
            )
        )
        self.assertEqual(result.parameters["factor_symbols"], "NIFTY")
        self.assertEqual(result.parameters["random_seed"], 42)
        self.assertEqual(result.source_snapshot_ids, ("prices-2026-01-07",))

    def test_seed_makes_repeated_generation_reproducible(self) -> None:
        generator = self._generator()

        self.assertEqual(generator.generate(), generator.generate())
        self.assertNotEqual(
            generator.generate().scenarios,
            self._generator(random_seed=43).generate().scenarios,
        )

    def test_rejects_invalid_factor_configuration_and_lookahead(self) -> None:
        with self.assertRaisesRegex(ScenarioValidationError, "absent"):
            self._generator(factor_symbols=("BANKNIFTY",))
        with self.assertRaisesRegex(ScenarioValidationError, "unique"):
            self._generator(factor_symbols=("NIFTY", "NIFTY"))
        with self.assertRaisesRegex(ScenarioValidationError, "after as_of_date"):
            self._generator(as_of_date="2026-01-06")
        with self.assertRaisesRegex(ScenarioValidationError, "integer or None"):
            self._generator(random_seed=True)

    def test_rejects_rank_deficient_factors_and_impossible_log_returns(self) -> None:
        duplicate_factors = AlignedReturnDataset(
            price_dates=self.dataset.price_dates,
            returns={
                **self.dataset.returns,
                "BANKNIFTY": self.dataset.returns["NIFTY"],
            },
        )
        with self.assertRaisesRegex(ScenarioValidationError, "rank deficient"):
            self._generator(
                dataset=duplicate_factors,
                factor_symbols=("NIFTY", "BANKNIFTY"),
            )

        invalid_returns = AlignedReturnDataset(
            price_dates=self.dataset.price_dates,
            returns={"NIFTY": (-1.0, -0.01, 0.0, 0.01, 0.02, 0.04)},
        )
        with self.assertRaisesRegex(ScenarioValidationError, "greater than -1"):
            self._generator(dataset=invalid_returns, factor_symbols=("NIFTY",))


if __name__ == "__main__":
    unittest.main()
