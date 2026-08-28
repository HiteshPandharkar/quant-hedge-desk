"""Controlled vocabularies shared by domain models."""

from enum import StrEnum


class Underlying(StrEnum):
    NIFTY = "NIFTY"
    BANKNIFTY = "BANKNIFTY"


class InstrumentType(StrEnum):
    FUTURE = "FUTURE"
    OPTION = "OPTION"


class OptionStyle(StrEnum):
    EUROPEAN = "EUROPEAN"


class LegDirection(StrEnum):
    """Economic direction of a derivative leg."""

    LONG = "LONG"
    SHORT = "SHORT"


class OptionType(StrEnum):
    """Payoff type of a vanilla option."""

    CALL = "CALL"
    PUT = "PUT"


class RebalanceFrequency(StrEnum):
    WEEKLY = "WEEKLY"


class RebalancingPricingMode(StrEnum):
    """Supported sources for pricing resize trades during a stress path."""

    EXPLICIT_MARKS = "EXPLICIT_MARKS"
    BLACK_76 = "BLACK_76"


class RebalanceTriggerType(StrEnum):
    """Reason a resize was required at a scenario step."""

    ROUTINE = "ROUTINE"
    EXCEPTIONAL = "EXCEPTIONAL"
    PENDING = "PENDING"


class SoftObjective(StrEnum):
    RESIDUAL_EXPECTED_SHORTFALL = "RESIDUAL_EXPECTED_SHORTFALL"
    TAIL_BREACH_PROBABILITY = "TAIL_BREACH_PROBABILITY"
    BASIS_RISK = "BASIS_RISK"
    TURNOVER_AND_COST = "TURNOVER_AND_COST"
    CROSS_METHODOLOGY_ROBUSTNESS = "CROSS_METHODOLOGY_ROBUSTNESS"
    SIMPLICITY = "SIMPLICITY"


class ScenarioMethodology(StrEnum):
    """Approved scenario methodologies from the business requirements."""

    HISTORICAL = "HISTORICAL"
    BLOCK_BOOTSTRAP = "BLOCK_BOOTSTRAP"
    FACTOR_SIMULATION = "FACTOR_SIMULATION"
    NAMED_STRESS = "NAMED_STRESS"


class RiskLimitStatus(StrEnum):
    """Outcome of comparing post-trade utilization with a dealer limit."""

    PASS = "PASS"
    WARNING = "WARNING"
    BREACH = "BREACH"


class PreTradeDecision(StrEnum):
    """Exactly one primary outcome required by the business rules."""

    QUOTE = "QUOTE"
    QUOTE_WITH_ADDITIONAL_RESERVE = "QUOTE_WITH_ADDITIONAL_RESERVE"
    REDUCE_NOTIONAL = "REDUCE_NOTIONAL"
    RESTRUCTURE = "RESTRUCTURE"
    DECLINE = "DECLINE"


class CandidateRelationship(StrEnum):
    """How a candidate relates to the transaction originally requested."""

    REQUESTED = "REQUESTED"
    REDUCED_NOTIONAL = "REDUCED_NOTIONAL"
    RESTRUCTURED = "RESTRUCTURED"


__all__ = [
    "CandidateRelationship",
    "InstrumentType",
    "LegDirection",
    "OptionStyle",
    "OptionType",
    "PreTradeDecision",
    "RebalanceFrequency",
    "RebalancingPricingMode",
    "RebalanceTriggerType",
    "RiskLimitStatus",
    "ScenarioMethodology",
    "SoftObjective",
    "Underlying",
]
