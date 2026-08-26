"""Download the reference case's adjusted EOD prices from Yahoo Finance."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yfinance as yf


BENCHMARK_TICKERS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}

YAHOO_SYMBOL_OVERRIDES = {
    # NSE changed the passenger-vehicle company's symbol from TATAMOTORS to
    # TMPV on 2025-10-24 after the commercial-vehicle business was demerged.
    "TATAMOTORS": "TMPV.NS",
}


def yahoo_ticker(symbol: str) -> str:
    return YAHOO_SYMBOL_OVERRIDES.get(symbol, f"{symbol}.NS")


def portfolio_symbols(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or "symbol" not in reader.fieldnames:
            raise ValueError(f"{path} does not contain a symbol column")
        symbols = [row["symbol"].strip().upper() for row in reader]
    if not symbols or any(not symbol for symbol in symbols):
        raise ValueError(f"{path} contains a blank symbol or no holdings")
    if len(symbols) != len(set(symbols)):
        raise ValueError(f"{path} contains duplicate symbols")
    return symbols


def download_symbol(
    symbol: str, ticker: str, start: date, end_exclusive: date
) -> list[dict[str, object]]:
    history = yf.Ticker(ticker).history(
        start=start.isoformat(),
        end=end_exclusive.isoformat(),
        interval="1d",
        auto_adjust=False,
        actions=False,
        # yfinance 0.2.66's optional repair pass mutates a read-only array under
        # pandas 3.  Yahoo's supplied Close and Adj Close fields do not require
        # that heuristic repair for this reference download.
        repair=False,
        timeout=30,
        raise_errors=True,
    )
    if history.empty:
        raise RuntimeError(f"Yahoo Finance returned no EOD prices for {symbol} ({ticker})")

    rows: list[dict[str, object]] = []
    for timestamp, values in history.iterrows():
        adjusted_close = values.get("Adj Close")
        close = values.get("Close")
        volume = values.get("Volume")
        if adjusted_close is None or close is None:
            raise RuntimeError(f"Yahoo Finance omitted close fields for {symbol} on {timestamp}")
        rows.append(
            {
                "date": timestamp.date().isoformat(),
                "symbol": symbol,
                "yahoo_ticker": ticker,
                "adjusted_close": format(float(adjusted_close), ".10g"),
                "close": format(float(close), ".10g"),
                "volume": str(int(volume)) if volume is not None else "",
                "data_source": "YAHOO_FINANCE_VIA_YFINANCE",
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        required=True,
        help="inclusive end date",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.start >= args.end:
        raise ValueError("start must be earlier than end")

    holdings = portfolio_symbols(args.portfolio)
    tickers = {symbol: yahoo_ticker(symbol) for symbol in holdings}
    tickers.update(BENCHMARK_TICKERS)
    end_exclusive = date.fromordinal(args.end.toordinal() + 1)

    all_rows: list[dict[str, object]] = []
    coverage: dict[str, dict[str, object]] = {}
    for number, (symbol, ticker) in enumerate(tickers.items(), start=1):
        print(f"[{number:02d}/{len(tickers)}] {symbol} <- {ticker}", file=sys.stderr)
        rows = download_symbol(symbol, ticker, args.start, end_exclusive)
        all_rows.extend(rows)
        coverage[symbol] = {
            "yahoo_ticker": ticker,
            "row_count": len(rows),
            "first_date": rows[0]["date"],
            "last_date": rows[-1]["date"],
        }

    all_rows.sort(key=lambda row: (str(row["date"]), str(row["symbol"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "date",
        "symbol",
        "yahoo_ticker",
        "adjusted_close",
        "close",
        "volume",
        "data_source",
    )
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)

    manifest = {
        "dataset": args.output.name,
        "source": "Yahoo Finance via yfinance",
        "yfinance_version": yf.__version__,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start": args.start.isoformat(),
        "requested_end_inclusive": args.end.isoformat(),
        "price_field_for_returns": "adjusted_close",
        "symbol_count": len(tickers),
        "row_count": len(all_rows),
        "coverage": coverage,
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(all_rows)} rows to {args.output}")
    print(f"Wrote manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
