"""Dora 节点包装示例：把颜色检测包成数据流节点（感知节点雏形）。

板上运行方式（dora 由 M-Robots 运行时提供）：
    hdc file send dora_node_example.py color_detect.py /data/local/robot/
    hdc shell
    run dora up
    run dora start /data/local/robot/dataflow.yml

本机没有 dora 包，直接 `python dora_node_example.py` 会走兜底分支：
模拟一个 tick，验证检测核心逻辑能跑。
"""
import json


def detect_once():
    """感知核心：真实场景从相机/ROS 话题取一帧，这里先用合成图演示。"""
    from color_detect import detect_colors, make_test_scene
    frame = make_test_scene()  # TODO(上板后): 换成相机取帧 / 订阅 ROS 图像话题
    return detect_colors(frame)


def main():
    import pyarrow as pa
    from dora import Node

    node = Node()
    for event in node:
        # timer 输入到点触发一次检测
        if event["type"] == "INPUT" and event["id"] == "tick":
            results = detect_once()
            payload = json.dumps(results)  # 板上日志用英文，别带中文（乱码）
            node.send_output("targets", pa.array([payload]))
            print(f"[perception] {len(results)} targets sent")


if __name__ == "__main__":
    try:
        main()
    except ImportError:
        # 本地兜底：没有 dora，就当手动跑了一个 tick（排障第一步永远先手动跑）
        print("(no dora package locally, simulating one tick)")
        print(json.dumps(detect_once(), ensure_ascii=False))
