"""Configuration constants for the mandate-assessment application service."""

from typing import Final


TRADING_DAYS_PER_MONTH: Final[int] = 21

BENCHMARK_SYMBOL_ALIASES: Final[dict[str, str]] = {
    "NIFTY 50": "NIFTY",
    "NIFTY50": "NIFTY",
}

ASSESSMENT_LIMITATIONS: Final[tuple[str, ...]] = (
    "Historical portfolio returns use current snapshot weights renormalized over holdings with prices at both interval endpoints and are not actual client P&L.",
    "Overlapping horizon returns are not statistically independent.",
    "Pre-listing holdings are omitted until they have endpoint prices; their weights are redistributed proportionally across available holdings.",
    "Scenario valuation, pricing, liquidity, hedge feasibility, and pre-trade decisions are not yet orchestrated by MandateAssessmentService.",
    "Historical and block-bootstrap scenarios are available but are not yet valued in the mandate assessment workflow.",
)

SCENARIO_PENDING_REASON: Final[str] = (
    "Historical rolling and block-bootstrap scenarios are implemented, but "
    "scenario valuation is not yet wired into the mandate assessment workflow."
)
HEDGE_PENDING_REASON: Final[str] = (
    "Candidate pricing and hedge evaluation are available through separate "
    "application services but are not yet orchestrated here."
)
FEASIBILITY_PENDING_REASON: Final[str] = (
    "Feasibility requires populated scenario and hedge assessments."
)


__all__ = [
    "ASSESSMENT_LIMITATIONS",
    "BENCHMARK_SYMBOL_ALIASES",
    "FEASIBILITY_PENDING_REASON",
    "HEDGE_PENDING_REASON",
    "SCENARIO_PENDING_REASON",
    "TRADING_DAYS_PER_MONTH",
]
