#!/usr/bin/env python3
"""02_arm_keys_smoke.py — S/X/J/L 按键处理函数的烟雾测试

前置 gate：logs/01_env_check/STATUS.txt 中 servo_states_online 必须 PASS。
动作（全部可逆，各 ±1 步后回到原位）：
    J2 +10 tick → 停 1.5s → J2 -10 tick（复原）
    夹爪 +25 tick → 停 1.5s → 夹爪 -25 tick（复原）
每步打印 goal/position 作为证据；写 logs/02_arm_keys_smoke/STATUS.txt。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rospy

LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "02_arm_keys_smoke")


def main():
    os.makedirs(LOGS, exist_ok=True)
    lines = []

    def log(s):
        print(s)
        lines.append(s)

    # 前置 gate：env_check 的舵机项必须 PASS
    env_status = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "logs", "01_env_check", "STATUS.txt")
    try:
        with open(env_status) as f:
            prev = f.read().strip()
    except FileNotFoundError:
        prev = "MISSING"
    if "servo_states_online" in prev or prev in ("MISSING",):
        log(f"GATE FAIL: predecessor 01_env_check STATUS={prev!r}（需先跑通 01_env_check 的舵机项）")
        with open(os.path.join(LOGS, "STATUS.txt"), "w") as f:
            f.write("FAIL predecessor\n")
        return 1
    log(f"GATE PASS: predecessor 01_env_check STATUS={prev!r}")

    rospy.init_node("teleop_arm_smoke", anonymous=True)
    import teleop
    import util_board as ub

    if teleop.ub is None:
        log(f"GATE FAIL: util_board 导入失败 {teleop._ARM_IMPORT_ERR}")
        with open(os.path.join(LOGS, "STATUS.txt"), "w") as f:
            f.write("FAIL import\n")
        return 1

    def show(tag):
        st = ub.get_servo_states()
        log(f"{tag}: J2 goal={st[2]['goal']} pos={st[2]['position']} | "
            f"gripper goal={st[10]['goal']} pos={st[10]['position']}")
        return st

    ok = True
    s0 = show("before")
    j2_0, g0 = s0[2]["goal"], s0[10]["goal"]

    teleop.joint2_jog(+1); time.sleep(1.5); s = show("J2 +10")
    if s[2]["goal"] != j2_0 + teleop.J2_STEP:
        log(f"FAIL: J2 goal 期望 {j2_0 + teleop.J2_STEP} 实测 {s[2]['goal']}"); ok = False
    teleop.joint2_jog(-1); time.sleep(1.5); s = show("J2 -10 (复原)")
    if s[2]["goal"] != j2_0:
        log(f"FAIL: J2 未复原到 {j2_0}，实测 {s[2]['goal']}"); ok = False

    teleop.gripper_jog(+1); time.sleep(1.5); s = show("gripper +25")
    if s[10]["goal"] != g0 + teleop.GRIP_STEP:
        log(f"FAIL: 夹爪 goal 期望 {g0 + teleop.GRIP_STEP} 实测 {s[10]['goal']}"); ok = False
    teleop.gripper_jog(-1); time.sleep(1.5); s = show("gripper -25 (复原)")
    if s[10]["goal"] != g0:
        log(f"FAIL: 夹爪未复原到 {g0}，实测 {s[10]['goal']}"); ok = False

    status = "PASS" if ok else "FAIL"
    with open(os.path.join(LOGS, "STATUS.txt"), "w") as f:
        f.write(status + "\n")
    with open(os.path.join(LOGS, "step.log"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"STATUS: {status}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
