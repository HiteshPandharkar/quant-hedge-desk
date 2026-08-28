"""Exceptions raised by domain contracts and invariants."""


class ScenarioValidationError(ValueError):
    """Raised when a scenario contract is incomplete or inconsistent."""


class RebalancingValidationError(ValueError):
    """Raised when a rebalancing policy or state contract is invalid."""


class RebalancePricingError(ValueError):
    """Raised when a scenario step cannot price a requested rebalance."""


class InstrumentValidationError(ValueError):
    """Raised when a derivative leg is incomplete or inconsistent."""


class HedgeCandidateValidationError(ValueError):
    """Raised when a configured hedge candidate is incomplete or inconsistent."""


class DealerRiskValidationError(ValueError):
    """Raised when a dealer-risk assessment input is invalid."""


class DecisionValidationError(ValueError):
    """Raised when decision evidence is missing or internally inconsistent."""


__all__ = [
    "DecisionValidationError",
    "DealerRiskValidationError",
    "HedgeCandidateValidationError",
    "InstrumentValidationError",
    "RebalancePricingError",
    "RebalancingValidationError",
    "ScenarioValidationError",
]
