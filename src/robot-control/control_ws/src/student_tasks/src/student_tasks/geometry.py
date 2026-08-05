"""Small ROS-free geometry helpers using base_link SI conventions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a number" % field)
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError("%s must be finite" % field)
    return normalized


@dataclass(frozen=True)
class Vector3:
    """Three-dimensional vector in the caller's documented frame."""

    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))
        object.__setattr__(self, "z", _finite(self.z, "z"))

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class CameraIntrinsics:
    """Pinhole intrinsics in pixels."""

    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    def __post_init__(self) -> None:
        for name in ("fx", "fy", "cx", "cy"):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if self.fx <= 0.0 or self.fy <= 0.0:
            raise ValueError("Focal lengths must be positive")
        if isinstance(self.width, bool) or not isinstance(self.width, int) or self.width <= 0:
            raise ValueError("Image width must be a positive integer")
        if isinstance(self.height, bool) or not isinstance(self.height, int) or self.height <= 0:
            raise ValueError("Image height must be a positive integer")


@dataclass(frozen=True)
class RigidTransform:
    """Right-handed rigid transform with row-major 3x3 rotation."""

    rotation: tuple[float, ...]
    translation: Vector3

    def __post_init__(self) -> None:
        if not isinstance(self.translation, Vector3):
            raise ValueError("translation must be Vector3")
        try:
            rotation = tuple(_finite(value, "rotation") for value in self.rotation)
        except TypeError as exc:
            raise ValueError("rotation must be an iterable") from exc
        if len(rotation) != 9:
            raise ValueError("rotation must contain nine row-major values")
        object.__setattr__(self, "rotation", rotation)

        rows = (rotation[0:3], rotation[3:6], rotation[6:9])
        for index, row in enumerate(rows):
            if not math.isclose(_dot(row, row), 1.0, abs_tol=1e-6):
                raise ValueError("rotation row %d is not unit length" % index)
        for first, second in ((0, 1), (0, 2), (1, 2)):
            if not math.isclose(_dot(rows[first], rows[second]), 0.0, abs_tol=1e-6):
                raise ValueError("rotation rows are not orthogonal")
        if not math.isclose(self.determinant, 1.0, abs_tol=1e-6):
            raise ValueError("rotation determinant must be +1")

    @property
    def determinant(self) -> float:
        r = self.rotation
        return (
            r[0] * (r[4] * r[8] - r[5] * r[7])
            - r[1] * (r[3] * r[8] - r[5] * r[6])
            + r[2] * (r[3] * r[7] - r[4] * r[6])
        )

    def apply(self, point: Vector3) -> Vector3:
        if not isinstance(point, Vector3):
            raise ValueError("point must be Vector3")
        r = self.rotation
        return Vector3(
            r[0] * point.x + r[1] * point.y + r[2] * point.z + self.translation.x,
            r[3] * point.x + r[4] * point.y + r[5] * point.z + self.translation.y,
            r[6] * point.x + r[7] * point.y + r[8] * point.z + self.translation.z,
        )


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(left * right for left, right in zip(first, second))


def unproject_pixel(u: object, v: object, depth_m: object, intrinsics: CameraIntrinsics) -> Vector3:
    """Return camera optical coordinates: x right, y down, z forward."""

    if not isinstance(intrinsics, CameraIntrinsics):
        raise ValueError("intrinsics must be CameraIntrinsics")
    pixel_u = _finite(u, "u")
    pixel_v = _finite(v, "v")
    depth = _finite(depth_m, "depth_m")
    if not 0.0 <= pixel_u < intrinsics.width or not 0.0 <= pixel_v < intrinsics.height:
        raise ValueError("pixel lies outside the calibrated image")
    if depth <= 0.0:
        raise ValueError("depth_m must be positive")
    return Vector3(
        (pixel_u - intrinsics.cx) * depth / intrinsics.fx,
        (pixel_v - intrinsics.cy) * depth / intrinsics.fy,
        depth,
    )


def base_planar_geometry(point: Vector3) -> tuple[float, float]:
    """Return planar distance and bearing; base_link z is height only."""

    if not isinstance(point, Vector3):
        raise ValueError("point must be Vector3")
    return math.hypot(point.x, point.y), math.atan2(point.y, point.x)
