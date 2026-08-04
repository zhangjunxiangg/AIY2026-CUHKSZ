"""Deterministic in-memory backend for offline control verification."""

from __future__ import annotations

from typing import Iterable

from .errors import failure
from .models import BackendEvent, BackendStatus, Velocity, VerificationLevel


class FakeBackend:
    """A virtual backend with ordered events and no external I/O."""

    def __init__(
        self,
        *,
        ready: bool = True,
        production: bool = False,
        configuration_kind: str = "synthetic",
        blocking_reasons: Iterable[str] = (),
        fail_status: bool = False,
        fail_acquire: bool = False,
        fail_nonzero_at: int | None = None,
        fail_zero: bool = False,
    ) -> None:
        self._ready = ready
        self._production = production
        self._configuration_kind = configuration_kind
        reasons = tuple(blocking_reasons)
        self._blocking_reasons = reasons or (() if ready else ("backend not ready",))
        self._fail_status = fail_status
        self._fail_acquire = fail_acquire
        self._fail_nonzero_at = fail_nonzero_at
        self._fail_zero = fail_zero
        self._time_s = 0.0
        self._events: list[BackendEvent] = []
        self._owned = False
        self._owner: str | None = None
        self._nonzero_attempts = 0

    @property
    def backend_name(self) -> str:
        return "fake"

    @property
    def verification_level(self) -> VerificationLevel:
        return VerificationLevel.OFFLINE_VERIFIED

    @property
    def events(self) -> tuple[BackendEvent, ...]:
        return tuple(self._events)

    @property
    def velocity_events(self) -> tuple[BackendEvent, ...]:
        return tuple(event for event in self._events if event.kind == "velocity")

    @property
    def nonzero_events(self) -> tuple[BackendEvent, ...]:
        return tuple(
            event
            for event in self.velocity_events
            if event.velocity is not None and not event.velocity.is_zero and event.metadata.get("accepted") is True
        )

    @property
    def zero_events(self) -> tuple[BackendEvent, ...]:
        return tuple(
            event
            for event in self.velocity_events
            if event.velocity is not None and event.velocity.is_zero and event.metadata.get("accepted") is True
        )

    @property
    def owned(self) -> bool:
        return self._owned

    def _record(
        self,
        kind: str,
        *,
        velocity: Velocity | None = None,
        metadata: dict[str, object] | None = None,
    ) -> BackendEvent:
        event = BackendEvent(
            sequence=len(self._events) + 1,
            kind=kind,
            at_s=self._time_s,
            velocity=velocity,
            metadata=metadata or {},
        )
        self._events.append(event)
        return event

    def status(self) -> BackendStatus:
        self._record("status", metadata={"accepted": not self._fail_status})
        if self._fail_status:
            raise failure("BACKEND_FAILURE", "fake status failure")
        return BackendStatus(
            ready=self._ready,
            backend=self.backend_name,
            production=self._production,
            configuration_kind=self._configuration_kind,
            blocking_reasons=self._blocking_reasons,
            details={"clock": "virtual", "owned": self._owned, "owner": self._owner},
        )

    def acquire(self, operation_id: str) -> None:
        accepted = not self._owned and not self._fail_acquire
        self._record("acquire", metadata={"operation_id": operation_id, "accepted": accepted})
        if self._owned:
            raise failure("MOTION_BUSY", "motion is already owned", owner=self._owner)
        if self._fail_acquire:
            raise failure("BACKEND_FAILURE", "fake ownership failure")
        self._owned = True
        self._owner = operation_id

    def release(self) -> None:
        if not self._owned:
            return
        self._record("release", metadata={"operation_id": self._owner})
        self._owned = False
        self._owner = None

    def publish_velocity(self, velocity: Velocity) -> None:
        if not isinstance(velocity, Velocity):
            raise failure("INVALID_INPUT", "backend velocity must be a Velocity")
        should_fail = self._fail_zero and velocity.is_zero
        if not velocity.is_zero:
            self._nonzero_attempts += 1
            should_fail = should_fail or self._fail_nonzero_at == self._nonzero_attempts
        self._record("velocity", velocity=velocity, metadata={"accepted": not should_fail})
        if should_fail:
            raise failure("BACKEND_FAILURE", "fake velocity publish failure")

    def monotonic(self) -> float:
        return self._time_s

    def sleep(self, duration_s: float) -> None:
        duration = float(duration_s)
        if duration < 0.0:
            raise ValueError("Fake sleep duration cannot be negative")
        self._record("sleep", metadata={"duration_s": duration})
        self._time_s += duration
