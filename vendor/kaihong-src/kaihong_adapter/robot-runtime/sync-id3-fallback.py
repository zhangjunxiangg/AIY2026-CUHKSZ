#!/usr/bin/env python3
"""Restore ID3's known last commanded position after a controller restart."""

import time

import rospy
from servo_msgs.msg import RawIdPosDur


KNOWN_LAST_POSITION = 38

rospy.init_node("sync_id3_fallback", anonymous=True, disable_signals=True)
publisher = rospy.Publisher(
    "/servo_controllers/port_id_1/id_pos_dur", RawIdPosDur, queue_size=1
)
deadline = time.time() + 5.0
while publisher.get_num_connections() < 1 and time.time() < deadline:
    time.sleep(0.1)
if publisher.get_num_connections() < 1:
    raise RuntimeError("servo command subscriber unavailable")
publisher.publish(RawIdPosDur(id=3, position=KNOWN_LAST_POSITION, duration=2.0))
print("ID3_FALLBACK_SYNC=SENT POSITION=%d" % KNOWN_LAST_POSITION, flush=True)
time.sleep(2.5)
print("ID3_FALLBACK_SYNC=COMPLETE", flush=True)
