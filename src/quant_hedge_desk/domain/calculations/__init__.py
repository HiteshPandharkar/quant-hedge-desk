"""Pure domain calculations used by models and application services."""

from quant_hedge_desk.domain.calculations.dealer_risk_limits import (
    assess_dealer_risk,
    build_risk_limit_diagnostic,
)

from quant_hedge_desk.domain.calculations.portfolio import (
    calculate_holding_market_value,
    calculate_total_market_value,
    relative_difference,
)
from quant_hedge_desk.domain.calculations.payoff import (
    direction_sign,
    future_terminal_payoff,
    option_terminal_payoff,
)
from quant_hedge_desk.domain.calculations.scenario_math import (
    compound_simple_returns,
    scenario_probability_weights,
)

__all__ = [
    "assess_dealer_risk",
    "build_risk_limit_diagnostic",
    "calculate_holding_market_value",
    "calculate_total_market_value",
    "compound_simple_returns",
    "direction_sign",
    "future_terminal_payoff",
    "option_terminal_payoff",
    "relative_difference",
    "scenario_probability_weights",
]
