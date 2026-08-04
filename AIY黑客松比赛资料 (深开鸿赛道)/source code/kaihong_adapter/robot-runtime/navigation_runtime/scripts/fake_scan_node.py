#!/usr/bin/env python3
"""Publish a deterministic synthetic scan for offline ROS integration tests."""

import math

import rospy
from sensor_msgs.msg import LaserScan


def main():
    rospy.init_node("fake_scan")
    publisher = rospy.Publisher("/scan", LaserScan, queue_size=1)
    rate = rospy.Rate(8)
    while not rospy.is_shutdown():
        msg = LaserScan()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = "laser"
        msg.angle_min = -math.pi
        msg.angle_max = math.pi
        msg.angle_increment = 2.0 * math.pi / 360.0
        msg.time_increment = 0.0
        msg.scan_time = 0.125
        msg.range_min = 0.12
        msg.range_max = 8.0
        msg.ranges = [2.0] * 360
        msg.intensities = [0.0] * 360
        publisher.publish(msg)
        rate.sleep()


if __name__ == "__main__":
    main()

