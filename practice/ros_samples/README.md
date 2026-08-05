# ROS1 talker/listener · 上板练习指引

> 对应官方文档《2-ROS开发/01-ROS1快速入门.md》。这是"三个官方样例"中的**第三个**。
> ⚠️ **今天跑不了**：需要板端 ROS1 运行时（roscore + rospy），PC 上没装也不该装。
> 今天的任务 = **读懂代码**；8/4 上板后 = 按本文件步骤实跑。
> 前两个样例（Dora 定时器、Dora 传感器+滤波）已在 PC 完成 ✅（见 `practice/dora_samples/`）。

## 这个例子是什么

ROS 世界的 Hello World：**发布者/订阅者**模型——

- `talker.py`：每秒往 `/chatter` 话题发布 `Hello, M-Robots! [n]`
- `listener.py`：订阅 `/chatter`，收到就打印
- 中间靠 `roscore`（Master）做注册中心：talker 和 listener 互不认识，都向 Master 登记，由 Master 牵线

## 今天：读懂代码（10 分钟）

对照 Dora 样例理解差异（这是两种节点模型）：

| | Dora 节点 | ROS 节点 |
|---|---|---|
| 触发方式 | 外部事件驱动（timer/上游输入） | 自带循环（`rospy.Rate`）或回调（`rospy.spin`） |
| 数据通道 | dataflow.yml 接线，Arrow 格式 | 话题（topic）发布/订阅，消息类型（`std_msgs/String`） |
| 注册中心 | Dora daemon（`dora up`） | ROS Master（`roscore`） |
| 进程数 | 一条 dataflow 可含多节点 | 每节点一进程 + roscore |

自查问题：
1. talker 和 listener 是靠什么"对上号"的？（同一个话题名 `/chatter` + 同一个消息类型 `String`）
2. `rospy.Rate(1)` 和 Dora 的 `dora/timer/millis/1000` 是不是一回事？（效果类似，机制不同：一个在进程内 sleep，一个由外部定时器触发）
3. 为什么 listener 里最后是 `rospy.spin()` 而不是 while 循环？（回调模型：spin 阻塞等消息，来了走 callback）

## 8/4 上板：实跑步骤

### 0. 前置验证（ROS1 运行时在不在）

```bash
hdc shell
mount -o remount,rw /
run rosversion -d                          # 预期 noetic；失败说明运行时没装→走应急预案
run python3 -c "import rospy; print('ROS is ready')"
```

### 1. 推文件（本目录三个文件）

```bash
hdc file send talker.py listener.py dataflow_ros.yml /data/local/robot/
```

### 2. 跑法 A：经典三终端（先理解原始形态）

```bash
# 终端1：hdc shell → run roscore
# 终端2：hdc shell → run python3 /data/local/robot/talker.py
# 终端3：hdc shell → run python3 /data/local/robot/listener.py
```

✅ 验收：终端2 打印 `[INFO] Hello, M-Robots! [0] [1]...`，终端3 同步打印 `receive:Hello, M-Robots! [0]...`

再开终端4 玩两个命令：`run rosnode list`、`run rosnode info /talker`
停止：各终端 `Ctrl+Z`，或 `run rosnode kill -a`

### 3. 跑法 B：Dora 统一管理（进阶，比赛时的推荐形态）

```bash
run roscore &          # 后台
run dora up
run dora start /data/local/robot/dataflow_ros.yml
run dora list && run dora logs <id>
```

✅ 验收：一条 dora 命令拉起两个 ROS 节点，日志里 talker/listener 输出交替出现。
📌 这就是比赛时你的感知节点（rospy 订阅图像话题）被 dataflow 管理的形态。

## 排障

| 现象 | 处理 |
|---|---|
| `import rospy` 报 No module | ①没加 `run` 前缀 ②ROS1 运行时没装（找主办方/走应急预案） |
| 混用成 rclpy | ROS1 用 `rospy`，ROS2 才用 `rclpy`，别串 |
| listener 收不到 | 确认 roscore 在跑、三个终端在同一台板子、话题名一致 |
| hilog 报错 Exec format | 你在 source 过 ros 环境的 shell 里跑了 hilog——换干净 shell |
