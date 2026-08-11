#!/usr/bin/env python3
# 模拟发布器：把 sample_targets_3d_fused.json 按固定频率发到 /student/perception/targets_3d_fused，
# 让角色 D 在没有相机/板子的情况下也能调试抓取代码。
"""Mock publisher for the fused 3D targets topic.

Usage (on board or any machine with ROS):
    python3 mock_output_publisher.py --ros --file sample_targets_3d_fused.json --rate 2

Without ROS it simply prints the JSON once (useful for checking the file).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_ros(args):
    import rospy
    from std_msgs.msg import String

    payload = Path(args.file).read_text(encoding="utf-8")
    # Validate that it is real JSON before publishing.
    json.loads(payload)

    rospy.init_node("student_mock_output_publisher", anonymous=False)
    pub = rospy.Publisher(args.topic, String, queue_size=1, latch=True)
    rate = rospy.Rate(args.rate)
    rospy.loginfo("[MOCK] publishing %s -> %s at %.1f Hz", args.file, args.topic, args.rate)
    while not rospy.is_shutdown():
        pub.publish(String(data=payload))
        rate.sleep()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ros", action="store_true", help="publish over ROS")
    parser.add_argument("--file", default=str(HERE / "sample_targets_3d_fused.json"),
                        help="JSON file to publish")
    parser.add_argument("--topic", default="/student/perception/targets_3d_fused",
                        help="ROS topic name")
    parser.add_argument("--rate", type=float, default=2.0, help="publish rate (Hz)")
    args = parser.parse_args()

    if args.ros:
        return run_ros(args)

    # No ROS: just print the file so you can eyeball the contract.
    print(Path(args.file).read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
