import sys
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.enums import InstrumentType, OptionType  # noqa: E402
from quant_hedge_desk.domain.errors import InstrumentValidationError  # noqa: E402
from quant_hedge_desk.domain.instrument_leg_validation import (  # noqa: E402
    enum_value,
    expiry_date,
    immutable_liquidity_attributes,
    leg_mapping,
    non_negative_decimal,
    quote_datetime,
)


class LegValidationRuleTests(unittest.TestCase):
    def test_enum_value_normalizes_valid_values_and_lists_allowed_values(self) -> None:
        self.assertEqual(enum_value("PUT", OptionType, "option_type"), OptionType.PUT)

        with self.assertRaisesRegex(
            InstrumentValidationError,
            r"option_type must be one of: CALL, PUT",
        ):
            enum_value("DIGITAL", OptionType, "option_type")

    def test_expiry_date_accepts_date_and_iso_text(self) -> None:
        expected = date(2027, 2, 25)

        self.assertIs(expiry_date(expected), expected)
        self.assertEqual(expiry_date(" 2027-02-25 "), expected)

    def test_expiry_date_rejects_datetime_and_invalid_text(self) -> None:
        invalid_values = (datetime(2027, 2, 25), "25-02-2027", 20270225)
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(InstrumentValidationError):
                    expiry_date(value)

    def test_quote_datetime_accepts_datetime_iso_text_and_z_suffix(self) -> None:
        expected = datetime(2026, 8, 21, 4, 30, tzinfo=timezone.utc)

        self.assertIs(quote_datetime(expected), expected)
        self.assertEqual(quote_datetime("2026-08-21T04:30:00Z"), expected)

    def test_quote_datetime_rejects_date_and_invalid_text(self) -> None:
        for value in (date(2026, 8, 21), "yesterday", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(InstrumentValidationError, "quote_timestamp"):
                    quote_datetime(value)

    def test_non_negative_decimal_accepts_zero_and_rejects_invalid_numbers(self) -> None:
        self.assertEqual(non_negative_decimal(0, "premium"), Decimal("0"))
        self.assertEqual(non_negative_decimal("1.25", "premium"), Decimal("1.25"))

        for value in (-1, True, "NaN", "Infinity"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(InstrumentValidationError, "premium"):
                    non_negative_decimal(value, "premium")

    def test_liquidity_attributes_require_a_mapping_and_are_read_only(self) -> None:
        original = {"bid_ask_spread": Decimal("1.5")}
        result = immutable_liquidity_attributes(original)

        original["bid_ask_spread"] = Decimal("9")
        self.assertEqual(result["bid_ask_spread"], Decimal("1.5"))
        with self.assertRaises(TypeError):
            result["bid_ask_spread"] = Decimal("2")
        with self.assertRaisesRegex(InstrumentValidationError, "mapping"):
            immutable_liquidity_attributes([])

    def test_leg_mapping_validates_shape_and_discriminator(self) -> None:
        required = {"instrument_type", "quantity"}
        valid = {"instrument_type": "FUTURE", "quantity": 2}

        self.assertIs(
            leg_mapping(
                valid,
                path="future leg",
                required=required,
                expected_instrument_type=InstrumentType.FUTURE,
            ),
            valid,
        )

        with self.assertRaisesRegex(InstrumentValidationError, "must be FUTURE"):
            leg_mapping(
                {"instrument_type": "OPTION", "quantity": 2},
                path="future leg",
                required=required,
                expected_instrument_type=InstrumentType.FUTURE,
            )


if __name__ == "__main__":
    unittest.main()
