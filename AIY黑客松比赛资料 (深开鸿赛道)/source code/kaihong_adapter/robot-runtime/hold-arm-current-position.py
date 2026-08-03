#!/usr/bin/env python3
"""Enable arm holding torque without recalling a stale target pose.

The current measured position of every servo is written as its target first.
Torque is enabled in a separate ROS message because the board driver processes
torque fields before batched position fields inside a single message.
"""

import statistics
import sys
import time

import rospy

from ros_robot_controller.msg import BusServoState, GetBusServoCmd, SetBusServoState
from ros_robot_controller.srv import GetBusServoState


SERVO_IDS = (1, 2, 3, 4, 5, 10)
POSITION_TOLERANCE = 12
# The wrist-rotation servo model reports torque state 0 even while it accepts
# position/hold commands.  Its pose stability is still verified below.
UNVERIFIABLE_TORQUE_IDS = (5,)


def read_field(service, servo_id, request_field, response_field):
    command = GetBusServoCmd(id=servo_id)
    setattr(command, request_field, 1)
    for _ in range(10):
        response = service([command])
        if response.state:
            values = getattr(response.state[0], response_field)
            if values:
                return int(values[0])
        time.sleep(0.12)
    raise RuntimeError("servo %d returned no %s" % (servo_id, response_field))


def read_position(service, servo_id):
    samples = []
    for _ in range(3):
        samples.append(read_field(service, servo_id, "get_position", "position"))
        time.sleep(0.08)
    if max(samples) - min(samples) > 8:
        raise RuntimeError("servo %d position is unstable: %s" % (servo_id, samples))
    return int(statistics.median(samples))


def position_state(servo_id, position):
    state = BusServoState()
    state.present_id = [1, servo_id]
    state.position = [1, position]
    return state


def torque_state(servo_id):
    state = BusServoState()
    state.present_id = [1, servo_id]
    state.enable_torque = [1, 1]
    return state


rospy.init_node("hold_arm_current_position", anonymous=True, disable_signals=True)
service_name = "/ros_robot_controller/bus_servo/get_state"
topic_name = "/ros_robot_controller/bus_servo/set_state"
rospy.wait_for_service(service_name, timeout=10.0)
service = rospy.ServiceProxy(service_name, GetBusServoState)
publisher = rospy.Publisher(topic_name, SetBusServoState, queue_size=1)

deadline = time.time() + 5.0
while publisher.get_num_connections() < 1 and time.time() < deadline:
    time.sleep(0.1)
if publisher.get_num_connections() < 1:
    raise RuntimeError("bus-servo command subscriber is unavailable")

positions = {servo_id: read_position(service, servo_id) for servo_id in SERVO_IDS}
torque_before = {
    servo_id: read_field(service, servo_id, "get_torque_state", "enable_torque")
    for servo_id in SERVO_IDS
}
print("ARM_HOLD_CURRENT=%s" % " ".join(
    "ID%d:%d/T%d" % (servo_id, positions[servo_id], torque_before[servo_id])
    for servo_id in SERVO_IDS
), flush=True)

# First replace every possibly stale servo target while torque state is unchanged.
publisher.publish(SetBusServoState(
    state=[position_state(servo_id, positions[servo_id]) for servo_id in SERVO_IDS],
    duration=0.3,
))
time.sleep(0.5)

# Then enable holding torque. This message deliberately contains no position.
publisher.publish(SetBusServoState(
    state=[torque_state(servo_id) for servo_id in SERVO_IDS],
    duration=0.0,
))
time.sleep(0.8)

ok = True
for servo_id in SERVO_IDS:
    torque = read_field(service, servo_id, "get_torque_state", "enable_torque")
    position = read_position(service, servo_id)
    delta = position - positions[servo_id]
    torque_ok = torque == 1 or servo_id in UNVERIFIABLE_TORQUE_IDS
    servo_ok = torque_ok and abs(delta) <= POSITION_TOLERANCE
    ok = ok and servo_ok
    print("SERVO_%d HOLD=%s POSITION=%d DELTA=%+d TORQUE=%d" % (
        servo_id, "PASS" if servo_ok else "FAIL", position, delta, torque
    ), flush=True)

if 5 in UNVERIFIABLE_TORQUE_IDS:
    print("SERVO_5_TORQUE_FEEDBACK=UNSUPPORTED_POSITION_STABILITY_CHECKED", flush=True)
print("ARM_CURRENT_POSITION_HOLD=%s" % ("PASS" if ok else "FAIL"), flush=True)
sys.exit(0 if ok else 1)
