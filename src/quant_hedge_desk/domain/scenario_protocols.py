"""Interfaces implemented by scenario-generation engines."""

from typing import Protocol, runtime_checkable

from quant_hedge_desk.domain.models.scenario_contracts import ScenarioSet


@runtime_checkable
class ScenarioGenerator(Protocol):
    """Structural interface implemented by each configured scenario engine."""

    def generate(self) -> ScenarioSet:
        """Generate and return one fully validated scenario set."""


__all__ = ["ScenarioGenerator"]
