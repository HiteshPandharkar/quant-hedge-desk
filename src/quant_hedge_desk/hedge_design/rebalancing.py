"""Pure pricing, target, and trigger logic for candidate rebalancing stresses."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from math import erf, exp, gcd, log, sqrt
from typing import Mapping

from quant_hedge_desk.domain.enums import (
    LegDirection,
    OptionType,
    RebalancingPricingMode,
    RebalanceTriggerType,
)
from quant_hedge_desk.domain.errors import (
    RebalancePricingError,
    RebalancingValidationError,
)
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg
from quant_hedge_desk.domain.models.rebalancing import (
    PositionState,
    RebalanceProposal,
    RebalancingStressPolicy,
)
from quant_hedge_desk.domain.models.scenario_contracts import ScenarioStep
from quant_hedge_desk.domain.option_contracts import option_contract_id
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate


def contract_id_for_leg(leg: FutureLeg | VanillaOptionLeg) -> str:
    """Return a stable identity for one candidate leg."""

    if isinstance(leg, VanillaOptionLeg):
        return option_contract_id(
            leg.underlying, leg.expiry, leg.option_type, leg.strike_or_level
        )
    level = format(leg.strike_or_level.normalize(), "f")
    return f"{leg.underlying.value}|{leg.expiry.isoformat()}|FUTURE|{level}"


def initial_position(candidate: HedgeCandidate) -> PositionState:
    """Build the inception position keyed by stable contract identity."""

    quantities = {contract_id_for_leg(leg): leg.quantity for leg in candidate.legs}
    if len(quantities) != len(candidate.legs):
        raise RebalancingValidationError("candidate legs must have unique contract identities")
    return PositionState(candidate.candidate_id, quantities)


def black_76_option_price(
    *,
    forward: Decimal | str | int,
    strike: Decimal | str | int,
    risk_free_rate: Decimal | str | int,
    volatility: Decimal | str | int,
    time_to_expiry_years: Decimal | str | int,
    option_type: OptionType | str,
) -> Decimal:
    """Price a European option on a forward using the Black-76 formula."""

    values: dict[str, Decimal] = {}
    for name, raw_value in {
        "forward": forward,
        "strike": strike,
        "risk_free_rate": risk_free_rate,
        "volatility": volatility,
        "time_to_expiry_years": time_to_expiry_years,
    }.items():
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RebalancePricingError(f"{name} must be numeric") from exc
        if not value.is_finite():
            raise RebalancePricingError(f"{name} must be finite")
        values[name] = value
    if values["forward"] <= 0 or values["strike"] <= 0:
        raise RebalancePricingError("forward and strike must be positive")
    if values["time_to_expiry_years"] <= 0:
        raise RebalancePricingError("time_to_expiry_years must be positive")
    if values["volatility"] <= 0 or values["volatility"] > 1:
        raise RebalancePricingError("volatility must be in (0, 1]")
    try:
        kind = OptionType(str(option_type).upper())
    except ValueError as exc:
        raise RebalancePricingError("option_type must be CALL or PUT") from exc

    f = float(values["forward"])
    k = float(values["strike"])
    rate = float(values["risk_free_rate"])
    sigma = float(values["volatility"])
    time = float(values["time_to_expiry_years"])
    sigma_root_time = sigma * sqrt(time)
    d1 = (log(f / k) + 0.5 * sigma * sigma * time) / sigma_root_time
    d2 = d1 - sigma_root_time
    def normal(value: float) -> float:
        return 0.5 * (1.0 + erf(value / sqrt(2.0)))

    discount = exp(-rate * time)
    if kind is OptionType.CALL:
        price = discount * (f * normal(d1) - k * normal(d2))
    else:
        price = discount * (k * normal(-d2) - f * normal(-d1))
    return Decimal(str(price))


def resolve_option_prices(
    candidate: HedgeCandidate,
    step: ScenarioStep,
    policy: RebalancingStressPolicy,
    *,
    contract_ids: set[str] | None = None,
) -> Mapping[str, Decimal]:
    """Resolve scenario prices for candidate option legs or fail with context."""

    option_legs = tuple(
        leg
        for leg in candidate.legs
        if isinstance(leg, VanillaOptionLeg)
        and (contract_ids is None or contract_id_for_leg(leg) in contract_ids)
    )
    if policy.pricing_mode is RebalancingPricingMode.EXPLICIT_MARKS:
        marks = {mark.contract_id: mark.mark for mark in step.option_marks}
        missing = sorted(
            contract_id_for_leg(leg)
            for leg in option_legs
            if contract_id_for_leg(leg) not in marks
        )
        if missing:
            raise RebalancePricingError("missing explicit option marks: " + ", ".join(missing))
        return {contract_id_for_leg(leg): marks[contract_id_for_leg(leg)] for leg in option_legs}

    if step.observation_date is None:
        raise RebalancePricingError("BLACK_76 requires observation_date")
    if step.risk_free_rate is None:
        raise RebalancePricingError("BLACK_76 requires risk_free_rate")
    prices: dict[str, Decimal] = {}
    for leg in option_legs:
        contract_id = contract_id_for_leg(leg)
        symbol = leg.underlying.value
        if symbol not in step.forward_levels:
            raise RebalancePricingError(f"BLACK_76 requires forward_levels.{symbol}")
        if contract_id not in policy.base_volatilities:
            raise RebalancePricingError(
                f"BLACK_76 requires base_volatilities.{contract_id}"
            )
        effective_volatility = (
            policy.base_volatilities[contract_id]
            + step.implied_volatility_shifts.get(symbol, Decimal("0"))
        )
        days = (leg.expiry - step.observation_date).days
        if days <= 0:
            raise RebalancePricingError(
                f"BLACK_76 contract {contract_id} must expire after observation_date"
            )
        prices[contract_id] = black_76_option_price(
            forward=step.forward_levels[symbol],
            strike=leg.strike_or_level,
            risk_free_rate=step.risk_free_rate,
            volatility=effective_volatility,
            time_to_expiry_years=Decimal(days) / Decimal("365"),
            option_type=leg.option_type,
        )
    return prices


def _positive_decimal(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RebalancingValidationError(f"{name} must be numeric") from exc
    if not result.is_finite() or result <= 0:
        raise RebalancingValidationError(f"{name} must be positive and finite")
    return result


def _protective_leg(leg: FutureLeg | VanillaOptionLeg) -> bool:
    return (
        isinstance(leg, FutureLeg) and leg.direction is LegDirection.SHORT
    ) or (
        isinstance(leg, VanillaOptionLeg)
        and leg.direction is LegDirection.LONG
        and leg.option_type is OptionType.PUT
    )


def target_quantities(
    candidate: HedgeCandidate,
    *,
    inception_portfolio_value: Decimal | str | int,
    current_portfolio_value: Decimal | str | int,
    current_underlying_levels: Mapping[str, Decimal | str | int],
) -> Mapping[str, int]:
    """Scale inception structures to retain their per-underlying coverage fractions."""

    inception_value = _positive_decimal(inception_portfolio_value, "inception_portfolio_value")
    current_value = _positive_decimal(current_portfolio_value, "current_portfolio_value")
    targets: dict[str, int] = {}
    symbols = {leg.underlying.value for leg in candidate.legs}
    for symbol in symbols:
        if symbol not in current_underlying_levels:
            raise RebalancingValidationError(f"current_underlying_levels.{symbol} is required")
        current_level = _positive_decimal(
            current_underlying_levels[symbol], f"current_underlying_levels.{symbol}"
        )
        group = tuple(leg for leg in candidate.legs if leg.underlying.value == symbol)
        anchors = tuple(leg for leg in group if _protective_leg(leg))
        if not anchors:
            raise RebalancingValidationError(f"candidate has no protective {symbol} leg")
        anchor = anchors[0]

        # Calculate the contract quantity required today to retain the hedge's
        # inception coverage fraction of the portfolio:
        # Q_target = Q_0 * (V_portfolio,current / V_portfolio,inception)
        #                  * (S_0 / S_current)
        # Q_0 is the inception contract quantity, V is portfolio value, and S
        # is the underlying level. The portfolio-value ratio resizes the hedge
        # with the portfolio, while the inverse underlying-level ratio offsets
        # the changed exposure represented by each contract.
        # Establish the anchor's inception reference notional so its original
        # share of portfolio value can be preserved.
        inception_notional = (
            # Start with the underlying level used when the hedge was created.
            candidate.initial_levels[symbol]
            # Apply the anchor's inception contract count.
            * anchor.quantity
            # Convert each contract into its underlying-equivalent exposure.
            * anchor.contract_multiplier
        )

        # Apply the inception coverage fraction to today's portfolio value.
        desired_notional = inception_notional / inception_value * current_value

        # Convert today's desired notional into an unrounded anchor quantity.
        raw_anchor_quantity = desired_notional / (current_level * anchor.contract_multiplier)

        # Reduce the inception leg quantities to their smallest whole-number
        # bundle, such as reducing 200:300 to the ratio 2:3.
        structure_quantum = gcd(*(leg.quantity for leg in group))

        # Express the desired anchor quantity as a number of complete bundles.
        raw_structure_count = raw_anchor_quantity * structure_quantum / anchor.quantity

        # Round bundles once so individual-leg rounding cannot distort the structure.
        structure_count = int(raw_structure_count.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        for leg in group:
            # Rebuild each leg from the same rounded bundle count to retain its
            # exact inception ratio to every other leg in the structure.
            targets[contract_id_for_leg(leg)] = structure_count * leg.quantity // structure_quantum
    return dict(sorted(targets.items()))


def coverage_drifts(
    candidate: HedgeCandidate,
    position: PositionState,
    *,
    inception_portfolio_value: Decimal | str | int,
    current_portfolio_value: Decimal | str | int,
    current_underlying_levels: Mapping[str, Decimal | str | int],
) -> Mapping[str, Decimal]:
    """Return absolute relative drift from each inception coverage allocation."""

    if position.candidate_id != candidate.candidate_id:
        raise RebalancingValidationError("position candidate_id does not match candidate")
    inception_value = _positive_decimal(inception_portfolio_value, "inception_portfolio_value")
    current_value = _positive_decimal(current_portfolio_value, "current_portfolio_value")
    drifts: dict[str, Decimal] = {}
    for symbol in {leg.underlying.value for leg in candidate.legs}:
        if symbol not in current_underlying_levels:
            raise RebalancingValidationError(f"current_underlying_levels.{symbol} is required")
        current_level = _positive_decimal(
            current_underlying_levels[symbol], f"current_underlying_levels.{symbol}"
        )
        anchor = next(
            leg for leg in candidate.legs
            if leg.underlying.value == symbol and _protective_leg(leg)
        )
        contract_id = contract_id_for_leg(anchor)
        if contract_id not in position.quantities:
            raise RebalancingValidationError(f"position is missing contract {contract_id}")
        inception_coverage = (
            candidate.initial_levels[symbol]
            * anchor.quantity
            * anchor.contract_multiplier
            / inception_value
        )
        current_coverage = (
            current_level
            * position.quantities[contract_id]
            * anchor.contract_multiplier
            / current_value
        )
        drifts[symbol] = abs(current_coverage / inception_coverage - Decimal("1"))
    return dict(sorted(drifts.items()))


def determine_rebalance_trigger(
    *,
    step_number: int,
    is_terminal_step: bool,
    drifts: Mapping[str, Decimal],
    policy: RebalancingStressPolicy,
) -> RebalanceTriggerType | None:
    """Select the trigger for a step, giving exceptional drift precedence."""

    if isinstance(step_number, bool) or not isinstance(step_number, int) or step_number <= 0:
        raise RebalancingValidationError("step_number must be a positive integer")
    if not isinstance(is_terminal_step, bool):
        raise RebalancingValidationError("is_terminal_step must be boolean")
    if is_terminal_step:
        return None
    if step_number % policy.routine_interval_trading_days == 0:
        return RebalanceTriggerType.ROUTINE
    if any(abs(Decimal(str(value))) > policy.exceptional_coverage_drift_threshold for value in drifts.values()):
        return RebalanceTriggerType.EXCEPTIONAL
    return None


def propose_rebalance(
    candidate: HedgeCandidate,
    position: PositionState,
    step: ScenarioStep,
    policy: RebalancingStressPolicy,
    *,
    inception_portfolio_value: Decimal | str | int,
    current_portfolio_value: Decimal | str | int,
    current_underlying_levels: Mapping[str, Decimal | str | int],
    is_terminal_step: bool,
) -> RebalanceProposal | None:
    """Create and price a resize request without executing or mutating state."""

    targets = target_quantities(
        candidate,
        inception_portfolio_value=inception_portfolio_value,
        current_portfolio_value=current_portfolio_value,
        current_underlying_levels=current_underlying_levels,
    )
    current = dict(position.quantities)
    if set(current) != set(targets):
        raise RebalancingValidationError("position contracts do not match candidate legs")
    trigger = determine_rebalance_trigger(
        step_number=step.step_number,
        is_terminal_step=is_terminal_step,
        drifts=coverage_drifts(
            candidate,
            position,
            inception_portfolio_value=inception_portfolio_value,
            current_portfolio_value=current_portfolio_value,
            current_underlying_levels=current_underlying_levels,
        ),
        policy=policy,
    )
    changes = {key: targets[key] - current[key] for key in targets}
    if trigger is None or not any(changes.values()):
        return None
    changed_contracts = {key for key, change in changes.items() if change}
    rejection_reason: str | None = None
    prices: Mapping[str, Decimal] = {}
    try:
        prices = resolve_option_prices(
            candidate, step, policy, contract_ids=changed_contracts
        )
    except RebalancePricingError as exc:
        rejection_reason = str(exc)
    return RebalanceProposal(
        candidate_id=candidate.candidate_id,
        step_number=step.step_number,
        trigger_type=trigger,
        current_quantities=current,
        target_quantities=targets,
        requested_changes=changes,
        option_prices=prices,
        rejection_reason=rejection_reason,
    )


__all__ = [
    "black_76_option_price",
    "contract_id_for_leg",
    "coverage_drifts",
    "determine_rebalance_trigger",
    "initial_position",
    "propose_rebalance",
    "resolve_option_prices",
    "target_quantities",
]
