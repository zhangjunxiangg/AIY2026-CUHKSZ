"""Shared bounded movement and explicit-stop semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .backend import Cancellation, MotionBackend
from .errors import ControlError, ControlFailure, control_error, failure
from .limits import finite_number
from .models import MotionRequest, MotionResult, ZERO_VELOCITY


@dataclass(frozen=True)
class _StopEvidence:
    attempted: bool
    confirmed: bool
    attempts: int
    failures: tuple[str, ...]


class MotionController:
    """One reusable controller for CLI and automatic callers."""

    def __init__(
        self,
        backend: MotionBackend,
        *,
        zero_message_count: int = 3,
        zero_interval_s: float = 0.02,
    ) -> None:
        if zero_message_count < 1:
            raise ValueError("zero_message_count must be positive")
        if zero_interval_s < 0.0:
            raise ValueError("zero_interval_s cannot be negative")
        self.backend = backend
        self.zero_message_count = zero_message_count
        self.zero_interval_s = zero_interval_s

    def status(self) -> MotionResult:
        """Return backend readiness without acquiring or publishing velocity."""

        start_s = self.backend.monotonic()
        error: ControlError | None = None
        data: dict[str, Any] = {}
        try:
            data["status"] = self.backend.status().to_dict()
        except ControlFailure as exc:
            error = exc.error
            data.update(exc.context)
        except Exception as exc:
            error = control_error("BACKEND_FAILURE", "backend status failed: %s" % exc)
        return MotionResult(
            operation="status",
            operation_id=None,
            ok=error is None,
            backend=self.backend.backend_name,
            verification=self.backend.verification_level,
            zero_velocity_attempted=False,
            zero_velocity_confirmed=False,
            elapsed_s=self._elapsed_since(start_s),
            data=data,
            error=error,
        )

    def stop(self) -> MotionResult:
        """Attempt zero velocity without requiring non-zero readiness."""

        start_s = self.backend.monotonic()
        stop = self._attempt_stop()
        error = None
        if not stop.confirmed:
            error = control_error("STOP_FAILED", "explicit zero-velocity sequence was not confirmed")
        data: dict[str, Any] = {"stop_attempts": stop.attempts}
        if stop.failures:
            data["stop_failures"] = list(stop.failures)
        return MotionResult(
            operation="stop",
            operation_id=None,
            ok=error is None,
            backend=self.backend.backend_name,
            verification=self.backend.verification_level,
            zero_velocity_attempted=stop.attempted,
            zero_velocity_confirmed=stop.confirmed,
            elapsed_s=self._elapsed_since(start_s),
            data=data,
            error=error,
        )

    def move(
        self,
        request: MotionRequest,
        cancellation: Cancellation | None = None,
        *,
        timeout_s: float | None = None,
    ) -> MotionResult:
        """Execute one bounded request and actively stop before releasing ownership."""

        start_s = self.backend.monotonic()
        primary_error: ControlError | None = None
        primary_context: dict[str, Any] = {}
        owned = False
        publish_count = 0
        status_data: dict[str, Any] = {}
        stop = _StopEvidence(False, False, 0, ())
        release_error: ControlError | None = None

        try:
            if not isinstance(request, MotionRequest):
                raise failure("INVALID_INPUT", "request must be a MotionRequest")
            timeout = None
            if timeout_s is not None:
                timeout = finite_number(timeout_s, "timeout_s")
                if timeout <= 0.0:
                    raise failure("INVALID_INPUT", "timeout_s must be positive")

            status = self.backend.status()
            status_data = status.to_dict()
            if status.production and status.configuration_kind != "measured":
                raise failure(
                    "PRODUCTION_CONFIG_REQUIRED",
                    "production motion requires measured configuration",
                )
            if not status.ready:
                detail = "; ".join(status.blocking_reasons) or "backend is not ready"
                raise failure("BACKEND_UNAVAILABLE", detail)

            self.backend.acquire(request.operation_id)
            owned = True
            movement_start_s = self.backend.monotonic()
            movement_end_s = movement_start_s + request.duration_s
            deadline_s = None if timeout is None else movement_start_s + timeout
            period_s = 1.0 / request.publish_rate_hz

            while self.backend.monotonic() < movement_end_s:
                now_s = self.backend.monotonic()
                if cancellation is not None and cancellation.is_cancelled():
                    raise failure("CANCELLED", "motion was cancelled")
                if deadline_s is not None and now_s >= deadline_s:
                    raise failure("TIMEOUT", "motion timeout reached")
                self.backend.publish_velocity(request.velocity)
                publish_count += 1
                next_boundary = movement_end_s
                if deadline_s is not None:
                    next_boundary = min(next_boundary, deadline_s)
                sleep_s = min(period_s, max(0.0, next_boundary - self.backend.monotonic()))
                if sleep_s > 0.0:
                    self.backend.sleep(sleep_s)
        except KeyboardInterrupt:
            primary_error = control_error("CANCELLED", "motion was interrupted")
        except ControlFailure as exc:
            primary_error = exc.error
            primary_context.update(exc.context)
        except Exception as exc:  # Backend implementations are an exception boundary.
            primary_error = control_error("BACKEND_FAILURE", "backend operation failed: %s" % exc)
        finally:
            if owned:
                stop = self._attempt_stop()
                try:
                    self.backend.release()
                except Exception as exc:  # Releasing cannot suppress stop evidence.
                    release_error = control_error("BACKEND_FAILURE", "motion release failed: %s" % exc)

        elapsed_s = self._elapsed_since(start_s)
        data: dict[str, Any] = {
            "request": {
                "velocity": request.velocity.to_dict() if isinstance(request, MotionRequest) else None,
                "duration_s": request.duration_s if isinstance(request, MotionRequest) else None,
                "publish_rate_hz": request.publish_rate_hz if isinstance(request, MotionRequest) else None,
            },
            "publish_count": publish_count,
            "stop_attempts": stop.attempts,
            "status": status_data,
        }
        data.update(primary_context)
        if stop.failures:
            data["stop_failures"] = list(stop.failures)

        final_error = primary_error or release_error
        if stop.attempted and not stop.confirmed:
            if final_error is not None:
                data["original_error"] = final_error.to_dict()
            final_error = control_error("STOP_FAILED", "explicit zero-velocity sequence was not confirmed")

        return MotionResult(
            operation="move",
            operation_id=request.operation_id if isinstance(request, MotionRequest) else None,
            ok=final_error is None,
            backend=self.backend.backend_name,
            verification=self.backend.verification_level,
            zero_velocity_attempted=stop.attempted,
            zero_velocity_confirmed=stop.confirmed,
            elapsed_s=elapsed_s,
            data=data,
            error=final_error,
        )

    def _attempt_stop(self) -> _StopEvidence:
        failures: list[str] = []
        for index in range(self.zero_message_count):
            try:
                self.backend.publish_velocity(ZERO_VELOCITY)
            except Exception as exc:
                failures.append("zero message %d: %s" % (index + 1, exc))
            if index + 1 < self.zero_message_count and self.zero_interval_s > 0.0:
                try:
                    self.backend.sleep(self.zero_interval_s)
                except Exception as exc:
                    failures.append("zero interval %d: %s" % (index + 1, exc))
        return _StopEvidence(True, not failures, self.zero_message_count, tuple(failures))

    def _elapsed_since(self, start_s: float) -> float:
        try:
            return max(0.0, self.backend.monotonic() - start_s)
        except Exception:
            return 0.0
