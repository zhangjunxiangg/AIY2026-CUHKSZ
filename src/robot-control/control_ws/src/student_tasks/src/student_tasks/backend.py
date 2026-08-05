"""ROS-free backend and cancellation protocols for the shared controller."""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from .models import BackendStatus, Velocity, VerificationLevel


@runtime_checkable
class Cancellation(Protocol):
    def is_cancelled(self) -> bool:
        """Return true when the current operation should stop."""


class CancellationToken:
    """Thread-safe cancellation state with no signal or transport coupling."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


@runtime_checkable
class MotionBackend(Protocol):
    @property
    def backend_name(self) -> str:
        ...

    @property
    def verification_level(self) -> VerificationLevel:
        ...

    def status(self) -> BackendStatus:
        ...

    def acquire(self, operation_id: str) -> None:
        ...

    def release(self) -> None:
        ...

    def publish_velocity(self, velocity: Velocity) -> None:
        ...

    def monotonic(self) -> float:
        ...

    def sleep(self, duration_s: float) -> None:
        ...
