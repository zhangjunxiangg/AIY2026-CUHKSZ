"""Constitutional motion limits and deterministic validation helpers."""

from __future__ import annotations

import math
from typing import Any

from .errors import failure


MAX_LINEAR_SPEED_M_S = 0.20
MAX_ANGULAR_SPEED_RAD_S = 0.50
MIN_DURATION_S = 0.10
MAX_DURATION_S = 10.0
MIN_PUBLISH_RATE_HZ = 2.0
MAX_PUBLISH_RATE_HZ = 50.0
MAX_OPERATION_ID_LENGTH = 128


def finite_number(value: Any, field: str) -> float:
    """Return a finite float while rejecting booleans and coercive strings."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise failure("INVALID_INPUT", "%s must be a finite number" % field)
    normalized = float(value)
    if not math.isfinite(normalized):
        raise failure("INVALID_INPUT", "%s must be a finite number" % field)
    return 0.0 if normalized == 0.0 else normalized


def validate_velocity_components(linear_x: Any, linear_y: Any, angular_z: Any) -> tuple[float, float, float]:
    """Validate base-frame planar velocity against hard magnitude limits."""

    x = finite_number(linear_x, "linear_x")
    y = finite_number(linear_y, "linear_y")
    az = finite_number(angular_z, "angular_z")
    magnitude = math.hypot(x, y)
    if magnitude > MAX_LINEAR_SPEED_M_S:
        raise failure(
            "LIMIT_EXCEEDED",
            "planar linear speed %.6f exceeds %.2f m/s" % (magnitude, MAX_LINEAR_SPEED_M_S),
            planar_speed=magnitude,
        )
    if abs(az) > MAX_ANGULAR_SPEED_RAD_S:
        raise failure(
            "LIMIT_EXCEEDED",
            "angular speed %.6f exceeds %.2f rad/s" % (abs(az), MAX_ANGULAR_SPEED_RAD_S),
            angular_speed=abs(az),
        )
    return x, y, az


def validate_duration(value: Any) -> float:
    duration = finite_number(value, "duration_s")
    if duration < MIN_DURATION_S or duration > MAX_DURATION_S:
        raise failure(
            "LIMIT_EXCEEDED",
            "duration must be within %.1f..%.1f s" % (MIN_DURATION_S, MAX_DURATION_S),
        )
    return duration


def validate_publish_rate(value: Any) -> float:
    rate = finite_number(value, "publish_rate_hz")
    if rate < MIN_PUBLISH_RATE_HZ or rate > MAX_PUBLISH_RATE_HZ:
        raise failure(
            "LIMIT_EXCEEDED",
            "publish rate must be within %.1f..%.1f Hz" % (MIN_PUBLISH_RATE_HZ, MAX_PUBLISH_RATE_HZ),
        )
    return rate


def validate_operation_id(value: Any) -> str:
    if not isinstance(value, str):
        raise failure("INVALID_INPUT", "operation_id must be a string")
    normalized = value.strip()
    if not normalized:
        raise failure("INVALID_INPUT", "operation_id must be non-empty")
    if len(normalized) > MAX_OPERATION_ID_LENGTH:
        raise failure("INVALID_INPUT", "operation_id exceeds 128 characters")
    return normalized
