"""Application-level assessment exceptions."""


class AssessmentInputError(ValueError):
    """Raised when valid source records cannot support an assessment."""


__all__ = ["AssessmentInputError"]
