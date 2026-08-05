#!/usr/bin/env python3
"""car_move.py — 底盘移动 CLI（麦轮，支持任意方向）

用法（板端，在 /data/local/grasping 下）：
    sh run_step.sh car_move.py forward 0.10     # 前进 10cm
    sh run_step.sh car_move.py back 0.05        # 后退 5cm
    sh run_step.sh car_move.py left 0.10        # 左平移 10cm（麦轮横移）
    sh run_step.sh car_move.py right 0.10       # 右平移 10cm
    sh run_step.sh car_move.py turn 30          # 原地逆时针转 30°（负数=顺时针）
    sh run_step.sh car_move.py raw 0.05 0 0 1.0 # 原始模式：vx vy wz 秒

方向约定（cmd_vel / 右手系，俯视）：
    linear.x  + = 前进      linear.y  + = 左移      angular.z + = 逆时针
安全：速度限 ±0.10 m/s（调试档），角速度限 ±0.4 rad/s，单次 ≤ 5s。
"""
import sys
import time

import rospy
from geometry_msgs.msg import Twist

LIN_SPEED = 0.05      # m/s（慢速调试档）
ANG_SPEED = 0.30      # rad/s


def publish_for(pub, vx, vy, wz, seconds):
    msg = Twist()
    msg.linear.x = vx
    msg.linear.y = vy
    msg.angular.z = wz
    t0 = time.time()
    r = rospy.Rate(10)
    while time.time() - t0 < seconds:
        pub.publish(msg)
        r.sleep()
    pub.publish(Twist())   # 显式停车
    rospy.sleep(0.2)


def main():
    rospy.init_node("car_move", anonymous=True)
    pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
    rospy.sleep(0.3)

    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]

    if cmd == "raw":
        vx, vy, wz, sec = map(float, sys.argv[2:6])
        vx = max(-0.1, min(0.1, vx))
        vy = max(-0.1, min(0.1, vy))
        wz = max(-0.4, min(0.4, wz))
        sec = min(sec, 5.0)
        publish_for(pub, vx, vy, wz, sec)
        print(f"raw: vx={vx} vy={vy} wz={wz} {sec}s")
        return

    if cmd == "turn":
        deg = float(sys.argv[2])
        sec = min(abs(deg) / 57.3 / ANG_SPEED, 5.0)
        publish_for(pub, 0, 0, ANG_SPEED if deg > 0 else -ANG_SPEED, sec)
        print(f"turn {'CCW' if deg > 0 else 'CW'} {abs(deg)}deg (~{sec:.1f}s)")
        return

    dist = float(sys.argv[2])
    sec = min(abs(dist) / LIN_SPEED, 5.0)
    if cmd in ("forward", "back"):
        vx = LIN_SPEED if cmd == "forward" else -LIN_SPEED
        publish_for(pub, vx, 0, 0, sec)
    elif cmd in ("left", "right"):
        vy = LIN_SPEED if cmd == "left" else -LIN_SPEED
        publish_for(pub, 0, vy, 0, sec)
    else:
        sys.exit(f"未知方向 {cmd}（forward/back/left/right/turn/raw）")
    print(f"{cmd} {dist}m (~{sec:.1f}s @ {LIN_SPEED}m/s)")


if __name__ == "__main__":
    main()
