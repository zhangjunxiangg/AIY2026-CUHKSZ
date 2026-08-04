#!/usr/bin/env python3
import cv2

print("OPENCV_VERSION=%s" % cv2.__version__)
print("QR_CODE_DETECTOR=%s" % hasattr(cv2, "QRCodeDetector"))
print("WECHAT_QR=%s" % hasattr(cv2, "wechat_qrcode_WeChatQRCode"))
print("ARUCO=%s" % hasattr(cv2, "aruco"))
if hasattr(cv2, "aruco"):
    print("APRILTAG_36H11=%s" % hasattr(cv2.aruco, "DICT_APRILTAG_36h11"))
