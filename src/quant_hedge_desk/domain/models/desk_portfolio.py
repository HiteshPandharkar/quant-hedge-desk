"""Versioned snapshots of the dealer's existing risk inventory.

The snapshot deliberately stores approved risk-system measures rather than
revaluing positions.  That keeps desk-incremental risk independent of a
particular pricing adapter and makes the sign convention explicit: positive
values are gains/exposures and negative crash-stress P&L is a loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from quant_hedge_desk.domain.enums import InstrumentType, Underlying
from quant_hedge_desk.domain.models._validation import ModelValidator


class DeskPortfolioValidationError(ValueError):
    """Raised when a desk portfolio snapshot is malformed or inconsistent."""


_validate = ModelValidator(DeskPortfolioValidationError)


def _enum(value: Any, enum_type: type, path: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise DeskPortfolioValidationError(
            f"{path} must be one of: {allowed}"
        ) from exc


def _valuation_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise DeskPortfolioValidationError(
                "valuation_timestamp must be an ISO datetime"
            ) from exc
    else:
        raise DeskPortfolioValidationError(
            "valuation_timestamp must be a datetime or ISO datetime string"
        )
    if result.tzinfo is None or result.utcoffset() is None:
        raise DeskPortfolioValidationError(
            "valuation_timestamp must include a UTC offset"
        )
    return result


@dataclass(frozen=True, slots=True)
class DeskRiskExposure:
    """Signed dealer exposure in the dimensions governed by desk limits."""

    net_index_delta_inr: Decimal
    one_month_vega_inr_per_vol_point: Decimal
    six_month_vega_inr_per_vol_point: Decimal
    crash_stress_pnl_inr: Decimal

    def __post_init__(self) -> None:
        for name in (
            "net_index_delta_inr",
            "one_month_vega_inr_per_vol_point",
            "six_month_vega_inr_per_vol_point",
            "crash_stress_pnl_inr",
        ):
            object.__setattr__(
                self, name, _validate.decimal(getattr(self, name), name)
            )

    def __add__(self, other: object) -> "DeskRiskExposure":
        if not isinstance(other, DeskRiskExposure):
            return NotImplemented
        return DeskRiskExposure(
            self.net_index_delta_inr + other.net_index_delta_inr,
            self.one_month_vega_inr_per_vol_point
            + other.one_month_vega_inr_per_vol_point,
            self.six_month_vega_inr_per_vol_point
            + other.six_month_vega_inr_per_vol_point,
            self.crash_stress_pnl_inr + other.crash_stress_pnl_inr,
        )

    @classmethod
    def zero(cls) -> "DeskRiskExposure":
        return cls(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))


@dataclass(frozen=True, slots=True)
class DeskPosition:
    """One existing inventory position and its approved risk snapshot."""

    position_id: str
    description: str
    underlying: Underlying
    instrument_type: InstrumentType
    risk: DeskRiskExposure

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "position_id", _validate.required_text(self.position_id, "position_id")
        )
        object.__setattr__(
            self, "description", _validate.required_text(self.description, "description")
        )
        object.__setattr__(
            self, "underlying", _enum(self.underlying, Underlying, "underlying")
        )
        object.__setattr__(
            self,
            "instrument_type",
            _enum(self.instrument_type, InstrumentType, "instrument_type"),
        )
        if not isinstance(self.risk, DeskRiskExposure):
            raise DeskPortfolioValidationError("risk must be a DeskRiskExposure")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DeskPosition":
        mapping = _validate.mapping(value, "desk position")
        required = {
            "position_id",
            "description",
            "underlying",
            "instrument_type",
            "net_index_delta_inr",
            "one_month_vega_inr_per_vol_point",
            "six_month_vega_inr_per_vol_point",
            "crash_stress_pnl_inr",
        }
        _validate.keys(mapping, required, "desk position")
        risk_fields = {
            key: mapping[key]
            for key in (
                "net_index_delta_inr",
                "one_month_vega_inr_per_vol_point",
                "six_month_vega_inr_per_vol_point",
                "crash_stress_pnl_inr",
            )
        }
        return cls(
            position_id=mapping["position_id"],
            description=mapping["description"],
            underlying=mapping["underlying"],
            instrument_type=mapping["instrument_type"],
            risk=DeskRiskExposure(**risk_fields),
        )


@dataclass(frozen=True, slots=True)
class DeskPortfolio:
    """Existing dealer inventory at one reproducible valuation instant."""

    desk_portfolio_id: str
    schema_version: str
    valuation_timestamp: datetime
    market_snapshot_id: str
    risk_model_version: str
    positions: tuple[DeskPosition, ...]

    def __post_init__(self) -> None:
        for name in (
            "desk_portfolio_id",
            "schema_version",
            "market_snapshot_id",
            "risk_model_version",
        ):
            object.__setattr__(
                self, name, _validate.required_text(getattr(self, name), name)
            )
        object.__setattr__(
            self, "valuation_timestamp", _valuation_timestamp(self.valuation_timestamp)
        )
        positions = tuple(self.positions)
        if any(not isinstance(item, DeskPosition) for item in positions):
            raise DeskPortfolioValidationError(
                "positions must contain only DeskPosition values"
            )
        position_ids = [item.position_id for item in positions]
        if len(position_ids) != len(set(position_ids)):
            duplicates = sorted(
                {item for item in position_ids if position_ids.count(item) > 1}
            )
            raise DeskPortfolioValidationError(
                f"duplicate position ids: {', '.join(duplicates)}"
            )
        object.__setattr__(self, "positions", positions)

    @property
    def aggregate_risk(self) -> DeskRiskExposure:
        total = DeskRiskExposure.zero()
        for position in self.positions:
            total += position.risk
        return total

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DeskPortfolio":
        mapping = _validate.mapping(value, "desk portfolio")
        required = {
            "desk_portfolio_id",
            "schema_version",
            "valuation_timestamp",
            "market_snapshot_id",
            "risk_model_version",
            "positions",
        }
        _validate.keys(mapping, required, "desk portfolio")
        raw_positions = _validate.sequence(mapping["positions"], "positions")
        return cls(
            **{key: mapping[key] for key in required - {"positions"}},
            positions=tuple(DeskPosition.from_mapping(item) for item in raw_positions),
        )


__all__ = [
    "DeskPortfolio",
    "DeskPortfolioValidationError",
    "DeskPosition",
    "DeskRiskExposure",
]
