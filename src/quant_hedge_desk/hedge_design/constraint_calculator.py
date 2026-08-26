"""Class-based calculation of every client hard constraint."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Mapping, Sequence

from quant_hedge_desk.analytics.risk import expected_shortfall
from quant_hedge_desk.domain.enums import LegDirection, OptionType
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg
from quant_hedge_desk.domain.models.mandate import Mandate
from quant_hedge_desk.domain.models.portfolio import Portfolio
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.constraint_enums import FeasibilityStatus
from quant_hedge_desk.hedge_design.constraint_models import (
    CandidateFeasibilityAssessment,
    ConstraintDiagnostic,
    ConstraintRelaxation,
    InfeasibilityDiagnosis,
)
from quant_hedge_desk.hedge_design.evaluator import evaluate_aggregate_terminal_payoff
from quant_hedge_desk.hedge_design.scenario_calculations import (
    all_in_hedge_cost,
    net_option_premium,
    terminal_levels_from_returns,
)


class CandidateConstraintCalculator:
    """Evaluate one candidate against all machine-evaluable client rules."""

    def __init__(
        self,
        *,
        candidate: HedgeCandidate,
        mandate: Mandate,
        portfolio: Portfolio,
        portfolio_horizon_returns: Sequence[float],
        underlying_horizon_returns: Mapping[str, Sequence[float]],
    ) -> None:
        self.candidate = candidate
        self.mandate = mandate
        self.portfolio = portfolio
        self.portfolio_returns = tuple(portfolio_horizon_returns)
        self.underlying_returns = {
            symbol: tuple(values)
            for symbol, values in underlying_horizon_returns.items()
        }
        self.required_symbols = {
            leg.underlying.value for leg in self.candidate.legs
        }
        self._validate_return_inputs()

    def assess(self) -> CandidateFeasibilityAssessment:
        """Calculate metrics, diagnostics, and the aggregate feasibility status."""

        portfolio_value = self.portfolio.total_market_value
        net_premium = net_option_premium(self.candidate)
        all_in_cost = all_in_hedge_cost(self.candidate)
        all_in_cost_fraction = all_in_cost / portfolio_value
        include_execution = self.mandate.client.cost.includes_execution_cost
        premium_constraint_cost = all_in_cost if include_execution else net_premium
        premium_constraint_fraction = premium_constraint_cost / portfolio_value

        gross_notional, protected_notional = self._reference_notionals()
        hedged_returns = self._hedged_returns(all_in_cost)
        (
            unhedged_es,
            hedged_es,
            unhedged_breach,
            hedged_breach,
        ) = self._risk_metrics(hedged_returns)
        maximum_upside_sacrifice, upside_set_matches = self._upside_sacrifice(
            all_in_cost
        )
        (
            estimated_unwind_days,
            liquidity_inputs_valid,
            liquidity_pass,
            liquidity_detail,
        ) = self._liquidity_assessment()
        expiry_months = self._expiry_months()
        eligibility_pass = self._eligibility_passes(expiry_months)

        diagnostics = self._diagnostics(
            eligibility_pass=eligibility_pass,
            expiry_months=expiry_months,
            premium_constraint_fraction=premium_constraint_fraction,
            net_premium=net_premium,
            include_execution=include_execution,
            maximum_upside_sacrifice=maximum_upside_sacrifice,
            upside_set_matches=upside_set_matches,
            estimated_unwind_days=estimated_unwind_days,
            liquidity_pass=liquidity_pass,
            liquidity_detail=liquidity_detail,
            hedged_expected_shortfall=hedged_es,
        )
        failed_constraints = tuple(
            diagnostic.constraint
            for diagnostic in diagnostics
            if not diagnostic.passed
        )
        status = (
            FeasibilityStatus.FEASIBLE
            if not failed_constraints
            else FeasibilityStatus.INFEASIBLE
        )
        infeasibility_diagnosis = self._diagnose_infeasibility(
            failed_constraints=failed_constraints,
            premium_constraint_fraction=premium_constraint_fraction,
            maximum_upside_sacrifice=maximum_upside_sacrifice,
            upside_set_matches=upside_set_matches,
            estimated_unwind_days=estimated_unwind_days,
            liquidity_inputs_valid=liquidity_inputs_valid,
            liquidity_detail=liquidity_detail,
            hedged_expected_shortfall=hedged_es,
        )
        return CandidateFeasibilityAssessment(
            candidate_id=self.candidate.candidate_id,
            family=self.candidate.family.value,
            status=status,
            net_option_premium=net_premium,
            estimated_execution_cost=self.candidate.estimated_execution_cost,
            all_in_client_cost=all_in_cost,
            all_in_cost_fraction=all_in_cost_fraction,
            premium_constraint_cost=premium_constraint_cost,
            premium_constraint_fraction=premium_constraint_fraction,
            gross_reference_notional=gross_notional,
            protected_reference_notional=protected_notional,
            notional_coverage_fraction=protected_notional / portfolio_value,
            unhedged_expected_shortfall=unhedged_es,
            hedged_expected_shortfall=hedged_es,
            unhedged_tail_breach_probability=unhedged_breach,
            hedged_tail_breach_probability=hedged_breach,
            tail_breach_reduction=unhedged_breach - hedged_breach,
            maximum_upside_sacrifice=maximum_upside_sacrifice,
            estimated_unwind_days=estimated_unwind_days,
            failed_constraints=failed_constraints,
            diagnostics=diagnostics,
            infeasibility_diagnosis=infeasibility_diagnosis,
            limitations=(
                "Historical rolling windows overlap; pre-listing holdings are omitted and available snapshot weights are renormalized.",
                "Configured option premiums, execution costs, reference levels and liquidity are user inputs, not independently verified market quotes.",
                "Terminal index hedges retain portfolio basis, gap, model and changing-beta risk.",
            ),
        )

    def _diagnose_infeasibility(
        self,
        *,
        failed_constraints: tuple[str, ...],
        premium_constraint_fraction: Decimal,
        maximum_upside_sacrifice: Decimal,
        upside_set_matches: bool,
        estimated_unwind_days: Decimal,
        liquidity_inputs_valid: bool,
        liquidity_detail: str,
        hedged_expected_shortfall: float,
    ) -> InfeasibilityDiagnosis | None:
        """Estimate independent, minimum relaxations for every failed rule.

        The estimates are local to this candidate: applying every listed change
        would make the already-calculated checks pass, but does not re-price or
        otherwise redesign the hedge.
        """

        if not failed_constraints:
            return None

        client = self.mandate.client
        failed = set(failed_constraints)
        relaxations: list[ConstraintRelaxation] = []

        if "ELIGIBILITY" in failed:
            relaxations.append(
                ConstraintRelaxation(
                    constraint="ELIGIBILITY",
                    mandate_parameter="client.eligibility",
                    current_limit="approved instrument universe",
                    required_limit="include all candidate leg attributes and expiry tenors",
                    relaxation_amount="categorical mandate amendment",
                    unit="categorical",
                    detail=(
                        "Alternatively redesign the candidate using only approved "
                        "underlyings, instruments, option style and expiry months."
                    ),
                )
            )

        if "ALL_IN_PREMIUM" in failed:
            current = client.cost.max_all_in_premium_fraction
            relaxations.append(
                ConstraintRelaxation(
                    constraint="ALL_IN_PREMIUM",
                    mandate_parameter="client.cost.max_all_in_premium_fraction",
                    current_limit=str(current),
                    required_limit=str(premium_constraint_fraction),
                    relaxation_amount=str(premium_constraint_fraction - current),
                    unit="portfolio_value_fraction",
                    detail=(
                        "Increase the permitted premium budget to the candidate's "
                        "calculated premium-constraint cost fraction."
                    ),
                )
            )

        if "UPSIDE_SACRIFICE" in failed:
            if not upside_set_matches:
                relaxations.append(
                    ConstraintRelaxation(
                        constraint="UPSIDE_SACRIFICE",
                        mandate_parameter="client.upside.scenario_set_id",
                        current_limit=client.upside.scenario_set_id,
                        required_limit=self.candidate.upside_scenario_set_id,
                        relaxation_amount="replace required scenario set",
                        unit="categorical",
                        detail=(
                            "Alternatively evaluate the candidate on the mandate's "
                            "required upside scenario set."
                        ),
                    )
                )
            current = client.upside.max_sacrifice_percentage_points
            if maximum_upside_sacrifice > current:
                relaxations.append(
                    ConstraintRelaxation(
                        constraint="UPSIDE_SACRIFICE",
                        mandate_parameter=(
                            "client.upside.max_sacrifice_percentage_points"
                        ),
                        current_limit=str(current),
                        required_limit=str(maximum_upside_sacrifice),
                        relaxation_amount=str(maximum_upside_sacrifice - current),
                        unit="portfolio_return_fraction",
                        detail=(
                            "Raise the permitted upside sacrifice to the maximum "
                            "calculated across the candidate's upside scenarios."
                        ),
                    )
                )

        if "LIQUIDITY" in failed:
            current_days = Decimal(client.liquidity.max_unwind_trading_days)
            if liquidity_inputs_valid:
                required_days = estimated_unwind_days.to_integral_value(
                    rounding=ROUND_CEILING
                )
                relaxations.append(
                    ConstraintRelaxation(
                        constraint="LIQUIDITY",
                        mandate_parameter="client.liquidity.max_unwind_trading_days",
                        current_limit=str(current_days),
                        required_limit=str(required_days),
                        relaxation_amount=str(required_days - current_days),
                        unit="trading_days",
                        detail=(
                            "Increase the permitted unwind window to the slowest "
                            "candidate leg's estimated unwind time."
                        ),
                    )
                )
            else:
                relaxations.append(
                    ConstraintRelaxation(
                        constraint="LIQUIDITY",
                        mandate_parameter="candidate.legs[].liquidity_attributes.normal_daily_volume",
                        current_limit=liquidity_detail,
                        required_limit="positive normal_daily_volume for every leg",
                        relaxation_amount="supply valid liquidity inputs",
                        unit="contracts_per_day",
                        detail=(
                            "A numeric relaxation cannot be estimated until every "
                            "leg has a positive volume input."
                        ),
                    )
                )

        if "EXPECTED_SHORTFALL" in failed:
            current_loss = client.protection.max_expected_shortfall_loss
            achievable_loss = Decimal(str(-hedged_expected_shortfall))
            relaxations.append(
                ConstraintRelaxation(
                    constraint="EXPECTED_SHORTFALL",
                    mandate_parameter=(
                        "client.protection.max_expected_shortfall_loss"
                    ),
                    current_limit=str(current_loss),
                    required_limit=str(achievable_loss),
                    relaxation_amount=str(achievable_loss - current_loss),
                    unit="portfolio_value_fraction",
                    detail=(
                        "The required limit is the candidate's achievable historical "
                        "expected-shortfall loss at the mandated confidence level."
                    ),
                )
            )

        return InfeasibilityDiagnosis(
            binding_constraints=failed_constraints,
            relaxations=tuple(relaxations),
        )

    def _validate_return_inputs(self) -> None:
        observation_count = len(self.portfolio_returns)
        if observation_count == 0:
            raise ValueError("portfolio_horizon_returns must be non-empty")
        missing = sorted(self.required_symbols - self.underlying_returns.keys())
        if missing:
            raise ValueError("missing underlying horizon returns: " + ", ".join(missing))
        if any(
            len(self.underlying_returns[symbol]) != observation_count
            for symbol in self.required_symbols
        ):
            raise ValueError("all horizon return series must have equal length")

    def _reference_notionals(self) -> tuple[Decimal, Decimal]:
        notionals = tuple(
            self.candidate.initial_levels[leg.underlying.value]
            * leg.quantity
            * leg.contract_multiplier
            for leg in self.candidate.legs
        )
        protected = sum(
            (
                notional
                for leg, notional in zip(self.candidate.legs, notionals)
                if (
                    isinstance(leg, FutureLeg)
                    and leg.direction is LegDirection.SHORT
                )
                or (
                    isinstance(leg, VanillaOptionLeg)
                    and leg.direction is LegDirection.LONG
                    and leg.option_type is OptionType.PUT
                )
            ),
            Decimal("0"),
        )
        return sum(notionals, Decimal("0")), protected

    def _hedged_returns(self, all_in_cost: Decimal) -> tuple[float, ...]:
        portfolio_value = self.portfolio.total_market_value
        results: list[float] = []
        for index, portfolio_return in enumerate(self.portfolio_returns):
            terminal_levels = terminal_levels_from_returns(
                self.candidate.initial_levels,
                {
                    symbol: Decimal(str(self.underlying_returns[symbol][index]))
                    for symbol in self.required_symbols
                },
            )
            payoff = evaluate_aggregate_terminal_payoff(
                self.candidate.legs, terminal_levels
            )
            results.append(
                float(
                    Decimal(str(portfolio_return))
                    + (payoff - all_in_cost) / portfolio_value
                )
            )
        return tuple(results)

    def _risk_metrics(
        self, hedged_returns: Sequence[float]
    ) -> tuple[float, float, float, float]:
        protection = self.mandate.client.protection
        confidence = float(protection.expected_shortfall_confidence)
        threshold = -float(protection.tail_loss_threshold)
        observation_count = len(self.portfolio_returns)
        return (
            expected_shortfall(self.portfolio_returns, confidence_level=confidence),
            expected_shortfall(hedged_returns, confidence_level=confidence),
            sum(value < threshold for value in self.portfolio_returns)
            / observation_count,
            sum(value < threshold for value in hedged_returns) / observation_count,
        )

    def _upside_sacrifice(self, all_in_cost: Decimal) -> tuple[Decimal, bool]:
        portfolio_value = self.portfolio.total_market_value
        sacrifices = tuple(
            max(
                Decimal("0"),
                -(
                    evaluate_aggregate_terminal_payoff(
                        self.candidate.legs, scenario.terminal_levels
                    )
                    - all_in_cost
                )
                / portfolio_value,
            )
            for scenario in self.candidate.upside_scenarios
        )
        return (
            max(sacrifices),
            self.candidate.upside_scenario_set_id
            == self.mandate.client.upside.scenario_set_id,
        )

    def _liquidity_assessment(self) -> tuple[Decimal, bool, bool, str]:
        maximum_participation = self.mandate.client.liquidity.max_market_participation
        unwind_days: list[Decimal] = []
        details: list[str] = []
        inputs_valid = True
        for number, leg in enumerate(self.candidate.legs, start=1):
            raw_volume = leg.liquidity_attributes.get("normal_daily_volume")
            try:
                volume = Decimal(str(raw_volume))
            except (InvalidOperation, TypeError, ValueError):
                volume = Decimal("0")
            if not volume.is_finite() or volume <= 0:
                inputs_valid = False
                details.append(f"leg {number} has no positive normal_daily_volume")
                continue
            days = Decimal(leg.quantity) / (volume * maximum_participation)
            unwind_days.append(days)
            details.append(f"leg {number}: {days.quantize(Decimal('0.001'))} days")
        estimated_days = max(unwind_days, default=Decimal("Infinity"))
        passed = (
            inputs_valid
            and estimated_days
            <= self.mandate.client.liquidity.max_unwind_trading_days
        )
        return estimated_days, inputs_valid, passed, "; ".join(details)

    def _expiry_months(self) -> set[int]:
        quote = self.candidate.quote_timestamp.date()
        return {
            (leg.expiry.year - quote.year) * 12
            + leg.expiry.month
            - quote.month
            - (leg.expiry.day < quote.day)
            for leg in self.candidate.legs
        }

    def _eligibility_passes(self, expiry_months: set[int]) -> bool:
        eligibility = self.mandate.client.eligibility
        return all(
            leg.underlying in eligibility.underlyings
            and leg.instrument_type in eligibility.instrument_types
            and (
                not isinstance(leg, VanillaOptionLeg)
                or leg.option_style is eligibility.option_style
            )
            for leg in self.candidate.legs
        ) and expiry_months.issubset(set(eligibility.approved_expiry_months))

    def _diagnostics(
        self,
        *,
        eligibility_pass: bool,
        expiry_months: set[int],
        premium_constraint_fraction: Decimal,
        net_premium: Decimal,
        include_execution: bool,
        maximum_upside_sacrifice: Decimal,
        upside_set_matches: bool,
        estimated_unwind_days: Decimal,
        liquidity_pass: bool,
        liquidity_detail: str,
        hedged_expected_shortfall: float,
    ) -> tuple[ConstraintDiagnostic, ...]:
        client = self.mandate.client
        confidence = float(client.protection.expected_shortfall_confidence)
        expected_shortfall_limit = -float(
            client.protection.max_expected_shortfall_loss
        )
        return (
            ConstraintDiagnostic(
                "ELIGIBILITY",
                eligibility_pass,
                self.candidate.family.value,
                "approved underlyings, instruments, style and expiry",
                f"expiry month offsets: {', '.join(map(str, sorted(expiry_months)))}",
            ),
            ConstraintDiagnostic(
                "ALL_IN_PREMIUM",
                premium_constraint_fraction
                <= client.cost.max_all_in_premium_fraction,
                str(premium_constraint_fraction),
                str(client.cost.max_all_in_premium_fraction),
                f"net option premium {net_premium}; execution cost "
                f"{self.candidate.estimated_execution_cost}; execution cost "
                f"{'included' if include_execution else 'excluded'} by mandate",
            ),
            ConstraintDiagnostic(
                "UPSIDE_SACRIFICE",
                upside_set_matches
                and maximum_upside_sacrifice
                <= client.upside.max_sacrifice_percentage_points,
                str(maximum_upside_sacrifice),
                str(client.upside.max_sacrifice_percentage_points),
                f"maximum across {len(self.candidate.upside_scenarios)} scenarios from "
                f"{self.candidate.upside_scenario_set_id}; mandate requires "
                f"{client.upside.scenario_set_id}",
            ),
            ConstraintDiagnostic(
                "LIQUIDITY",
                liquidity_pass,
                str(estimated_unwind_days),
                str(client.liquidity.max_unwind_trading_days),
                liquidity_detail,
            ),
            ConstraintDiagnostic(
                "EXPECTED_SHORTFALL",
                hedged_expected_shortfall >= expected_shortfall_limit,
                str(hedged_expected_shortfall),
                str(expected_shortfall_limit),
                f"historical {confidence:.1%} ES across "
                f"{len(self.portfolio_returns)} rolling horizon windows",
            ),
        )


__all__ = ["CandidateConstraintCalculator"]
