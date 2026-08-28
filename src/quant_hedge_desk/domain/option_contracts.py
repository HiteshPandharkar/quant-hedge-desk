"""Stable identities for listed option contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from quant_hedge_desk.domain.enums import OptionType, Underlying


def option_contract_id(
    underlying: Underlying | str,
    expiry: date,
    option_type: OptionType | str,
    strike: Decimal,
) -> str:
    """Return the canonical identity shared by candidates, marks, and policy data."""

    underlying_value = Underlying(str(underlying).upper()).value
    option_type_value = OptionType(str(option_type).upper()).value
    normalized_strike = format(strike.normalize(), "f")
    return (
        f"{underlying_value}|{expiry.isoformat()}|"
        f"{option_type_value}|{normalized_strike}"
    )


__all__ = ["option_contract_id"]
