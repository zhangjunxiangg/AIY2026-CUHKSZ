#!/usr/bin/env python3
"""Decode QR/AprilTag and report red/blue rectangle centers with depth."""

import math
import time

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs import point_cloud2
from sensor_msgs.msg import CameraInfo, Image, PointCloud2


def median_depth(depth, cx, cy, radius=7):
    h, w = depth.shape[:2]
    x0, x1 = max(0, int(cx) - radius), min(w, int(cx) + radius + 1)
    y0, y1 = max(0, int(cy) - radius), min(h, int(cy) + radius + 1)
    values = depth[y0:y1, x0:x1]
    values = values[np.isfinite(values) & (values > 0) & (values < 10000)]
    return float(np.median(values)) if values.size else float("nan")


def cloud_xyz(cloud, cx, cy, radius=10):
    if cloud.height <= 1 or cloud.width <= 1:
        return None
    uvs = []
    for y in range(max(0, int(cy) - radius), min(cloud.height, int(cy) + radius + 1), 2):
        for x in range(max(0, int(cx) - radius), min(cloud.width, int(cx) + radius + 1), 2):
            uvs.append((x, y))
    points = list(point_cloud2.read_points(cloud, field_names=("x", "y", "z"),
                                           skip_nans=True, uvs=uvs))
    if not points:
        return None
    values = np.asarray(points, dtype=np.float32)
    values = values[np.isfinite(values).all(axis=1) & (values[:, 2] > 0.1) & (values[:, 2] < 4.0)]
    if not values.size:
        return None
    # The nearest quartile suppresses background pixels around a small object.
    limit = np.percentile(values[:, 2], 35)
    foreground = values[values[:, 2] <= limit]
    return np.median(foreground, axis=0)


def find_color(frame, name, ranges):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in ranges:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, np.array(lower), np.array(upper)))
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
    candidates = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < 120.0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        candidates.append((area, x, y, w, h))
    return sorted(candidates, reverse=True)


rospy.init_node("scene_detect_once", anonymous=True, disable_signals=True)
bridge = CvBridge()
rgb_msg = rospy.wait_for_message("/astra_camera/rgb/image_raw", Image, timeout=10.0)
depth_msg = rospy.wait_for_message("/astra_camera/depth/image_raw", Image, timeout=10.0)
info = rospy.wait_for_message("/astra_camera/depth/camera_info", CameraInfo, timeout=10.0)
cloud = rospy.wait_for_message("/astra_camera/depth/points", PointCloud2, timeout=10.0)
frame = bridge.imgmsg_to_cv2(rgb_msg, "bgr8")
depth = np.asarray(bridge.imgmsg_to_cv2(depth_msg, "passthrough"))

print("FRAME=%dx%d DEPTH=%dx%d CLOUD=%dx%d fields=%s" % (
    frame.shape[1], frame.shape[0], depth.shape[1], depth.shape[0],
    cloud.width, cloud.height, ",".join(field.name for field in cloud.fields)
))
hsv_debug = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
for label, px, py in (("TAG", 402, 315), ("RED_OBJECT", 418, 389), ("BLUE_OBJECT", 466, 389)):
    if 0 <= px < frame.shape[1] and 0 <= py < frame.shape[0]:
        print("HSV_%s=%s BGR=%s" % (label, hsv_debug[py, px].tolist(), frame[py, px].tolist()))

qr_value, qr_points, _ = cv2.QRCodeDetector().detectAndDecode(frame)
if qr_points is not None:
    points = np.asarray(qr_points).reshape(-1, 2).astype(int)
    cv2.polylines(frame, [points], True, (255, 255, 0), 2)
    center = points.mean(axis=0)
    print("QR_FOUND value=%r center=(%.1f,%.1f)" % (qr_value, center[0], center[1]))
else:
    print("QR_FOUND=NO")

# Small distant tags benefit greatly from a bounded upscale. The current task
# places the marker and blocks in the right side of the image.
tag_roi_origin = (int(frame.shape[1] * 0.48), int(frame.shape[0] * 0.48))
tag_roi = frame[tag_roi_origin[1]:int(frame.shape[0] * 0.78), tag_roi_origin[0]:int(frame.shape[1] * 0.78)]
tag_roi_up = cv2.resize(tag_roi, None, fx=5.0, fy=5.0, interpolation=cv2.INTER_CUBIC)
roi_qr_value, roi_qr_points, _ = cv2.QRCodeDetector().detectAndDecode(tag_roi_up)
if roi_qr_points is not None:
    center = np.asarray(roi_qr_points).reshape(-1, 2).mean(axis=0) / 5.0 + np.asarray(tag_roi_origin)
    print("QR_UPSCALED_FOUND value=%r center=(%.1f,%.1f)" % (roi_qr_value, center[0], center[1]))
else:
    print("QR_UPSCALED_FOUND=NO")

tag_found = False
aruco = cv2.aruco
for label, dictionary_id in (
    ("APRILTAG_36H11", aruco.DICT_APRILTAG_36h11),
    ("ARUCO_4X4_50", aruco.DICT_4X4_50),
    ("ARUCO_5X5_100", aruco.DICT_5X5_100),
):
    dictionary = aruco.Dictionary_get(dictionary_id)
    parameters = aruco.DetectorParameters_create()
    parameters.adaptiveThreshWinSizeMin = 3
    parameters.adaptiveThreshWinSizeMax = 53
    parameters.minMarkerPerimeterRate = 0.015
    corners, ids, _ = aruco.detectMarkers(frame, dictionary, parameters=parameters)
    if ids is None:
        continue
    tag_found = True
    aruco.drawDetectedMarkers(frame, corners, ids)
    for marker_corners, marker_id in zip(corners, ids.flatten()):
        points = marker_corners.reshape(-1, 2)
        center = points.mean(axis=0)
        distance = median_depth(depth, center[0], center[1])
        print("TAG_FOUND family=%s id=%d center=(%.1f,%.1f) depth_mm=%s" % (
            label, marker_id, center[0], center[1], "nan" if math.isnan(distance) else "%.1f" % distance
        ))
if not tag_found:
    for label, dictionary_id in (
        ("APRILTAG_36H11", aruco.DICT_APRILTAG_36h11),
        ("ARUCO_4X4_50", aruco.DICT_4X4_50),
        ("ARUCO_5X5_100", aruco.DICT_5X5_100),
    ):
        dictionary = aruco.Dictionary_get(dictionary_id)
        parameters = aruco.DetectorParameters_create()
        parameters.minMarkerPerimeterRate = 0.008
        corners, ids, _ = aruco.detectMarkers(tag_roi_up, dictionary, parameters=parameters)
        if ids is None:
            continue
        tag_found = True
        for marker_corners, marker_id in zip(corners, ids.flatten()):
            center = marker_corners.reshape(-1, 2).mean(axis=0) / 5.0 + np.asarray(tag_roi_origin)
            print("TAG_UPSCALED_FOUND family=%s id=%d center=(%.1f,%.1f)" % (
                label, marker_id, center[0], center[1]
            ))
    if not tag_found:
        print("TAG_FOUND=NO")

specs = {
    "blue": [((80, 35, 35), (145, 255, 255))],
    "red": [((0, 60, 45), (15, 255, 255)), ((165, 60, 45), (179, 255, 255))],
}
for name, ranges in specs.items():
    candidates = find_color(frame, name, ranges)
    if not candidates:
        print("COLOR_%s=NO" % name.upper())
        continue
    for index, (area, x, y, w, h) in enumerate(candidates[:10]):
        cx, cy = x + w / 2.0, y + h / 2.0
        distance = median_depth(depth, cx, cy)
        xyz = cloud_xyz(cloud, cx, cy)
        print("COLOR_%s_%d area=%.1f box=(%d,%d,%d,%d) center=(%.1f,%.1f) depth_mm=%s" % (
            name.upper(), index, area, x, y, w, h, cx, cy,
            "nan" if math.isnan(distance) else "%.1f" % distance,
        ))
        if xyz is not None:
            print("COLOR_%s_%d_CLOUD xyz_m=(%.3f,%.3f,%.3f)" % (
                name.upper(), index, xyz[0], xyz[1], xyz[2]
            ))
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0) if name == "blue" else (0, 0, 255), 2)
        cv2.putText(frame, name, (x, max(15, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 0, 0) if name == "blue" else (0, 0, 255), 2)

cv2.imwrite("/tmp/scene-detect.jpg", frame)
print("ANNOTATED=/tmp/scene-detect.jpg")
