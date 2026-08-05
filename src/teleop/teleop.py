#!/usr/bin/env python3
"""teleop.py — 键盘遥操作主程序

按键：
    ↑/↓/←/→  前/后/左/右 平移（麦轮）
    A / D     左转 / 右转（原地）
    S / X     Joint 2 抬升 / 下降（只动 J2，每按一次 10 tick ≈ 2.4°）
    J / L     夹爪 闭合 / 张开（每按一次 25 tick）
    W         拍照（夹爪相机 + Astra 各一张，存 captures/）
    Q / ESC   退出（自动停车）

机制：20Hz 主循环，每轮排空 stdin 只取最新键；0.3s 无输入自动刹车（deadman）；
退出（含 Ctrl+C / kill）必发零速。
臂/夹爪控制复用 grasping/util_board.py 的安全护栏（跳变/速度/范围钳制）。
"""
import os
import select
import sys
import termios
import time
import tty

import cv2
import numpy as np
import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image

LIN_SPEED = 0.10      # m/s
ANG_SPEED = 0.40      # rad/s
DEADMAN_S = 0.3       # 无输入超时停车
LOOP_HZ = 20

# 臂/夹爪增量（tick）：J2 实测脉冲增大=抬升（300 离地 / 200 贴地）；
# 夹爪脉冲增大=闭合（300 张开 / 540 夹住圆柱）。方向反了改这里。
J2_STEP = 10
J2_MIN, J2_MAX = 100, 400        # 保守软限位，需要更大范围再放宽
GRIP_STEP = 25

# 复用 grasping 的板端硬件接口（本地与板端都是 grasping/ 与 teleop/ 同级）
_ARM_IMPORT_ERR = None
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "grasping"))
    import util_board as ub
except Exception as e:           # 导入失败只禁臂控功能，错误原文打印
    ub = None
    _ARM_IMPORT_ERR = e

GRIPPER_TOPIC = "/gripper_camera/image_raw"
ASTRA_TOPIC = "/astra_camera/rgb/image_raw"
CAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

KEYMAP = {
    "UP":    ( LIN_SPEED, 0.0, 0.0),
    "DOWN":  (-LIN_SPEED, 0.0, 0.0),
    "LEFT":  (0.0,  LIN_SPEED, 0.0),   # 麦轮左平移
    "RIGHT": (0.0, -LIN_SPEED, 0.0),
    "A":     (0.0, 0.0,  ANG_SPEED),   # 左转（CCW）
    "D":     (0.0, 0.0, -ANG_SPEED),
}


class KeyReader:
    """状态化键盘解析：转义序列跨读缓冲切断时不误判。
    ESC 挂起 0.2s 无后续才算退出键；ESC ESC 立即退出。"""

    ARROWS = {b"A": "UP", b"B": "DOWN", b"C": "RIGHT", b"D": "LEFT"}

    def __init__(self, fd):
        self.fd = fd
        self.buf = b""
        self.esc_since = None

    def read_latest(self):
        while select.select([self.fd], [], [], 0)[0]:
            d = os.read(self.fd, 64)
            if not d:
                break
            self.buf += d

        key = None
        i = 0
        while i < len(self.buf):
            b = self.buf[i:i+1]
            if b == b"\x1b":
                if i + 2 < len(self.buf) and self.buf[i+1:i+2] == b"[":
                    arrow = self.ARROWS.get(self.buf[i+2:i+3])
                    if arrow:
                        key = arrow
                        i += 3
                        continue
                if i + 1 < len(self.buf) and self.buf[i+1:i+2] == b"\x1b":
                    key = "ESC"          # ESC ESC = 立即退出
                    i += 2
                    continue
                if i == len(self.buf) - 1:
                    # 落单 ESC：可能是被切断的转义序列开头，挂起等后续
                    if self.esc_since is None:
                        self.esc_since = time.time()
                    elif time.time() - self.esc_since > 0.2:
                        key = "ESC"
                        i += 1
                    break
                i += 1   # ESC + 其他键（Alt 组合），忽略
                continue
            if b in (b"\x03",):          # Ctrl+C 字节
                key = "ESC"
            elif b in (b"w", b"W"):
                key = "W"
            elif b in (b"a", b"A"):
                key = "A"
            elif b in (b"d", b"D"):
                key = "D"
            elif b in (b"s", b"S"):
                key = "S"
            elif b in (b"x", b"X"):
                key = "X"
            elif b in (b"j", b"J"):
                key = "J"
            elif b in (b"l", b"L"):
                key = "L"
            elif b in (b"q", b"Q"):
                key = "Q"
            i += 1
        self.buf = self.buf[i:]
        if key is not None:
            self.esc_since = None
        return key


def read_latest_key(fd, _reader={}):
    """兼容原接口：每个 fd 一个 KeyReader。"""
    if fd not in _reader:
        _reader[fd] = KeyReader(fd)
    return _reader[fd].read_latest()


def joint2_jog(direction):
    """J2 单关节微动：direction=+1 抬升 / -1 下降。其余关节保持当前 goal。
    安全：软限位 J2_MIN..J2_MAX；move_joints_pulses 自带跳变/速度护栏。"""
    if ub is None:
        print(f"\r臂控不可用（util_board 导入失败）：{_ARM_IMPORT_ERR}          ")
        return
    states = ub.get_servo_states()
    cur = states[2]["goal"]
    target = max(J2_MIN, min(J2_MAX, cur + direction * J2_STEP))
    if target == cur:
        print(f"\rJ2 已到软限位 {cur}（{J2_MIN}..{J2_MAX}）          ")
        return
    pulses = [states[j]["goal"] for j in ub.ARM_IDS]
    pulses[ub.ARM_IDS.index(2)] = target
    ub.move_joints_pulses(pulses, duration=0.6, wait=False)
    print(f"\rJ2: {cur} -> {target}          ")


def gripper_jog(direction):
    """夹爪微动：direction=+1 闭合 / -1 张开。gripper_set 自带 200-700 钳制。"""
    if ub is None:
        print(f"\r臂控不可用（util_board 导入失败）：{_ARM_IMPORT_ERR}          ")
        return
    cur = ub.get_servo_states()[ub.GRIPPER_ID]["goal"]
    target = max(ub.GRIPPER_MIN, min(ub.GRIPPER_MAX, cur + direction * GRIP_STEP))
    if target == cur:
        print(f"\r夹爪已到限位 {cur}（{ub.GRIPPER_MIN}..{ub.GRIPPER_MAX}）          ")
        return
    ub.gripper_set(target, duration=1.0, wait=False)
    print(f"\r夹爪: {cur} -> {target}          ")


def capture(pub_note):
    """两相机各拍一张，时间戳命名。"""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    ok = []
    for topic, name in [(GRIPPER_TOPIC, "gripper"), (ASTRA_TOPIC, "astra")]:
        try:
            msg = rospy.wait_for_message(topic, Image, timeout=2.0)
            ch = 3 if msg.encoding in ("bgr8", "rgb8") else 1
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, ch)
            path = os.path.join(CAP_DIR, f"{stamp}_{name}.jpg")
            cv2.imwrite(path, arr)
            ok.append(f"{name}✓")
        except Exception as e:
            ok.append(f"{name}✗({e})")
    print(f"\r📷 {stamp} {' '.join(ok)}          ")


def main():
    os.makedirs(CAP_DIR, exist_ok=True)
    rospy.init_node("teleop", anonymous=True)
    pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
    t0 = time.time()
    while pub.get_num_connections() == 0 and time.time() - t0 < 5.0:
        time.sleep(0.1)   # 等 chassis_controller 连上，防止指令丢给空气

    # 优雅退出：SIGTERM/SIGHUP（kill、终端关闭）→ 走 finally 刹车退出
    import signal as _sig
    def _on_sig(s, _f):
        rospy.signal_shutdown(f"signal {s}")
    _sig.signal(_sig.SIGTERM, _on_sig)
    _sig.signal(_sig.SIGHUP, _on_sig)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)   # 无缓冲逐字节读

    current = (0.0, 0.0, 0.0)
    last_key_time = 0.0
    print("teleop 就绪：方向键=平移  A/D=旋转  S/X=J2升/降  J/L=夹爪闭/开  W=拍照  Q/ESC=退出")
    if ub is None:
        print(f"⚠ 臂控不可用（util_board 导入失败）：{_ARM_IMPORT_ERR}")
    try:
        rate = rospy.Rate(LOOP_HZ)
        while not rospy.is_shutdown():
            key = read_latest_key(fd)
            if key in ("Q", "ESC"):
                break
            if key == "W":
                capture(pub)
            elif key == "S":
                joint2_jog(+1)
            elif key == "X":
                joint2_jog(-1)
            elif key == "J":
                gripper_jog(+1)
            elif key == "L":
                gripper_jog(-1)
            elif key in KEYMAP:
                current = KEYMAP[key]
                last_key_time = time.time()

            if time.time() - last_key_time > DEADMAN_S:
                current = (0.0, 0.0, 0.0)

            msg = Twist()
            msg.linear.x, msg.linear.y, msg.angular.z = current
            pub.publish(msg)
            rate.sleep()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        pub.publish(Twist())   # 退出必刹车
        print("\nteleop 退出，底盘已停车")


if __name__ == "__main__":
    main()
