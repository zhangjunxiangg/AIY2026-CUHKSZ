# ROS1 talker/listener Demo 运行记录

> 运行时间：2026-08-04  
> 板端目标：`ec29004133314d38433031a523403c00`  
> 运行目录：`/data/local/robot`

## 环境要点

- 板端 ROS1 运行时使用 `run` 命令启动（`run roscore`、`run python3 ...`）。
- `run` 包装器会自动设置 `PYTHONHOME`、`LD_LIBRARY_PATH`、`ROS_PACKAGE_PATH` 等环境变量，无需手动 source `/data/local/release/usr/setup.sh`。
- 如果直接用 `python3` 而不带 `run`，会出现 `libpython3.12.so` / `libintl.so` 符号找不到的错误；解决方案是设置 `LD_LIBRARY_PATH` 与 `LD_PRELOAD`，或者直接使用 `run`。

## 文件

- `prep/demo代码/talker.py`
- `prep/demo代码/listener.py`

## 运行结果

```text
--- start roscore ---
--- rosnode list ---
/rosout
--- start talker ---
--- start listener (5s) ---
[listener] receive: Hello M-Robots 6
[listener] receive: Hello M-Robots 4
[listener] receive: Hello M-Robots 7
[listener] receive: Hello M-Robots 5
[listener] receive: Hello M-Robots 8
[listener] receive: Hello M-Robots 6
[listener] receive: Hello M-Robots 9
[listener] receive: Hello M-Robots 7
[listener] receive: Hello M-Robots 10
--- rosnode list ---
/rosout
/talker_13692_1785831085579
/talker_14084_1785831178642
```

状态：✅ listener 持续打印 `receive: Hello M-Robots N`，`rosnode list` 可见 talker 节点。

## 命令速查

```shell
# 开发机推送
cp prep/demo代码/talker.py prep/demo代码/listener.py .
hdc -t <target> file send talker.py data/local/robot/
hdc -t <target> file send listener.py data/local/robot/

# 板端运行
cd /data/local/robot
run roscore &
run python3 talker.py &
run python3 listener.py

# 停止
run rosnode kill -a
pkill -f roscore
```
