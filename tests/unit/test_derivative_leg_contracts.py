import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.instruments import (  # noqa: E402
    Direction,
    FutureLeg,
    FuturesLeg,
    InstrumentType,
    InstrumentValidationError,
    LegDirection,
    OptionLeg,
    OptionRight,
    OptionStyle,
    OptionType,
    Underlying,
    VanillaOptionLeg,
)


class InstrumentLegTests(unittest.TestCase):
    def setUp(self) -> None:
        self.common = {
            "underlying": "NIFTY",
            "direction": "LONG",
            "strike_or_level": "24000",
            "expiry": "2027-02-25",
            "quantity": 10,
            "contract_multiplier": "25",
            "quote_timestamp": "2026-08-21T10:00:00+05:30",
            "liquidity_attributes": {"normal_daily_volume": 100_000},
        }

    def test_future_leg_normalizes_a_valid_mapping(self) -> None:
        leg = FutureLeg.from_mapping(
            {**self.common, "instrument_type": "FUTURE"}
        )

        self.assertEqual(leg.underlying, Underlying.NIFTY)
        self.assertEqual(leg.direction, LegDirection.LONG)
        self.assertEqual(leg.instrument_type, InstrumentType.FUTURE)
        self.assertEqual(leg.strike_or_level, Decimal("24000"))
        self.assertEqual(leg.expiry, date(2027, 2, 25))
        self.assertEqual(leg.quote_timestamp.utcoffset(), timedelta(hours=5, minutes=30))

    def test_vanilla_option_requires_its_payoff_terms(self) -> None:
        leg = VanillaOptionLeg.from_mapping(
            {
                **self.common,
                "instrument_type": "OPTION",
                "premium": "650.25",
                "option_type": "PUT",
                "option_style": "EUROPEAN",
            }
        )

        self.assertEqual(leg.option_type, OptionType.PUT)
        self.assertEqual(leg.option_style, OptionStyle.EUROPEAN)
        self.assertEqual(leg.premium, Decimal("650.25"))

    def test_option_constructor_defaults_to_european_style(self) -> None:
        leg = VanillaOptionLeg(
            **self.common,
            premium=0,
            option_type="CALL",
        )

        self.assertEqual(leg.instrument_type, InstrumentType.OPTION)
        self.assertEqual(leg.option_type, OptionType.CALL)
        self.assertEqual(leg.option_style, OptionStyle.EUROPEAN)

    def test_public_aliases_resolve_to_canonical_types(self) -> None:
        self.assertIs(FuturesLeg, FutureLeg)
        self.assertIs(OptionLeg, VanillaOptionLeg)
        self.assertIs(OptionRight, OptionType)
        self.assertIs(Direction, LegDirection)

    def test_future_has_no_premium_field(self) -> None:
        leg = FutureLeg(**self.common)

        self.assertFalse(hasattr(leg, "premium"))

    def test_future_mapping_rejects_option_premium(self) -> None:
        with self.assertRaisesRegex(InstrumentValidationError, "unknown fields: premium"):
            FutureLeg.from_mapping(
                {**self.common, "instrument_type": "FUTURE", "premium": 0}
            )

    def test_wrong_mapping_instrument_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(InstrumentValidationError, "FUTURE"):
            FutureLeg.from_mapping(
                {**self.common, "instrument_type": "OPTION"}
            )

    def test_option_mapping_rejects_future_discriminator(self) -> None:
        with self.assertRaisesRegex(InstrumentValidationError, "OPTION"):
            VanillaOptionLeg.from_mapping(
                {
                    **self.common,
                    "instrument_type": "FUTURE",
                    "premium": 0,
                    "option_type": "PUT",
                    "option_style": "EUROPEAN",
                }
            )

    def test_mapping_rejects_missing_and_unknown_fields(self) -> None:
        incomplete = {**self.common, "instrument_type": "FUTURE"}
        incomplete.pop("quantity")
        with self.assertRaisesRegex(InstrumentValidationError, "missing: quantity"):
            FutureLeg.from_mapping(
                incomplete
            )

        with self.assertRaisesRegex(InstrumentValidationError, "unknown fields: desk"):
            FutureLeg.from_mapping(
                {
                    **self.common,
                    "instrument_type": "FUTURE",
                    "desk": "INDEX",
                }
            )

    def test_invalid_controlled_vocabularies_are_rejected(self) -> None:
        invalid_fields = {
            "underlying": "SENSEX",
            "direction": "BUY",
        }
        for field, invalid_value in invalid_fields.items():
            with self.subTest(field=field):
                values = {**self.common, field: invalid_value}
                with self.assertRaisesRegex(InstrumentValidationError, field):
                    FutureLeg(**values)

        with self.assertRaisesRegex(InstrumentValidationError, "option_type"):
            VanillaOptionLeg(
                **self.common,
                premium=0,
                option_type="STRADDLE",
            )

    def test_positive_contract_fields_are_enforced(self) -> None:
        invalid_fields = {
            "strike_or_level": 0,
            "quantity": 0,
            "contract_multiplier": -1,
        }
        for field, invalid_value in invalid_fields.items():
            with self.subTest(field=field):
                values = {**self.common, field: invalid_value}
                with self.assertRaisesRegex(InstrumentValidationError, field):
                    FutureLeg(**values)

    def test_quantity_must_be_an_integer(self) -> None:
        for invalid_quantity in (True, Decimal("1.5"), "10"):
            with self.subTest(quantity=invalid_quantity):
                with self.assertRaisesRegex(InstrumentValidationError, "positive integer"):
                    FutureLeg(**{**self.common, "quantity": invalid_quantity})

    def test_option_rejects_negative_or_non_finite_premium(self) -> None:
        for invalid_premium in ("-0.01", "NaN", "Infinity"):
            with self.subTest(premium=invalid_premium):
                with self.assertRaisesRegex(InstrumentValidationError, "premium"):
                    VanillaOptionLeg(
                        **self.common,
                        premium=invalid_premium,
                        option_type="PUT",
                    )

    def test_original_liquidity_mapping_is_defensively_copied(self) -> None:
        attributes = {"normal_daily_volume": 100_000}
        leg = FutureLeg(
            **{**self.common, "liquidity_attributes": attributes},
        )

        attributes["normal_daily_volume"] = 1

        self.assertEqual(leg.liquidity_attributes["normal_daily_volume"], 100_000)

    def test_leg_and_liquidity_mapping_are_immutable(self) -> None:
        leg = FutureLeg(**self.common)
        with self.assertRaises(FrozenInstanceError):
            leg.quantity = 20
        with self.assertRaises(TypeError):
            leg.liquidity_attributes["normal_daily_volume"] = 1


if __name__ == "__main__":
    unittest.main()
