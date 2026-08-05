"""Stable error taxonomy shared by every control adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class ErrorCategory(str, Enum):
    """Stable CLI exit-class categories."""

    USAGE = "usage"
    VALIDATION = "validation"
    UNAVAILABLE = "unavailable"
    RUNTIME = "runtime"
    STOP_SAFETY = "stop_safety"


_ERROR_DEFINITIONS: Mapping[str, tuple[ErrorCategory, bool]] = {
    "INVALID_INPUT": (ErrorCategory.VALIDATION, False),
    "LIMIT_EXCEEDED": (ErrorCategory.VALIDATION, False),
    "BACKEND_UNAVAILABLE": (ErrorCategory.UNAVAILABLE, True),
    "CAPABILITY_DISABLED": (ErrorCategory.UNAVAILABLE, False),
    "PRODUCTION_CONFIG_REQUIRED": (ErrorCategory.UNAVAILABLE, False),
    "MOTION_BUSY": (ErrorCategory.UNAVAILABLE, True),
    "CANCELLED": (ErrorCategory.RUNTIME, True),
    "TIMEOUT": (ErrorCategory.RUNTIME, True),
    "BACKEND_FAILURE": (ErrorCategory.RUNTIME, True),
    "STOP_FAILED": (ErrorCategory.STOP_SAFETY, True),
}


@dataclass(frozen=True)
class ControlError:
    """Machine-readable control failure."""

    code: str
    category: ErrorCategory
    detail: str
    retryable: bool

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("Control error detail must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category.value,
            "detail": self.detail,
            "retryable": self.retryable,
        }


def control_error(code: str, detail: str) -> ControlError:
    """Build a known error without scattering category decisions."""

    try:
        category, retryable = _ERROR_DEFINITIONS[code]
    except KeyError as exc:
        raise ValueError("Unknown control error code: %s" % code) from exc
    return ControlError(code, category, detail, retryable)


class ControlFailure(RuntimeError):
    """Internal exception carrying one stable public error."""

    def __init__(self, error: ControlError, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(error.detail)
        self.error = error
        self.context = dict(context or {})


def failure(code: str, detail: str, **context: Any) -> ControlFailure:
    """Create a control exception with optional diagnostic context."""

    return ControlFailure(control_error(code, detail), context=context)
