"""Terminal contractual payoff calculations for listed derivative legs."""

from __future__ import annotations

from decimal import Decimal

from quant_hedge_desk.domain.enums import LegDirection, OptionType


def direction_sign(direction: LegDirection) -> Decimal:
    """Return the arithmetic sign associated with a leg direction."""

    return Decimal("1") if direction is LegDirection.LONG else Decimal("-1")


def future_terminal_payoff(
    *,
    terminal_level: Decimal,
    entry_level: Decimal,
    quantity: int,
    contract_multiplier: Decimal,
    direction: LegDirection,
) -> Decimal:
    """Return a futures leg's terminal variation value."""

    return (
        direction_sign(direction)
        * (terminal_level - entry_level)
        * quantity
        * contract_multiplier
    )


def option_terminal_payoff(
    *,
    terminal_level: Decimal,
    strike: Decimal,
    quantity: int,
    contract_multiplier: Decimal,
    direction: LegDirection,
    option_type: OptionType,
) -> Decimal:
    """Return a vanilla option leg's terminal intrinsic payoff.

    Premium is deliberately excluded: it is an inception cash flow, while this
    function represents the contractual cash flow at expiry.
    """

    if option_type is OptionType.CALL:
        intrinsic_value = max(terminal_level - strike, Decimal("0"))
    else:
        intrinsic_value = max(strike - terminal_level, Decimal("0"))
    return (
        direction_sign(direction)
        * intrinsic_value
        * quantity
        * contract_multiplier
    )


__all__ = [
    "direction_sign",
    "future_terminal_payoff",
    "option_terminal_payoff",
]
