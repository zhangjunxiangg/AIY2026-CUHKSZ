#!/usr/bin/env python3
import threading

import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy


class GamepadTeleop:
    def __init__(self):
        self.joy_topic = rospy.get_param("~joy_topic", "/ros_robot_controller/joy")
        self.cmd_vel_topic = rospy.get_param("~cmd_vel_topic", "/cmd_vel")
        self.max_linear = float(rospy.get_param("~max_linear", 0.15))
        self.max_angular = float(rospy.get_param("~max_angular", 0.40))
        self.deadzone = float(rospy.get_param("~deadzone", 0.10))
        self.joy_timeout = float(rospy.get_param("~joy_timeout", 0.50))
        self.enable_button = int(rospy.get_param("~enable_button", -1))
        self.lock = threading.Lock()
        self.last_joy = None
        self.axes = []
        self.buttons = []

        self.pub = rospy.Publisher(self.cmd_vel_topic, Twist, queue_size=1)
        self.sub = rospy.Subscriber(self.joy_topic, Joy, self.joy_callback, queue_size=1)
        self.timer = rospy.Timer(rospy.Duration(0.05), self.publish)
        rospy.on_shutdown(self.stop)
        rospy.loginfo("gamepad teleop ready: %s -> %s", self.joy_topic, self.cmd_vel_topic)

    def joy_callback(self, msg):
        with self.lock:
            self.axes = list(msg.axes)
            self.buttons = list(msg.buttons)
            self.last_joy = rospy.Time.now()

    def axis(self, index):
        value = self.axes[index] if index < len(self.axes) else 0.0
        return 0.0 if abs(value) < self.deadzone else value

    def enabled(self):
        if self.enable_button < 0:
            return True
        return self.enable_button < len(self.buttons) and bool(self.buttons[self.enable_button])

    def publish(self, _event=None):
        msg = Twist()
        with self.lock:
            fresh = self.last_joy is not None and \
                (rospy.Time.now() - self.last_joy).to_sec() <= self.joy_timeout
            if fresh and self.enabled():
                # RRC built-in gamepad mapping: lx=0, ly=1, rx=2.
                msg.linear.x = self.axis(1) * self.max_linear
                msg.linear.y = self.axis(0) * self.max_linear
                msg.angular.z = self.axis(2) * self.max_angular
        self.pub.publish(msg)

    def stop(self):
        for _ in range(3):
            self.pub.publish(Twist())
            rospy.sleep(0.03)


if __name__ == "__main__":
    rospy.init_node("gamepad_teleop")
    GamepadTeleop()
    rospy.spin()
