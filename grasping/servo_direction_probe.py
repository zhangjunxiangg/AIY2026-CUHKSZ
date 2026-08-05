#!/usr/bin/env python3
"""servo_direction_probe.py — 每个舵机方向实证探针（非 gate 步骤，产文档数据）

对每个关节：当前位姿 → 单关节 +20 tick → 记录 FK 位姿变化 → 回 -20 tick。
夹爪 ID 10 单独测 ±50 tick。所有运动小步、慢速、可回退。
输出：logs/servo_direction_probe/probe.log + probe.json
"""
import json
import os
import time

import rospy

from util_board import (get_current_pose, get_servo_states,
                        move_joints_pulses, gripper_set, ARM_IDS)

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "logs", "servo_direction_probe")


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    rospy.init_node("servo_direction_probe", anonymous=True)
    lines = []

    def log(msg):
        print(msg, flush=True)
        lines.append(msg)

    base_pulses = [get_servo_states()[j]["goal"] for j in ARM_IDS]
    pos0, rpy0 = get_current_pose()
    log(f"base pulses: {base_pulses}")
    log(f"base pose: pos={[round(v,4) for v in pos0]} rpy={[round(a,1) for a in rpy0]}")

    results = {}
    for idx, jid in enumerate(ARM_IDS):
        test = list(base_pulses)
        test[idx] = base_pulses[idx] + 20
        move_joints_pulses(test, duration=2.0)
        pos1, rpy1 = get_current_pose()
        dpos = [round((pos1[k] - pos0[k]) * 1000, 1) for k in range(3)]
        drpy = [round(rpy1[k] - rpy0[k], 1) for k in range(3)]
        log(f"J{jid} +20 tick: dpos(mm)={dpos} drpy(deg)={drpy}")
        results[f"J{jid}"] = {"plus20_dpos_mm": dpos, "plus20_drpy_deg": drpy}
        move_joints_pulses(base_pulses, duration=2.0)
        time.sleep(0.5)

    g0 = get_servo_states()[10]["goal"]
    gripper_set(g0 + 50, duration=2.0)
    g1 = get_servo_states()[10]["position"]
    log(f"gripper +50 tick: goal {g0} -> pos {g1}（数值增大方向实测）")
    results["gripper"] = {"plus50_from": g0, "to": g1}
    gripper_set(g0, duration=2.0)

    with open(os.path.join(LOG_DIR, "probe.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    with open(os.path.join(LOG_DIR, "probe.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
