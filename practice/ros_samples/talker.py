# talker.py —— 每秒发布一条消息到 /chatter 话题
import rospy
from std_msgs.msg import String

def talker():
    rospy.init_node('talker', anonymous=True)
    pub = rospy.Publisher('/chatter', String, queue_size=10)
    rate = rospy.Rate(1)  # 1 Hz
    count = 0

    while not rospy.is_shutdown():
        msg = f"Hello, M-Robots! [{count}]"
        rospy.loginfo(msg)
        pub.publish(msg)
        count += 1
        rate.sleep()

if __name__ == '__main__':
    try:
        talker()
    except rospy.ROSInterruptException:
        pass
