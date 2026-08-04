#!/usr/bin/env python3
"""Minimal, motion-free rospy smoke test."""

import rospy


def main():
    rospy.init_node("ros_python_smoke", anonymous=True, disable_signals=True)
    rospy.loginfo("minimal rospy node started")
    print("ROS_PYTHON_SMOKE_TEST=PASS")


if __name__ == "__main__":
    main()
