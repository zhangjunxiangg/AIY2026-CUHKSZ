#!/usr/bin/env python3
"""Minimal ROS1 LaserScan publisher for an RPLIDAR A1-compatible serial stream.

The board's A1 currently returns standard five-byte measurement nodes but does
not answer the SDK's device-info request.  This node uses only the documented
standard-scan command and keeps the same /scan contract as rplidar_ros.
"""

from __future__ import annotations

import fcntl
import glob
import math
import os
import select
import signal
import struct
import termios
import time
from collections.abc import Iterator

import rospy
from sensor_msgs.msg import LaserScan


VID_PID = ("1a86", "7523")
BAUD = termios.B115200
TIOCMBIC = 0x5417
TIOCMBIS = 0x5416
TIOCM_DTR = 0x002
START_SCAN = b"\xA5\x20"
STOP_SCAN = b"\xA5\x25"
FRAME_ID = "laser"
BIN_COUNT = 360
RANGE_MIN_M = 0.15
RANGE_MAX_M = 12.0


def find_port() -> str:
    requested = rospy.get_param("~serial_port", "")
    candidates = [requested] if requested else sorted(glob.glob("/dev/ttyUSB*"))
    for port in candidates:
        if not port or not os.path.exists(port):
            continue
        tty = os.path.basename(port)
        device = os.path.realpath(f"/sys/class/tty/{tty}/device")
        try:
            with open(os.path.join(device, "..", "..", "idVendor"), encoding="ascii") as stream:
                vid = stream.read().strip()
            with open(os.path.join(device, "..", "..", "idProduct"), encoding="ascii") as stream:
                pid = stream.read().strip()
        except OSError:
            continue
        if (vid, pid) == VID_PID:
            return port
    raise RuntimeError("RPLIDAR CH341 1a86:7523 serial device not found")


def configure_serial(fd: int) -> None:
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = BAUD
    attrs[5] = BAUD
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def set_motor(fd: int, enabled: bool) -> None:
    operation = TIOCMBIC if enabled else TIOCMBIS
    fcntl.ioctl(fd, operation, struct.pack("I", TIOCM_DTR))


def valid_node(node: bytes) -> bool:
    if len(node) != 5:
        return False
    start = node[0] & 0x01
    inverse_start = (node[0] >> 1) & 0x01
    return start != inverse_start and (node[1] & 0x01) == 0x01


def nodes(fd: int) -> Iterator[tuple[bool, float, float, int]]:
    buffer = bytearray()
    last_valid = time.monotonic()
    while not rospy.is_shutdown():
        ready, _, _ = select.select([fd], [], [], 0.5)
        if ready:
            chunk = os.read(fd, 4096)
            if chunk:
                buffer.extend(chunk)
        elif time.monotonic() - last_valid > 5.0:
            raise RuntimeError("no valid RPLIDAR measurement nodes for 5 seconds")
        while len(buffer) >= 5:
            candidate = bytes(buffer[:5])
            if not valid_node(candidate):
                del buffer[0]
                continue
            del buffer[:5]
            last_valid = time.monotonic()
            start = bool(candidate[0] & 0x01)
            quality = candidate[0] >> 2
            angle_q6 = (candidate[1] >> 1) | (candidate[2] << 7)
            angle_deg = angle_q6 / 64.0
            distance_m = ((candidate[3] | (candidate[4] << 8)) / 4.0) / 1000.0
            yield start, angle_deg, distance_m, quality


def publish_scan(
    publisher: rospy.Publisher,
    measurements: list[tuple[float, float, int]],
    scan_time: float,
) -> None:
    ranges = [math.inf] * BIN_COUNT
    intensities = [0.0] * BIN_COUNT
    angle_min = -math.pi
    angle_increment = (2.0 * math.pi) / BIN_COUNT

    for angle_deg, distance_m, quality in measurements:
        angle = math.radians(angle_deg)
        if angle >= math.pi:
            angle -= 2.0 * math.pi
        index = int(round((angle - angle_min) / angle_increment)) % BIN_COUNT
        if RANGE_MIN_M <= distance_m <= RANGE_MAX_M:
            if not math.isfinite(ranges[index]) or distance_m < ranges[index]:
                ranges[index] = distance_m
                intensities[index] = float(quality)

    message = LaserScan()
    message.header.stamp = rospy.Time.now()
    message.header.frame_id = FRAME_ID
    message.angle_min = angle_min
    message.angle_max = math.pi
    message.angle_increment = angle_increment
    message.scan_time = max(0.01, scan_time)
    message.time_increment = message.scan_time / BIN_COUNT
    message.range_min = RANGE_MIN_M
    message.range_max = RANGE_MAX_M
    message.ranges = ranges
    message.intensities = intensities
    publisher.publish(message)


def main() -> int:
    rospy.init_node("rplidar_raw_node", disable_signals=True)
    port = find_port()
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, request_stop)

    publisher = rospy.Publisher("/scan", LaserScan, queue_size=2)
    try:
        configure_serial(fd)
        set_motor(fd, enabled=True)
        os.write(fd, STOP_SCAN)
        time.sleep(0.2)
        termios.tcflush(fd, termios.TCIFLUSH)
        os.write(fd, START_SCAN)
        rospy.loginfo("RPLIDAR raw standard scan started on %s", port)

        current: list[tuple[float, float, int]] = []
        last_angle: float | None = None
        last_boundary = time.monotonic()
        valid_nodes = 0
        for start, angle_deg, distance_m, quality in nodes(fd):
            if stopping or rospy.is_shutdown():
                break
            valid_nodes += 1
            wrapped = last_angle is not None and angle_deg + 30.0 < last_angle
            boundary = start or wrapped
            if boundary and len(current) >= 20:
                now = time.monotonic()
                publish_scan(publisher, current, now - last_boundary)
                current = []
                last_boundary = now
            current.append((angle_deg, distance_m, quality))
            last_angle = angle_deg
            if valid_nodes == 1:
                rospy.loginfo("RPLIDAR raw stream synchronized")
    finally:
        try:
            os.write(fd, STOP_SCAN)
            time.sleep(0.05)
            set_motor(fd, enabled=False)
        except OSError:
            pass
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
