"""Immutable pricing and dealer-quote values."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from quant_hedge_desk.domain.enums import OptionType, Underlying
from quant_hedge_desk.pricing.errors import QuoteWaterfallError
from quant_hedge_desk.serialization import json_ready


@dataclass(frozen=True, slots=True)
class InstrumentQuote:
    """One observed unit premium for a listed vanilla option contract."""

    underlying: Underlying
    expiry: date
    strike_or_level: Decimal
    option_type: OptionType
    premium: Decimal
    quote_timestamp: datetime
    source: str
    normal_daily_volume: int | None = None


@dataclass(frozen=True, slots=True)
class QuoteWaterfall:
    """Auditable reconciliation from clean value to quoted client premium.

    Every component is expressed as a non-negative INR amount charged to the
    client.  ``quoted_client_premium_inr`` may be omitted to derive an exact
    quote from the components.  When a displayed or externally supplied quote
    is provided, construction fails unless it agrees within the stated
    currency-rounding tolerance.
    """

    clean_value_inr: Decimal
    initial_hedge_execution_cost_inr: Decimal
    expected_rehedging_cost_inr: Decimal
    liquidity_reserve_inr: Decimal
    model_reserve_inr: Decimal
    capital_funding_estimate_inr: Decimal
    dealer_margin_inr: Decimal
    quoted_client_premium_inr: Decimal | None = None
    rounding_tolerance_inr: Decimal = Decimal("0.01")

    def __post_init__(self) -> None:
        component_names = (
            "clean_value_inr",
            "initial_hedge_execution_cost_inr",
            "expected_rehedging_cost_inr",
            "liquidity_reserve_inr",
            "model_reserve_inr",
            "capital_funding_estimate_inr",
            "dealer_margin_inr",
        )
        for name in component_names:
            amount = _non_negative_amount(getattr(self, name), name)
            object.__setattr__(self, name, amount)

        tolerance = _non_negative_amount(
            self.rounding_tolerance_inr, "rounding_tolerance_inr"
        )
        object.__setattr__(self, "rounding_tolerance_inr", tolerance)

        calculated = self.calculated_client_premium_inr
        if self.quoted_client_premium_inr is None:
            object.__setattr__(self, "quoted_client_premium_inr", calculated)
            return

        quoted = _non_negative_amount(
            self.quoted_client_premium_inr, "quoted_client_premium_inr"
        )
        object.__setattr__(self, "quoted_client_premium_inr", quoted)
        difference = quoted - calculated
        if abs(difference) > tolerance:
            raise QuoteWaterfallError(
                "quoted_client_premium_inr does not reconcile to the quote "
                f"waterfall: difference {difference} exceeds rounding tolerance "
                f"{tolerance}"
            )

    @property
    def total_adjustments_inr(self) -> Decimal:
        """Return all execution, reserve, funding, and margin adjustments."""

        return sum(
            (
                self.initial_hedge_execution_cost_inr,
                self.expected_rehedging_cost_inr,
                self.liquidity_reserve_inr,
                self.model_reserve_inr,
                self.capital_funding_estimate_inr,
                self.dealer_margin_inr,
            ),
            Decimal("0"),
        )

    @property
    def calculated_client_premium_inr(self) -> Decimal:
        """Return clean value plus every separately disclosed adjustment."""

        return self.clean_value_inr + self.total_adjustments_inr

    @property
    def reconciliation_difference_inr(self) -> Decimal:
        """Return quoted premium less the unrounded component total."""

        # __post_init__ always replaces None with the calculated Decimal.
        assert self.quoted_client_premium_inr is not None
        return self.quoted_client_premium_inr - self.calculated_client_premium_inr

    @property
    def reconciled(self) -> bool:
        return abs(self.reconciliation_difference_inr) <= self.rounding_tolerance_inr

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QuoteWaterfall":
        if not isinstance(value, Mapping):
            raise QuoteWaterfallError("quote waterfall must be a mapping")
        required = {
            "clean_value_inr",
            "initial_hedge_execution_cost_inr",
            "expected_rehedging_cost_inr",
            "liquidity_reserve_inr",
            "model_reserve_inr",
            "capital_funding_estimate_inr",
            "dealer_margin_inr",
        }
        optional = {"quoted_client_premium_inr", "rounding_tolerance_inr"}
        missing = required - value.keys()
        extra = value.keys() - required - optional
        if missing:
            raise QuoteWaterfallError(
                f"quote waterfall is missing: {', '.join(sorted(missing))}"
            )
        if extra:
            raise QuoteWaterfallError(
                f"quote waterfall has unknown fields: {', '.join(sorted(extra))}"
            )
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready reconciliation without losing decimal precision."""

        result = json_ready(asdict(self))
        result["total_adjustments_inr"] = str(self.total_adjustments_inr)
        result["calculated_client_premium_inr"] = str(
            self.calculated_client_premium_inr
        )
        result["reconciliation_difference_inr"] = str(
            self.reconciliation_difference_inr
        )
        result["reconciled"] = self.reconciled
        return result


def _non_negative_amount(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise QuoteWaterfallError(f"{name} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise QuoteWaterfallError(f"{name} must be numeric") from exc
    if not result.is_finite():
        raise QuoteWaterfallError(f"{name} must be finite")
    if result < 0:
        raise QuoteWaterfallError(f"{name} must be non-negative")
    return result


__all__ = ["InstrumentQuote", "QuoteWaterfall"]
