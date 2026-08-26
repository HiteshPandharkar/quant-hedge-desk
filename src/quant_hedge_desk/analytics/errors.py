"""Exceptions raised by analytics validation and calculations."""


class ReturnDataError(ValueError):
    """Raised when price history cannot form a reliable aligned dataset."""


class RiskMetricError(ValueError):
    """Raised when a risk metric cannot be calculated reliably."""


class ConcentrationMetricError(ValueError):
    """Raised when a concentration calculation parameter is invalid."""


class ExposureMetricError(ValueError):
    """Raised when benchmark-relative metrics cannot be calculated reliably."""


class DownsideMetricError(ExposureMetricError):
    """Raised when a downside metric cannot be calculated reliably."""


__all__ = [
    "ConcentrationMetricError",
    "DownsideMetricError",
    "ExposureMetricError",
    "ReturnDataError",
    "RiskMetricError",
]
