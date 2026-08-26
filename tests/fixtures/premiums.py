"""Deterministic option-premium fixtures shared by hedge-design tests.

Premiums are quoted in index points.  Expected cash amounts use the desk
convention that a positive value is an upfront client outlay and a negative
value is premium received by the client.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from quant_hedge_desk.domain.instruments import FutureLeg, VanillaOptionLeg


QUOTE_TIMESTAMP = datetime.fromisoformat("2026-08-21T10:00:00+05:30")
EXPIRY = date(2027, 2, 25)


def nifty_future(*, quantity: int = 10) -> FutureLeg:
    """Return the futures-overlay fixture; futures carry no upfront premium."""

    return FutureLeg(
        underlying="NIFTY",
        direction="SHORT",
        strike_or_level="24000",
        expiry=EXPIRY,
        quantity=quantity,
        contract_multiplier="25",
        quote_timestamp=QUOTE_TIMESTAMP,
        liquidity_attributes={"normal_daily_volume": 250_000},
    )


def nifty_put(
    *,
    strike: str = "22800",
    direction: str = "LONG",
    premium: str = "650.25",
    quantity: int = 10,
) -> VanillaOptionLeg:
    """Return a NIFTY put with overridable terms for spreads."""

    return VanillaOptionLeg(
        underlying="NIFTY",
        direction=direction,
        strike_or_level=strike,
        expiry=EXPIRY,
        quantity=quantity,
        contract_multiplier="25",
        premium=premium,
        quote_timestamp=QUOTE_TIMESTAMP,
        liquidity_attributes={"normal_daily_volume": 100_000},
        option_type="PUT",
    )


def nifty_call(
    *,
    strike: str = "26400",
    direction: str = "SHORT",
    premium: str = "310.10",
    quantity: int = 10,
) -> VanillaOptionLeg:
    """Return the short NIFTY call used by the collar fixture."""

    return VanillaOptionLeg(
        underlying="NIFTY",
        direction=direction,
        strike_or_level=strike,
        expiry=EXPIRY,
        quantity=quantity,
        contract_multiplier="25",
        premium=premium,
        quote_timestamp=QUOTE_TIMESTAMP,
        liquidity_attributes={"normal_daily_volume": 90_000},
        option_type="CALL",
    )


def banknifty_put(*, quantity: int = 5) -> VanillaOptionLeg:
    """Return the BANKNIFTY component of the hybrid hedge fixture."""

    return VanillaOptionLeg(
        underlying="BANKNIFTY",
        direction="LONG",
        strike_or_level="47500",
        expiry=EXPIRY,
        quantity=quantity,
        contract_multiplier="15",
        premium="1425.50",
        quote_timestamp=QUOTE_TIMESTAMP,
        liquidity_attributes={"normal_daily_volume": 60_000},
        option_type="PUT",
    )


@dataclass(frozen=True, slots=True)
class PremiumFixture:
    """A named structure and its expected signed upfront premium in INR."""

    name: str
    legs: tuple[FutureLeg | VanillaOptionLeg, ...]
    expected_net_premium: Decimal


def premium_fixtures() -> tuple[PremiumFixture, ...]:
    """Cover every approved v1 hedge family with exact expected premiums."""

    protective_put = nifty_put()
    spread_long = nifty_put()
    spread_short = nifty_put(
        strike="21600", direction="SHORT", premium="325.40"
    )
    collar_put = nifty_put()
    collar_call = nifty_call()
    hybrid_nifty = nifty_put(quantity=6)
    hybrid_banknifty = banknifty_put()

    return (
        PremiumFixture(
            name="nifty_futures_beta_hedge",
            legs=(nifty_future(),),
            expected_net_premium=Decimal("0"),
        ),
        PremiumFixture(
            name="nifty_protective_put",
            legs=(protective_put,),
            expected_net_premium=Decimal("162562.50"),
        ),
        PremiumFixture(
            name="nifty_vertical_put_spread",
            legs=(spread_long, spread_short),
            expected_net_premium=Decimal("81212.50"),
        ),
        PremiumFixture(
            name="nifty_collar",
            legs=(collar_put, collar_call),
            expected_net_premium=Decimal("85037.50"),
        ),
        PremiumFixture(
            name="hybrid_nifty_banknifty_put_hedge",
            legs=(hybrid_nifty, hybrid_banknifty),
            expected_net_premium=Decimal("204450.00"),
        ),
    )


__all__ = [
    "EXPIRY",
    "QUOTE_TIMESTAMP",
    "PremiumFixture",
    "banknifty_put",
    "nifty_call",
    "nifty_future",
    "nifty_put",
    "premium_fixtures",
]
