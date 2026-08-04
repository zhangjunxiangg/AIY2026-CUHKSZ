#!/bin/sh
# Read-only validation. This script never publishes an arm or gripper command.
set -u

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
ARM_STATE_SCRIPT=/data/local/tmp/.mclaw/skills/kaihong-robot-operations/scripts/arm_state.py
. "$ROOT/robot-env.sh"
. "$ROOT/host-arm-env.sh"

fail=0
"$ROOT/status-host-arm-4.1.sh" || fail=1

for package in servo_msgs servo_driver servo_controllers interfaces kinematics; do
    if rospack find "$package" >/dev/null 2>&1; then
        echo "PACKAGE_${package}=PASS"
    else
        echo "PACKAGE_${package}=FAIL"
        fail=1
    fi
done

if [ -f "$ARM_STATE_SCRIPT" ] && timeout 25 "$ROOT/bin/python3" "$ARM_STATE_SCRIPT"; then
    echo "SERVO_STATES=PASS"
else
    echo "SERVO_STATES=FAIL"
    fail=1
fi

if timeout 8 rosservice call /kinematics/get_link; then
    echo "KINEMATICS_GET_LINK=PASS"
else
    echo "KINEMATICS_GET_LINK=FAIL"
    fail=1
fi

if timeout 8 rosservice call /kinematics/get_joint_range >/dev/null; then
    echo "KINEMATICS_GET_RANGE=PASS"
else
    echo "KINEMATICS_GET_RANGE=FAIL"
    fail=1
fi

echo "host_arm_healthcheck_no_motion=$([ "$fail" -eq 0 ] && echo PASS || echo FAIL)"
exit "$fail"
