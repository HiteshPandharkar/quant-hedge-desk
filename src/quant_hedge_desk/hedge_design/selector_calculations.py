"""Pure calculations and validation used by candidate ranking."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from quant_hedge_desk.domain.enums import SoftObjective
from quant_hedge_desk.domain.instrument_leg_validation import non_negative_decimal
from quant_hedge_desk.hedge_design.selector_models import (
    CandidateRankingInput,
    ObjectiveValue,
)


class CandidateRankingCalculator:
    """Calculate sortable soft-objective values for one candidate."""

    def __init__(
        self,
        candidate: CandidateRankingInput,
        objectives: Sequence[SoftObjective | str],
    ) -> None:
        if not isinstance(candidate, CandidateRankingInput):
            raise TypeError("candidate must be a CandidateRankingInput")
        self.candidate = candidate
        self.objectives = self.validate_objectives(objectives)
        self.objective_values = tuple(
            ObjectiveValue(objective, self._values_for(objective))
            for objective in self.objectives
        )

    def _values_for(self, objective: SoftObjective) -> tuple[Decimal, ...]:
        """Return lower-is-better values for one soft objective."""

        assessment = self.candidate.assessment
        if objective is SoftObjective.RESIDUAL_EXPECTED_SHORTFALL:
            # Expected shortfall is stored as a signed return; ranking uses a
            # positive residual-loss penalty.
            return (
                max(
                    Decimal("0"),
                    -Decimal(str(assessment.hedged_expected_shortfall)),
                ),
            )
        if objective is SoftObjective.TAIL_BREACH_PROBABILITY:
            return (
                non_negative_decimal(
                    assessment.hedged_tail_breach_probability,
                    "hedged_tail_breach_probability",
                ),
            )
        if objective is SoftObjective.BASIS_RISK:
            return (self.candidate.basis_risk,)
        if objective is SoftObjective.TURNOVER_AND_COST:
            return (
                self.candidate.estimated_turnover,
                non_negative_decimal(
                    assessment.all_in_cost_fraction,
                    "all_in_cost_fraction",
                ),
                non_negative_decimal(
                    assessment.estimated_execution_cost,
                    "estimated_execution_cost",
                ),
            )
        if objective is SoftObjective.CROSS_METHODOLOGY_ROBUSTNESS:
            return (self.candidate.cross_methodology_robustness_penalty,)
        if objective is SoftObjective.SIMPLICITY:
            return (Decimal(self.candidate.complexity),)
        raise ValueError(f"unsupported soft objective: {objective!r}")

    @property
    def ranking_key(self) -> tuple[tuple[Decimal, ...], str]:
        """Flatten objective values and append the deterministic tie-break."""

        return (
            tuple(
                value
                for objective in self.objective_values
                for value in objective.values
            ),
            self.candidate.assessment.candidate_id,
        )

    @staticmethod
    def validate_objectives(
        soft_objectives: Sequence[SoftObjective | str],
    ) -> tuple[SoftObjective, ...]:
        """Normalize and validate a mandate's ordered soft objectives."""

        try:
            objectives = tuple(SoftObjective(value) for value in soft_objectives)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "soft_objectives contains an unsupported objective"
            ) from exc
        if not objectives:
            raise ValueError("soft_objectives must be non-empty")
        if len(objectives) != len(set(objectives)):
            raise ValueError("soft_objectives must be unique")
        return objectives

    @staticmethod
    def ranking_basis(objectives: Sequence[SoftObjective]) -> str:
        return (
            "Lower penalties are preferred in mandate order: "
            + " > ".join(objective.value for objective in objectives)
            + "; candidate_id breaks exact ties."
        )


__all__ = ["CandidateRankingCalculator"]
