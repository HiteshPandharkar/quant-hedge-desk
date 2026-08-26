import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.analytics.models import AlignedReturnDataset  # noqa: E402
from quant_hedge_desk.domain.enums import ScenarioMethodology  # noqa: E402
from quant_hedge_desk.domain.errors import ScenarioValidationError  # noqa: E402
from quant_hedge_desk.domain.scenario_protocols import ScenarioGenerator  # noqa: E402
from quant_hedge_desk.scenarios.historical import (  # noqa: E402
    HistoricalRollingScenarioGenerator,
)


class HistoricalRollingScenarioGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = AlignedReturnDataset(
            price_dates=tuple(date(2026, 1, day) for day in range(1, 7)),
            returns={
                "PORTFOLIO": (0.10, -0.10, 0.20, -0.20, 0.05),
                "NIFTY": (0.05, -0.05, 0.10, -0.10, 0.02),
            },
        )

    def _generator(self, **overrides: object) -> HistoricalRollingScenarioGenerator:
        arguments = {
            "scenario_set_id": "historical-v1",
            "version": "1.0",
            "as_of_date": "2026-01-06",
            "horizon_trading_days": 3,
            "dataset": self.dataset,
            "source_snapshot_ids": ("prices-2026-01-06",),
        }
        arguments.update(overrides)
        return HistoricalRollingScenarioGenerator(**arguments)

    def test_generates_every_overlapping_window_with_daily_path(self) -> None:
        generator = self._generator()

        result = generator.generate()

        self.assertIsInstance(generator, ScenarioGenerator)
        self.assertIs(result.methodology, ScenarioMethodology.HISTORICAL)
        self.assertEqual(result.scenario_count, 3)
        self.assertEqual(len(result.scenarios[0].steps), 3)
        self.assertEqual(result.scenarios[0].steps[0].observation_date, date(2026, 1, 2))
        self.assertEqual(result.scenarios[-1].steps[-1].observation_date, date(2026, 1, 6))
        self.assertEqual(
            result.scenarios[0].terminal_return("PORTFOLIO"), Decimal("0.188")
        )
        self.assertEqual(
            result.probability_weights,
            (Decimal("0.3333333333333333333333333333"),) * 3,
        )
        self.assertEqual(result.parameters["window_length"], 3)
        self.assertEqual(result.parameters["window_stride"], 1)
        self.assertTrue(result.parameters["overlapping"])

    def test_configurable_stride_supports_non_overlapping_windows(self) -> None:
        result = self._generator(window_stride=3).generate()

        self.assertEqual(result.scenario_count, 1)
        self.assertFalse(result.parameters["overlapping"])

    def test_rejects_lookahead_and_insufficient_history(self) -> None:
        with self.assertRaisesRegex(ScenarioValidationError, "after as_of_date"):
            self._generator(as_of_date="2026-01-05")
        with self.assertRaisesRegex(ScenarioValidationError, "at least 6"):
            self._generator(horizon_trading_days=6)

    def test_scenario_ids_record_exact_price_interval(self) -> None:
        result = self._generator().generate()

        self.assertEqual(
            result.scenarios[0].scenario_id,
            "historical-2026-01-01-to-2026-01-04",
        )


if __name__ == "__main__":
    unittest.main()
