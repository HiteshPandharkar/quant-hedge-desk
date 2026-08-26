import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.instruments import (  # noqa: E402
    FutureLeg,
    InstrumentValidationError,
    VanillaOptionLeg,
)
from quant_hedge_desk.hedge_design.evaluator import (  # noqa: E402
    evaluate_aggregate_terminal_payoff,
    evaluate_terminal_payoff,
)


class TerminalPayoffEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.common = {
            "underlying": "NIFTY",
            "strike_or_level": "24000",
            "expiry": "2027-02-25",
            "quantity": 2,
            "contract_multiplier": "25",
            "quote_timestamp": "2026-08-21T10:00:00+05:30",
            "liquidity_attributes": {},
        }

    def test_long_and_short_futures_have_opposite_payoffs(self) -> None:
        long_leg = FutureLeg(**self.common, direction="LONG")
        short_leg = FutureLeg(**self.common, direction="SHORT")

        self.assertEqual(evaluate_terminal_payoff(long_leg, "24200"), Decimal("10000"))
        self.assertEqual(evaluate_terminal_payoff(short_leg, "24200"), Decimal("-10000"))

    def test_calls_and_puts_pay_intrinsic_value_only(self) -> None:
        call = VanillaOptionLeg(
            **self.common, direction="LONG", option_type="CALL", premium="500"
        )
        put = VanillaOptionLeg(
            **self.common, direction="SHORT", option_type="PUT", premium="500"
        )

        self.assertEqual(evaluate_terminal_payoff(call, "24500"), Decimal("25000"))
        self.assertEqual(evaluate_terminal_payoff(call, "23500"), Decimal("0"))
        self.assertEqual(evaluate_terminal_payoff(put, "23500"), Decimal("-25000"))
        self.assertEqual(evaluate_terminal_payoff(put, "24500"), Decimal("0"))

    def test_aggregate_uses_each_underlyings_terminal_level(self) -> None:
        nifty = FutureLeg(**self.common, direction="LONG")
        banknifty = FutureLeg(
            **{**self.common, "underlying": "BANKNIFTY", "strike_or_level": "50000"},
            direction="SHORT",
        )

        self.assertEqual(
            evaluate_aggregate_terminal_payoff(
                (nifty, banknifty), {"nifty": "24100", "BANKNIFTY": "49800"}
            ),
            Decimal("15000"),
        )

    def test_terminal_level_must_be_finite_and_non_negative(self) -> None:
        leg = FutureLeg(**self.common, direction="LONG")
        for level in (-1, "NaN", "Infinity", True):
            with self.subTest(level=level):
                with self.assertRaisesRegex(InstrumentValidationError, "terminal_level"):
                    evaluate_terminal_payoff(leg, level)


if __name__ == "__main__":
    unittest.main()
