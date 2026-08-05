import pyarrow as pa
from dora import Node

node = Node()
count = 0

for event in node:
    if event["type"] == "INPUT" and event["id"] == "tick":
        count += 1
        print(f"[#{count}] Hello, M-Robots!")
        node.send_output("count", pa.array([count]))
