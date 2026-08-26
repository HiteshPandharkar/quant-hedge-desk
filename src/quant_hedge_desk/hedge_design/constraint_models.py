"""Immutable outputs from client hard-constraint assessment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus
from quant_hedge_desk.serialization import json_ready


@dataclass(frozen=True, slots=True)
class ConstraintDiagnostic:
    constraint: str
    passed: bool
    actual: str
    limit: str
    detail: str


@dataclass(frozen=True, slots=True)
class ConstraintRelaxation:
    """Smallest policy or input change that would make one failed check pass."""

    constraint: str
    mandate_parameter: str
    current_limit: str
    required_limit: str
    relaxation_amount: str
    unit: str
    detail: str


@dataclass(frozen=True, slots=True)
class InfeasibilityDiagnosis:
    """Binding constraints and actionable alternatives for an infeasible hedge."""

    binding_constraints: tuple[str, ...]
    relaxations: tuple[ConstraintRelaxation, ...]


@dataclass(frozen=True, slots=True)
class CandidateFeasibilityAssessment:
    candidate_id: str
    family: str
    status: FeasibilityStatus
    net_option_premium: Decimal
    estimated_execution_cost: Decimal
    all_in_client_cost: Decimal
    all_in_cost_fraction: Decimal
    premium_constraint_cost: Decimal
    premium_constraint_fraction: Decimal
    gross_reference_notional: Decimal
    protected_reference_notional: Decimal
    notional_coverage_fraction: Decimal
    unhedged_expected_shortfall: float
    hedged_expected_shortfall: float
    unhedged_tail_breach_probability: float
    hedged_tail_breach_probability: float
    tail_breach_reduction: float
    maximum_upside_sacrifice: Decimal
    estimated_unwind_days: Decimal
    failed_constraints: tuple[str, ...]
    diagnostics: tuple[ConstraintDiagnostic, ...]
    infeasibility_diagnosis: InfeasibilityDiagnosis | None
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))


__all__ = [
    "CandidateFeasibilityAssessment",
    "ConstraintDiagnostic",
    "ConstraintRelaxation",
    "InfeasibilityDiagnosis",
]
