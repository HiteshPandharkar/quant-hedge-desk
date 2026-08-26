"""Application-facing pricing ports."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol, runtime_checkable

from quant_hedge_desk.domain.models.derivative_legs import VanillaOptionLeg
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.pricing.models import InstrumentQuote


@runtime_checkable
class PricingAdapter(Protocol):
    """Port implemented by sources of executable or reference option quotes."""

    def quote_for(
        self,
        leg: VanillaOptionLeg,
        *,
        max_age: timedelta | None = None,
    ) -> InstrumentQuote: ...

    def price_candidate(
        self,
        candidate: HedgeCandidate,
        *,
        max_age: timedelta | None = None,
    ) -> HedgeCandidate: ...


__all__ = ["PricingAdapter"]
