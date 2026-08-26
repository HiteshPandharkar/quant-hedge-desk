"""Immutable input and output contracts for candidate ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from quant_hedge_desk.domain.enums import SoftObjective
from quant_hedge_desk.domain.instrument_leg_validation import (
    non_negative_decimal,
    validator,
)
from quant_hedge_desk.hedge_design.constraint_models import (
    CandidateFeasibilityAssessment,
)
from quant_hedge_desk.serialization import json_ready


@dataclass(frozen=True, slots=True)
class CandidateRankingInput:
    """A feasibility result plus independently measured soft-objective inputs.

    All fields are penalties where a lower value is preferable. Turnover is a
    dimensionless fraction. ``complexity`` is a documented ordinal score. The
    robustness penalty must use one consistent definition across the universe.
    """

    assessment: CandidateFeasibilityAssessment
    basis_risk: Decimal
    estimated_turnover: Decimal
    cross_methodology_robustness_penalty: Decimal
    complexity: int

    def __post_init__(self) -> None:
        if not isinstance(self.assessment, CandidateFeasibilityAssessment):
            raise TypeError("assessment must be a CandidateFeasibilityAssessment")
        for name in (
            "basis_risk",
            "estimated_turnover",
            "cross_methodology_robustness_penalty",
        ):
            object.__setattr__(
                self,
                name,
                non_negative_decimal(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "complexity",
            validator.positive_int(self.complexity, "complexity"),
        )


@dataclass(frozen=True, slots=True)
class ObjectiveValue:
    objective: SoftObjective
    values: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    rank: int
    candidate_id: str
    family: str
    objective_values: tuple[ObjectiveValue, ...]
    ranking_basis: str

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))


__all__ = ["CandidateRankingInput", "ObjectiveValue", "RankedCandidate"]
