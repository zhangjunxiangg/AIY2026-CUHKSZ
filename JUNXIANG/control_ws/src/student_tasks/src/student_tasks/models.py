"""Immutable versioned domain values for robot motion control."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .errors import ControlError, failure
from .limits import (
    validate_duration,
    validate_operation_id,
    validate_publish_rate,
    validate_velocity_components,
)


RESULT_SCHEMA = "robot-control/v1"


class VerificationLevel(str, Enum):
    OFFLINE_VERIFIED = "OFFLINE_VERIFIED"
    SOURCE_VERIFIED_HIL_PENDING = "SOURCE_VERIFIED_HIL_PENDING"
    HIL_VERIFIED = "HIL_VERIFIED"


@dataclass(frozen=True)
class Velocity:
    """Velocity in base_link coordinates: x forward, y left, z counterclockwise."""

    linear_x: float
    linear_y: float
    angular_z: float

    def __post_init__(self) -> None:
        x, y, az = validate_velocity_components(self.linear_x, self.linear_y, self.angular_z)
        object.__setattr__(self, "linear_x", x)
        object.__setattr__(self, "linear_y", y)
        object.__setattr__(self, "angular_z", az)

    @property
    def is_zero(self) -> bool:
        return self.linear_x == 0.0 and self.linear_y == 0.0 and self.angular_z == 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "linear_x": self.linear_x,
            "linear_y": self.linear_y,
            "angular_z": self.angular_z,
        }


ZERO_VELOCITY = Velocity(0.0, 0.0, 0.0)


@dataclass(frozen=True)
class MotionRequest:
    operation_id: str
    velocity: Velocity
    duration_s: float
    publish_rate_hz: float = 20.0

    def __post_init__(self) -> None:
        if not isinstance(self.velocity, Velocity):
            raise failure("INVALID_INPUT", "velocity must be a Velocity value")
        object.__setattr__(self, "operation_id", validate_operation_id(self.operation_id))
        object.__setattr__(self, "duration_s", validate_duration(self.duration_s))
        object.__setattr__(self, "publish_rate_hz", validate_publish_rate(self.publish_rate_hz))


@dataclass(frozen=True)
class BackendStatus:
    ready: bool
    backend: str
    production: bool
    configuration_kind: str
    blocking_reasons: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.ready, bool) or not isinstance(self.production, bool):
            raise ValueError("Status booleans must be bool")
        if not isinstance(self.backend, str) or not self.backend:
            raise ValueError("Backend identity must be non-empty")
        if self.configuration_kind not in {"synthetic", "measured", "missing"}:
            raise ValueError("Unknown configuration kind")
        reasons = tuple(dict.fromkeys(self.blocking_reasons))
        if any(not isinstance(reason, str) or not reason for reason in reasons):
            raise ValueError("Blocking reasons must be non-empty strings")
        object.__setattr__(self, "blocking_reasons", reasons)
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "backend": self.backend,
            "production": self.production,
            "configuration_kind": self.configuration_kind,
            "blocking_reasons": list(self.blocking_reasons),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class MotionResult:
    operation: str
    operation_id: str | None
    ok: bool
    backend: str
    verification: VerificationLevel
    zero_velocity_attempted: bool
    zero_velocity_confirmed: bool
    elapsed_s: float
    data: Mapping[str, Any] = field(default_factory=dict)
    error: ControlError | None = None
    schema: str = RESULT_SCHEMA

    def __post_init__(self) -> None:
        if self.operation not in {"status", "move", "stop"}:
            raise ValueError("Unknown motion operation")
        if self.operation_id is not None:
            object.__setattr__(self, "operation_id", validate_operation_id(self.operation_id))
        if not isinstance(self.ok, bool):
            raise ValueError("ok must be bool")
        if not self.backend:
            raise ValueError("backend must be non-empty")
        if not isinstance(self.verification, VerificationLevel):
            raise ValueError("verification must be a VerificationLevel")
        elapsed = float(self.elapsed_s)
        if elapsed < 0.0:
            raise ValueError("elapsed_s cannot be negative")
        object.__setattr__(self, "elapsed_s", elapsed)
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))
        if self.ok and self.error is not None:
            raise ValueError("Successful result cannot contain an error")
        if not self.ok and self.error is None:
            raise ValueError("Failed result requires an error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "operation": self.operation,
            "operation_id": self.operation_id,
            "ok": self.ok,
            "backend": self.backend,
            "verification": self.verification.value,
            "zero_velocity_attempted": self.zero_velocity_attempted,
            "zero_velocity_confirmed": self.zero_velocity_confirmed,
            "elapsed_s": self.elapsed_s,
            "data": dict(self.data),
            "error": None if self.error is None else self.error.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class BackendEvent:
    sequence: int
    kind: str
    at_s: float
    velocity: Velocity | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("Event sequence starts at one")
        if self.kind not in {"acquire", "velocity", "release", "status", "sleep"}:
            raise ValueError("Unknown backend event kind")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "kind": self.kind,
            "at_s": self.at_s,
            "velocity": None if self.velocity is None else self.velocity.to_dict(),
            "metadata": dict(self.metadata),
        }
