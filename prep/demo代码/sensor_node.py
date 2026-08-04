#!/usr/bin/env python3
"""Dora sensor 节点：以 5Hz 产生模拟传感器读数。"""

import random
import pyarrow as pa
from dora import Node


def main():
    node = Node()

    for event in node:
        if event is None:
            continue
        if event["type"] == "INPUT" and event["id"] == "tick":
            # 模拟带噪声的传感器读数（范围 0-100）
            value = 50.0 + random.gauss(0, 10)
            value = max(0.0, min(100.0, value))
            print(f"[sensor_node] raw={value:.2f}")
            node.send_output("raw", pa.array([value], type=pa.float64()))
        elif event["type"] == "STOP":
            print("[sensor_node] stopping")
            break


if __name__ == "__main__":
    main()
