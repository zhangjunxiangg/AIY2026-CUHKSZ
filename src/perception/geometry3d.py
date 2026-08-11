# 纯几何换算库：像素+深度 -> 相机坐标 -> base_link / map。不依赖 ROS，本机可测。
"""3D geometry helpers for perception.

Conventions:
- Camera optical frame: z forward, x right, y down (ROS standard).
- Depth values are in millimetres; all 3D points are in metres.
- `CameraExtrinsics` stores the transform **base_link -> camera_optical_frame**
  (same convention as the official astra-to-base.json). Use `camera_to_base()`
  to project a camera-frame point into base_link.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class CameraIntrinsics:
    """Pinhole camera intrinsics."""
    fx: float
    fy: float
    cx: float
    cy: float
    width: int = 0
    height: int = 0

    @classmethod
    def from_camera_info(cls, msg) -> "CameraIntrinsics":
        """Build from sensor_msgs/CameraInfo."""
        k = msg.K  # row-major 3x3
        return cls(fx=k[0], fy=k[4], cx=k[2], cy=k[5], width=msg.width, height=msg.height)

    @classmethod
    def from_dict(cls, d: dict) -> "CameraIntrinsics":
        return cls(
            fx=float(d["fx"]),
            fy=float(d["fy"]),
            cx=float(d["cx"]),
            cy=float(d["cy"]),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
        )

    def pixel_to_camera(self, u: float, v: float, depth_m: float) -> np.ndarray:
        """Project a pixel + depth (m) into the camera optical frame."""
        z = float(depth_m)
        x = (float(u) - self.cx) * z / self.fx
        y = (float(v) - self.cy) * z / self.fy
        return np.array([x, y, z], dtype=float)

    def mono_depth_from_bbox(
        self,
        bbox: list,
        real_width_m: float | None = None,
        real_height_m: float | None = None,
    ) -> float | None:
        """Estimate depth (m) from a bbox and known object real size.

        Uses width and height independently and averages the valid estimates.
        Returns None if no estimate is possible.
        """
        _, _, w_px, h_px = bbox
        estimates = []
        if real_width_m and w_px > 0:
            estimates.append(self.fx * float(real_width_m) / float(w_px))
        if real_height_m and h_px > 0:
            estimates.append(self.fy * float(real_height_m) / float(h_px))
        if not estimates:
            return None
        return float(sum(estimates) / len(estimates))


@dataclass
class CameraExtrinsics:
    """Transform base_link -> camera_optical_frame."""
    translation_m: np.ndarray  # shape (3,)
    rotation_matrix: np.ndarray  # shape (3,3)

    @classmethod
    def from_dict(cls, d: dict) -> "CameraExtrinsics":
        t = np.array(d["translation_m"], dtype=float)
        r = np.array(d["rotation_matrix"], dtype=float)
        return cls(translation_m=t, rotation_matrix=r)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "CameraExtrinsics":
        """Load the official calibration JSON format (e.g. astra-to-base.json)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data["base_to_camera"])

    def base_to_camera(self, point_base: np.ndarray) -> np.ndarray:
        """Apply base_link -> camera."""
        return self.rotation_matrix @ point_base + self.translation_m

    def camera_to_base(self, point_camera: np.ndarray) -> np.ndarray:
        """Apply camera -> base_link (inverse transform)."""
        return self.rotation_matrix.T @ (point_camera - self.translation_m)


def quaternion_to_rotation_matrix(x: float, y: float, z: float, w: float) -> np.ndarray:
    """Convert quaternion (xyzw) to a 3x3 rotation matrix."""
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0:
        raise ValueError("zero-length quaternion")
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=float)


def transform_point_with_tf(tf_msg, point: np.ndarray) -> np.ndarray:
    """Apply a geometry_msgs/TransformStamped to a 3D point.

    `point` is in the child frame; the result is in the parent frame.
    """
    t = tf_msg.transform.translation
    q = tf_msg.transform.rotation
    rot = quaternion_to_rotation_matrix(q.x, q.y, q.z, q.w)
    return rot @ point + np.array([t.x, t.y, t.z], dtype=float)


def transform_point_with_matrix(translation_m: list, quaternion_xyzw: list, point: np.ndarray) -> np.ndarray:
    """Pure-Python version of transform_point_with_tf for offline tests."""
    rot = quaternion_to_rotation_matrix(*quaternion_xyzw)
    return rot @ point + np.array(translation_m, dtype=float)
