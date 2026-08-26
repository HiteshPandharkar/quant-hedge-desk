"""Auditable portfolio concentration metrics.

The Week 1 mandate describes concentration through both single-name and sector
exposure.  This module calculates those measures from the reconciled portfolio
weights; it does not recalculate weights from market values or silently
renormalize invalid input.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from quant_hedge_desk.analytics.constants import (
    DEFAULT_SINGLE_NAME_LIMIT,
    DEFAULT_TOP_N,
    DEFAULT_TOP_N_MAXIMUM,
    DEFAULT_TOP_N_MINIMUM,
)
from quant_hedge_desk.analytics.errors import ConcentrationMetricError
from quant_hedge_desk.analytics.models import (
    ConcentrationMetrics,
    HoldingWeight,
    SectorWeight,
)
from quant_hedge_desk.analytics._validation import positive_integer
from quant_hedge_desk.domain.constants import WEIGHT_RECONCILIATION_TOLERANCE
from quant_hedge_desk.domain.models.portfolio import Portfolio


def _fraction(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ConcentrationMetricError(f"{name} must be numeric")
    divisor = Decimal("1")
    if isinstance(value, str) and value.strip().endswith("%"):
        value = value.strip()[:-1].strip()
        divisor = Decimal("100")
    try:
        result = Decimal(str(value)) / divisor
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ConcentrationMetricError(f"{name} must be numeric") from exc
    if not result.is_finite() or result < 0 or result > 1:
        raise ConcentrationMetricError(f"{name} must be a finite fraction in [0, 1]")
    return result


def concentration_ratio(portfolio: Portfolio, n: int) -> Decimal:
    """Return the share held by the ``n`` largest positions (CRn).

    When ``n`` exceeds the number of holdings, the result is the full portfolio
    weight.  A positive integer is required to prevent ambiguous CR0 results.
    """

    if not isinstance(portfolio, Portfolio):
        raise TypeError("portfolio must be a Portfolio")
    n = positive_integer(n, "n", error_type=ConcentrationMetricError)
    weights = sorted(
        (holding.portfolio_weight for holding in portfolio.holdings), reverse=True
    )
    return sum(weights[:n], Decimal("0"))


def herfindahl_hirschman_index(weights: Iterable[Any]) -> Decimal:
    """Return HHI as the sum of squared fractional weights.

    This low-level helper intentionally requires weights to sum to one.  It is
    useful for independently reproducing both holding and sector HHI values.
    """

    try:
        raw_weights = tuple(weights)
    except TypeError as exc:
        raise ConcentrationMetricError("weights must be an iterable") from exc
    if not raw_weights:
        raise ConcentrationMetricError("weights must be non-empty")
    parsed = tuple(_fraction(weight, "weight") for weight in raw_weights)
    if abs(sum(parsed, Decimal("0")) - Decimal("1")) > WEIGHT_RECONCILIATION_TOLERANCE:
        raise ConcentrationMetricError(
            "weights must sum to 1 within 0.01 percentage points"
        )
    return sum((weight * weight for weight in parsed), Decimal("0"))


def calculate_concentration_metrics(
    portfolio: Portfolio,
    *,
    top_n: int = DEFAULT_TOP_N,
    single_name_limit: Any = DEFAULT_SINGLE_NAME_LIMIT,
    top_n_minimum: Any | None = DEFAULT_TOP_N_MINIMUM,
    top_n_maximum: Any | None = DEFAULT_TOP_N_MAXIMUM,
) -> ConcentrationMetrics:
    """Calculate the Week 1 portfolio concentration diagnosis.

    Bounds accept either fractions (``Decimal("0.10")``) or percentage strings
    (``"10%"``).  They diagnose the reference portfolio design; they do not
    alter or reject an otherwise valid portfolio snapshot.
    """

    if not isinstance(portfolio, Portfolio):
        raise TypeError("portfolio must be a Portfolio")
    top_n = positive_integer(
        top_n, "top_n", error_type=ConcentrationMetricError
    )

    limit = _fraction(single_name_limit, "single_name_limit")
    minimum = None if top_n_minimum is None else _fraction(top_n_minimum, "top_n_minimum")
    maximum = None if top_n_maximum is None else _fraction(top_n_maximum, "top_n_maximum")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ConcentrationMetricError("top_n_minimum cannot exceed top_n_maximum")

    ordered_holdings = sorted(
        portfolio.holdings,
        key=lambda holding: (-holding.portfolio_weight, holding.symbol),
    )
    ranked_holdings = tuple(
        HoldingWeight(rank, holding.symbol, holding.portfolio_weight)
        for rank, holding in enumerate(ordered_holdings, start=1)
    )

    sector_totals: dict[str, Decimal] = {}
    sector_counts: dict[str, int] = {}
    for holding in portfolio.holdings:
        sector_totals[holding.sector] = (
            sector_totals.get(holding.sector, Decimal("0")) + holding.portfolio_weight
        )
        sector_counts[holding.sector] = sector_counts.get(holding.sector, 0) + 1
    ordered_sectors = sorted(sector_totals, key=lambda sector: (-sector_totals[sector], sector))
    ranked_sectors = tuple(
        SectorWeight(rank, sector, sector_totals[sector], sector_counts[sector])
        for rank, sector in enumerate(ordered_sectors, start=1)
    )

    holding_hhi = herfindahl_hirschman_index(
        tuple(item.weight for item in ranked_holdings)
    )
    sector_hhi = herfindahl_hirschman_index(tuple(item.weight for item in ranked_sectors))

    return ConcentrationMetrics(
        holding_count=len(ranked_holdings),
        sector_count=len(ranked_sectors),
        ranked_holdings=ranked_holdings,
        ranked_sectors=ranked_sectors,
        top_n=top_n,
        top_n_weight=sum(
            (item.weight for item in ranked_holdings[:top_n]), Decimal("0")
        ),
        single_name_limit=limit,
        single_name_breaches=tuple(
            item for item in ranked_holdings if item.weight > limit
        ),
        holding_hhi=holding_hhi,
        effective_holding_count=Decimal("1") / holding_hhi,
        sector_hhi=sector_hhi,
        effective_sector_count=Decimal("1") / sector_hhi,
        top_n_minimum=minimum,
        top_n_maximum=maximum,
    )


# A concise alias is convenient for report/application callers.
portfolio_concentration = calculate_concentration_metrics


__all__ = [
    "ConcentrationMetricError",
    "ConcentrationMetrics",
    "DEFAULT_SINGLE_NAME_LIMIT",
    "DEFAULT_TOP_N",
    "DEFAULT_TOP_N_MAXIMUM",
    "DEFAULT_TOP_N_MINIMUM",
    "HoldingWeight",
    "SectorWeight",
    "calculate_concentration_metrics",
    "concentration_ratio",
    "herfindahl_hirschman_index",
    "portfolio_concentration",
]
