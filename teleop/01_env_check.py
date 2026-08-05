#!/usr/bin/env python3
"""01_env_check.py — teleop 环境 gate

检查项：
1. termios/select 模块可用（键盘 raw 输入的前提）
2. stdin 是否 TTY（hdc/ssh 交互终端才支持实时键盘）
3. ROS 话题在线：/cmd_vel、/gripper_camera/image_raw、/astra_camera/rgb/image_raw
4. 两个相机各取一帧并存盘成功
5. 舵机状态在线：servo_states 话题有数据，且臂 1-5 + 夹爪 10 全部在列（S/X/J/L 键的前提）
"""
import os
import sys

import rospy

LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "01_env_check")


def main():
    os.makedirs(LOGS, exist_ok=True)
    failures = []

    def gate(name, ok, detail=""):
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
        if not ok:
            failures.append(name)

    # 1. 模块
    try:
        import termios, tty, select  # noqa
        gate("modules_termios_select", True)
    except ImportError as e:
        gate("modules_termios_select", False, str(e))

    # 2. stdin TTY
    gate("stdin_is_tty", sys.stdin.isatty(),
         "（非 TTY 时键盘实时输入不可用；请在 hdc shell / ssh 交互终端运行）")

    # 3. ROS 话题
    rospy.init_node("teleop_env_check", anonymous=True)
    from sensor_msgs.msg import Image
    for topic, name in [("/gripper_camera/image_raw", "gripper_cam"),
                        ("/astra_camera/rgb/image_raw", "astra_cam")]:
        try:
            msg = rospy.wait_for_message(topic, Image, timeout=5.0)
            gate(f"topic_{name}", True, f"{msg.width}x{msg.height}")
        except Exception as e:
            gate(f"topic_{name}", False, str(e))

    # 4. 取帧存盘
    import cv2
    import numpy as np
    cap_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")
    os.makedirs(cap_dir, exist_ok=True)
    for topic, name in [("/gripper_camera/image_raw", "gripper"),
                        ("/astra_camera/rgb/image_raw", "astra")]:
        try:
            msg = rospy.wait_for_message(topic, Image, timeout=5.0)
            ch = 3 if msg.encoding in ("bgr8", "rgb8") else 1
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, ch)
            path = os.path.join(cap_dir, f"envcheck_{name}.jpg")
            cv2.imwrite(path, arr)
            gate(f"capture_{name}", os.path.exists(path) and os.path.getsize(path) > 10000,
                 f"{path} {os.path.getsize(path)}B encoding={msg.encoding}")
        except Exception as e:
            gate(f"capture_{name}", False, str(e))

    # 5. 舵机状态在线（S/X/J/L 键的前提：臂 1-5 + 夹爪 10 都在 servo_states 里）
    try:
        from servo_msgs.msg import ServoStateList
        msg = rospy.wait_for_message("/servo_controllers/port_id_1/servo_states",
                                     ServoStateList, timeout=5.0)
        ids = sorted(s.id for s in msg.servo_states)
        need = [1, 2, 3, 4, 5, 10]
        missing = [i for i in need if i not in ids]
        gate("servo_states_online", not missing,
             f"在线={ids}" + (f" 缺={missing}" if missing else ""))
    except Exception as e:
        gate("servo_states_online", False, str(e))

    status = "FAIL " + ",".join(failures) if failures else "PASS"
    with open(os.path.join(LOGS, "STATUS.txt"), "w") as f:
        f.write(status + "\n")
    print("STATUS:", status)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
