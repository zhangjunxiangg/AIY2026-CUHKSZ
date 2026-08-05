"""mini-dora 本地运行器：读 dataflow.yml，把每个节点脚本跑在独立线程里。

用法（在 practice/dora_samples 目录下）：
    python mini_dora.py dataflow_hello.yml 5      # 跑样例一 5 秒
    python mini_dora.py dataflow_sensor.yml 5     # 跑样例二 5 秒

对应板上真环境（8/4 上板后）：
    run dora up && run dora start /data/local/robot/dataflow.yml
"""
import os
import runpy
import sys
import threading
import time

import yaml

import dora  # 同目录的本地桩


def main(yml_path, seconds=6):
    base = os.path.dirname(os.path.abspath(yml_path))
    with open(yml_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # 先注册、再接线（避免节点未订阅时消息丢失），最后才启动线程
    for n in spec["nodes"]:
        dora._register(n["id"])
    for n in spec["nodes"]:
        for input_id, src in (n.get("inputs") or {}).items():
            dora._subscribe(n["id"], input_id, src)

    for n in spec["nodes"]:
        script = os.path.join(base, os.path.basename(n["path"]))

        def go(name=n["id"], path=script):
            dora._CURRENT.name = name
            runpy.run_path(path, run_name="__main__")

        threading.Thread(target=go, daemon=True).start()

    print(f"[mini-dora] dataflow started ({yml_path}), running {seconds}s ...")
    time.sleep(seconds)
    print("[mini-dora] stopped")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dataflow.yml",
         int(sys.argv[2]) if len(sys.argv) > 2 else 6)
