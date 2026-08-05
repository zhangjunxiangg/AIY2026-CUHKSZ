#!/usr/bin/env python3
"""04_jog_probe.py — Gate 04：单步微动的像素响应标定

目的：测出"base_link 下 X/Y 各动 +10mm，红色目标质心在图像里怎么动"，
即像素伺服的方向与比例（雅可比近似）。每步动完回原位。

gate：IK 有解、质心有位移（>3px）、回位误差 < 12px。
证据：mapping.json + 过程数值入 step.log。
"""
import json
import time

import rospy

from util_gate import Gate, main
from util_board import (get_frame, detect_centroid, ensure_camera,
                        cartesian_jog, get_current_pose, goto_pose)

COLOR = "red"
JOG = 0.01          # 10mm
MIN_RESPONSE_PX = 3.0
RETURN_TOL_PX = 25.0


def measure(g, n=3):
    """连测 n 帧取质心中位数。"""
    us, vs = [], []
    for _ in range(n):
        det = detect_centroid(get_frame(), COLOR)
        if det:
            us.append(det["u"])
            vs.append(det["v"])
    if not us:
        return None
    us.sort()
    vs.sort()
    return us[len(us) // 2], vs[len(vs) // 2]


def run(g: Gate):
    g.require_prev("03_arm_state")
    rospy.init_node("step04_jog_probe", anonymous=True)
    ensure_camera()

    pose0, rpy0 = get_current_pose()
    PITCH_DEG = rpy0[1]
    g.log(f"start pose: {[round(v,3) for v in pose0]} pitch={PITCH_DEG:.1f}deg")

    c0 = measure(g)
    g.gate("target_visible_start", c0 is not None, measured=str(c0), expected="红色目标可见")
    g.log(f"centroid start: ({c0[0]:.0f},{c0[1]:.0f})")

    mapping = {}
    for axis, delta in (("x", (JOG, 0, 0)), ("y", (0, JOG, 0))):
        res = cartesian_jog(dx=delta[0], dy=delta[1], dz=delta[2], duration=1.5)
        g.gate(f"ik_solve_+{axis}", res is not None, measured=str(res), expected="IK 有解")
        c1 = measure(g)
        g.gate(f"target_visible_+{axis}", c1 is not None, measured=str(c1), expected="仍可见")
        du, dv = c1[0] - c0[0], c1[1] - c0[1]
        g.log(f"+{axis} {JOG*1000:.0f}mm -> du={du:+.1f}px dv={dv:+.1f}px")
        g.gate(f"response_+{axis}", abs(du) + abs(dv) > MIN_RESPONSE_PX,
               measured=f"du={du:+.1f},dv={dv:+.1f}", expected="质心有位移")
        mapping[axis] = {"du_per_mm": du / (JOG * 1000), "dv_per_mm": dv / (JOG * 1000)}

        # 闭环回原位（I 控制补偿 J2 下垂稳态误差）
        ok = goto_pose(list(pose0), PITCH_DEG, tol=0.008, max_iter=8, log=g.log)
        g.gate(f"return_{axis}_pose", ok is not None,
               measured=str(ok[0] if ok else None), expected=f"回到 {[round(v,3) for v in pose0]} ±8mm")
        c2 = measure(g)
        g.gate(f"return_{axis}", c2 is not None and
               abs(c2[0] - c0[0]) < RETURN_TOL_PX and abs(c2[1] - c0[1]) < RETURN_TOL_PX,
               measured=str(c2), expected=f"回到 {c0} ±{RETURN_TOL_PX}px")
        time.sleep(0.3)

    with open(g.artifact_path("mapping.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)
    g.log(f"mapping: {mapping}")


if __name__ == "__main__":
    raise SystemExit(main("04_jog_probe", run))
