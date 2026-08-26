import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quant_hedge_desk.data.loaders import (  # noqa: E402
    PORTFOLIO_CSV_FIELDS,
    PortfolioCSVValidationError,
    PortfolioCSVWarning,
    load_portfolio_csv,
    load_portfolio_csv_with_report,
)


def row(symbol: str, quantity: str, price: str, value: str, weight: str) -> str:
    return ",".join(
        (
            "ASTERIA-001",
            "2026-01-30",
            symbol,
            quantity,
            price,
            value,
            weight,
            "Financials",
            "20%",
            "HIGH",
            "NONE",
            "TEST",
        )
    )


class PortfolioCSVLoaderTests(unittest.TestCase):
    def write_csv(self, contents: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "portfolio.csv"
        path.write_text(contents, encoding="utf-8")
        return path

    def valid_csv(self) -> str:
        return (
            ",".join(PORTFOLIO_CSV_FIELDS)
            + "\n"
            + row("AAA", "60", "10", "600", "60%")
            + "\n"
            + row("BBB", "20", "20", "400", "40%")
            + "\n"
        )

    def test_loads_and_reconciles_reference_csv(self) -> None:
        result = load_portfolio_csv(
            ROOT / "cases" / "asteria_capital" / "portfolio.csv",
            supplied_total_market_value="5000000000",
        )

        self.assertEqual(result.portfolio_id, "ASTERIA-001")
        self.assertEqual(len(result.holdings), 50)

    def test_invalid_row_is_reported_by_physical_line(self) -> None:
        path = self.write_csv(self.valid_csv().replace("BBB,20,20", "BBB,not-a-number,20"))

        with self.assertRaises(PortfolioCSVValidationError) as caught:
            load_portfolio_csv(path)

        issue = caught.exception.report.errors[0]
        self.assertEqual(issue.code, "invalid_holding")
        self.assertEqual(issue.row_number, 3)
        self.assertIn("quantity must be numeric", issue.message)

    def test_duplicate_holding_is_rejected_after_symbol_normalization(self) -> None:
        contents = self.valid_csv().replace("BBB,20,20,400,40%", "aaa,40,10,400,40%")
        path = self.write_csv(contents)

        with self.assertRaises(PortfolioCSVValidationError) as caught:
            load_portfolio_csv(path)

        duplicate_rows = [
            issue.row_number
            for issue in caught.exception.report.errors
            if issue.code == "duplicate_holding"
        ]
        self.assertEqual(duplicate_rows, [2, 3])

    def test_missing_header_is_rejected_before_rows_are_read(self) -> None:
        contents = self.valid_csv().replace("data_source", "", 1)
        path = self.write_csv(contents)

        with self.assertRaises(PortfolioCSVValidationError) as caught:
            load_portfolio_csv(path)

        codes = {issue.code for issue in caught.exception.report.errors}
        self.assertIn("missing_columns", codes)
        self.assertIn("unknown_columns", codes)

    def test_stale_prices_are_flagged_without_rejecting_historical_snapshot(self) -> None:
        path = self.write_csv(self.valid_csv())

        result = load_portfolio_csv_with_report(
            path,
            valuation_date=date(2026, 2, 2),
            max_price_age_days=1,
        )

        self.assertTrue(result.report.is_valid)
        self.assertEqual(len(result.report.warnings), 2)
        self.assertTrue(all(issue.code == "stale_price" for issue in result.report.warnings))

        with self.assertWarns(PortfolioCSVWarning):
            portfolio = load_portfolio_csv(
                path,
                valuation_date=date(2026, 2, 2),
                max_price_age_days=1,
            )
        self.assertEqual(len(portfolio.holdings), 2)

    def test_portfolio_level_reconciliation_error_is_preserved(self) -> None:
        path = self.write_csv(self.valid_csv())

        with self.assertRaises(PortfolioCSVValidationError) as caught:
            load_portfolio_csv(path, supplied_total_market_value="900")

        self.assertEqual(caught.exception.report.errors[0].code, "portfolio_reconciliation")
        self.assertIn("supplied total", caught.exception.report.errors[0].message)

    def test_mixed_snapshot_date_identifies_the_inconsistent_row(self) -> None:
        contents = self.valid_csv().replace("2026-01-30,BBB", "2026-01-29,BBB")
        path = self.write_csv(contents)

        with self.assertRaises(PortfolioCSVValidationError) as caught:
            load_portfolio_csv(path)

        issue = next(
            issue
            for issue in caught.exception.report.errors
            if issue.code == "inconsistent_as_of_date"
        )
        self.assertEqual(issue.row_number, 3)
        self.assertEqual(issue.field, "as_of_date")


if __name__ == "__main__":
    unittest.main()
