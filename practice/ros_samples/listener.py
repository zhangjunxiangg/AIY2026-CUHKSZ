# listener.py —— 订阅 /chatter 话题并打印收到的消息
import rospy
from std_msgs.msg import String

def callback(msg):
    rospy.loginfo(f"receive:{msg.data}")

def listener():
    rospy.init_node('listener', anonymous=True)
    rospy.Subscriber('/chatter', String, callback)
    rospy.spin()  # 保持节点运行，等待消息

if __name__ == '__main__':
    listener()
