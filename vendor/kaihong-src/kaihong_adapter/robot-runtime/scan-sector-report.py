#!/usr/bin/env python3
import math
import numpy as np
import rospy
from sensor_msgs.msg import LaserScan

rospy.init_node("scan_sector_report", anonymous=True, disable_signals=True)
scan = rospy.wait_for_message("/scan", LaserScan, timeout=8.0)
print("SCAN_POINTS=%d range=(%.2f,%.2f)" % (len(scan.ranges), scan.range_min, scan.range_max))
for center_deg in range(-180, 180, 30):
    center = math.radians(center_deg)
    values = []
    for index, distance in enumerate(scan.ranges):
        angle = scan.angle_min + index * scan.angle_increment
        delta = (angle - center + math.pi) % (2.0 * math.pi) - math.pi
        if abs(delta) <= math.radians(12) and math.isfinite(distance) and scan.range_min <= distance <= scan.range_max:
            values.append(distance)
    if values:
        values = np.asarray(values)
        print("SECTOR_%+04d count=%d min=%.3f p10=%.3f median=%.3f" % (
            center_deg, values.size, values.min(), np.percentile(values, 10), np.median(values)
        ))
    else:
        print("SECTOR_%+04d count=0 clear_or_no_return" % center_deg)
