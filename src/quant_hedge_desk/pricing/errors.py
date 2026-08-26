"""Pricing-boundary errors."""


class PricingAdapterError(ValueError):
    """Raised when an external quote source cannot price a requested leg."""


class QuoteWaterfallError(ValueError):
    """Raised when dealer quote components are invalid or do not reconcile."""


__all__ = ["PricingAdapterError", "QuoteWaterfallError"]
