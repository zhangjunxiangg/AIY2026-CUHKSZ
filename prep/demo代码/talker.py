#!/usr/bin/env python3
"""ROS1 talker 示例：循环发布 'Hello M-Robots'。"""

import rospy
from std_msgs.msg import String


def main():
    rospy.init_node("talker", anonymous=True)
    pub = rospy.Publisher("chatter", String, queue_size=10)
    rate = rospy.Rate(1)  # 1 Hz
    count = 0

    while not rospy.is_shutdown():
        count += 1
        msg = f"Hello M-Robots {count}"
        print(f"[talker] {msg}")
        pub.publish(msg)
        rate.sleep()


if __name__ == "__main__":
    main()
