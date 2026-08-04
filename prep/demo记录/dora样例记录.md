# Dora 双节点 Demo 运行记录

> 运行时间：2026-08-04  
> 板端目标：`ec29004133314d38433031a523403c00`（KaihongBoard-3588S-SBC）  
> 运行目录：`/data/local/robot`  
> Dora 版本：`dora-cli 0.3.12`

## 环境要点

- 板端 Python 为 `/data/local/release/usr/bin/python3.12`。
- 运行 Python 节点时必须设置 `LD_PRELOAD=/data/local/release/usr/lib/libpython3.12.so.1.0`，否则 `dora` / `pyarrow` 会因缺少 `_Py_Dealloc` / `Py_DecRef` 等符号而崩溃。
- 数据流 YAML 里的每个节点都配置了该 `LD_PRELOAD` 环境变量。
- `hdc file send` 在此版本上目标路径**不能带前导 `/`**，需写成 `data/local/robot/xxx` 才能正确放到板端。

## 样例一：Hello World（定时器 + 计数）

文件：
- `prep/demo代码/hello_node.py`
- `prep/demo代码/dataflow_hello.yml`

运行结果（节选）：

```text
hello: INFO   daemon    node is ready
INFO   daemon    all nodes are ready, starting dataflow
hello: stdout    [hello_node] Hello M-Robots #1
hello: stdout    [hello_node] Hello M-Robots #2
hello: stdout    [hello_node] Hello M-Robots #3
...
hello: stdout    [hello_node] Hello M-Robots #117
```

状态：✅ 每秒输出 `Hello M-Robots #N`，count 递增。

## 样例二：Sensor 5Hz + Filter 滑动平均

文件：
- `prep/demo代码/sensor_node.py`
- `prep/demo代码/filter_node.py`
- `prep/demo代码/dataflow_sensor.yml`

运行结果（节选）：

```text
filter: INFO   daemon    node is ready
sensor: INFO   daemon    node is ready
INFO   daemon    all nodes are ready, starting dataflow
sensor: stdout    [sensor_node] raw=48.02
filter: stdout    [filter_node] raw=48.02 smoothed=48.02 (window=1)
sensor: stdout    [sensor_node] raw=43.46
filter: stdout    [filter_node] raw=43.46 smoothed=45.74 (window=2)
sensor: stdout    [sensor_node] raw=37.84
filter: stdout    [filter_node] raw=37.84 smoothed=43.11 (window=3)
sensor: stdout    [sensor_node] raw=51.88
filter: stdout    [filter_node] raw=51.88 smoothed=45.30 (window=4)
sensor: stdout    [sensor_node] raw=47.60
filter: stdout    [filter_node] raw=47.60 smoothed=45.76 (window=5)
sensor: stdout    [sensor_node] raw=46.32
filter: stdout    [filter_node] raw=46.32 smoothed=45.42 (window=5)
...
sensor: stdout    [sensor_node] raw=62.31
filter: stdout    [filter_node] raw=62.31 smoothed=48.59 (window=5)
```

状态：✅ sensor 以 5Hz 输出模拟读数，filter 接收后做 5 点滑动平均，`smoothed` 随窗口填满而稳定收敛。

## 命令速查

```shell
# 开发机推送（注意目标路径不带前导 /）
hdc -t <target> file send hello_node.py data/local/robot/
hdc -t <target> file send sensor_node.py data/local/robot/
hdc -t <target> file send filter_node.py data/local/robot/
hdc -t <target> file send dataflow_hello.yml data/local/robot/
hdc -t <target> file send dataflow_sensor.yml data/local/robot/

# 板端运行
export LD_PRELOAD=/data/local/release/usr/lib/libpython3.12.so.1.0
export PATH=/data/local/release/usr/bin:/data/local/release/bin:$PATH
. /data/local/release/usr/setup.sh
cd /data/local/robot

dora up
dora start dataflow_hello.yml     # 前台运行，Ctrl+C 停止
dora start dataflow_sensor.yml    # 前台运行
dora list
dora check
dora stop <dataflow-uuid>
dora destroy
```
