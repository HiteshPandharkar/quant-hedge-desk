"""Repositories for reading external market-data sources."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Protocol, Sequence

from quant_hedge_desk.data.constants import (
    ADJUSTED_CLOSE_FIELD,
    EOD_PRICE_CSV_REQUIRED_FIELDS,
)


class MarketDataRepositoryError(ValueError):
    """Raised when a market-data source cannot satisfy its contract."""


class AdjustedCloseRepository(Protocol):
    """Port implemented by adjusted-close market-data adapters."""

    def load(
        self,
        path: str | Path,
        *,
        required_symbols: Sequence[str],
        end_date: date,
    ) -> dict[str, dict[str, str]]: ...


class AdjustedCloseCSVRepository:
    """Read adjusted closes from the canonical long-form EOD CSV."""

    def load(
        self,
        path: str | Path,
        *,
        required_symbols: Sequence[str],
        end_date: date,
    ) -> dict[str, dict[str, str]]:
        source = Path(path)
        required = tuple(symbol.strip().upper() for symbol in required_symbols)
        required_set = set(required)
        history: dict[str, dict[str, str]] = {symbol: {} for symbol in required}

        try:
            with source.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                missing_fields = sorted(
                    EOD_PRICE_CSV_REQUIRED_FIELDS - set(reader.fieldnames or ())
                )
                if missing_fields:
                    raise MarketDataRepositoryError(
                        f"market data {source} is missing fields: "
                        + ", ".join(missing_fields)
                    )

                for line_number, row in enumerate(reader, start=2):
                    symbol = (row.get("symbol") or "").strip().upper()
                    if symbol not in required_set:
                        continue
                    raw_date = (row.get("date") or "").strip()
                    try:
                        observation_date = date.fromisoformat(raw_date)
                    except ValueError as exc:
                        raise MarketDataRepositoryError(
                            f"market data {source} line {line_number} has invalid "
                            f"date: {raw_date!r}"
                        ) from exc
                    if observation_date > end_date:
                        continue
                    if raw_date in history[symbol]:
                        raise MarketDataRepositoryError(
                            f"market data {source} has duplicate {symbol} date "
                            f"{raw_date}"
                        )
                    history[symbol][raw_date] = row.get(ADJUSTED_CLOSE_FIELD) or ""
        except OSError as exc:
            raise MarketDataRepositoryError(
                f"could not load market data {source}: {exc}"
            ) from exc

        missing_symbols = sorted(
            symbol for symbol, observations in history.items() if not observations
        )
        if missing_symbols:
            raise MarketDataRepositoryError(
                f"market data has no observations through {end_date} for: "
                + ", ".join(missing_symbols)
            )
        return history


__all__ = [
    "AdjustedCloseCSVRepository",
    "AdjustedCloseRepository",
    "MarketDataRepositoryError",
]
