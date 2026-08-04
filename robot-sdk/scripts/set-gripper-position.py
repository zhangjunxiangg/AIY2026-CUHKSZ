#!/usr/bin/env python3
"""Set gripper ID10 to a bounded position with real feedback."""

import sys
import time

import rospy
from ros_robot_controller.msg import GetBusServoCmd
from ros_robot_controller.srv import GetBusServoState
from servo_msgs.msg import RawIdPosDur


SERVO_ID = 10
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 300
DURATION = 4.0
if TARGET < 250 or TARGET > 800:
    raise SystemExit("GRIPPER=FAIL TARGET_LIMIT")


def read_position(service):
    command = GetBusServoCmd(id=SERVO_ID, get_position=1)
    for _ in range(8):
        response = service([command])
        if response.state and response.state[0].position:
            value = int(response.state[0].position[0])
            if 0 <= value <= 1000:
                return value
        time.sleep(0.15)
    raise RuntimeError("gripper position unavailable")


rospy.init_node("set_gripper_position", anonymous=True, disable_signals=True)
rospy.wait_for_service("/ros_robot_controller/bus_servo/get_state", timeout=8.0)
service = rospy.ServiceProxy(
    "/ros_robot_controller/bus_servo/get_state", GetBusServoState
)
publisher = rospy.Publisher(
    "/servo_controllers/port_id_1/id_pos_dur", RawIdPosDur, queue_size=1
)
deadline = time.time() + 5.0
while publisher.get_num_connections() < 1 and time.time() < deadline:
    time.sleep(0.1)
if publisher.get_num_connections() < 1:
    raise RuntimeError("gripper command subscriber unavailable")

original = read_position(service)
print("GRIPPER ORIGINAL=%d TARGET=%d" % (original, TARGET), flush=True)
publisher.publish(RawIdPosDur(id=SERVO_ID, position=TARGET, duration=DURATION))
deadline = time.time() + DURATION + 4.0
actual = original
while time.time() < deadline:
    actual = read_position(service)
    if abs(actual - TARGET) <= 10:
        break
    time.sleep(0.25)
passed = abs(actual - TARGET) <= 10
print("GRIPPER=%s ACTUAL=%d" % ("PASS" if passed else "FAIL", actual), flush=True)
sys.exit(0 if passed else 1)
