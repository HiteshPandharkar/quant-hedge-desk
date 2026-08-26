"""Controlled application-level assessment states."""

from enum import StrEnum


class StageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    NOT_ASSESSED = "NOT_ASSESSED"


__all__ = ["StageStatus"]
