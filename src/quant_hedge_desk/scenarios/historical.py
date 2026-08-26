"""Historical scenarios built from rolling windows of aligned daily returns."""

from __future__ import annotations

from datetime import date
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


DEFAULT_HISTORICAL_MODEL_VERSION = "historical-rolling-windows/1.0"


class HistoricalRollingScenarioGenerator:
    """Replay every eligible fixed-length window in an aligned return dataset.

    A path contains the actual ordered daily returns in its historical window,
    rather than only its terminal return.  This lets downstream valuations
    assess both terminal P&L and intra-horizon drawdowns.  Windows receive no
    explicit probability, so :class:`ScenarioSet` assigns equal empirical
    weights.

    ``window_stride=1`` creates overlapping rolling windows.  Set the stride
    equal to ``horizon_trading_days`` for non-overlapping windows.
    """

    __slots__ = (
        "_as_of_date",
        "_dataset",
        "_horizon_trading_days",
        "_model_version",
        "_scenario_set_id",
        "_source_snapshot_ids",
        "_version",
        "_window_stride",
    )

    def __init__(
        self,
        *,
        scenario_set_id: str,
        version: str,
        as_of_date: date | str,
        horizon_trading_days: int,
        dataset: AlignedReturnDataset,
        window_stride: int = 1,
        model_version: str = DEFAULT_HISTORICAL_MODEL_VERSION,
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
            window_stride,
            "window_stride",
            error_type=ScenarioValidationError,
        )
        if dataset.observation_count < horizon_trading_days:
            raise ScenarioValidationError(
                f"dataset has {dataset.observation_count} returns; at least "
                f"{horizon_trading_days} are required for one historical window"
            )

        normalized_as_of_date = scenario_date(as_of_date, "as_of_date")
        if dataset.dates[-1] > normalized_as_of_date:
            raise ScenarioValidationError(
                "dataset contains returns after as_of_date"
            )

        self._scenario_set_id = scenario_set_id
        self._version = version
        self._as_of_date = normalized_as_of_date
        self._horizon_trading_days = horizon_trading_days
        self._dataset = dataset
        self._window_stride = window_stride
        self._model_version = model_version
        self._source_snapshot_ids = tuple(source_snapshot_ids)

    @property
    def window_count(self) -> int:
        """Number of complete windows that will be generated."""

        available_starts = (
            self._dataset.observation_count - self._horizon_trading_days
        )
        return available_starts // self._window_stride + 1

    def generate(self) -> ScenarioSet:
        """Return a validated historical scenario set in chronological order."""

        scenarios = tuple(
            self._build_path(start)
            for start in range(
                0,
                self._dataset.observation_count
                - self._horizon_trading_days
                + 1,
                self._window_stride,
            )
        )
        return ScenarioSet(
            scenario_set_id=self._scenario_set_id,
            version=self._version,
            methodology=ScenarioMethodology.HISTORICAL,
            as_of_date=self._as_of_date,
            horizon_trading_days=self._horizon_trading_days,
            scenarios=scenarios,
            model_version=self._model_version,
            parameters={
                "window_length": self._horizon_trading_days,
                "window_stride": self._window_stride,
                "overlapping": self._window_stride < self._horizon_trading_days,
                "source_observation_count": self._dataset.observation_count,
                "window_count": len(scenarios),
            },
            source_snapshot_ids=self._source_snapshot_ids,
        )

    def _build_path(self, start: int) -> ScenarioPath:
        stop = start + self._horizon_trading_days
        start_date = self._dataset.price_dates[start]
        end_date = self._dataset.price_dates[stop]
        steps = tuple(
            ScenarioStep(
                step_number=offset + 1,
                observation_date=self._dataset.dates[index],
                asset_returns={
                    symbol: str(self._dataset.returns[symbol][index])
                    for symbol in self._dataset.symbols
                },
            )
            for offset, index in enumerate(range(start, stop))
        )
        date_range = f"{start_date.isoformat()}-to-{end_date.isoformat()}"
        return ScenarioPath(
            scenario_id=f"historical-{date_range}",
            name=f"Historical window {start_date.isoformat()} to {end_date.isoformat()}",
            description=(
                f"Replay of {self._horizon_trading_days} aligned daily returns "
                f"from {start_date.isoformat()} through {end_date.isoformat()}."
            ),
            steps=steps,
        )


# A concise alias for callers that do not need to distinguish rolling from
# other future historical methodologies.
HistoricalScenarioGenerator = HistoricalRollingScenarioGenerator


__all__ = [
    "DEFAULT_HISTORICAL_MODEL_VERSION",
    "HistoricalRollingScenarioGenerator",
    "HistoricalScenarioGenerator",
]
