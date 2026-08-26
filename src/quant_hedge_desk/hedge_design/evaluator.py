"""Terminal evaluation of eligible derivative legs and hedge structures."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping, TypeAlias

from quant_hedge_desk.domain.calculations.payoff import (
    future_terminal_payoff,
    option_terminal_payoff,
)
from quant_hedge_desk.domain.instrument_leg_validation import non_negative_decimal
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg


DerivativeLeg: TypeAlias = FutureLeg | VanillaOptionLeg


def evaluate_terminal_payoff(
    leg: DerivativeLeg, terminal_level: object
) -> Decimal:
    """Evaluate one leg at expiry using exact decimal arithmetic.

    ``terminal_level`` may be any finite, non-negative numeric value accepted
    by the domain's decimal validation rules. Option premium is not deducted
    because this is terminal payoff rather than inception-to-expiry profit.
    """

    level = non_negative_decimal(terminal_level, "terminal_level")
    if isinstance(leg, FutureLeg):
        return future_terminal_payoff(
            terminal_level=level,
            entry_level=leg.strike_or_level,
            quantity=leg.quantity,
            contract_multiplier=leg.contract_multiplier,
            direction=leg.direction,
        )
    if isinstance(leg, VanillaOptionLeg):
        return option_terminal_payoff(
            terminal_level=level,
            strike=leg.strike_or_level,
            quantity=leg.quantity,
            contract_multiplier=leg.contract_multiplier,
            direction=leg.direction,
            option_type=leg.option_type,
        )
    raise TypeError("leg must be a FutureLeg or VanillaOptionLeg")


def evaluate_terminal_payoffs(
    legs: Iterable[DerivativeLeg],
    terminal_levels: Mapping[object, object],
) -> tuple[Decimal, ...]:
    """Return leg-level payoffs using terminal levels keyed by underlying."""

    if not isinstance(terminal_levels, Mapping):
        raise TypeError("terminal_levels must be a mapping")
    normalized_levels = {
        str(key).strip().upper(): value for key, value in terminal_levels.items()
    }
    results: list[Decimal] = []
    for leg in legs:
        if not isinstance(leg, (FutureLeg, VanillaOptionLeg)):
            raise TypeError("legs must contain only FutureLeg or VanillaOptionLeg objects")
        key = leg.underlying.value
        if key not in normalized_levels:
            raise KeyError(key)
        results.append(evaluate_terminal_payoff(leg, normalized_levels[key]))
    return tuple(results)


def evaluate_aggregate_terminal_payoff(
    legs: Iterable[DerivativeLeg],
    terminal_levels: Mapping[object, object],
) -> Decimal:
    """Return the total terminal payoff of all legs in a hedge structure."""

    return sum(evaluate_terminal_payoffs(legs, terminal_levels), Decimal("0"))


# Concise compatibility names for callers that treat this module as arithmetic.
terminal_payoff = evaluate_terminal_payoff
aggregate_terminal_payoff = evaluate_aggregate_terminal_payoff


__all__ = [
    "DerivativeLeg",
    "aggregate_terminal_payoff",
    "evaluate_aggregate_terminal_payoff",
    "evaluate_terminal_payoff",
    "evaluate_terminal_payoffs",
    "terminal_payoff",
]
