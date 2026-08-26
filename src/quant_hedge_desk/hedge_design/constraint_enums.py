"""Controlled vocabulary for client hard-constraint assessment."""

from enum import StrEnum


class FeasibilityStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"


__all__ = ["FeasibilityStatus"]
