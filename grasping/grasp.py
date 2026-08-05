#!/usr/bin/env python3
"""grasp.py — 夹爪相机像素伺服抓取主程序（交付物）

用法（板端）：
    sh run_step.sh grasp.py --color red --shape cylinder
    sh run_step.sh grasp.py --color yellow --shape cylinder --release   # 抓完放回

链路（每步带 gate，证据写 logs/08_full_run/）：
    相机自检 → 观察位姿(pitch≈87°) → u 对准(dy) → 前进逼近(+x, z 自然下降)
    → 闭合(540) → 阻力验证 → 抬升 → 侧移验证持有 [--release 放回原位]

约束：仅用夹爪相机；底盘不动；形状目前支持 cylinder（决定闭合位置）。
"""
import argparse

import cv2
import rospy

from util_gate import Gate
from util_board import (get_frame, detect_centroid, ensure_camera, annotate,
                        u_align, advance_to_grasp, bottom_center,
                        gripper_set, get_servo_states, cartesian_jog,
                        get_current_pose, goto_pose, move_joints_pulses,
                        ARM_IDS)

OBS_POSE = [0.18, 0.0, 0.06]
OBS_PITCH = 87.0
U_TARGET = 287.0
V_TRIGGER = 380.0
CLOSE_BY_SHAPE = {"cylinder": 540}
MIN_HOLD_AREA = 12000.0

# HOME 复位（用户指定脉冲，2026-08-05）：J1=500 J2=210 J3=150 J4=450 J5=500(中位)
# 说明：该臂共 6 舵机（ID1-5 臂 + ID10 夹爪）；J5 腕自转对抓取无影响，保持 500。
HOME_PULSES = [500, 210, 150, 450, 500]


def go_home(g) -> bool:
    """脉冲级复位到 HOME。跳变 >100 tick 时自动插值分步，避免大动作刮碰。
    返回是否到位（各关节误差 ≤15 tick）。"""
    import math
    cur = [get_servo_states()[j]["goal"] for j in ARM_IDS]
    max_delta = max(abs(a - b) for a, b in zip(cur, HOME_PULSES))
    n = max(1, math.ceil(max_delta / 100))
    g.log(f"go_home: cur={cur} target={HOME_PULSES} 分 {n} 步")
    for k in range(1, n + 1):
        step = [round(cur[i] + (HOME_PULSES[i] - cur[i]) * k / n) for i in range(5)]
        move_joints_pulses(step, duration=max(2.0, max_delta / 60.0 / n + 0.5))
    final = get_servo_states()
    ok = all(abs(final[j]["position"] - p) <= 15 for j, p in zip(ARM_IDS, HOME_PULSES))
    g.log(f"go_home: final={[(j, final[j]['position']) for j in ARM_IDS]} ok={ok}")
    gripper_set(300, duration=2.0)   # HOME 含夹爪张开位
    return ok


def run_grasp(color: str, shape: str, release: bool, g: Gate):
    rospy.init_node("grasp", anonymous=True)
    ensure_camera()

    close_pos = CLOSE_BY_SHAPE.get(shape)
    g.gate("shape_supported", close_pos is not None,
           measured=shape, expected=str(list(CLOSE_BY_SHAPE.keys())))

    # 1. 复位到 HOME（每次抓取必做）
    g.gate("home_reached", go_home(g), measured="见上日志", expected=f"HOME={HOME_PULSES}")

    # 2. 目标可见
    det0 = detect_centroid(get_frame(), color)
    g.gate("target_visible", det0 is not None,
           measured=color, expected=f"{color} 目标在视野内")

    # 3. 夹爪预开（前进前确保能容纳目标）
    gripper_set(330, duration=2.0)

    # HOME 构型的实际俯仰角作为工作 pitch（不硬编码，跟随 HOME 定义）
    _, rpy_home = get_current_pose()
    work_pitch = rpy_home[1]
    g.log(f"work pitch from HOME: {work_pitch:.1f} deg")

    # 4. u 对准
    d = u_align(color, u_target=U_TARGET, pitch_deg=work_pitch, log=g.log)
    g.gate("u_aligned", d is not None,
           measured=str(None if d is None else round(d["u"])), expected=f"u={U_TARGET}±12")

    # 5. 前进逼近（z 自然下降）
    res = advance_to_grasp(color, v_trigger=V_TRIGGER, pitch_deg=work_pitch, log=g.log)
    g.gate("approach_done", res is not None, measured="None", expected="逼近到位")
    pos, det = res
    if det is not None:
        g.log(f"approach: bc=({bottom_center(det)[0]:.0f},{bottom_center(det)[1]:.0f})")
    cv2.imwrite(g.artifact_path("pre_grasp.jpg"),
                annotate(get_frame(), detect_centroid(get_frame(), color), color))

    # 6. 闭合 + 阻力验证
    gripper_set(close_pos, duration=3.0)
    rospy.sleep(1.0)
    gs = get_servo_states()[10]
    g.gate("grip_resistance", gs["error"] <= -8,
           measured=f"goal={gs['goal']} pos={gs['position']} err={gs['error']}",
           expected="error ≤ -8（夹到物体）")

    # 7. 抬升 + 持有验证
    for _ in range(3):
        cartesian_jog(dz=0.02, duration=2.5, pitch_deg=work_pitch)
    det = detect_centroid(get_frame(), color)
    g.gate("held_after_lift", det is not None and det["area"] >= MIN_HOLD_AREA,
           measured=str(None if det is None else int(det["area"])), expected="抬升后目标跟随")
    cartesian_jog(dy=0.02, duration=2.5, pitch_deg=work_pitch)
    det2 = detect_centroid(get_frame(), color)
    g.gate("held_after_lateral", det2 is not None and det2["area"] >= MIN_HOLD_AREA,
           measured=str(None if det2 is None else int(det2["area"])), expected="侧移后仍持有")
    cv2.imwrite(g.artifact_path("held.jpg"),
                annotate(get_frame(), detect_centroid(get_frame(), color), color + " held"))

    # 8. 可选放回
    if release:
        cartesian_jog(dz=-0.02, duration=2.5, pitch_deg=work_pitch)
        cartesian_jog(dz=-0.02, duration=2.5, pitch_deg=work_pitch)
        gripper_set(300, duration=2.5)
        cartesian_jog(dx=-0.02, duration=2.5, pitch_deg=work_pitch)
        cartesian_jog(dz=0.02, duration=2.5, pitch_deg=work_pitch)
        g.log("released and retreated")
        det3 = detect_centroid(get_frame(), color)
        g.gate("release_verified", det3 is not None,
               measured=str(None if det3 is None else int(det3["area"])),
               expected="放回后目标在桌面可见")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--color", required=True, choices=["red", "yellow", "green"])
    ap.add_argument("--shape", default="cylinder", choices=["cylinder"])
    ap.add_argument("--release", action="store_true", help="抓取验证后放回原位")
    args = ap.parse_args()

    g = Gate("08_full_run")
    g.log(f"task: color={args.color} shape={args.shape} release={args.release}")
    try:
        run_grasp(args.color, args.shape, args.release, g)
        g.pass_()
        return 0
    except SystemExit:
        raise
    except Exception as e:
        g.log(f"EXCEPTION: {type(e).__name__}: {e}")
        g._write_status("FAIL", f"exception: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
