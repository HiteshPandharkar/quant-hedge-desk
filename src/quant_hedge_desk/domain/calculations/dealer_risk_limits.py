"""Pure calculations for dealer risk-limit utilization."""

from __future__ import annotations

from decimal import Decimal

from quant_hedge_desk.domain.enums import RiskLimitStatus
from quant_hedge_desk.domain.errors import DealerRiskValidationError
from quant_hedge_desk.domain.models.dealer_risk_models import (
    DealerRiskAssessment,
    ProposedTradeRisk,
    RiskLimitDiagnostic,
)
from quant_hedge_desk.domain.models.desk_limits import DeskLimitSet
from quant_hedge_desk.domain.models.desk_portfolio import DeskPortfolio


def build_risk_limit_diagnostic(
    measure: str,
    *,
    before: Decimal,
    incremental: Decimal,
    after: Decimal,
    limit: Decimal,
    warning_utilization: Decimal,
) -> RiskLimitDiagnostic:
    """Build one utilization diagnostic from normalized decimal inputs."""

    before_utilization = before / limit
    after_utilization = after / limit
    if after_utilization > 1:
        status = RiskLimitStatus.BREACH
    elif after_utilization >= warning_utilization:
        status = RiskLimitStatus.WARNING
    else:
        status = RiskLimitStatus.PASS
    return RiskLimitDiagnostic(
        measure=measure,
        before=before,
        incremental=incremental,
        after=after,
        limit=limit,
        before_utilization=before_utilization,
        after_utilization=after_utilization,
        status=status,
    )


def assess_dealer_risk(
    desk_portfolio: DeskPortfolio,
    proposed_trade: ProposedTradeRisk,
    mandate: DeskLimitSet,
) -> DealerRiskAssessment:
    """Compare existing and post-trade risk with every configured hard limit.

    Delta and vega are two-sided limits, so their utilization is based on the
    absolute net post-trade exposure. Crash risk is a loss limit: positive
    stress P&L consumes no crash-loss capacity.
    """

    if not isinstance(desk_portfolio, DeskPortfolio):
        raise DealerRiskValidationError("desk_portfolio must be a DeskPortfolio")
    if not isinstance(proposed_trade, ProposedTradeRisk):
        raise DealerRiskValidationError("proposed_trade must be a ProposedTradeRisk")
    if not isinstance(mandate, DeskLimitSet):
        raise DealerRiskValidationError("mandate must be a DeskLimitSet")

    existing = desk_portfolio.aggregate_risk
    incremental = proposed_trade.exposure
    post_trade = existing + incremental
    limits = mandate.limits
    warning = limits.warning_utilization

    exposure_checks = (
        (
            "absolute_net_index_delta_inr",
            abs(existing.net_index_delta_inr),
            abs(post_trade.net_index_delta_inr) - abs(existing.net_index_delta_inr),
            abs(post_trade.net_index_delta_inr),
            limits.max_absolute_net_index_delta_inr,
        ),
        (
            "absolute_one_month_vega_inr_per_vol_point",
            abs(existing.one_month_vega_inr_per_vol_point),
            abs(post_trade.one_month_vega_inr_per_vol_point)
            - abs(existing.one_month_vega_inr_per_vol_point),
            abs(post_trade.one_month_vega_inr_per_vol_point),
            limits.max_one_month_vega_inr_per_vol_point,
        ),
        (
            "absolute_six_month_vega_inr_per_vol_point",
            abs(existing.six_month_vega_inr_per_vol_point),
            abs(post_trade.six_month_vega_inr_per_vol_point)
            - abs(existing.six_month_vega_inr_per_vol_point),
            abs(post_trade.six_month_vega_inr_per_vol_point),
            limits.max_six_month_vega_inr_per_vol_point,
        ),
        (
            "crash_stress_loss_inr",
            max(-existing.crash_stress_pnl_inr, Decimal("0")),
            max(-post_trade.crash_stress_pnl_inr, Decimal("0"))
            - max(-existing.crash_stress_pnl_inr, Decimal("0")),
            max(-post_trade.crash_stress_pnl_inr, Decimal("0")),
            limits.max_crash_stress_loss_inr,
        ),
    )
    diagnostics = [
        build_risk_limit_diagnostic(
            name,
            before=before,
            incremental=change,
            after=after,
            limit=limit,
            warning_utilization=warning,
        )
        for name, before, change, after, limit in exposure_checks
    ]
    diagnostics.extend(
        (
            build_risk_limit_diagnostic(
                "market_participation",
                before=Decimal("0"),
                incremental=proposed_trade.market_participation,
                after=proposed_trade.market_participation,
                limit=limits.max_market_participation,
                warning_utilization=warning,
            ),
            build_risk_limit_diagnostic(
                "liquidation_trading_days",
                before=Decimal("0"),
                incremental=Decimal(proposed_trade.liquidation_trading_days),
                after=Decimal(proposed_trade.liquidation_trading_days),
                limit=Decimal(limits.max_liquidation_trading_days),
                warning_utilization=warning,
            ),
            build_risk_limit_diagnostic(
                "model_reserve_inr",
                before=Decimal("0"),
                incremental=proposed_trade.model_reserve_inr,
                after=proposed_trade.model_reserve_inr,
                limit=(
                    proposed_trade.clean_value_inr
                    * limits.max_model_reserve_fraction_of_clean_value
                ),
                warning_utilization=warning,
            ),
        )
    )
    return DealerRiskAssessment(
        desk_limits_id=mandate.desk_limits_id,
        desk_portfolio_id=desk_portfolio.desk_portfolio_id,
        existing_risk=existing,
        incremental_risk=incremental,
        post_trade_risk=post_trade,
        diagnostics=tuple(diagnostics),
    )


__all__ = ["assess_dealer_risk", "build_risk_limit_diagnostic"]
