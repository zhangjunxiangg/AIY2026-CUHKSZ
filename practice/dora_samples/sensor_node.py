import pyarrow as pa
import random
from dora import Node

node = Node()

for event in node:
    if event["type"] == "INPUT" and event["id"] == "tick":
        raw = 100.0 + random.gauss(0, 5.0)
        node.send_output("raw_data", pa.array([raw]))
        print(f"[sensor] raw: {raw:.2f}")
