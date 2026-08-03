#!/usr/bin/env python3
import math
import rospy
import tf2_ros

rospy.init_node("capture_slam_pose", anonymous=True, disable_signals=True)
buffer = tf2_ros.Buffer(cache_time=rospy.Duration(10.0))
listener = tf2_ros.TransformListener(buffer)
transform = buffer.lookup_transform("map", "base_footprint", rospy.Time(0), rospy.Duration(8.0))
t = transform.transform.translation
q = transform.transform.rotation
yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
print("SLAM_POSE x=%.9f y=%.9f yaw=%.9f qz=%.9f qw=%.9f" % (t.x, t.y, yaw, q.z, q.w))
