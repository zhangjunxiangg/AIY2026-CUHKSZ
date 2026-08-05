import pyarrow as pa
from collections import deque
from dora import Node

node = Node()
window = deque(maxlen=5)

for event in node:
    if event["type"] == "INPUT" and event["id"] == "raw_data":
        raw = event["value"].to_pylist()[0]
        window.append(raw)
        filtered = sum(window) / len(window)
        node.send_output("filtered_data", pa.array([filtered]))
        print(f"[filter] filtered: {filtered:.2f}")
