"""本地 mini-dora 桩（仅用于 PC 练习，板上请删除/忽略本文件，用真 dora）。

作用：Windows 上 dora-rs 只有 Python API（dora.pyd）没有命令行守护进程，
本桩实现 dora 的两件核心事，让官方样例节点**原封不动**在 PC 跑起来：
  1. 定时器输入（dora/timer/millis/N）
  2. 节点间消息路由（A 节点的输出 → B 节点的输入）
官方样例里的 `from dora import Node` 会优先命中本文件（同目录优先于 site-packages）。
"""
import queue
import threading
import time

_NODE_QUEUES = {}   # node_name -> 输入事件队列
_BUS = {}           # (src_node, output_id) -> [(输入队列, input_id), ...]
_CURRENT = threading.local()


def _register(node_name):
    _NODE_QUEUES[node_name] = queue.Queue()


def _subscribe(node_name, input_id, source):
    q = _NODE_QUEUES[node_name]
    if source.startswith("dora/timer/millis/"):
        period = int(source.rsplit("/", 1)[1]) / 1000.0

        def tick():
            while True:
                time.sleep(period)
                q.put({"type": "INPUT", "id": input_id})

        threading.Thread(target=tick, daemon=True).start()
    else:
        src_node, out_id = source.split("/", 1)
        _BUS.setdefault((src_node, out_id), []).append((q, input_id))


class Node:
    """与板上 dora.Node 同形：迭代取事件、send_output 发数据。"""

    def __init__(self):
        self.name = _CURRENT.name
        self._q = _NODE_QUEUES[self.name]

    def __iter__(self):
        return self

    def __next__(self):
        return self._q.get()

    def send_output(self, output_id, value):
        for q, in_id in _BUS.get((self.name, output_id), []):
            q.put({"type": "INPUT", "id": in_id, "value": value})
