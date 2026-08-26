"""Configurable generator for manually specified scenario paths."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

from quant_hedge_desk.domain.enums import ScenarioMethodology
from quant_hedge_desk.domain.errors import ScenarioValidationError
from quant_hedge_desk.domain.models.scenario_contracts import (
    ScenarioParameter,
    ScenarioPath,
    ScenarioSet,
)


DEFAULT_MANUAL_MODEL_VERSION = "manual-scenario-generator/1.0"


class ManualScenarioGenerator:
    """Generate a validated scenario set from explicit scenario definitions.

    Manual scenarios are identified as ``NAMED_STRESS`` methodology. Each
    scenario may contain one or many steps and can configure asset returns,
    volatility shifts, spread multipliers and whether rebalancing is allowed.
    The resulting records are immutable, so a generator can be shared safely.
    """

    __slots__ = ("_scenario_set",)

    def __init__(
        self,
        *,
        scenario_set_id: str,
        version: str,
        as_of_date: date | str,
        horizon_trading_days: int,
        scenarios: Iterable[ScenarioPath | Mapping[str, Any]],
        model_version: str = DEFAULT_MANUAL_MODEL_VERSION,
        parameters: Mapping[str, ScenarioParameter] | None = None,
        source_snapshot_ids: Iterable[str] = (),
    ) -> None:
        parsed_scenarios = tuple(
            item
            if isinstance(item, ScenarioPath)
            else ScenarioPath.from_mapping(item)
            for item in scenarios
        )
        self._scenario_set = ScenarioSet(
            scenario_set_id=scenario_set_id,
            version=version,
            methodology=ScenarioMethodology.NAMED_STRESS,
            as_of_date=as_of_date,
            horizon_trading_days=horizon_trading_days,
            scenarios=parsed_scenarios,
            model_version=model_version,
            parameters={} if parameters is None else parameters,
            source_snapshot_ids=tuple(source_snapshot_ids),
        )

    @property
    def configuration(self) -> ScenarioSet:
        """Return the normalized, immutable configuration."""

        return self._scenario_set

    def generate(self) -> ScenarioSet:
        """Return the fully validated manual scenario set."""

        return self._scenario_set

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ManualScenarioGenerator:
        """Build a generator from a serialization-friendly configuration.

        ``methodology`` may be omitted. If supplied, it must be
        ``NAMED_STRESS`` so the generated set's lineage remains truthful.
        """

        if not isinstance(value, Mapping):
            raise ScenarioValidationError("manual_scenario_config must be a mapping")
        allowed = {
            "scenario_set_id",
            "version",
            "methodology",
            "as_of_date",
            "horizon_trading_days",
            "scenarios",
            "model_version",
            "parameters",
            "source_snapshot_ids",
        }
        required = {
            "scenario_set_id",
            "version",
            "as_of_date",
            "horizon_trading_days",
            "scenarios",
        }
        missing = required - value.keys()
        extra = value.keys() - allowed
        if missing:
            raise ScenarioValidationError(
                "manual_scenario_config is missing: "
                + ", ".join(sorted(missing))
            )
        if extra:
            raise ScenarioValidationError(
                "manual_scenario_config has unknown fields: "
                + ", ".join(sorted(extra))
            )

        methodology = value.get(
            "methodology", ScenarioMethodology.NAMED_STRESS
        )
        try:
            normalized_methodology = ScenarioMethodology(str(methodology).upper())
        except ValueError as exc:
            raise ScenarioValidationError(
                "manual_scenario_config.methodology must be NAMED_STRESS"
            ) from exc
        if normalized_methodology is not ScenarioMethodology.NAMED_STRESS:
            raise ScenarioValidationError(
                "manual_scenario_config.methodology must be NAMED_STRESS"
            )

        raw_scenarios = value["scenarios"]
        if isinstance(raw_scenarios, (str, bytes)) or not isinstance(
            raw_scenarios, (list, tuple)
        ):
            raise ScenarioValidationError(
                "manual_scenario_config.scenarios must be a sequence"
            )
        raw_sources = value.get("source_snapshot_ids", ())
        if isinstance(raw_sources, (str, bytes)) or not isinstance(
            raw_sources, (list, tuple)
        ):
            raise ScenarioValidationError(
                "manual_scenario_config.source_snapshot_ids must be a sequence"
            )

        return cls(
            scenario_set_id=value["scenario_set_id"],
            version=value["version"],
            as_of_date=value["as_of_date"],
            horizon_trading_days=value["horizon_trading_days"],
            scenarios=raw_scenarios,
            model_version=value.get(
                "model_version", DEFAULT_MANUAL_MODEL_VERSION
            ),
            parameters=value.get("parameters"),
            source_snapshot_ids=raw_sources,
        )


__all__ = ["DEFAULT_MANUAL_MODEL_VERSION", "ManualScenarioGenerator"]
