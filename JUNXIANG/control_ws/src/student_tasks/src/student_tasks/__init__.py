"""Stable public API for shared robot motion control."""

from .backend import Cancellation, CancellationToken, MotionBackend
from .core import MotionController
from .errors import ControlError, ControlFailure, ErrorCategory
from .models import (
    BackendStatus,
    MotionRequest,
    MotionResult,
    Velocity,
    VerificationLevel,
    ZERO_VELOCITY,
)

__all__ = [
    "BackendStatus",
    "Cancellation",
    "CancellationToken",
    "ControlError",
    "ControlFailure",
    "ErrorCategory",
    "MotionBackend",
    "MotionController",
    "MotionRequest",
    "MotionResult",
    "Velocity",
    "VerificationLevel",
    "ZERO_VELOCITY",
]
