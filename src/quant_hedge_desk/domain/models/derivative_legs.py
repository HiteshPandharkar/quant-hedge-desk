"""Tradable futures and vanilla-option leg contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping

from quant_hedge_desk.domain.enums import (
    InstrumentType,
    LegDirection,
    OptionStyle,
    OptionType,
    Underlying,
)
from quant_hedge_desk.domain.instrument_leg_validation import (
    enum_value,
    expiry_date,
    immutable_liquidity_attributes,
    leg_mapping,
    non_negative_decimal,
    quote_datetime,
    validator,
)


@dataclass(frozen=True, slots=True)
class FutureLeg:
    """One listed index-futures position, expressed as a contract count."""

    underlying: Underlying
    direction: LegDirection
    strike_or_level: Decimal
    expiry: date
    quantity: int
    contract_multiplier: Decimal
    quote_timestamp: datetime
    liquidity_attributes: Mapping[str, object]
    instrument_type: InstrumentType = field(
        default=InstrumentType.FUTURE, init=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "underlying", enum_value(self.underlying, Underlying, "underlying"))
        object.__setattr__(self, "direction", enum_value(self.direction, LegDirection, "direction"))
        object.__setattr__(self, "strike_or_level", validator.positive_decimal(self.strike_or_level, "strike_or_level"))
        object.__setattr__(self, "expiry", expiry_date(self.expiry))
        object.__setattr__(self, "quantity", validator.positive_int(self.quantity, "quantity"))
        object.__setattr__(self, "contract_multiplier", validator.positive_decimal(self.contract_multiplier, "contract_multiplier"))
        object.__setattr__(self, "quote_timestamp", quote_datetime(self.quote_timestamp))
        object.__setattr__(self, "liquidity_attributes", immutable_liquidity_attributes(self.liquidity_attributes))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> FutureLeg:
        required = {
            "underlying", "instrument_type", "direction", "strike_or_level",
            "expiry", "quantity", "contract_multiplier",
            "quote_timestamp", "liquidity_attributes",
        }
        mapping = leg_mapping(
            value,
            path="future leg",
            required=required,
            expected_instrument_type=InstrumentType.FUTURE,
        )
        return cls(**{key: mapping[key] for key in required - {"instrument_type"}})


@dataclass(frozen=True, slots=True)
class VanillaOptionLeg:
    """One listed European call or put position."""

    underlying: Underlying
    direction: LegDirection
    strike_or_level: Decimal
    expiry: date
    quantity: int
    contract_multiplier: Decimal
    premium: Decimal
    quote_timestamp: datetime
    liquidity_attributes: Mapping[str, object]
    option_type: OptionType
    option_style: OptionStyle = OptionStyle.EUROPEAN
    instrument_type: InstrumentType = field(
        default=InstrumentType.OPTION, init=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "underlying", enum_value(self.underlying, Underlying, "underlying"))
        object.__setattr__(self, "direction", enum_value(self.direction, LegDirection, "direction"))
        object.__setattr__(self, "strike_or_level", validator.positive_decimal(self.strike_or_level, "strike_or_level"))
        object.__setattr__(self, "expiry", expiry_date(self.expiry))
        object.__setattr__(self, "quantity", validator.positive_int(self.quantity, "quantity"))
        object.__setattr__(self, "contract_multiplier", validator.positive_decimal(self.contract_multiplier, "contract_multiplier"))
        object.__setattr__(self, "premium", non_negative_decimal(self.premium, "premium"))
        object.__setattr__(self, "quote_timestamp", quote_datetime(self.quote_timestamp))
        object.__setattr__(self, "liquidity_attributes", immutable_liquidity_attributes(self.liquidity_attributes))
        object.__setattr__(self, "option_type", enum_value(self.option_type, OptionType, "option_type"))
        object.__setattr__(self, "option_style", enum_value(self.option_style, OptionStyle, "option_style"))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> VanillaOptionLeg:
        required = {
            "underlying", "instrument_type", "direction", "strike_or_level",
            "expiry", "quantity", "contract_multiplier", "premium",
            "quote_timestamp", "liquidity_attributes", "option_type",
            "option_style",
        }
        mapping = leg_mapping(
            value,
            path="vanilla option leg",
            required=required,
            expected_instrument_type=InstrumentType.OPTION,
        )
        return cls(**{key: mapping[key] for key in required - {"instrument_type"}})


# Compatibility names used in desk terminology.
FuturesLeg = FutureLeg
OptionLeg = VanillaOptionLeg
OptionRight = OptionType


__all__ = [
    "FutureLeg",
    "FuturesLeg",
    "OptionLeg",
    "OptionRight",
    "VanillaOptionLeg",
]
