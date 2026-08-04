#!/usr/bin/env python3
"""Print the current arm base-to-gripper pose as machine-readable JSON."""

import json
import math
import sys

import rospy
from interfaces.srv import GetRobotPose


def rotation_matrix(quaternion):
    x, y, z, w = (
        quaternion.x,
        quaternion.y,
        quaternion.z,
        quaternion.w,
    )
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm < 1e-12:
        raise RuntimeError("invalid zero quaternion")
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def main():
    rospy.init_node("student_read_arm_pose", anonymous=True, disable_signals=True)
    rospy.wait_for_service("/kinematics/get_current_pose", timeout=8.0)
    response = rospy.ServiceProxy(
        "/kinematics/get_current_pose", GetRobotPose
    )()
    if not response.success or not response.solution:
        raise RuntimeError("current arm pose unavailable")
    pose = response.pose
    print(
        json.dumps(
            {
                "ok": True,
                "parent_frame": "base_link",
                "child_frame": "gripper_reference",
                "base_to_gripper": {
                    "translation_m": [
                        pose.position.x,
                        pose.position.y,
                        pose.position.z,
                    ],
                    "rotation_matrix": rotation_matrix(pose.orientation),
                    "quaternion_xyzw": [
                        pose.orientation.x,
                        pose.orientation.y,
                        pose.orientation.z,
                        pose.orientation.w,
                    ],
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
