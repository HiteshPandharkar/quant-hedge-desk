"""Pure arithmetic used by scenario domain models."""

from decimal import Decimal
from typing import Iterable


def compound_simple_returns(returns: Iterable[Decimal]) -> Decimal:
    """Compound a sequence of simple returns into one terminal return."""

    wealth = Decimal("1")
    for period_return in returns:
        wealth *= Decimal("1") + period_return
    return wealth - Decimal("1")


def scenario_probability_weights(
    probabilities: Iterable[Decimal | None],
) -> tuple[Decimal, ...]:
    """Return explicit probabilities or equal weights when none are supplied."""

    values = tuple(probabilities)
    if not values:
        raise ValueError("at least one scenario probability is required")
    if all(value is None for value in values):
        equal_weight = Decimal("1") / Decimal(len(values))
        return tuple(equal_weight for _ in values)
    if any(value is None for value in values):
        raise ValueError("probabilities must be supplied for every scenario or none")
    return tuple(value for value in values if value is not None)


__all__ = ["compound_simple_returns", "scenario_probability_weights"]
