"""Deterministic, mandate-ordered ranking of client-feasible candidates."""

from __future__ import annotations

from typing import Iterable, Sequence

from quant_hedge_desk.domain.enums import SoftObjective
from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus
from quant_hedge_desk.hedge_design.selector_calculations import (
    CandidateRankingCalculator,
)
from quant_hedge_desk.hedge_design.selector_models import (
    CandidateRankingInput,
    ObjectiveValue,
    RankedCandidate,
)


def rank_feasible_candidates(
    candidates: Iterable[CandidateRankingInput],
    soft_objectives: Sequence[SoftObjective | str] = tuple(SoftObjective),
) -> tuple[RankedCandidate, ...]:
    """Rank feasible candidates lexicographically by mandate priority."""

    objectives = CandidateRankingCalculator.validate_objectives(soft_objectives)
    items = tuple(candidates)
    if any(not isinstance(item, CandidateRankingInput) for item in items):
        raise TypeError("candidates must contain only CandidateRankingInput objects")
    identifiers = tuple(item.assessment.candidate_id for item in items)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("candidate IDs must be unique")

    calculators = tuple(
        CandidateRankingCalculator(item, objectives)
        for item in items
        if item.assessment.status is FeasibilityStatus.FEASIBLE
    )
    ordered = sorted(calculators, key=lambda calculator: calculator.ranking_key)
    basis = CandidateRankingCalculator.ranking_basis(objectives)
    return tuple(
        RankedCandidate(
            rank=rank,
            candidate_id=calculator.candidate.assessment.candidate_id,
            family=calculator.candidate.assessment.family,
            objective_values=calculator.objective_values,
            ranking_basis=basis,
        )
        for rank, calculator in enumerate(ordered, start=1)
    )


__all__ = [
    "CandidateRankingCalculator",
    "CandidateRankingInput",
    "ObjectiveValue",
    "RankedCandidate",
    "rank_feasible_candidates",
]
