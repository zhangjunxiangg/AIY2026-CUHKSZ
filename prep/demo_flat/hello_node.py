#!/usr/bin/env python3
"""Dora Hello World 节点：每秒发送一次带递增序号的问候消息。"""

import pyarrow as pa
from dora import Node


def main():
    node = Node()
    count = 0

    for event in node:
        if event is None:
            continue
        if event["type"] == "INPUT" and event["id"] == "tick":
            count += 1
            message = f"Hello M-Robots #{count}"
            print(f"[hello_node] {message}")
            node.send_output("message", pa.array([message]))
        elif event["type"] == "STOP":
            print("[hello_node] stopping")
            break


if __name__ == "__main__":
    main()
