#!/usr/bin/env python3
import os
import time

import cv2
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import CompressedImage, Image


INPUT_TOPIC = os.environ.get("GEMINI_COLOR_TOPIC", "/aux_camera/color/image_raw")
OUTPUT_TOPIC = os.environ.get(
    "GEMINI_COMPRESSED_COLOR_TOPIC", "/aux_camera/color/image_raw/compressed"
)
QUALITY = int(os.environ.get("GEMINI_JPEG_QUALITY", "75"))
MAX_FPS = float(os.environ.get("GEMINI_COMPRESSED_MAX_FPS", "5"))


class CompressedColorPublisher:
    def __init__(self):
        self.bridge = CvBridge()
        self.publisher = rospy.Publisher(OUTPUT_TOPIC, CompressedImage, queue_size=1)
        self.minimum_period = 1.0 / max(MAX_FPS, 0.1)
        self.last_publish = 0.0
        self.subscriber = rospy.Subscriber(
            INPUT_TOPIC, Image, self.on_image, queue_size=1, buff_size=4 * 1024 * 1024
        )

    def on_image(self, message):
        now = time.monotonic()
        if now - self.last_publish < self.minimum_period:
            return
        self.last_publish = now
        image = self.bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        ok, encoded = cv2.imencode(
            ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), QUALITY]
        )
        if not ok:
            rospy.logwarn_throttle(5.0, "Gemini color JPEG encoding failed")
            return
        output = CompressedImage()
        output.header = message.header
        output.format = "jpeg"
        output.data = encoded.tobytes()
        self.publisher.publish(output)


def main():
    rospy.init_node("gemini335_compressed_color", anonymous=False)
    CompressedColorPublisher()
    rospy.spin()


if __name__ == "__main__":
    main()
