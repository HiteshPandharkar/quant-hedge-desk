import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.data.repositories import (  # noqa: E402
    AdjustedCloseCSVRepository,
    MarketDataRepositoryError,
)


class AdjustedCloseCSVRepositoryTests(unittest.TestCase):
    def write_csv(self, contents: str) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        path = Path(temporary_directory.name) / "prices.csv"
        path.write_text(contents, encoding="utf-8")
        return path

    def test_loads_required_symbols_and_applies_snapshot_cutoff(self) -> None:
        path = self.write_csv(
            "date,symbol,adjusted_close,ignored\n"
            "2026-01-29,AAA,100,x\n"
            "2026-01-30,AAA,101,x\n"
            "2026-01-31,AAA,999,x\n"
            "2026-01-30,UNUSED,50,x\n"
        )

        result = AdjustedCloseCSVRepository().load(
            path,
            required_symbols=("aaa",),
            end_date=date(2026, 1, 30),
        )

        self.assertEqual(
            result,
            {"AAA": {"2026-01-29": "100", "2026-01-30": "101"}},
        )

    def test_rejects_a_source_that_does_not_satisfy_the_contract(self) -> None:
        path = self.write_csv("date,symbol\n2026-01-30,AAA\n")

        with self.assertRaisesRegex(MarketDataRepositoryError, "adjusted_close"):
            AdjustedCloseCSVRepository().load(
                path,
                required_symbols=("AAA",),
                end_date=date(2026, 1, 30),
            )


if __name__ == "__main__":
    unittest.main()
