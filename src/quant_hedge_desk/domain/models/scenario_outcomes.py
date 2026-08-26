"""Immutable results produced by terminal scenario evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from quant_hedge_desk.serialization import json_ready


@dataclass(frozen=True, slots=True)
class ScenarioOutcome:
    """Auditable terminal valuation for one scenario path."""

    scenario_id: str
    scenario_name: str
    probability: Decimal
    portfolio_return: Decimal
    unhedged_terminal_value: Decimal
    hedge_payoff: Decimal
    hedge_profit: Decimal
    hedged_terminal_value: Decimal
    hedged_return: Decimal
    return_improvement: Decimal


@dataclass(frozen=True, slots=True)
class ScenarioEvaluation:
    """Candidate results and lineage for one complete scenario set."""

    scenario_set_id: str
    scenario_set_version: str
    methodology: str
    model_version: str
    candidate_id: str
    portfolio_id: str
    initial_portfolio_value: Decimal
    all_in_hedge_cost: Decimal
    tail_loss_threshold: Decimal
    unhedged_tail_breach_probability: Decimal
    hedged_tail_breach_probability: Decimal
    outcomes: tuple[ScenarioOutcome, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation without losing decimal precision."""

        return json_ready(asdict(self))


__all__ = ["ScenarioEvaluation", "ScenarioOutcome"]
