"""Block-bootstrap scenarios built from aligned daily returns."""

from __future__ import annotations

from datetime import date
from random import Random
from typing import Iterable

from quant_hedge_desk.analytics._validation import positive_integer
from quant_hedge_desk.analytics.models import AlignedReturnDataset
from quant_hedge_desk.domain.enums import ScenarioMethodology
from quant_hedge_desk.domain.errors import ScenarioValidationError
from quant_hedge_desk.domain.models.scenario_contracts import (
    ScenarioPath,
    ScenarioSet,
    ScenarioStep,
)
from quant_hedge_desk.domain.scenario_validation import scenario_date


DEFAULT_BLOCK_BOOTSTRAP_MODEL_VERSION = "moving-block-bootstrap/1.0"


class BlockBootstrapScenarioGenerator:
    """Resample contiguous blocks of aligned returns with replacement.

    Sampling whole rows preserves cross-asset dependence, while sampling
    contiguous blocks preserves short-range serial dependence.  A fresh local
    pseudo-random generator is created by :meth:`generate`, making repeated
    calls deterministic for a configured seed and avoiding mutation of the
    process-wide random state.

    The final sampled block is truncated when the horizon is not an exact
    multiple of ``block_length``.  Observation dates are intentionally omitted
    from generated steps because concatenated historical blocks do not form a
    genuine chronological sequence.
    """

    __slots__ = (
        "_as_of_date",
        "_block_length",
        "_dataset",
        "_horizon_trading_days",
        "_model_version",
        "_random_seed",
        "_scenario_count",
        "_scenario_set_id",
        "_source_snapshot_ids",
        "_version",
    )

    def __init__(
        self,
        *,
        scenario_set_id: str,
        version: str,
        as_of_date: date | str,
        horizon_trading_days: int,
        dataset: AlignedReturnDataset,
        scenario_count: int,
        block_length: int,
        random_seed: int | None = None,
        model_version: str = DEFAULT_BLOCK_BOOTSTRAP_MODEL_VERSION,
        source_snapshot_ids: Iterable[str] = (),
    ) -> None:
        if not isinstance(dataset, AlignedReturnDataset):
            raise ScenarioValidationError("dataset must be an AlignedReturnDataset")
        positive_integer(
            horizon_trading_days,
            "horizon_trading_days",
            error_type=ScenarioValidationError,
        )
        positive_integer(
            scenario_count,
            "scenario_count",
            error_type=ScenarioValidationError,
        )
        positive_integer(
            block_length,
            "block_length",
            error_type=ScenarioValidationError,
        )
        if block_length > dataset.observation_count:
            raise ScenarioValidationError(
                f"block_length cannot exceed the dataset's "
                f"{dataset.observation_count} return observations"
            )
        if isinstance(random_seed, bool) or (
            random_seed is not None and not isinstance(random_seed, int)
        ):
            raise ScenarioValidationError("random_seed must be an integer or None")

        normalized_as_of_date = scenario_date(as_of_date, "as_of_date")
        if dataset.dates[-1] > normalized_as_of_date:
            raise ScenarioValidationError("dataset contains returns after as_of_date")

        self._scenario_set_id = scenario_set_id
        self._version = version
        self._as_of_date = normalized_as_of_date
        self._horizon_trading_days = horizon_trading_days
        self._dataset = dataset
        self._scenario_count = scenario_count
        self._block_length = block_length
        self._random_seed = random_seed
        self._model_version = model_version
        self._source_snapshot_ids = tuple(source_snapshot_ids)

    @property
    def eligible_block_count(self) -> int:
        """Number of distinct contiguous source blocks available to sample."""

        return self._dataset.observation_count - self._block_length + 1

    @property
    def blocks_per_scenario(self) -> int:
        """Number of draws needed to fill one scenario path."""

        return (
            self._horizon_trading_days + self._block_length - 1
        ) // self._block_length

    def generate(self) -> ScenarioSet:
        """Generate an equally weighted, reproducible bootstrap scenario set."""

        random = Random(self._random_seed)
        scenarios = tuple(
            self._build_path(index, random)
            for index in range(1, self._scenario_count + 1)
        )
        parameters: dict[str, str | int | bool] = {
            "sampling_method": "moving_block",
            "scenario_count": self._scenario_count,
            "block_length": self._block_length,
            "blocks_per_scenario": self.blocks_per_scenario,
            "eligible_block_count": self.eligible_block_count,
            "source_observation_count": self._dataset.observation_count,
            "sample_with_replacement": True,
        }
        if self._random_seed is not None:
            parameters["random_seed"] = self._random_seed

        return ScenarioSet(
            scenario_set_id=self._scenario_set_id,
            version=self._version,
            methodology=ScenarioMethodology.BLOCK_BOOTSTRAP,
            as_of_date=self._as_of_date,
            horizon_trading_days=self._horizon_trading_days,
            scenarios=scenarios,
            model_version=self._model_version,
            parameters=parameters,
            source_snapshot_ids=self._source_snapshot_ids,
        )

    def _build_path(self, scenario_number: int, random: Random) -> ScenarioPath:
        source_indices: list[int] = []
        for _ in range(self.blocks_per_scenario):
            start = random.randrange(self.eligible_block_count)
            source_indices.extend(
                range(start, min(start + self._block_length, self._dataset.observation_count))
            )
        source_indices = source_indices[: self._horizon_trading_days]

        steps = tuple(
            ScenarioStep(
                step_number=step_number,
                asset_returns={
                    symbol: str(self._dataset.returns[symbol][source_index])
                    for symbol in self._dataset.symbols
                },
            )
            for step_number, source_index in enumerate(source_indices, start=1)
        )
        identifier = f"bootstrap-{scenario_number:06d}"
        return ScenarioPath(
            scenario_id=identifier,
            name=f"Block bootstrap scenario {scenario_number}",
            description=(
                f"{self._horizon_trading_days}-day path sampled with replacement "
                f"from contiguous {self._block_length}-day historical blocks."
            ),
            steps=steps,
        )


# The explicit alias mirrors the historical generator's concise public name.
MovingBlockBootstrapScenarioGenerator = BlockBootstrapScenarioGenerator


__all__ = [
    "DEFAULT_BLOCK_BOOTSTRAP_MODEL_VERSION",
    "BlockBootstrapScenarioGenerator",
    "MovingBlockBootstrapScenarioGenerator",
]
