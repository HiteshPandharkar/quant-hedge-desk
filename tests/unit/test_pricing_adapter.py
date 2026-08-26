import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.data.loaders import load_yaml_mapping  # noqa: E402
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate  # noqa: E402
from quant_hedge_desk.pricing import (  # noqa: E402
    CSVQuotePricingAdapter,
    PricingAdapter,
    PricingAdapterError,
)


HEADER = (
    "quote_timestamp,underlying,instrument_type,expiry,strike_or_level,"
    "option_type,premium,source,normal_daily_volume\n"
)


class CSVQuotePricingAdapterTests(unittest.TestCase):
    def write_csv(self, rows: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "quotes.csv"
        path.write_text(HEADER + rows, encoding="utf-8")
        return path

    @staticmethod
    def candidate() -> HedgeCandidate:
        mapping = load_yaml_mapping(
            ROOT / "cases" / "asteria_capital" / "candidate_03_nifty_protective_put.yaml"
        )
        return HedgeCandidate.from_mapping(mapping)

    def test_prices_candidate_from_latest_non_future_quote(self) -> None:
        adapter = CSVQuotePricingAdapter(
            self.write_csv(
                "2026-01-29T15:30:00+05:30,NIFTY,OPTION,2026-07-30,24000,PUT,675.00,TEST,90000\n"
                "2026-01-30T15:30:00+05:30,NIFTY,OPTION,2026-07-30,24000,PUT,686.03,TEST,100000\n"
                "2026-01-31T15:30:00+05:30,NIFTY,OPTION,2026-07-30,24000,PUT,999.00,FUTURE,1\n"
            )
        )

        priced = adapter.price_candidate(self.candidate(), max_age=timedelta(days=1))

        self.assertIsInstance(adapter, PricingAdapter)
        self.assertEqual(str(priced.legs[0].premium), "686.03")
        self.assertEqual(priced.legs[0].liquidity_attributes["pricing_source"], "TEST")
        self.assertEqual(priced.legs[0].liquidity_attributes["normal_daily_volume"], 100000)

    def test_rejects_missing_and_stale_contract_quotes(self) -> None:
        adapter = CSVQuotePricingAdapter(
            self.write_csv(
                "2026-01-28T15:30:00+05:30,NIFTY,OPTION,2026-07-30,24000,PUT,660,TEST,100000\n"
            )
        )
        candidate = self.candidate()

        with self.assertRaisesRegex(PricingAdapterError, "stale quote"):
            adapter.quote_for(candidate.legs[0], max_age=timedelta(days=1))
        with self.assertRaisesRegex(PricingAdapterError, "no quote"):
            adapter.quote_for(replace(candidate.legs[0], strike_or_level="22000"))

    def test_rejects_duplicate_contract_timestamp(self) -> None:
        row = "2026-01-30T15:30:00+05:30,NIFTY,OPTION,2026-07-30,24000,PUT,686.03,TEST,100000\n"
        with self.assertRaisesRegex(PricingAdapterError, "duplicate"):
            CSVQuotePricingAdapter(self.write_csv(row + row))

    def test_rejects_timezone_naive_snapshot(self) -> None:
        with self.assertRaisesRegex(PricingAdapterError, "UTC offset"):
            CSVQuotePricingAdapter(
                self.write_csv(
                    "2026-01-30T15:30:00,NIFTY,OPTION,2026-07-30,24000,PUT,686.03,TEST,100000\n"
                )
            )


if __name__ == "__main__":
    unittest.main()
