import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.domain.enums import LegDirection  # noqa: E402
from quant_hedge_desk.domain.models.derivative_legs import (  # noqa: E402
    FutureLeg,
    VanillaOptionLeg,
)
from tests.fixtures.premiums import premium_fixtures  # noqa: E402


def signed_premium(leg: FutureLeg | VanillaOptionLeg) -> Decimal:
    if isinstance(leg, FutureLeg):
        return Decimal("0")
    sign = Decimal("1") if leg.direction is LegDirection.LONG else Decimal("-1")
    return sign * leg.premium * leg.quantity * leg.contract_multiplier


class PremiumFixtureTests(unittest.TestCase):
    def test_fixtures_cover_each_approved_structure_family(self) -> None:
        fixtures = premium_fixtures()

        self.assertEqual(len(fixtures), 5)
        self.assertEqual(len({fixture.name for fixture in fixtures}), 5)

    def test_expected_net_premiums_reconcile_to_their_legs(self) -> None:
        for fixture in premium_fixtures():
            with self.subTest(fixture=fixture.name):
                actual = sum(map(signed_premium, fixture.legs), Decimal("0"))
                self.assertEqual(actual, fixture.expected_net_premium)

    def test_each_structure_uses_one_coherent_market_snapshot(self) -> None:
        for fixture in premium_fixtures():
            with self.subTest(fixture=fixture.name):
                timestamps = {leg.quote_timestamp for leg in fixture.legs}
                expiries = {leg.expiry for leg in fixture.legs}
                self.assertEqual(len(timestamps), 1)
                self.assertEqual(len(expiries), 1)


if __name__ == "__main__":
    unittest.main()
