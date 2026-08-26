"""Compatibility imports for tradable derivative-leg domain types."""

from quant_hedge_desk.domain.enums import (
    InstrumentType,
    LegDirection,
    OptionStyle,
    OptionType,
    Underlying,
)
from quant_hedge_desk.domain.errors import InstrumentValidationError
from quant_hedge_desk.domain.models.derivative_legs import (
    FutureLeg,
    FuturesLeg,
    OptionLeg,
    OptionRight,
    VanillaOptionLeg,
)

Direction = LegDirection

__all__ = [
    "Direction",
    "FutureLeg",
    "FuturesLeg",
    "InstrumentType",
    "InstrumentValidationError",
    "LegDirection",
    "OptionLeg",
    "OptionRight",
    "OptionStyle",
    "OptionType",
    "Underlying",
    "VanillaOptionLeg",
]
