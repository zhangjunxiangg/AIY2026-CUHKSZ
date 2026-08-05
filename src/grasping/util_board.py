#!/usr/bin/env python3
"""util_board.py — 板端 ROS 硬件接口（取帧/检测/臂状态/IK/微动/夹爪）

所有函数在板端 `run python3` 环境使用；调用方负责 rospy.init_node。
坐标约定：base_link 基座坐标系，X 前、Y 左、Z 上，单位米。
舵机原始值 0-1000，中位 500，反向映射；夹爪 ID 10，安全范围 200-700。
"""
from __future__ import annotations

import math
import time

import cv2
import numpy as np
import rospy
from sensor_msgs.msg import Image
from servo_msgs.msg import MultiRawIdPosDur, RawIdPosDur, ServoStateList
from interfaces.srv import GetRobotPose, SetRobotPose

CAMERA_TOPIC = "/gripper_camera/image_raw"
SERVO_STATES_TOPIC = "/servo_controllers/port_id_1/servo_states"
RAW_CMD_TOPIC = "/servo_controllers/port_id_1/id_pos_dur"
MULTI_CMD_TOPIC = "/servo_controllers/port_id_1/multi_id_pos_dur"
IK_SERVICE = "/kinematics/set_pose_target"
POSE_SERVICE = "/kinematics/get_current_pose"

FRAME_W, FRAME_H = 640, 480
FRAME_CENTER = (FRAME_W // 2, FRAME_H // 2)

GRIPPER_ID = 10
GRIPPER_MIN, GRIPPER_MAX = 200, 700   # 实测安全范围，绝不超过 700
GRIPPER_OPEN = 300

ARM_IDS = [1, 2, 3, 4, 5]
PULSE_MIN, PULSE_MAX = 0, 1000

# ---------------- 安全不变量（任何运动不得违反） ----------------
class SafetyError(RuntimeError):
    pass

WORKSPACE = {"x": (0.05, 0.45), "y": (-0.40, 0.40), "z": (-0.03, 0.45)}  # 末端允许空间（米）
MAX_PULSE_JUMP = 120      # 单关节单次命令与当前目标的最大跳变（tick）
MAX_TICKS_PER_SEC = 60    # 单关节最大速度（tick/s ≈ 14°/s，慢速安全）

# HSV 范围（OpenCV H:0-179），2026-08-05 实测校准：
#   红 H=0（S=255 高饱和），黄 H=12-16（偏橙），绿 H=62-66
HSV_RANGES = {
    "red":    [((0, 120, 80), (6, 255, 255)), ((172, 120, 80), (179, 255, 255))],
    "yellow": [((8, 80, 60), (24, 255, 255))],
    "green":  [((50, 80, 50), (80, 255, 255))],
}


# ---------------- 相机 ----------------

def ensure_camera():
    """确认相机话题在出帧；失败则调用 start_camera.sh 自愈（按名字重新解析设备号）。
    设备号会随重枚举漂移，任何 step 开始前都应调用本函数。"""
    import os
    try:
        get_frame(timeout=4.0)
        return
    except Exception:
        pass
    os.system("sh /data/local/grasping/start_camera.sh")
    get_frame(timeout=8.0)  # 再失败就抛异常，由 gate 报告


def get_frame(timeout: float = 5.0) -> np.ndarray:
    """取一帧 BGR 图像（np.uint8, HxWx3）。"""
    msg = rospy.wait_for_message(CAMERA_TOPIC, Image, timeout=timeout)
    if msg.encoding != "bgr8":
        raise ValueError(f"unexpected encoding {msg.encoding}")
    return np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3)).copy()


def wait_exposure(discard: int = 20):
    """丢前 N 帧等自动曝光收敛（icSpring 首帧近全白，实测 10-20 帧收敛）。"""
    for _ in range(discard):
        get_frame(timeout=5.0)


def frame_stats(frame: np.ndarray):
    return {"mean": float(frame.mean()), "std": float(frame.std())}


# ---------------- 颜色质心检测 ----------------

def detect_centroid(frame: np.ndarray, color: str, min_area: float = 300.0):
    """HSV 阈值 + 最大连通域质心。返回 dict(u,v,area,bbox) 或 None。"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = None
    for lo, hi in HSV_RANGES[color]:
        m = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
        mask = m if mask is None else cv2.bitwise_or(mask, m)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area < min_area:
        return None
    m = cv2.moments(c)
    if m["m00"] <= 0:
        return None
    u, v = m["m10"] / m["m00"], m["m01"] / m["m00"]
    x, y, w, h = cv2.boundingRect(c)
    return {"u": u, "v": v, "area": area, "bbox": (x, y, w, h), "width": w, "height": h}


def annotate(frame: np.ndarray, det, color: str) -> np.ndarray:
    out = frame.copy()
    if det:
        x, y, w, h = det["bbox"]
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.circle(out, (int(det["u"]), int(det["v"])), 6, (255, 0, 255), -1)
    cv2.drawMarker(out, FRAME_CENTER, (255, 255, 255), cv2.MARKER_CROSS, 20, 1)
    cv2.putText(out, color, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    return out


# ---------------- 机械臂状态 ----------------

def get_servo_states(timeout: float = 5.0) -> dict:
    msg = rospy.wait_for_message(SERVO_STATES_TOPIC, ServoStateList, timeout=timeout)
    return {s.id: {"goal": s.goal, "position": s.position, "error": s.error, "voltage": s.voltage}
            for s in msg.servo_states}


def get_current_pose(timeout: float = 5.0):
    """FK 当前末端位姿。返回 (position[3], rpy[3]（度）)。
    防呆：新节点首次调用偶发返回全零位姿，校验失败后重试。"""
    rospy.wait_for_service(POSE_SERVICE, timeout=timeout)
    fn = rospy.ServiceProxy(POSE_SERVICE, GetRobotPose)
    for attempt in range(8):
        res = fn()
        if res.success:
            p = res.pose.position
            norm = math.sqrt(p.x * p.x + p.y * p.y + p.z * p.z)
            if norm > 0.05:  # 全零/近零 = 无效读数
                return [p.x, p.y, p.z], _quat_to_rpy_deg(
                    res.pose.orientation.x, res.pose.orientation.y,
                    res.pose.orientation.z, res.pose.orientation.w)
        time.sleep(0.5)
    raise RuntimeError("get_current_pose 连续返回无效位姿（全零）")


def _quat_to_rpy_deg(x, y, z, w):
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    sinp = max(-1.0, min(1.0, 2 * (w * y - z * x)))
    pitch = math.asin(sinp)
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]


# ---------------- 运动 ----------------

def solve_ik(position, pitch_deg, pitch_range=(-180.0, 180.0), resolution=1.0, timeout=5.0):
    """IK 求解，返回 5 路脉冲 list[int]；无解返回 None。"""
    rospy.wait_for_service(IK_SERVICE, timeout=timeout)
    fn = rospy.ServiceProxy(IK_SERVICE, SetRobotPose)
    res = fn([float(v) for v in position], float(pitch_deg),
             [float(pitch_range[0]), float(pitch_range[1])], float(resolution))
    if not res.success or len(res.pulse) != 5:
        return None
    return [int(round(v)) for v in res.pulse]


def move_joints_pulses(pulses, duration: float = 2.0, wait: bool = True):
    """5 关节同步到脉冲目标（MultiRawIdPosDur）。
    安全护栏：1) 范围钳制 0-1000；2) 单关节跳变 ≤ MAX_PULSE_JUMP（对当前 goal）；
    3) duration 必须满足速度 ≤ MAX_TICKS_PER_SEC。违反即抛 SafetyError，不执行。"""
    pulses = [int(max(PULSE_MIN, min(PULSE_MAX, p))) for p in pulses]
    states = get_servo_states()
    max_delta = 0
    for jid, pos in zip(ARM_IDS, pulses):
        cur = states.get(jid, {}).get("goal")
        if cur is None:
            raise SafetyError(f"舵机 {jid} 状态缺失，拒绝运动")
        delta = abs(pos - cur)
        max_delta = max(max_delta, delta)
        if delta > MAX_PULSE_JUMP:
            raise SafetyError(
                f"舵机 {jid} 跳变 {delta} tick（{cur}→{pos}）超过 {MAX_PULSE_JUMP}，拒绝执行")
    min_duration = max_delta / MAX_TICKS_PER_SEC
    if duration < min_duration:
        # 自动降速以满足速度上限（ slower = safer ），不静默提速
        print(f"[SAFETY] duration {duration:.1f}s 过短，自动延长到 {min_duration + 0.3:.1f}s")
        duration = min_duration + 0.3
    pub = rospy.Publisher(MULTI_CMD_TOPIC, MultiRawIdPosDur, queue_size=1)
    rospy.sleep(0.3)
    items = [RawIdPosDur(id=jid, position=pos, duration=float(duration))
             for jid, pos in zip(ARM_IDS, pulses)]
    pub.publish(MultiRawIdPosDur(id_pos_dur_list=items))
    if wait:
        rospy.sleep(duration + 0.8)


def gripper_set(position: int, duration: float = 2.0, wait: bool = True):
    position = int(max(GRIPPER_MIN, min(GRIPPER_MAX, position)))
    if duration < 1.0:
        raise SafetyError("夹爪 duration 不得小于 1.0s")
    pub = rospy.Publisher(RAW_CMD_TOPIC, RawIdPosDur, queue_size=1)
    rospy.sleep(0.3)
    pub.publish(RawIdPosDur(id=GRIPPER_ID, position=position, duration=float(duration)))
    if wait:
        rospy.sleep(duration + 0.5)


def _in_workspace(pos) -> bool:
    return (WORKSPACE["x"][0] <= pos[0] <= WORKSPACE["x"][1]
            and WORKSPACE["y"][0] <= pos[1] <= WORKSPACE["y"][1]
            and WORKSPACE["z"][0] <= pos[2] <= WORKSPACE["z"][1])


def _ws_violation(pos) -> float:
    """出工作空间的程度（米），0 = 在内。"""
    v = 0.0
    for i, axis in enumerate(("x", "y", "z")):
        lo, hi = WORKSPACE[axis]
        if pos[i] < lo:
            v = max(v, lo - pos[i])
        elif pos[i] > hi:
            v = max(v, pos[i] - hi)
    return v


def cartesian_jog(dx=0.0, dy=0.0, dz=0.0, duration: float = 1.5, max_step: float = 0.02,
                  pitch_deg=None):
    """末端在 base_link 下微动。pitch_deg 不给则保持当前 pitch。
    安全：目标出工作空间则拒绝；若当前已在空间外，只允许"违规程度变小"的回程运动。
    返回 (目标位姿, 脉冲) 或 None（IK 无解/目标出工作空间）。"""
    if max(abs(dx), abs(dy), abs(dz)) > max_step:
        raise ValueError(f"jog too large: {dx},{dy},{dz} (max {max_step})")
    try:
        pos, rpy = get_current_pose()
    except RuntimeError:
        return None   # 位姿服务暂时不可用，由调用方重试/中止
    cur_v = _ws_violation(pos)
    target = [pos[0] + dx, pos[1] + dy, pos[2] + dz]
    tgt_v = _ws_violation(target)
    if tgt_v > 0 and tgt_v >= cur_v:
        if cur_v == 0:
            return None  # 从内向外：不解算不执行，由调用方 gate
        raise SafetyError(f"当前位姿 {['%.3f'%v for v in pos]} 出界且该 jog 不能回界，拒绝运动")
    pitch = rpy[1] if pitch_deg is None else pitch_deg
    pulses = solve_ik(target, pitch)
    if pulses is None:
        return None
    move_joints_pulses(pulses, duration=duration)
    return target, pulses


def goto_pose(target_pos, pitch_deg, tol: float = 0.008, max_iter: int = 8,
              duration: float = 1.5, max_step: float = 0.02, pitch_step: float = 10.0,
              ki: float = 0.5, log=None):
    """闭环到目标位姿（位姿空间 I 控制）：补偿 J2 负重下垂的稳态误差。
    bias 积分项累积"目标-实际"偏差，命令瞄准 target+bias 从而收敛到真实目标。
    pitch 每次最多转 pitch_step 度。返回最终 (pos, rpy)；不收敛返回 None。"""
    bias = [0.0, 0.0, 0.0]
    pitch_bias = 0.0
    for i in range(max_iter):
        pos, rpy = get_current_pose()
        err = [target_pos[k] - pos[k] for k in range(3)]
        dist = math.sqrt(sum(e * e for e in err))
        pitch_err = pitch_deg - rpy[1]
        if log:
            log(f"goto_pose iter{i}: pos={[round(v,4) for v in pos]} pitch={rpy[1]:.1f} "
                f"err={dist*1000:.1f}mm pitch_err={pitch_err:.1f} bias={[round(b*1000,1) for b in bias]}")
        if dist < tol and abs(pitch_err) < 5.0:
            return pos, rpy
        bias = [max(-0.03, min(0.03, bias[k] + err[k])) for k in range(3)]
        pitch_bias = max(-10.0, min(10.0, pitch_bias + pitch_err))
        cmd = [pos[k] + err[k] + ki * bias[k] for k in range(3)]
        delta = [cmd[k] - pos[k] for k in range(3)]
        dnorm = math.sqrt(sum(d * d for d in delta))
        if dnorm > max_step:
            delta = [d * max_step / dnorm for d in delta]
        pitch_cmd = rpy[1] + max(-pitch_step, min(pitch_step, pitch_err + 0.5 * pitch_bias))
        res = cartesian_jog(dx=delta[0], dy=delta[1], dz=delta[2],
                            duration=duration, max_step=max_step, pitch_deg=pitch_cmd)
        if res is None:
            return None
    return None


# ---------------- 像素伺服 ----------------

# 04_jog_probe 实测雅可比（每 mm 基座位移 → 像素位移），z≈0.03 处标定
JACOBIAN = {"x": {"du": -0.147, "dv": -0.403}, "y": {"du": 4.723, "dv": -6.034}}


def pixel_to_jog(du: float, dv: float, gain: float = 0.5, max_step: float = 0.012):
    """像素误差 → base_link XY 微动（米）。J 逆解 + 增益阻尼 + 步长钳制。"""
    a, b = JACOBIAN["x"]["du"], JACOBIAN["y"]["du"]
    c, d = JACOBIAN["x"]["dv"], JACOBIAN["y"]["dv"]
    det = a * d - b * c
    dx = (d * du - b * dv) / det * gain / 1000.0
    dy = (-c * du + a * dv) / det * gain / 1000.0
    norm = math.hypot(dx, dy)
    if norm > max_step:
        dx, dy = dx * max_step / norm, dy * max_step / norm
    return dx, dy


def servo_align(color: str, target_px, tol_px: float = 12.0, max_iter: int = 8,
                gain: float = 0.5, log=None):
    """像素伺服：把 color 目标质心驱动到 target_px。
    返回最终 (u, v)；不收敛或目标丢失返回 None。"""
    for i in range(max_iter):
        det = detect_centroid(get_frame(), color)
        if det is None:
            if log:
                log(f"servo_align iter{i}: 目标丢失")
            return None
        eu, ev = target_px[0] - det["u"], target_px[1] - det["v"]
        err = math.hypot(eu, ev)
        if log:
            log(f"servo_align iter{i}: centroid=({det['u']:.0f},{det['v']:.0f}) err={err:.1f}px")
        if abs(eu) <= tol_px and abs(ev) <= tol_px:
            return det["u"], det["v"]
        dx, dy = pixel_to_jog(eu, ev, gain=gain)
        if cartesian_jog(dx=dx, dy=dy) is None:
            if log:
                log(f"servo_align iter{i}: jog 失败（IK 无解/出工作空间）")
            return None
    return None


# ---------------- 2D 自适应伺服（u:dy / v:dx，v 方向在线判定） ----------------

DU_PER_MM_Y = 4.7    # 实测：+dy → u 增大，增益稳定（px/mm）


def bottom_center(det):
    x, y, w, h = det["bbox"]
    return x + w / 2.0, y + h


def servo2d(color: str, u_target: float = 287.0, v_band=(430, 479),
            u_tol: float = 12.0, max_iter: int = 12, log=None):
    """u 通道用 dy（增益已知），v 通道用 bbox 底边 + dx（方向在线探测）。
    返回最终 det；不收敛/目标丢失返回 None。
    设计依据：u-dy 增益稳定；v-dx 方向随位姿变化（减速箱回程差），故在线判定。"""
    v_sign = None  # +1 表示 +dx 使 v_bc 增大
    for i in range(max_iter):
        det = detect_centroid(get_frame(), color)
        if det is None:
            if log:
                log(f"servo2d iter{i}: 目标丢失")
            return None
        u_bc, v_bc = bottom_center(det)
        eu = u_target - u_bc
        u_ok = abs(eu) <= u_tol
        v_ok = v_band[0] <= v_bc <= v_band[1]
        if log:
            log(f"servo2d iter{i}: bc=({u_bc:.0f},{v_bc:.0f}) eu={eu:+.0f} v_ok={v_ok}")
        if u_ok and v_ok:
            return det

        dx = dy = 0.0
        if not u_ok:
            dy = eu / DU_PER_MM_Y / 1000.0 * 0.6   # 实测 +dy → u 增大，eu>0 需 +dy
            dy = max(-0.005, min(0.005, dy))
        if not v_ok:
            want_up = v_bc < v_band[0]   # v 需要增大
            if v_sign is None:
                # 在线方向探测：+2mm dx 试一次
                probe = +0.002
                if cartesian_jog(dx=probe, duration=1.5) is None:
                    return None
                det2 = detect_centroid(get_frame(), color)
                if det2 is None:
                    return None
                dv = bottom_center(det2)[1] - v_bc
                v_sign = 1.0 if dv > 0 else -1.0
                if log:
                    log(f"servo2d: v 方向探测 dv={dv:+.1f} → v_sign={v_sign:+.0f}")
                continue
            dx = (0.003 if want_up else -0.003) * v_sign
        if cartesian_jog(dx=dx, dy=dy, duration=1.5) is None:
            if log:
                log(f"servo2d iter{i}: jog 失败")
            return None
    return None


# ---------------- 手指检测（夹爪抓取点在线标定） ----------------

def detect_finger_gap(frame: np.ndarray):
    """检测画面中两个夹爪手指（底部深色圆斑），返回指缝中心像素 (u, v)。
    依据：手指在画面底部为低亮度圆形区域。找不到返回 None。"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    roi = gray[int(FRAME_H * 0.55):, :]                    # 只看下半部
    _, mask = cv2.threshold(roi, 60, 255, cv2.THRESH_BINARY_INV)   # 深色
    kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 200:
            continue
        m = cv2.moments(c)
        if m["m00"] <= 0:
            continue
        blobs.append((m["m10"] / m["m00"], m["m01"] / m["m00"] + int(FRAME_H * 0.55), area))
    if len(blobs) < 2:
        return None
    blobs.sort(key=lambda b: b[2], reverse=True)
    left, right = sorted(blobs[:2], key=lambda b: b[0])
    if right[0] - left[0] < 40:    # 两指横向距离太近 = 误检
        return None
    return ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0,
            (left, right))


def servo_adaptive(color: str, max_iter: int = 15, tol_px: float = 14.0,
                   gain: float = 0.5, max_step_mm: float = 8.0, log=None,
                   feature="centroid"):
    """自适应图像伺服：在线 Broyden 更新 2x2 增益矩阵（mm→px），
    目标点 = 每帧实测的指缝中心像素。返回最终 det 或 None。
    feature: 'centroid' 用质心；'bottom' 用 bbox 底边中点。"""
    # 初值（top-down 位姿实测量级）：du/dy≈+2.5, dv/dx≈-5 px/mm
    M = np.array([[0.0, 2.5], [-5.0, 0.0]])   # [[du/dx, du/dy],[dv/dx, dv/dy]]
    prev = None  # (delta_mm_vec, delta_px_vec)
    for i in range(max_iter):
        frame = get_frame()
        det = detect_centroid(frame, color)
        gap = detect_finger_gap(frame)
        if det is None or gap is None:
            if log:
                log(f"servo_adaptive iter{i}: det={det is not None} gap={gap is not None}，失败")
            return None
        target = (gap[0], gap[1] - 15.0)   # 指缝中心略上方（质心 vs 底边的折中）
        if feature == "bottom":
            cur = bottom_center(det)
        else:
            cur = (det["u"], det["v"])
        err = np.array([target[0] - cur[0], target[1] - cur[1]])
        if log:
            log(f"servo_adaptive iter{i}: cur=({cur[0]:.0f},{cur[1]:.0f}) "
                f"target=({target[0]:.0f},{target[1]:.0f}) err=({err[0]:+.0f},{err[1]:+.0f})")
        if abs(err[0]) <= tol_px and abs(err[1]) <= tol_px:
            return det

        # Broyden 更新
        if prev is not None:
            d_mm, d_px = prev
            denom = float(d_mm @ d_mm)
            if denom > 1e-6:
                M = M + np.outer(d_px - M @ d_mm, d_mm) / denom
                if log:
                    log(f"  M更新: [[{M[0,0]:.1f},{M[0,1]:.1f}],[{M[1,0]:.1f},{M[1,1]:.1f}]]")

        try:
            delta_mm = np.linalg.solve(M, err) * gain
        except np.linalg.LinAlgError:
            return None
        norm = float(np.hypot(*delta_mm))
        if norm > max_step_mm:
            delta_mm *= max_step_mm / norm
        if norm < 1.0:
            delta_mm = delta_mm / max(norm, 1e-6) * 1.0   # 小于 1mm 的步长打不动（死区）
        if cartesian_jog(dx=float(delta_mm[0]) / 1000.0,
                         dy=float(delta_mm[1]) / 1000.0, duration=2.0) is None:
            if log:
                log(f"servo_adaptive iter{i}: jog 失败")
            return None
        # 记录实际响应用于下一轮 Broyden 更新
        det2 = detect_centroid(get_frame(), color)
        if det2 is not None:
            cur2 = bottom_center(det2) if feature == "bottom" else (det2["u"], det2["v"])
            prev = (delta_mm, np.array([cur2[0] - cur[0], cur2[1] - cur[1]]))
    return None


# ---------------- 分通道对准与下降（实战版） ----------------

def u_align(color: str, u_target: float = 287.0, tol: float = 12.0,
            max_iter: int = 10, pitch_deg: float = 80.0, log=None):
    """u 通道对准（dy）。du/dy 符号随构型翻转（实测 87° 俯视 +2.5px/mm，
    平夹构型反向），首轮在线探测符号后使用。"""
    u_sign = None
    for i in range(max_iter):
        det = detect_centroid(get_frame(), color)
        if det is None:
            if log:
                log(f"u_align iter{i}: 目标丢失")
            return None
        eu = u_target - det["u"]
        if log:
            log(f"u_align iter{i}: u={det['u']:.0f} eu={eu:+.0f}")
        if abs(eu) <= tol:
            return det
        if u_sign is None:
            probe = 0.002
            if cartesian_jog(dy=probe, duration=2.0, pitch_deg=pitch_deg) is None:
                return None
            det2 = detect_centroid(get_frame(), color)
            if det2 is None:
                return None
            du = det2["u"] - det["u"]
            u_sign = 1.0 if du > 0 else -1.0
            if log:
                log(f"u_align: 方向探测 +2mm dy → du={du:+.1f}，u_sign={u_sign:+.0f}")
            continue
        # eu>0 需 u 增大；du/dy 符号 = u_sign → dy = eu * u_sign / 增益
        dy = eu * u_sign / 2.5 / 1000.0 * 0.6
        dy = max(-0.006, min(0.006, dy))
        if abs(dy) < 0.0015:
            dy = 0.0015 if dy > 0 else -0.0015   # 小于死区的步长打不动
        if cartesian_jog(dy=dy, duration=2.0, pitch_deg=pitch_deg) is None:
            return None
    return None


def v_coarse_align(color: str, v_band=(380, 440), max_iter: int = 10,
                   pitch_deg: float = 80.0, log=None):
    """v 通道粗对准（bbox 底边进带）。dx 方向在线探测（带记忆）。
    设计：v 只要求进捕获带，精确性靠下降阶段宽夹爪容差兜底。"""
    v_sign = None
    for i in range(max_iter):
        det = detect_centroid(get_frame(), color)
        if det is None:
            if log:
                log(f"v_align iter{i}: 目标丢失")
            return None
        _, v_bc = bottom_center(det)
        if log:
            log(f"v_align iter{i}: v_bc={v_bc:.0f} band={v_band}")
        if v_band[0] <= v_bc <= v_band[1]:
            return det
        want_up = v_bc > v_band[1]   # 底边太低（贴底）→ 需 v 减小
        if v_sign is None:
            probe = 0.003
            if cartesian_jog(dx=probe, duration=2.0, pitch_deg=pitch_deg) is None:
                return None
            det2 = detect_centroid(get_frame(), color)
            if det2 is None:
                return None
            dv = bottom_center(det2)[1] - v_bc
            v_sign = 1.0 if dv > 0 else -1.0
            if log:
                log(f"v_align: 方向探测 +3mm → dv={dv:+.1f}，v_sign={v_sign:+.0f}")
            continue
        dx = (-0.004 if want_up else 0.004) * v_sign
        if cartesian_jog(dx=dx, duration=2.0, pitch_deg=pitch_deg) is None:
            return None
    return None


def descend_to_grasp(color: str, z_floor: float = 0.005, step: float = 0.004,
                     max_steps: int = 12, pitch_deg: float = 80.0, log=None):
    """分段下降：每步 4mm，降后 u 重对准。停止：z<=floor 或 bbox 底边贴底裁切。
    返回最终 (pos, det)；异常返回 None。"""
    for i in range(max_steps):
        pos, _ = get_current_pose()
        det = detect_centroid(get_frame(), color)
        if det is not None:
            _, v_bc = bottom_center(det)
            if log:
                log(f"descend iter{i}: z={pos[2]*1000:.0f}mm v_bc={v_bc:.0f}")
            if v_bc >= 479:
                if log:
                    log("descend: bbox 贴底裁切，到位")
                return pos, det
        else:
            if log:
                log(f"descend iter{i}: z={pos[2]*1000:.0f}mm 目标被遮挡/丢失（可能已入夹）")
            return pos, None
        if pos[2] <= z_floor:
            if log:
                log("descend: 到达 z 下限，到位")
            return pos, det
        if cartesian_jog(dz=-step, duration=2.0, pitch_deg=pitch_deg) is None:
            if log:
                log(f"descend iter{i}: jog 失败（到底或 IK 无解）")
            return pos, det
        # 每步降完重对 u（可靠通道）
        u_align(color, max_iter=3, pitch_deg=pitch_deg, log=log)
    return None


def advance_to_grasp(color: str, u_target: float = 287.0, v_trigger: float = 380.0,
                     max_steps: int = 18, step_x: float = 0.015,
                     pitch_deg: float = 87.0, z_min: float = -0.025, log=None):
    """前进逼近：每步 +x 15mm + u 重对准，直到 bbox 底边 v_bc >= v_trigger。
    实测特性：此几何下前进时 z 自然下降至桌面；v 响应弱但单调（近距加速）。
    返回最终 (pos, det)；失败返回 None。"""
    for i in range(max_steps):
        det = detect_centroid(get_frame(), color)
        if det is None:
            if log:
                log(f"advance iter{i}: 目标丢失/被遮挡（可能已入夹指上方）")
            pos, _ = get_current_pose()
            return pos, None
        pos, _ = get_current_pose()
        _, v_bc = bottom_center(det)
        if log:
            log(f"advance iter{i}: x={pos[0]:.3f} z={pos[2]:.3f} u={det['u']:.0f} "
                f"v_bc={v_bc:.0f} area={det['area']:.0f}")
        if v_bc >= v_trigger:
            return pos, det
        if pos[2] <= z_min:
            if log:
                log(f"advance iter{i}: z 到下限 {z_min}，停止前进")
            return pos, det
        if cartesian_jog(dx=step_x, duration=2.5, pitch_deg=pitch_deg) is None:
            if log:
                log(f"advance iter{i}: jog 失败")
            return None
        u_align(color, u_target=u_target, max_iter=3, pitch_deg=pitch_deg, log=log)
    return None


# ---------------- J1 扫描与旋转对准 ----------------

def j1_set(pulse: int, duration: float = 1.5):
    """单动 J1（其余关节保持当前 goal）。"""
    states = get_servo_states()
    pulses = [states[j]["goal"] for j in ARM_IDS]
    pulses[0] = int(pulse)
    move_joints_pulses(pulses, duration=duration)


def scan_for_color(color: str, lo: int = 200, hi: int = 800, step: int = 60,
                   settle: float = 0.4, log=None):
    """J1 旋转扫描找目标：从中心 500 向两端扩展，每步停 settle 秒检测。
    返回找到时的 det（含当时 J1 位置），整圈找不到返回 None。"""
    states = get_servo_states()
    j1_home = states[1]["goal"]
    # 扫描顺序：中心 → 右 → 左交替扩展
    offsets = [0]
    k = step
    while k <= max(hi - 500, 500 - lo):
        offsets.append(k)
        offsets.append(-k)
        k += step
    for off in offsets:
        target = max(lo, min(hi, 500 + off))
        j1_set(target, duration=1.5)
        rospy.sleep(settle)
        det = detect_centroid(get_frame(), color)
        if log:
            log(f"scan: J1={target} -> {'FOUND u=%.0f v=%.0f area=%.0f' % (det['u'], det['v'], det['area']) if det else 'none'}")
        if det is not None:
            return det
    j1_set(j1_home, duration=1.5)
    return None


def j1_align(color: str, u_target: float = 321.0, tol: float = 12.0,
             max_iter: int = 12, log=None):
    """J1 旋转对准：让目标质心 u → u_target。符号在线探测。"""
    sign = None
    for i in range(max_iter):
        det = detect_centroid(get_frame(), color)
        if det is None:
            if log:
                log(f"j1_align iter{i}: 目标丢失")
            return None
        eu = u_target - det["u"]
        if log:
            log(f"j1_align iter{i}: u={det['u']:.0f} eu={eu:+.0f}")
        if abs(eu) <= tol:
            return det
        j1_now = get_servo_states()[1]["goal"]
        if sign is None:
            j1_set(j1_now + 15, duration=1.0)
            det2 = detect_centroid(get_frame(), color)
            if det2 is None:
                return None
            du = det2["u"] - det["u"]
            sign = 1.0 if du > 0 else -1.0
            if log:
                log(f"j1_align: 方向探测 +15tick → du={du:+.1f}，sign={sign:+.0f}")
            continue
        # eu>0 需 u 增大；du/dtick 符号 = sign。增益实测 ~1.5px/tick（近距更小）
        step = eu * sign / 1.5 * 0.5
        step = max(-40.0, min(40.0, step))
        min_step = 4.0 if abs(eu) < 30 else 8.0   # 接近目标时允许小步，防过冲振荡
        if abs(step) < min_step:
            step = min_step if step > 0 else -min_step
        j1_set(j1_now + int(step), duration=1.0)
    return None


def arm_joint_set(jid: int, pos: int, duration: float = 3.0):
    """单关节到位（自动分步，每步 ≤100 tick）。"""
    import math as _m
    states = get_servo_states()
    pulses = [states[j]["goal"] for j in ARM_IDS]
    idx = ARM_IDS.index(jid)
    cur = pulses[idx]
    n = max(1, _m.ceil(abs(pos - cur) / 100))
    for k in range(1, n + 1):
        pulses[idx] = round(cur + (pos - cur) * k / n)
        move_joints_pulses(list(pulses), duration=max(duration / n, 1.0))
        cur = pulses[idx]


def _wait_subscriber(pub, timeout: float = 5.0):
    """等订阅者连上再发指令（防 master 重启后指令丢给空气）。"""
    t0 = time.time()
    while pub.get_num_connections() == 0 and time.time() - t0 < timeout:
        time.sleep(0.1)


# ---------------- 底盘直进（逼近阶段用） ----------------

def chassis_move(linear_x: float = 0.05, seconds: float = 0.3):
    """底盘直行一小段（限速 0.05m/s 内，时长可控）。
    chassis_controller 有 0.5s cmd 超时自停；先连续发再走零速确保停止。"""
    from geometry_msgs.msg import Twist
    pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
    _wait_subscriber(pub)
    linear_x = max(-0.05, min(0.05, linear_x))
    msg = Twist()
    msg.linear.x = linear_x
    t0 = time.time()
    r = rospy.Rate(10)
    while time.time() - t0 < seconds:
        pub.publish(msg)
        r.sleep()
    pub.publish(Twist())
    rospy.sleep(0.2)


def j1_align_oneshot(color: str, u_target: float = 321.0, log=None):
    """J1 一次性对准：按质心偏差一次算好转角，只动一次（不摇头）。
    增益 ~4px/tick（实测 3.3-5.6，取中；残余误差由宽夹爪容差吸收）。
    符号：本抓取构型实测 J1 脉冲增大 → u 增大。"""
    det = detect_centroid(get_frame(), color)
    if det is None:
        if log:
            log("j1_align_oneshot: 目标丢失")
        return None
    eu = u_target - det["u"]
    delta = int(max(-150, min(150, eu / 4.0)))
    j1_now = get_servo_states()[1]["goal"]
    if log:
        log(f"j1_align_oneshot: u={det['u']:.0f} eu={eu:+.0f} -> J1 {j1_now}+{delta}")
    j1_set(j1_now + delta, duration=max(1.0, abs(delta) / 60.0 + 0.5))
    det2 = detect_centroid(get_frame(), color)
    if log and det2:
        log(f"j1_align_oneshot: after u={det2['u']:.0f}")
    return det2


def chassis_turn(degrees: float, ang_speed: float = 0.3):
    """底盘原地旋转。degrees > 0 = 逆时针（左转），< 0 = 顺时针。
    角速度限 0.4 rad/s，单次 ≤ 3s。"""
    from geometry_msgs.msg import Twist
    degrees = max(-60.0, min(60.0, degrees))
    wz = min(0.4, abs(ang_speed)) * (1 if degrees > 0 else -1)
    seconds = min(abs(degrees) / 57.3 / abs(wz), 3.0)
    pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
    _wait_subscriber(pub)
    msg = Twist()
    msg.angular.z = wz
    t0 = time.time()
    r = rospy.Rate(10)
    while time.time() - t0 < seconds:
        pub.publish(msg)
        r.sleep()
    pub.publish(Twist())
    rospy.sleep(0.3)
