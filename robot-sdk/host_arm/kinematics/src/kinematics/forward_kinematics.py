#!/usr/bin/env python3
"""OpenHarmony-compatible forward kinematics for the Hiwonder 5-DOF arm.

The vendor image ships this module as a glibc/CPython 3.6 extension.  The
board host uses OpenHarmony and Python 3.12, so the small analytic model is
implemented directly in Python while preserving the original public API.
"""

from __future__ import annotations

from math import cos, sin

from geometry_msgs.msg import Quaternion


_RAD_TO_DEG = 180.0 / 3.141592653589793
_DEG_TO_RAD = 1.0 / _RAD_TO_DEG
_JOINT_LIMIT_TOLERANCE_RAD = 0.5 * _DEG_TO_RAD

_DEFAULT_LINKS = [0.23, 0.13, 0.13, 0.055, 0.117]
_DEFAULT_JOINT_RANGE_DEG = [
    [-120.2, 120.2],
    [-180.2, 0.2],
    [-120.2, 120.2],
    [-200.2, 20.2],
    [-120.2, 120.2],
]


def _quaternion_from_rpy(roll: float, pitch: float, yaw: float) -> Quaternion:
    """Return a ROS quaternion for intrinsic roll/pitch/yaw radians."""

    cr, sr = cos(roll * 0.5), sin(roll * 0.5)
    cp, sp = cos(pitch * 0.5), sin(pitch * 0.5)
    cy, sy = cos(yaw * 0.5), sin(yaw * 0.5)
    quaternion = Quaternion()
    quaternion.x = sr * cp * cy - cr * sp * sy
    quaternion.y = cr * sp * cy + sr * cp * sy
    quaternion.z = cr * cp * sy - sr * sp * cy
    quaternion.w = cr * cp * cy + sr * sp * sy
    return quaternion


class ForwardKinematics:
    """Drop-in replacement for the vendor ``ForwardKinematics`` extension."""

    def __init__(self, debug: bool = False):
        self.debug = bool(debug)
        self._links = list(_DEFAULT_LINKS)
        self._joint_range_deg = [list(item) for item in _DEFAULT_JOINT_RANGE_DEG]

    def set_link(
        self,
        base_link: float,
        link1: float,
        link2: float,
        link3: float,
        end_effector_link: float,
    ):
        values = [
            float(base_link),
            float(link1),
            float(link2),
            float(link3),
            float(end_effector_link),
        ]
        if any(value <= 0.0 for value in values):
            return False
        self._links = values
        return True

    def get_link(self):
        return list(self._links)

    def set_joint_range(self, *args):
        """Set five joint ranges and preserve the vendor ``unit`` argument."""

        if len(args) not in (5, 6):
            return False
        unit = args[5] if len(args) == 6 else "rad"
        ranges = args[:5]
        factor = _RAD_TO_DEG if unit == "rad" else 1.0
        converted = []
        for item in ranges:
            if len(item) != 2 or float(item[0]) > float(item[1]):
                return False
            converted.append([float(item[0]) * factor, float(item[1]) * factor])
        self._joint_range_deg = converted
        return True

    def get_joint_range(self, unit: str = "rad"):
        factor = _DEG_TO_RAD if unit == "rad" else 1.0
        return [
            [limits[0] * factor, limits[1] * factor]
            for limits in self._joint_range_deg
        ]

    def get_fk(self, joint_values):
        if len(joint_values) != 5:
            return []
        joints = []
        for raw_value, limits in zip(
            [float(value) for value in joint_values],
            self.get_joint_range("rad"),
        ):
            # Servo feedback is integer pulse data. At a configured endpoint,
            # pulse rounding can place the converted angle a few tenths of a
            # degree outside the nominal range (for example ID4 pulse 40 gives
            # 20.4 degrees for a 20.2-degree endpoint). Accept only this small
            # quantization margin and clamp it to the declared limit.
            if (
                raw_value < limits[0] - _JOINT_LIMIT_TOLERANCE_RAD
                or raw_value > limits[1] + _JOINT_LIMIT_TOLERANCE_RAD
            ):
                return []
            joints.append(min(max(raw_value, limits[0]), limits[1]))

        q1, q2, q3, q4, q5 = joints
        base_link, link1, link2, link3, tool_link = self._links
        tool_length = link3 + tool_link

        shoulder_angle = -q2
        elbow_angle = -(q2 + q3)
        tool_angle = -(q2 + q3 + q4) - 0.5 * 3.141592653589793

        radial = (
            link1 * cos(shoulder_angle)
            + link2 * cos(elbow_angle)
            + tool_length * cos(tool_angle)
        )
        z = (
            base_link
            + link1 * sin(shoulder_angle)
            + link2 * sin(elbow_angle)
            + tool_length * sin(tool_angle)
        )
        position = [radial * cos(q1), radial * sin(q1), z]

        pitch = q2 + q3 + q4 + 0.5 * 3.141592653589793
        orientation = _quaternion_from_rpy(q5, pitch, q1)
        if self.debug:
            print("fk position:", position)
        return [position, orientation]
