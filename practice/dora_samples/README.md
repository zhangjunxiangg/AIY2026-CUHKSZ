# Dora 节点开发样例 · 分步练习指引

> 对应官方文档《3-DORA开发/01-节点开发样例.md》的两个样例。
> 本目录文件已就位并经本地验证。**你来动手，照步骤做**，每步有验收标准和自查问题。
> 原理：板上用真 Dora（`run dora up/start`）；PC 上用本目录的 `dora.py`（mini-dora 桩）+ `mini_dora.py`（运行器）模拟同样的行为——节点代码和 dataflow.yml 与官方**一字不差**，上板直接复用。

## 文件清单

| 文件 | 作用 | 来源 |
|---|---|---|
| `hello_node.py` | 样例一：定时器节点 | 官方样例，原样 |
| `sensor_node.py` / `filter_node.py` | 样例二：传感器+滤波 | 官方样例，原样 |
| `dataflow_hello.yml` / `dataflow_sensor.yml` | 两个数据流编排 | 官方样例，原样 |
| `dora.py` | mini-dora 桩（仅 PC 用，**别推上板**） | 本地模拟 |
| `mini_dora.py` | 本地运行器（仅 PC 用） | 本地模拟 |

---

## 步骤 0：进目录

```bash
cd "C:\Users\15728\Desktop\AIY黑客松\practice\dora_samples"
```

## 步骤 1：跑样例一（定时器 Hello World）

```bash
python mini_dora.py dataflow_hello.yml 5
```

✅ **验收**：每秒一行 `[#1] Hello, M-Robots!` … `[#4]`，5 秒后自动停止。

🔍 **自查**（答不出就重读代码）：
1. 节点怎么拿到"每秒一次"的事件？（`dataflow_hello.yml` 里 `tick: dora/timer/millis/1000`）
2. `event["type"]` 和 `event["id"]` 分别判什么？
3. `node.send_output("count", pa.array([count]))` 里 `pa.array` 是什么格式？（Apache Arrow——板上节点间数据传输的统一格式）

## 步骤 2：读懂样例一的两个文件

打开 `hello_node.py`（12 行）和 `dataflow_hello.yml`（7 行），对照回答：

- yml 里 `path: /data/local/robot/hello_node.py` 为什么是这个路径？（板上节点代码统一放 `/data/local/robot/`；本地 mini_dora 会自动映射到本目录同名文件）
- 如果把 `millis/1000` 改成 `millis/200`，会发生什么？（先想答案，再看步骤 4 验证）

## 步骤 3：跑样例二（传感器 + 滤波，双节点串联）

```bash
python mini_dora.py dataflow_sensor.yml 5
```

✅ **验收**：`[sensor] raw: 数字` 与 `[filter] filtered: 数字` 交替出现（约 25 对），且 **filtered 比 raw 波动小**、围绕 100 附近。

🔍 **自查**：
1. filter 节点的输入从哪来？（yml 里 `raw_data: sensor/raw_data`——`节点id/输出id` 的接线写法，**这就是 dataflow 的核心**）
2. `event["value"].to_pylist()[0]` 在做什么？（把 Arrow 数组转回 Python 列表取值）
3. 两节点在板上是两个独立进程，数据靠什么传？（Arrow；在本机是 mini-dora 的队列模拟）

## 步骤 4：改造练习（真正内化的关键）

改完重跑验证，每条都能说出观察到的变化：

- [ ] 把 `dataflow_sensor.yml` 的 `millis/200` 改成 `millis/100` → 输出频率从 5Hz 变 10Hz
- [ ] 把 `filter_node.py` 的 `deque(maxlen=5)` 改成 `maxlen=20` → filtered 更平滑但滞后更明显
- [ ] 给 sensor 的噪声 `random.gauss(0, 5.0)` 改成 `30.0` → 看滤波还压不压得住（理解移动平均的极限）

✅ **验收**：三个变化都能一句话解释原因。

## 步骤 5：对照我的感知节点

打开 `../dora_node_example.py`（之前写好的感知节点雏形），回答：把"timer 触发 → 检测 → send_output 发 JSON"这套结构和今天的样例对比，**一模一样吗？**（一模一样——这就是你感知节点进 dataflow 的写法）

## 步骤 6：上板正式跑（8/4，板子到手后）

把 mini-dora 留在 PC，**只推官方文件**（千万别把 `dora.py` 桩推上板，会盖住真 dora）：

```bash
hdc file send hello_node.py sensor_node.py filter_node.py dataflow_hello.yml dataflow_sensor.yml /data/local/robot/
hdc shell
run dora up
run dora start /data/local/robot/dataflow_hello.yml
run dora list                    # 拿 dataflow ID
run dora logs <id>               # 看 [#1] [#2] ...
run dora stop <id>
run dora start /data/local/robot/dataflow_sensor.yml
run dora logs <id>               # 看 sensor/filter 交替输出
```

✅ **验收**：板上输出与本地一致；`run dora list/logs/stop` 三个命令都亲手用过。

## 排障

| 现象 | 处理 |
|---|---|
| 本地跑没有输出 | 确认在 `dora_samples` 目录里跑；确认 `dora.py` 桩在同目录 |
| 板上节点起不来 | 三板斧：①手动 `run python3 hello_node.py` 看报错 ②`run ldd` 查缺库 ③查 yml 语法/路径 |
| 板上日志看不到 print | `run dora logs <id>`；系统日志 `hilog \| grep Hello`（干净 shell） |
| 节点崩溃刷屏 | Dora 会自动重启节点，先 `run dora stop` 再查 |
