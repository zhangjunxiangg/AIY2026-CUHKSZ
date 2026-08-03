#!/usr/bin/env python3
import threading

import rospy
from geometry_msgs.msg import Twist
from ros_robot_controller.msg import MotorState, MotorsState
from chassis_controller.kinematics import calculate_wheel_rps


class ChassisController:
    def __init__(self):
        self.wheelbase = float(rospy.get_param("~wheelbase", 0.216))
        self.track_width = float(rospy.get_param("~track_width", 0.195))
        self.wheel_diameter = float(rospy.get_param("~wheel_diameter", 0.100))
        self.max_linear = float(rospy.get_param("~max_linear", 0.20))
        self.max_angular = float(rospy.get_param("~max_angular", 0.50))
        self.max_motor_rps = float(rospy.get_param("~max_motor_rps", 1.50))
        self.cmd_timeout = float(rospy.get_param("~cmd_timeout", 0.50))
        self.publish_rate = float(rospy.get_param("~publish_rate", 20.0))
        self.deadband = float(rospy.get_param("~deadband", 0.001))

        self.lock = threading.Lock()
        self.last_cmd_time = None
        self.target = [0.0, 0.0, 0.0, 0.0]
        self.timed_out = True

        motor_topic = rospy.get_param("~motor_topic", "/ros_robot_controller/set_motor")
        cmd_vel_topic = rospy.get_param("~cmd_vel_topic", "/cmd_vel")
        self.motor_pub = rospy.Publisher(motor_topic, MotorsState, queue_size=1)
        self.cmd_sub = rospy.Subscriber(cmd_vel_topic, Twist, self.cmd_vel_callback, queue_size=1)
        self.timer = rospy.Timer(rospy.Duration(1.0 / self.publish_rate), self.publish)
        rospy.on_shutdown(self.shutdown)
        rospy.loginfo("chassis_controller ready: %s -> %s", cmd_vel_topic, motor_topic)

    def cmd_vel_callback(self, msg):
        rps = calculate_wheel_rps(
            msg.linear.x, msg.linear.y, msg.angular.z,
            wheelbase=self.wheelbase, track_width=self.track_width,
            wheel_diameter=self.wheel_diameter,
            max_linear=self.max_linear, max_angular=self.max_angular,
            max_motor_rps=self.max_motor_rps, deadband=self.deadband,
        )

        with self.lock:
            self.target = rps
            self.last_cmd_time = rospy.Time.now()
            self.timed_out = False

    @staticmethod
    def make_message(values):
        msg = MotorsState()
        for motor_id, rps in enumerate(values, 1):
            state = MotorState()
            state.id = motor_id
            state.rps = rps
            msg.data.append(state)
        return msg

    def publish(self, _event=None):
        now = rospy.Time.now()
        with self.lock:
            stale = self.last_cmd_time is None or (now - self.last_cmd_time).to_sec() > self.cmd_timeout
            values = [0.0] * 4 if stale else list(self.target)
            should_warn = stale and not self.timed_out
            self.timed_out = stale
        self.motor_pub.publish(self.make_message(values))
        if should_warn:
            rospy.logwarn("cmd_vel timeout; motors stopped")

    def shutdown(self):
        zero = self.make_message([0.0] * 4)
        for _ in range(3):
            self.motor_pub.publish(zero)
            rospy.sleep(0.03)


if __name__ == "__main__":
    rospy.init_node("chassis_controller")
    ChassisController()
    rospy.spin()
