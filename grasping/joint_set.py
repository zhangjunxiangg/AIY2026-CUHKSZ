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


def get_states_retry(jid=None, tries: int = 6):
    """读舵机状态，目标 id 缺失时重试（启动瞬间可能拿到不完整的首帧）。"""
    import time as _t
    for _ in range(tries):
        states = get_servo_states()
        if jid is None or jid in states:
            return states
        _t.sleep(0.5)
    raise KeyError(f"舵机 id {jid} 不在 servo_states 中（当前 ids: {sorted(states.keys())}）。")


def main():
    rospy.init_node("joint_set", anonymous=True)
    if len(sys.argv) < 3:
        # 无参数：打印全部关节状态
        states = get_states_retry()
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

    before = get_states_retry(jid)[jid]["goal"]

    if jid == 10:
        gripper_set(pos, duration=dur)
    elif jid in ARM_IDS:
        states = get_states_retry()
        pulses = [states[j]["goal"] for j in ARM_IDS]
        idx = ARM_IDS.index(jid)
        cur = pulses[idx]
        # 大跳变自动分步（每步 ≤100 tick），保证速度受限且平滑
        import math as _m
        n = max(1, _m.ceil(abs(pos - cur) / 100))
        for k in range(1, n + 1):
            pulses[idx] = round(cur + (pos - cur) * k / n)
            step_dur = max(dur / n, abs(pulses[idx] - cur) / 60.0 / n + 0.5)
            move_joints_pulses(pulses, duration=step_dur)
            cur = pulses[idx]
    else:
        sys.exit(f"未知关节 id {jid}（1-5 臂关节，10 夹爪）")

    after = get_states_retry(jid)[jid]
    print(f"J{jid}: {before} -> goal {pos} | pos={after['position']} err={after['error']} volt={after['voltage']}")


if __name__ == "__main__":
    main()
