#!/usr/bin/env python3
"""OpenHarmony-compatible analytic IK for the Hiwonder 5-DOF arm."""

from __future__ import annotations

from math import acos, atan2, cos, degrees, hypot, pi, radians, sin


_links = [0.23, 0.13, 0.13, 0.055, 0.117]
_joint_range_deg = [
    [-120.2, 120.2],
    [-180.2, 0.2],
    [-120.2, 120.2],
    [-200.2, 20.2],
    [-120.2, 120.2],
]


def set_link(
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
    _links[:] = values
    return True


def get_link():
    return list(_links)


def set_joint_range(*args):
    if len(args) not in (5, 6):
        return False
    unit = args[5] if len(args) == 6 else "rad"
    factor = 180.0 / pi if unit == "rad" else 1.0
    converted = []
    for item in args[:5]:
        if len(item) != 2 or float(item[0]) > float(item[1]):
            return False
        converted.append([float(item[0]) * factor, float(item[1]) * factor])
    _joint_range_deg[:] = converted
    return True


def get_joint_range(unit: str = "rad"):
    factor = pi / 180.0 if unit == "rad" else 1.0
    return [
        [limits[0] * factor, limits[1] * factor]
        for limits in _joint_range_deg
    ]


def _within_joint_ranges(solution):
    return all(
        limits[0] - 1e-8 <= value <= limits[1] + 1e-8
        for value, limits in zip(solution, get_joint_range("rad"))
    )


def _solve_position_pitch(position, pitch_deg: float, wrist_roll_deg: float = 0.0):
    if len(position) != 3:
        return []
    x, y, z = [float(value) for value in position]
    base_link, link1, link2, link3, tool_link = _links
    tool_length = link3 + tool_link

    radial = hypot(x, y)
    yaw = atan2(y, x)
    pitch = radians(float(pitch_deg))

    # The tool axis in the radial/z plane is the negative requested pitch.
    wrist_r = radial - tool_length * cos(pitch)
    wrist_z = z - base_link + tool_length * sin(pitch)

    denominator = 2.0 * link1 * link2
    if denominator <= 0.0:
        return []
    cosine_delta = (
        wrist_r * wrist_r
        + wrist_z * wrist_z
        - link1 * link1
        - link2 * link2
    ) / denominator
    if cosine_delta < -1.0 - 1e-9 or cosine_delta > 1.0 + 1e-9:
        return []
    cosine_delta = min(1.0, max(-1.0, cosine_delta))
    delta = acos(cosine_delta)

    solutions = []
    # Positive q3 first matches the original extension's solution ordering.
    for q3 in (delta, -delta):
        elbow_delta = -q3
        shoulder_angle = atan2(wrist_z, wrist_r) - atan2(
            link2 * sin(elbow_delta),
            link1 + link2 * cos(elbow_delta),
        )
        q2 = -shoulder_angle
        q4 = pitch - 0.5 * pi - q2 - q3
        solution = [yaw, q2, q3, q4, radians(float(wrist_roll_deg))]
        if _within_joint_ranges(solution):
            solutions.append(solution)
    return solutions


def get_position_ik(x, y, z, roll, pitch, yaw):
    """Return exact-pitch solutions using the vendor extension's API shape."""

    position_yaw = degrees(atan2(float(y), float(x)))
    if abs(((position_yaw - float(yaw) + 180.0) % 360.0) - 180.0) > 1.0:
        return []
    return _solve_position_pitch([x, y, z], float(pitch), float(roll))


def _pitch_candidates(requested, minimum, maximum, resolution):
    requested = min(max(float(requested), minimum), maximum)
    yield requested
    step = 1
    while True:
        emitted = False
        lower = requested - step * resolution
        upper = requested + step * resolution
        if lower >= minimum - 1e-9:
            emitted = True
            yield lower
        if upper <= maximum + 1e-9:
            emitted = True
            yield upper
        if not emitted:
            return
        step += 1


def get_ik(position, pitch, pitch_range=(-180.0, 180.0), resolution=1.0):
    if len(pitch_range) != 2:
        return []
    minimum, maximum = sorted(float(value) for value in pitch_range)
    resolution = abs(float(resolution))
    if resolution <= 0.0:
        resolution = 1.0

    yaw_deg = degrees(atan2(float(position[1]), float(position[0])))
    for candidate_pitch in _pitch_candidates(
        float(pitch), minimum, maximum, resolution
    ):
        solutions = _solve_position_pitch(position, candidate_pitch, 0.0)
        if solutions:
            return [[solutions, [0.0, candidate_pitch, yaw_deg]]]
    return []

