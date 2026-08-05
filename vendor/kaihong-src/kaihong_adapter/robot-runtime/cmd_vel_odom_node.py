#!/usr/bin/env python3
"""Open-loop mecanum odometry for the 4.1 host control stack.

The STM32 protocol used by this chassis reports IMU and battery data but does
not expose wheel encoder feedback. This node mirrors the original src1
controller behavior without publishing duplicate motor commands.
"""

import math
import threading

import rospy
import tf2_ros
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry


def yaw_quaternion(yaw):
    half = yaw * 0.5
    return 0.0, 0.0, math.sin(half), math.cos(half)


class CmdVelOdometry:
    def __init__(self):
        self.rate = float(rospy.get_param("~rate", 30.0))
        self.timeout = float(rospy.get_param("~cmd_timeout", 0.5))
        self.linear_factor = float(rospy.get_param("~linear_correction_factor", 1.0))
        self.angular_factor = float(rospy.get_param("~angular_correction_factor", 1.0))
        self.odom_frame = rospy.get_param("~odom_frame", "odom")
        self.base_frame = rospy.get_param("~base_frame", "base_footprint")
        self.cmd_topic = rospy.get_param("~cmd_vel_topic", "/cmd_vel")
        self.odom_topic = rospy.get_param("~odom_topic", "/odom")

        self.lock = threading.Lock()
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.wz = 0.0
        self.last_cmd = None
        self.last_update = rospy.Time.now()

        self.publisher = rospy.Publisher(self.odom_topic, Odometry, queue_size=10)
        self.broadcaster = tf2_ros.TransformBroadcaster()
        self.subscriber = rospy.Subscriber(self.cmd_topic, Twist, self.command, queue_size=1)
        self.timer = rospy.Timer(rospy.Duration(1.0 / self.rate), self.update)
        rospy.logwarn("open-loop odometry enabled: no STM32 encoder feedback is available")

    def command(self, msg):
        with self.lock:
            self.vx = max(-0.2, min(0.2, msg.linear.x))
            self.vy = max(-0.2, min(0.2, msg.linear.y))
            self.wz = max(-0.5, min(0.5, msg.angular.z))
            self.last_cmd = rospy.Time.now()

    def update(self, event):
        now = event.current_real
        dt = max(0.0, (now - self.last_update).to_sec())
        self.last_update = now
        with self.lock:
            stale = self.last_cmd is None or (now - self.last_cmd).to_sec() > self.timeout
            vx, vy, wz = (0.0, 0.0, 0.0) if stale else (self.vx, self.vy, self.wz)
            self.x += self.linear_factor * (math.cos(self.yaw) * vx - math.sin(self.yaw) * vy) * dt
            self.y += self.linear_factor * (math.sin(self.yaw) * vx + math.cos(self.yaw) * vy) * dt
            self.yaw += self.angular_factor * wz * dt
            x, y, yaw = self.x, self.y, self.yaw

        qx, qy, qz, qw = yaw_quaternion(yaw)
        msg = Odometry()
        msg.header.stamp = now
        msg.header.frame_id = self.odom_frame
        msg.child_frame_id = self.base_frame
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.x = qx
        msg.pose.pose.orientation.y = qy
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw
        msg.twist.twist.linear.x = vx
        msg.twist.twist.linear.y = vy
        msg.twist.twist.angular.z = wz
        msg.pose.covariance[0] = 0.02
        msg.pose.covariance[7] = 0.02
        msg.pose.covariance[35] = 0.05
        msg.twist.covariance[0] = 0.03
        msg.twist.covariance[7] = 0.03
        msg.twist.covariance[35] = 0.08
        self.publisher.publish(msg)

        transform = TransformStamped()
        transform.header = msg.header
        transform.child_frame_id = self.base_frame
        transform.transform.translation.x = x
        transform.transform.translation.y = y
        transform.transform.rotation = msg.pose.pose.orientation
        self.broadcaster.sendTransform(transform)


if __name__ == "__main__":
    rospy.init_node("cmd_vel_odom")
    CmdVelOdometry()
    rospy.spin()

