# M-Robots 开发踩坑与参考库

> 用途：黑客松（8/3–8/6）及后续开发的现场速查手册。内容全部来自 robot_docs 官方文档（14 篇全量阅读）与三路审计发现。
> 更新日期：2026-07-28

---

## 0. 最高优先级：需要提前向深开鸿申请的东西 ⚠️

以下**不是开发板自带**，官方文档明确写"如需使用请向深开鸿申请"。黑客松现场再要就来不及了，务必提前联系（邮箱：M-RobotsOS@kaihong.com 或社区微信群）：

| 物品 | 说明 | 不拿到的后果 |
|------|------|-------------|
| 含 **ROS1 (noetic)** 运行时的 `release.tar.gz` | 并非所有发布包都内置 ROS1 | `run rosversion -d` 失败，ROS1 全部不可用 |
| 含 **ROS2 Jazzy** 运行时的 `release.tar.gz` | 同上 | ROS2 全部不可用 |
| **`ros2_env.sh`** 环境初始化脚本 | 开发板不自带，需放到 `/data/local/` 并 `chmod +x` | ROS2 节点无法运行（`import rclpy` 失败） |
| 含 **RViz** 的运行环境 | 并非所有包都内置 rviz | 无法可视化点云/地图/TF |

---

## 1. 板上运行的基本事实（先建立正确心智模型）

- **`run` 前缀**：几乎所有机器人相关命令都要加 `run`（`run python3`、`run roscore`、`run dora up`），它注入 `LD_LIBRARY_PATH`、`PYTHONPATH` 等运行时环境变量。不加 = 各种莫名其妙的库找不到。
- **根文件系统默认只读**：写文件前先 `mount -o remount,rw /`。
- **节点代码放 `/data/local/robot/`**；自定义动态库 `.so` 放 `/data/local/robot/lib/`；ROS2 脚本放 `/data/local/`。
- **部署方式**：开发机写好代码 → `hdc file send xxx /data/local/robot/` → `hdc shell` 里 `run` 执行。没有传统意义的"安装"。
- **默认 shell 是 mksh**（不是 bash）：不支持进程替换 `<()`；想换 bash 改 `/etc/passwd` 指向 `/data/local/release/usr/bin/bash`。
- **pip 只能装纯 Python 包**（无 C 扩展），如 `run pip3 install requests debugpy`。numpy 之类带 C 扩展的不要指望现场 pip 装。
- **板上 Python 3.11**；Rust/C++ 交叉编译目标为 `aarch64-unknown-linux-musl`（musl，不是 gnu！）。
- **终端中文乱码**：节点日志和消息字符串一律用英文。

## 2. ROS1 速查

```shell
run rosversion -d          # 验证，预期 noetic
run roscore                # 终端1：Master
run python3 /data/local/robot/talker.py    # 终端2/3：节点
run rosnode list           # 查看节点
run rosnode kill -a        # 批量关闭
```

- 节点用 `rospy`（ROS1 风格），**别和 ROS2 的 `rclpy` 混用**（混用报 `No module named 'rospy'`）。
- 停止用 `Ctrl+Z`（官方文档写法）或 `rosnode kill -a`。
- 纯 ROS 节点可直接塞进 Dora dataflow.yml 让 Dora 当进程管理器（免开多个终端）。

## 3. ROS2 (Jazzy) 速查

```shell
cd /data/local && . ./ros2_env.sh    # 每个新终端都要重新 source！
echo $ROS_DISTRO                     # 验证，预期 jazzy（ros2 --version 不存在）
ros2 doctor                          # 预期 All 3 checks passed
python3 /data/local/talker.py        # 加载环境后直接 python3（此 shell 内环境已就绪）
```

- **每个新 shell 必须重新 `. ./ros2_env.sh`**，否则 `import rclpy` 失败。
- ROS2 **不需要 roscore**，节点自动互相发现。
- 以下报错/警告**可忽略**（官方明确说明）：退出时 `Error (-1) in dlclose` / `Signal 6` / `rcl_shutdown already called`；`workspace missing: /data/local/ros2_ws/install`；`ros2 doctor` 的 `No module named 'rosdistro'`。
- 默认中间件 `rmw_fastrtps_cpp`；自定义功能包目录 `/data/local/ros2_ws/install`（需交叉编译后推送）。

## 4. Dora 数据流速查（M-Robots 的核心框架）

```shell
run dora up                                   # 启动 coordinator
run dora start /data/local/robot/dataflow.yml # 启动数据流
run dora list                                 # 拿 dataflow ID
run dora logs <id>                            # 看日志
run dora stop <id> / run dora destroy         # 停止
RUST_LOG=debug run dora start ...             # 详细日志
run dora reload <id> --dataflow <yml>         # 热重载
```

- 节点间数据用 **Apache Arrow** 格式传递：`node.send_output("x", pa.array([v]))`；定时器输入 `dora/timer/millis/1000`。
- **节点崩溃后 Dora 会自动重启它** → 崩溃日志会快速堆积，排查前先 `run dora stop`。
- 排查节点启动失败三板斧：① 手动 `run python3 节点` 看原始报错 ② `run ldd 二进制` 看缺哪个 .so ③ 校验 dataflow.yml 语法和路径。
- ArkTS 动态节点必须在 `dora start` **之后**再启动应用，否则无注册槽位。

## 5. 调试工具箱

| 场景 | 命令 |
|------|------|
| 看应用/节点日志 | `hilog -b d -p off`（debug 级+不脱敏），配合 `\| grep 关键字` |
| 只看错误 | `hilog -L E` |
| 日志落盘 | `hilog -w start -f /data/log/hi.log` / `hilog -w stop` |
| 内核/驱动问题 | `dmesg`、`dmesg -w`、`dmesg \| grep oom` |
| 资源占用 | `run top`、`hidumper`、`hidumper --pid <PID>`、`hidumper --mem <PID>` |
| 进程调用栈 | `dumpchecker -p <PID>`（不用停进程） |
| CPU 热点 | `hiperf record -p <PID> -d 10 -o /data/local/tmp/perf.data` → `hiperf report -i ...` |
| 内存泄漏 | 循环 `grep VmRSS /proc/<PID>/status` 看是否线性增长 |
| 崩溃日志 | `/data/log/faultlog/faultlogger/cppcrash-*`（自动生成，无需配置） |
| 崩溃地址还原 | 开发机上 `llvm-addr2line -e 带符号二进制 -f 0x地址`（部署用 strip 版，本地留 debug 版） |

**⚠️ hilog 与 ros2_env.sh 冲突**：source 过 `ros2_env.sh` 的 shell 里跑 `hilog` 会报 `libc++.so: Exec format error`（LD_LIBRARY_PATH 被覆盖）。**看日志另开一个干净 shell**。

**Python 远程断点调试（debugpy + VSCode）**：

```shell
run pip3 install debugpy   # 板上只需一次
run python3 -m debugpy --listen 0.0.0.0:5678 --wait-for-client /data/local/robot/my_node.py
```

- VSCode `launch.json`：`type: debugpy`、`request: attach`、`connect.host=板子IP`、`pathMappings: localRoot↔/data/local/robot`、`justMyCode: false`。
- 调 Dora 拉起的节点：在节点代码顶部加 `debugpy.listen(("0.0.0.0",5678)); debugpy.wait_for_client()`，多节点用不同端口。
- 断点不命中 → 检查 pathMappings、确认本地与板上文件一致（重新 push 一次）。

## 6. 可视化（RViz / rqt）：X11 + VNC 方案

OpenHarmony 原生不支持 X11，走虚拟显示：

```shell
hdc shell
startxvfb                # 启动 Xvfb 虚拟显示器（需部署目录含此脚本）
run x11vnc &             # VNC 服务，监听 5900
run roscore &
DISPLAY=:0 run rviz      # DISPLAY=:0 必须！rqt / rqt_graph / rqt_image_view 同理
```

开发机端：`hdc fport tcp:5900 tcp:5900`（USB 连接时）→ VNC 客户端连 `localhost:5900`（或直连 `板子IP:5900`）。

- 黑屏 → 查 `pgrep -x Xvfb` 和 `echo $DISPLAY`；连不上 → 查 `pgrep -x x11vnc`、`netstat -tlnp | grep 5900`。
- 卡顿 → 走有线网络、降 VNC 画质、降点云密度。

## 7. WiFi 配置（sta_test 交互菜单）

```shell
hdc shell → sta_test → 输网卡号 0 → 菜单序号操作
```

推荐顺序：**1**(EnableWifi) → **4**(Scan) → **5**(GetScanResults) → **15**(ConnectToDevice) → **20**(GetIpInfo)。

- 安全类型选 `3`（WPA-PSK，家用路由器）；IP 选 `0`（DHCP）。
- 扫不到 → 确认已 Enable、路由器开 **2.4GHz**（部分板不支持 5GHz）。
- 其他序号：12 看已存配置、10 删配置（要 networkId）、16 是否已连、21 断开。

## 8. 自启服务（演示时让机器人上电即跑）

`/etc/init/*.cfg`（JSON 格式）→ `hdc file send robot.cfg /etc/init/` → `chmod 644` → `reboot`。

```json
{ "services": [{ "name": "robot_node",
  "path": ["run", "python3", "/data/local/robot/my_node.py"],
  "uid": "root", "gid": ["root", "shell"], "once": 0 }] }
```

- `once: 0` = 退出自动重启；`importance: 1` = 崩溃会重启整机（慎设）。
- 服务起不来先查：路径、可执行权限、**SELinux**（`setenforce 0` 临时关闭验证）、hilog 日志。
- jobs 可做预置命令（建目录、改设备权限如 `chmod 666 /dev/video0`）。

## 9. 网络与 HDC 排障

- `hdc kill && hdc start` 重置服务能解决大部分连接异常；多设备/端口冲突设 `HDC_SERVER_PORT`。
- 网络连接板子：`hdc tconn <板子IP>:5555`；查 IP `ifconfig`；端口探测 `nc -zv <IP> 5900`。

## 10. 已知边界与未开放内容

- **迁移文档（Linux/x86 应用迁到 KaihongOS）**：官方标注"待推出"。
- **RKNPU 推理文档**：标注"待推出"（工具链→部署→YOLO 实战）。黑客松要做端侧 AI 推理需提前向社区确认可用方案。
- **硬件执行器控制（GPIO/PWM/CAN/电机驱动）**：14 篇官方文档均未覆盖。板上已知有 RS485 接口（3588A）、MIPI CSI（3588S）、`/dev/video0`（摄像头）。接电机/舵机的具体方案需赛前向社区确认或自备驱动板。
- **编译源码仅支持 3588A**；`./package.sh` 产物路径两份官方文档互相矛盾，以实际输出为准。
- developer.kaihong.com 的 M-Robots 文档页目前只有目录没有正文，以 robot_docs 仓库为准。

## 11. 参考链接库

**官方仓库与文档**

- 文档仓库（最全）：https://gitcode.com/m-robots/robot_docs
- 固件下载：https://atomgit.com/m-robots/M-Robots_release （GitCode 镜像：https://gitcode.com/m-robots/M-Robots_release ；**git clone 需 `git lfs pull`**，或直接网页下载）
- 源码 manifest：https://gitcode.com/m-robots/mrobots_manifest （分支 `M-Robots_6.1_Release`）
- 核心中间件（Rust）：robot_middleware；可视化低代码工具（JavaScript）：robot_tools_maestro
- 社区主页：https://gitcode.com/org/m-robots （Discussions 提问）

**工具下载**

- RKDevTool v2.84：https://gitcode.com/open-source-toolkit/0d69c
- DriverAssistant v5.1.1：https://gitcode.com/open-source-toolkit/a045e
- OpenHarmony SDK（含 hdc）：见 OpenHarmony v5.1.0 release notes
- Linux 烧录替代：https://github.com/rockchip-linux/rkdeveloptool
- 开发板购买：3588A https://mall.kaihong.com/productDetail?skuId=1838843977558724610&goodsId=1838843977013465090 ｜ 3588S https://mall.kaihong.com/productDetail?skuId=1923320571576188929&goodsId=1923320571030929409

**外部参考**

- Dora-rs 官方文档（M-Robots 完全兼容其节点 API）：https://dora-rs.ai/zh-CN/docs/guides/
- ROS Wiki：http://wiki.ros.org/
- OpenHarmony 文档：https://docs.openharmony.cn/
- HDC 官方文档：https://docs.openharmony.cn/pages/v5.1/zh-cn/application-dev/dfx/hdc.md
- init.cfg 服务配置说明：https://gitcode.com/openharmony/docs/blob/master/zh-cn/device-dev/subsystems/subsys-boot-init-cfg.md

**联系方式**

- 邮箱：M-RobotsOS@kaihong.com（申请 ROS/RViz 运行时、ros2_env.sh）
- 社区官方微信群（见新手手册）

**本地缓存**

- 官方 14 篇文档原文副本：`_audit-cache/raw-docs/`（断网可查阅）
