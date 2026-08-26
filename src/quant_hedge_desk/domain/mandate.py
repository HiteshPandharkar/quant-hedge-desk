"""Compatibility imports for mandate domain types.

New code may import dataclasses from ``domain.models.mandate`` and controlled
vocabularies from ``domain.enums`` directly.
"""

from quant_hedge_desk.domain.enums import (
    InstrumentType,
    OptionStyle,
    RebalanceFrequency,
    SoftObjective,
    Underlying,
)
from quant_hedge_desk.domain.models.mandate import (
    ClientMandate,
    CostConstraint,
    EligibilityConstraint,
    LiquidityConstraint,
    Mandate,
    MandateValidationError,
    ProtectionConstraint,
    RebalancingPolicy,
    RequirementInterpretation,
    UpsideConstraint,
)

__all__ = [
    "ClientMandate", "CostConstraint", "EligibilityConstraint",
    "InstrumentType", "LiquidityConstraint", "Mandate", "MandateValidationError",
    "OptionStyle", "ProtectionConstraint", "RebalanceFrequency", "RebalancingPolicy",
    "RequirementInterpretation", "SoftObjective", "Underlying", "UpsideConstraint",
]
