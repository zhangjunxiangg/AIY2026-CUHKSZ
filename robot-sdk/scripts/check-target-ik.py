#!/usr/bin/env python3
"""Scan all practical tool pitches for an absolute Cartesian target."""

import sys

import rospy
from interfaces.srv import SetRobotPose


if len(sys.argv) != 4:
    raise SystemExit("usage: check-target-ik.py X Y Z")

target = [float(value) for value in sys.argv[1:4]]
rospy.init_node("check_target_ik", anonymous=True, disable_signals=True)
rospy.wait_for_service("/kinematics/set_pose_target", timeout=5.0)
solve = rospy.ServiceProxy("/kinematics/set_pose_target", SetRobotPose)

solutions = []
for pitch in range(-90, 91, 5):
    result = solve(target, float(pitch), [float(pitch), float(pitch)], 1.0)
    if result.success and len(result.pulse) == 5:
        pulses = [int(round(value)) for value in result.pulse]
        current = [int(value) for value in result.current_pulse]
        deltas = [value - before for value, before in zip(pulses, current)]
        solutions.append((pitch, pulses, current, deltas))
        print(
            "IK pitch=%d pulses=%s current=%s deltas=%s"
            % (pitch, pulses, current, deltas),
            flush=True,
        )

print("IK_SOLUTION_COUNT=%d" % len(solutions), flush=True)
raise SystemExit(0 if solutions else 2)
