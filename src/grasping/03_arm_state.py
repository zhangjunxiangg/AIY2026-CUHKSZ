#!/usr/bin/env python3
"""03_arm_state.py — Gate 03：机械臂状态与 FK 位姿读取

验证链：6 个舵机状态齐全且电压正常 → /kinematics/get_current_pose 返回合理位姿。
证据：舵机读数与位姿写入 step.log + pose.json。
"""
import json

import rospy

from util_gate import Gate, main
from util_board import get_servo_states, get_current_pose, ARM_IDS, GRIPPER_ID


def run(g: Gate):
    g.require_prev("02_detect_centroid")
    rospy.init_node("step03_arm_state", anonymous=True)

    states = get_servo_states()
    for jid in ARM_IDS + [GRIPPER_ID]:
        g.gate(f"servo_{jid}_present", jid in states,
               measured=str(list(states.keys())), expected=f"id {jid} 在 servo_states 中")
        s = states[jid]
        g.gate(f"servo_{jid}_voltage", 6000 <= s["voltage"] <= 13000,
               measured=f"{s['voltage']}mV", expected="6000-13000mV")
        g.log(f"servo {jid}: goal={s['goal']} pos={s['position']} err={s['error']} volt={s['voltage']}")

    pos, rpy = get_current_pose()
    g.gate("pose_position_sane", 0.0 < abs(pos[0]) < 0.6 and abs(pos[1]) < 0.6 and -0.1 < pos[2] < 0.7,
           measured=str([round(v, 3) for v in pos]), expected="机械臂工作空间内（米）")
    g.gate("pose_rpy_sane", all(abs(a) <= 360.0 for a in rpy),
           measured=str([round(a, 1) for a in rpy]), expected="rpy 角度合理")
    g.log(f"current pose: pos={[round(v,3) for v in pos]} rpy(deg)={[round(a,1) for a in rpy]}")

    with open(g.artifact_path("pose.json"), "w", encoding="utf-8") as f:
        json.dump({"position": pos, "rpy_deg": rpy,
                   "servos": {str(k): v for k, v in states.items()}}, f, indent=2)


if __name__ == "__main__":
    raise SystemExit(main("03_arm_state", run))
