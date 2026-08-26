"""Pure calculations used to value hedge candidates on scenario paths."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Iterable, Mapping

from quant_hedge_desk.domain.enums import LegDirection
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg
from quant_hedge_desk.domain.models.portfolio import Portfolio
from quant_hedge_desk.domain.models.scenario_contracts import ScenarioPath
from quant_hedge_desk.domain.models.scenario_outcomes import ScenarioOutcome
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.evaluator import evaluate_aggregate_terminal_payoff


def positive_fraction(value: Decimal | str, name: str) -> Decimal:
    """Normalize a finite fraction in ``(0, 1]``."""

    if isinstance(value, bool):
        raise ValueError(f"{name} must be in (0, 1]")
    try:
        result = Decimal(str(value).strip())
    except Exception as exc:
        raise ValueError(f"{name} must be in (0, 1]") from exc
    if not result.is_finite() or result <= 0 or result > 1:
        raise ValueError(f"{name} must be in (0, 1]")
    return result


def net_option_premium(candidate: HedgeCandidate) -> Decimal:
    """Return premiums paid less premiums received across candidate legs."""

    premium = Decimal("0")
    for leg in candidate.legs:
        if isinstance(leg, FutureLeg):
            continue
        if not isinstance(leg, VanillaOptionLeg):
            raise TypeError("candidate legs must be futures or vanilla options")
        sign = Decimal("1") if leg.direction is LegDirection.LONG else Decimal("-1")
        premium += sign * leg.premium * leg.quantity * leg.contract_multiplier
    return premium


def all_in_hedge_cost(candidate: HedgeCandidate) -> Decimal:
    """Return net option premium plus the candidate's execution cost."""

    return net_option_premium(candidate) + candidate.estimated_execution_cost


def terminal_levels_from_returns(
    initial_levels: Mapping[str, Decimal],
    terminal_returns: Mapping[str, Decimal],
) -> Mapping[str, Decimal]:
    """Convert terminal returns to levels using supplied initial references."""

    return {
        symbol: initial_levels[symbol] * (Decimal("1") + terminal_return)
        for symbol, terminal_return in terminal_returns.items()
    }


def portfolio_terminal_return(
    scenario: ScenarioPath, portfolio: Portfolio
) -> Decimal:
    """Return the supplied aggregate shock or derive a buy-and-hold return."""

    if "PORTFOLIO" in scenario.symbols:
        return scenario.terminal_return("PORTFOLIO")
    return sum(
        (
            holding.portfolio_weight * scenario.terminal_return(holding.symbol)
            for holding in portfolio.holdings
        ),
        Decimal("0"),
    )


def candidate_terminal_levels(
    scenario: ScenarioPath,
    candidate: HedgeCandidate,
    underlying_symbols: Iterable[str],
) -> Mapping[str, Decimal]:
    """Convert scenario returns to terminal index levels for candidate valuation."""

    return terminal_levels_from_returns(
        candidate.initial_levels,
        {
            symbol: scenario.terminal_return(symbol)
            for symbol in underlying_symbols
        },
    )


def calculate_scenario_outcome(
    *,
    scenario: ScenarioPath,
    probability: Decimal,
    portfolio: Portfolio,
    candidate: HedgeCandidate,
    underlying_symbols: Iterable[str],
    all_in_hedge_cost: Decimal,
) -> ScenarioOutcome:
    """Calculate all terminal values for one scenario path."""

    initial_value = portfolio.total_market_value
    portfolio_return = portfolio_terminal_return(scenario, portfolio)
    hedge_payoff = evaluate_aggregate_terminal_payoff(
        candidate.legs,
        candidate_terminal_levels(scenario, candidate, underlying_symbols),
    )
    hedge_profit = hedge_payoff - all_in_hedge_cost
    unhedged_value = initial_value * (Decimal("1") + portfolio_return)
    hedged_value = unhedged_value + hedge_profit
    hedged_return = hedged_value / initial_value - Decimal("1")
    return ScenarioOutcome(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        probability=probability,
        portfolio_return=portfolio_return,
        unhedged_terminal_value=unhedged_value,
        hedge_payoff=hedge_payoff,
        hedge_profit=hedge_profit,
        hedged_terminal_value=hedged_value,
        hedged_return=hedged_return,
        return_improvement=hedged_return - portfolio_return,
    )


def tail_breach_probability(
    outcomes: Iterable[ScenarioOutcome],
    *,
    threshold: Decimal,
    return_value: Callable[[ScenarioOutcome], Decimal],
) -> Decimal:
    """Sum scenario probabilities whose selected return breaches the loss limit."""

    signed_threshold = -threshold
    return sum(
        (
            outcome.probability
            for outcome in outcomes
            if return_value(outcome) < signed_threshold
        ),
        Decimal("0"),
    )


__all__ = [
    "all_in_hedge_cost",
    "calculate_scenario_outcome",
    "candidate_terminal_levels",
    "net_option_premium",
    "portfolio_terminal_return",
    "positive_fraction",
    "tail_breach_probability",
    "terminal_levels_from_returns",
]
