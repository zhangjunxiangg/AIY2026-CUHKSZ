#!/usr/bin/env python3
"""Dora filter 节点：对 sensor 节点输出做滑动平均滤波。"""

from collections import deque
import pyarrow as pa
from dora import Node


def main():
    node = Node()
    window = deque(maxlen=5)

    for event in node:
        if event is None:
            continue
        if event["type"] == "INPUT" and event["id"] == "raw":
            values = event["value"].to_pylist()
            raw = float(values[0]) if values else 0.0
            window.append(raw)
            smoothed = sum(window) / len(window)
            print(f"[filter_node] raw={raw:.2f} smoothed={smoothed:.2f} (window={len(window)})")
            node.send_output("smoothed", pa.array([smoothed], type=pa.float64()))
        elif event["type"] == "STOP":
            print("[filter_node] stopping")
            break


if __name__ == "__main__":
    main()
