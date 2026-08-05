#!/usr/bin/env python3
"""Read-only comparison of servo 3 feedback with adjacent bus servos."""

import time

import rospy
from ros_robot_controller.msg import GetBusServoCmd
from ros_robot_controller.srv import GetBusServoState


FIELDS = (
    ("position", "get_position", "position"),
    ("voltage", "get_voltage", "voltage"),
    ("temperature", "get_temperature", "temperature"),
    ("id", "get_id", "present_id"),
)


rospy.init_node("diagnose_servo3_feedback", anonymous=True, disable_signals=True)
rospy.wait_for_service("/ros_robot_controller/bus_servo/get_state", timeout=8.0)
service = rospy.ServiceProxy(
    "/ros_robot_controller/bus_servo/get_state", GetBusServoState
)

for servo_id in (2, 3, 4):
    for label, request_field, response_field in FIELDS:
        samples = []
        for _ in range(3):
            command = GetBusServoCmd(id=servo_id)
            setattr(command, request_field, 1)
            try:
                response = service([command])
                if not response.success or not response.state:
                    samples.append("NO_STATE")
                else:
                    values = list(getattr(response.state[0], response_field))
                    samples.append(str(values[0]) if values else "EMPTY")
            except Exception as error:
                samples.append("ERROR:%s" % type(error).__name__)
            time.sleep(0.12)
        print(
            "SERVO_%d_%s=%s" % (servo_id, label.upper(), ",".join(samples)),
            flush=True,
        )
