"""Adapters for external pricing snapshots."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from quant_hedge_desk.domain.enums import InstrumentType, OptionType, Underlying
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.pricing.errors import PricingAdapterError
from quant_hedge_desk.pricing.models import InstrumentQuote


_REQUIRED_FIELDS = frozenset(
    {
        "quote_timestamp",
        "underlying",
        "instrument_type",
        "expiry",
        "strike_or_level",
        "option_type",
        "premium",
        "source",
    }
)
_ContractKey = tuple[Underlying, date, Decimal, OptionType]


class CSVQuotePricingAdapter:
    """Resolve vanilla-option premiums from a point-in-time CSV quote history.

    Contract identity deliberately excludes direction, quantity, and multiplier:
    a market unit premium is the same for a long or short position.  For each
    request the latest observation at or before the leg's ``quote_timestamp``
    is selected.  Future observations are never back-cast into an earlier
    snapshot.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._quotes = self._load(self.path)

    def quote_for(
        self,
        leg: VanillaOptionLeg,
        *,
        max_age: timedelta | None = None,
    ) -> InstrumentQuote:
        if not isinstance(leg, VanillaOptionLeg):
            raise TypeError("quote_for requires a VanillaOptionLeg")
        self._validate_max_age(max_age)
        key = (leg.underlying, leg.expiry, leg.strike_or_level, leg.option_type)
        observations = self._quotes.get(key, ())
        eligible = tuple(
            quote
            for quote in observations
            if _comparable_timestamp(quote.quote_timestamp, leg.quote_timestamp)
            <= leg.quote_timestamp
        )
        if not eligible:
            contract = _describe_contract(key)
            raise PricingAdapterError(
                f"no quote for {contract} at or before {leg.quote_timestamp.isoformat()}"
            )
        quote = eligible[-1]
        if max_age is not None:
            age = leg.quote_timestamp - _comparable_timestamp(
                quote.quote_timestamp, leg.quote_timestamp
            )
            if age > max_age:
                raise PricingAdapterError(
                    f"stale quote for {_describe_contract(key)}: age {age} exceeds {max_age}"
                )
        return quote

    # An intuitive alias for callers that think in leg pricing terminology.
    price_leg = quote_for

    def price_candidate(
        self,
        candidate: HedgeCandidate,
        *,
        max_age: timedelta | None = None,
    ) -> HedgeCandidate:
        """Return a copy with option premiums and quote lineage from this source."""

        priced_legs: list[FutureLeg | VanillaOptionLeg] = []
        for leg in candidate.legs:
            if isinstance(leg, FutureLeg):
                priced_legs.append(leg)
                continue
            quote = self.quote_for(leg, max_age=max_age)
            liquidity = dict(leg.liquidity_attributes)
            liquidity["pricing_source"] = quote.source
            if quote.normal_daily_volume is not None:
                liquidity["normal_daily_volume"] = quote.normal_daily_volume
            priced_legs.append(
                replace(
                    leg,
                    premium=quote.premium,
                    liquidity_attributes=MappingProxyType(liquidity),
                )
            )
        return replace(candidate, legs=tuple(priced_legs))

    @staticmethod
    def _validate_max_age(max_age: timedelta | None) -> None:
        if max_age is not None and (
            not isinstance(max_age, timedelta) or max_age < timedelta(0)
        ):
            raise ValueError("max_age must be a non-negative timedelta or None")

    @staticmethod
    def _load(path: Path) -> dict[_ContractKey, tuple[InstrumentQuote, ...]]:
        quotes: dict[_ContractKey, list[InstrumentQuote]] = {}
        seen: set[tuple[_ContractKey, datetime]] = set()
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, strict=True)
                missing = sorted(_REQUIRED_FIELDS - set(reader.fieldnames or ()))
                if missing:
                    raise PricingAdapterError(
                        f"pricing data {path} is missing fields: {', '.join(missing)}"
                    )
                for line_number, row in enumerate(reader, start=2):
                    if not any((value or "").strip() for value in row.values()):
                        continue
                    quote = _parse_quote(row, path=path, line_number=line_number)
                    key = (
                        quote.underlying,
                        quote.expiry,
                        quote.strike_or_level,
                        quote.option_type,
                    )
                    identity = (key, quote.quote_timestamp)
                    if identity in seen:
                        raise PricingAdapterError(
                            f"pricing data {path} has duplicate {_describe_contract(key)} "
                            f"timestamp {quote.quote_timestamp.isoformat()}"
                        )
                    seen.add(identity)
                    quotes.setdefault(key, []).append(quote)
        except PricingAdapterError:
            raise
        except (OSError, csv.Error) as exc:
            raise PricingAdapterError(f"could not load pricing data {path}: {exc}") from exc

        if not quotes:
            raise PricingAdapterError(f"pricing data {path} contains no option quotes")
        return {
            key: tuple(sorted(values, key=lambda item: item.quote_timestamp))
            for key, values in quotes.items()
        }


def _parse_quote(
    row: dict[str, str | None], *, path: Path, line_number: int
) -> InstrumentQuote:
    def value(field: str) -> str:
        result = (row.get(field) or "").strip()
        if not result:
            raise PricingAdapterError(
                f"pricing data {path} line {line_number} has blank {field}"
            )
        return result

    try:
        instrument_type = InstrumentType(value("instrument_type").upper())
        if instrument_type is not InstrumentType.OPTION:
            raise ValueError("instrument_type must be OPTION")
        timestamp = datetime.fromisoformat(value("quote_timestamp").replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("quote_timestamp must include a UTC offset")
        strike = Decimal(value("strike_or_level"))
        premium = Decimal(value("premium"))
        if not strike.is_finite() or strike <= 0:
            raise ValueError("strike_or_level must be a finite positive decimal")
        if not premium.is_finite() or premium < 0:
            raise ValueError("premium must be a finite non-negative decimal")
        raw_volume = (row.get("normal_daily_volume") or "").strip()
        volume = int(raw_volume) if raw_volume else None
        if volume is not None and volume <= 0:
            raise ValueError("normal_daily_volume must be a positive integer")
        return InstrumentQuote(
            underlying=Underlying(value("underlying").upper()),
            expiry=date.fromisoformat(value("expiry")),
            strike_or_level=strike,
            option_type=OptionType(value("option_type").upper()),
            premium=premium,
            quote_timestamp=timestamp,
            source=value("source"),
            normal_daily_volume=volume,
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PricingAdapterError(
            f"pricing data {path} line {line_number} is invalid: {exc}"
        ) from exc


def _comparable_timestamp(observed: datetime, requested: datetime) -> datetime:
    if requested.tzinfo is None or requested.utcoffset() is None:
        raise PricingAdapterError("leg quote_timestamp must include a UTC offset")
    return observed.astimezone(requested.tzinfo)


def _describe_contract(key: _ContractKey) -> str:
    underlying, expiry, strike, option_type = key
    return f"{underlying.value} {expiry.isoformat()} {strike} {option_type.value}"


__all__ = ["CSVQuotePricingAdapter"]
