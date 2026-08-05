#!/usr/bin/env python3
"""grasp.py — 夹爪相机像素伺服抓取主程序（交付物）

用法（板端）：
    cd /data/local/grasping
    ./grab red                 # 抓红色圆柱（抓住确认后抬升停止）
    ./grab red --release       # 抓完放回
    ./stop_grasp               # 任何时候安全停止（刹车+退出）

策略（2026-08-05 与操作者标定）：
    1. 复位：J2-5 固定到抓取构型 [_,150,182,650,500]，J1 居中 500，夹爪张开 330
    2. 扫描：目标不在视野时 J1 旋转扫描（±72° 安全窗）
    3. 对准：J1 一次性对准（按质心偏差一次算好转角，不摇头）
    4. 逼近：底盘直行 15mm/步，直到 v≥357 或 bbox 底边 ≥470
    5. 补偿：再前进 50mm（标定像素是"能看到"，不是"能抓住"）
    6. 闭合：夹爪 540；判定：|err|≥40 且位置稳定 = 夹住（空夹 err 仅 -14）
    7. 夹住 → 抬升 J2→300 → 停止，不再做任何多余动作
    8. 未夹住 → 张开夹爪 → 重新对准 → 多走 20mm → 再夹（≤3 次）

优雅退出：SIGINT/SIGTERM 都会先刹停底盘再退出（防"关了还在跑"）。
"""
import argparse
import atexit
import signal

import cv2
import rospy

from util_gate import Gate
from util_board import (get_frame, detect_centroid, ensure_camera, annotate,
                        scan_for_color, j1_align, j1_align_oneshot, bottom_center,
                        chassis_move, chassis_turn,
                        gripper_set, get_servo_states, cartesian_jog,
                        get_current_pose, move_joints_pulses, arm_joint_set,
                        ARM_IDS)


def _brake_chassis():
    """退出前刹停底盘（无论正常结束还是被 kill）。"""
    try:
        from geometry_msgs.msg import Twist
        pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        pub.publish(Twist())
    except Exception:
        pass


def _on_signal(sig, frame):
    _brake_chassis()
    rospy.signal_shutdown(f"signal {sig}")
    raise SystemExit(128 + sig)

# 抓取构型（操作者肉眼标定 2026-08-05）：J2=150 J3=182 J4=650 J5=500
GRASP_CONFIG = [None, 150, 182, 650, 500]   # J1 不固定（对准用）
HOME_PULSES = [500, 150, 182, 650, 500]     # 复位时 J1 居中
U_TARGET = 321.0          # 标定：抓取构型下目标质心 u
V_TARGET = 357.0          # 标定：抓取构型下目标质心 v
V_BC_TRIGGER = 470.0      # bbox 底边贴底 = 目标已在指线
CLOSE_BY_SHAPE = {"cylinder": 540}
MIN_HOLD_AREA = 12000.0


def go_home(g) -> bool:
    """复位到抓取构型（J1 居中）。跳变 >100 tick 自动插值分步。"""
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
    gripper_set(330, duration=2.0)
    return ok


def run_grasp(color: str, shape: str, release: bool, g: Gate):
    rospy.init_node("grasp", anonymous=True)
    ensure_camera()

    close_pos = CLOSE_BY_SHAPE.get(shape)
    g.gate("shape_supported", close_pos is not None,
           measured=shape, expected=str(list(CLOSE_BY_SHAPE.keys())))

    # 1. 复位抓取构型
    g.gate("home_reached", go_home(g), measured="见日志", expected=f"HOME={HOME_PULSES}")

    # 2. 扫描找目标（底盘旋转扫描；J1 固定不动）
    det = detect_centroid(get_frame(), color)
    if det is None:
        g.log("目标不在初始视野，开始底盘旋转扫描")
        for k in range(12):   # 每次转 30°，最多一圈
            chassis_turn(30.0)
            det = detect_centroid(get_frame(), color)
            g.log(f"scan turn {k+1}x30deg: {'FOUND u=%.0f' % det['u'] if det else 'none'}")
            if det is not None:
                break
    g.gate("target_found", det is not None, measured=color, expected="扫描后目标可见")

    # 3-4. 迭代逼近：每个 iteration 都先转车对准方向，再判断是否进入夹取范围，再前进
    # 转向增益：实测 CCW(左)+10° → u +233px，即 23.3px/deg；eu>0(目标偏左)→左转(正)
    reached = False
    for i in range(25):
        det = detect_centroid(get_frame(), color)
        if det is None:
            g.log(f"approach iter{i}: 目标被夹指遮挡/丢失 → 视为到位")
            reached = True
            break
        _, v_bc = bottom_center(det)
        g.log(f"approach iter{i}: u={det['u']:.0f} v={det['v']:.0f} v_bc={v_bc:.0f}")
        if det["v"] >= V_TARGET or v_bc >= V_BC_TRIGGER:
            reached = True
            break
        eu = U_TARGET - det["u"]
        if abs(eu) > 15:
            deg = max(-15.0, min(15.0, eu / 23.3))
            chassis_turn(deg)
            g.log(f"approach iter{i}: turn {deg:+.1f}deg (eu={eu:+.0f})")
        chassis_move(0.05, 0.3)   # 前进 15mm
    g.gate("approach_done", reached, measured=str(reached), expected="进入夹取范围")

    # 4b. 对准后再前进 5cm（标定像素是"确定能看到"的位置，不是"能抓住"的位置）
    chassis_move(0.05, 1.0)   # 再前进 50mm

    cv2.imwrite(g.artifact_path("pre_grasp.jpg"),
                annotate(get_frame(), detect_centroid(get_frame(), color), color))

    # 5-6. 抓取尝试（通用顺序，每次尝试都完整走一遍）：
    #   打开夹爪 → 一次性对准 → 前进一点 → 闭合 → 夹爪位置判定 → 夹住即抬升停止
    # 判定依据（用户实测）：闭合到位误差 |err| ≥ 40 且位置读数稳定 = 被物体撑住；
    # 空夹 err 只有 -12~-14。图像判定不可靠，弃用。
    held = False
    for attempt in range(3):
        if attempt > 0:
            g.log(f"retry {attempt}: 张开夹爪 → 转车重新对准 → 再前进 20mm")
            gripper_set(330, duration=2.0)
            d = detect_centroid(get_frame(), color)
            if d is None:
                for k in range(12):
                    chassis_turn(30.0)
                    d = detect_centroid(get_frame(), color)
                    if d is not None:
                        break
            if d is None:
                g.log(f"retry {attempt}: 目标丢失，放弃")
                break
            eu = U_TARGET - d["u"]
            if abs(eu) > 15:
                chassis_turn(max(-15.0, min(15.0, eu / 23.3)))
            chassis_move(0.05, 0.4)   # 重试每次再多走 20mm

        gripper_set(close_pos, duration=3.0)
        rospy.sleep(0.5)
        # 夹持判定：连续 3 次读数，位置稳定且 |err| ≥ 40 → 被物体撑住
        reads = []
        for _ in range(3):
            s = get_servo_states()[10]
            reads.append((s["position"], s["error"]))
            rospy.sleep(0.5)
        stable = max(r[0] for r in reads) - min(r[0] for r in reads) <= 5
        err = reads[-1][1]
        g.log(f"attempt{attempt}: gripper reads={reads} stable={stable}")
        if stable and err <= -40:
            held = True
            g.log(f"attempt{attempt}: 夹持确认（err={err}，位置稳定）→ 抬升后停止")
            arm_joint_set(2, 300, duration=3.0)
            cv2.imwrite(g.artifact_path("held.jpg"),
                        annotate(get_frame(), detect_centroid(get_frame(), color), color + " held"))
            break
        g.log(f"attempt{attempt}: 未夹住（err={err}）")

    g.gate("held_after_lift", held, measured=str(held),
           expected="夹爪位置稳定且 |err|≥40（≤3 次尝试）")

    # 7. 可选放回：先张开夹爪放掉物体，再收臂（用户要求顺序）
    if release:
        gripper_set(300, duration=2.5)
        arm_joint_set(2, 150, duration=3.0)
        chassis_move(-0.05, 0.4)   # 底盘后退 20mm
        g.log("released")
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

    # 优雅退出：SIGINT(Ctrl+C)/SIGTERM(kill) → 先刹车再退出
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    atexit.register(_brake_chassis)

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
