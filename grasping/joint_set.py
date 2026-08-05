#!/usr/bin/env python3
"""joint_set.py — 单关节 CLI 控制（调试用）

用法（板端）：
    sh run_step.sh joint_set.py <joint_id> <position> [duration]
示例：
    sh run_step.sh joint_set.py 4 500        # J4 到 500，默认 2s
    sh run_step.sh joint_set.py 10 300 2.5   # 夹爪张开
"""
import sys

import rospy

from util_board import move_joints_pulses, gripper_set, get_servo_states, ARM_IDS


def main():
    rospy.init_node("joint_set", anonymous=True)
    if len(sys.argv) < 3:
        # 无参数：打印全部关节状态
        states = get_servo_states()
        names = {1: "J1 基座旋转", 2: "J2 肩", 3: "J3 肘", 4: "J4 腕俯仰", 5: "J5 腕自转", 10: "夹爪"}
        for j in [1, 2, 3, 4, 5, 10]:
            s = states[j]
            print(f"{names[j]:<10} id={j:<3} goal={s['goal']:<4} pos={s['position']:<4} "
                  f"err={s['error']:<4} volt={s['voltage']}")
        return
    jid = int(sys.argv[1])
    pos = int(sys.argv[2])
    dur = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    if not (0 <= pos <= 1000):
        sys.exit("position 必须在 0-1000")

    rospy.init_node("joint_set", anonymous=True)
    before = get_servo_states()[jid]["goal"]

    if jid == 10:
        gripper_set(pos, duration=dur)
    elif jid in ARM_IDS:
        states = get_servo_states()
        pulses = [states[j]["goal"] for j in ARM_IDS]
        pulses[ARM_IDS.index(jid)] = pos
        move_joints_pulses(pulses, duration=dur)
    else:
        sys.exit(f"未知关节 id {jid}（1-5 臂关节，10 夹爪）")

    after = get_servo_states()[jid]
    print(f"J{jid}: {before} -> goal {pos} | pos={after['position']} err={after['error']} volt={after['voltage']}")


if __name__ == "__main__":
    main()
