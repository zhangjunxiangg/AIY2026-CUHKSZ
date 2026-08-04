#!/usr/bin/env python3
"""ROS1 listener 示例：订阅 chatter 话题并打印。"""

import rospy
from std_msgs.msg import String


def callback(msg):
    print(f"[listener] receive: {msg.data}")


def main():
    rospy.init_node("listener", anonymous=True)
    rospy.Subscriber("chatter", String, callback)
    rospy.spin()


if __name__ == "__main__":
    main()
