import math


def _clamp(value, limit):
    return max(-limit, min(limit, float(value)))


def calculate_wheel_rps(vx, vy, wz, *, wheelbase=0.216, track_width=0.195,
                        wheel_diameter=0.100, max_linear=0.20,
                        max_angular=0.50, max_motor_rps=1.50,
                        deadband=0.001):
    """Convert ROS REP-103 chassis velocity into verified RRC motor order."""
    vx = _clamp(vx, max_linear)
    vy = _clamp(vy, max_linear)
    wz = _clamp(wz, max_angular)
    vx = 0.0 if abs(vx) < deadband else vx
    vy = 0.0 if abs(vy) < deadband else vy
    wz = 0.0 if abs(wz) < deadband else wz

    vp = wz * (wheelbase + track_width) / 2.0
    linear = [vx - vy - vp, vx + vy - vp,
              -vx - vy - vp, -vx + vy - vp]
    rps = [value / (math.pi * wheel_diameter) for value in linear]
    peak = max(abs(value) for value in rps)
    if peak > max_motor_rps:
        scale = max_motor_rps / peak
        rps = [value * scale for value in rps]
    return rps
