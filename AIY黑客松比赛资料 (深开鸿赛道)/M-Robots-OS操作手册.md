# M-Robots OS 操作手册

> 更新日期：2026-08-01  
> 适用范围：M-Robots OS 开发、连接、运行与调试  
> 兼容性说明：不同开发板型号和系统镜像可能存在差异，涉及端口、路径和预装组件时请以实际设备为准。
> 文档密级：外部公开

## 目录

1. [开始之前](#1-开始之前)
2. [开发环境准备](#2-开发环境准备)
3. [第一次连接开发板](#3-第一次连接开发板)
4. [HDC 日常操作](#4-hdc-日常操作)
5. [Shell 基础](#5-shell-基础)
6. [必须掌握的 run 指令](#6-必须掌握的-run-指令)
7. [配置 Wi-Fi](#7-配置-wi-fi)
8. [运行项目](#8-运行项目)
9. [VS Code 远程调试 Python](#9-vs-code-远程调试-python)
10. [使用 X11、VNC 和 RViz](#10-使用-x11vnc-和-rviz)
11. [开机自启动（进阶）](#11-开机自启动进阶)
12. [调试与故障排查](#12-调试与故障排查)
13. [常用命令速查表](#13-常用命令速查表)
14. [实践任务与验收](#14-实践任务与验收)
15. [问题反馈模板](#15-问题反馈模板)

## 1. 开始之前

### 1.1 你将学会什么

完成本手册后，你应能独立完成：

1. 安装开发工具并连接 M-Robots 开发板；
2. 使用 HDC 进入开发板、传输文件和查看日志；
3. 使用 Shell 和 `run` 指令运行 Python、ROS、Dora 程序；
4. 为开发板配置 Wi-Fi；
5. 使用 VNC 查看 RViz、rqt 等 X11 图形程序；
6. 配置项目开机自启动；
7. 根据日志、崩溃报告和资源信息定位常见问题。

### 1.2 名词说明

| 名词 | 本手册中的含义 |
| --- | --- |
| 开发机 | 你使用的 Windows、macOS 或 Linux 电脑 |
| 开发板 | 运行 M-Robots OS 的机器人控制板 |
| HDC | 连接开发机与 OpenHarmony 设备的命令行工具 |
| Shell | 在开发板上输入命令的终端环境 |
| 节点 | 完成某项机器人功能的独立程序 |
| `<开发板IP>` | 占位符，使用时替换成真实地址，如 `192.168.1.100` |
| `<PID>` | 进程编号，使用时替换成真实数字 |

### 1.3 先分清命令在哪里执行

本手册中的命令按执行位置分为两类。开发板命令既可以通过 HDC 进入 Shell 后执行，也可以直接在 M-Robots 自带的 **M-Terminal** 中执行。

| 标记 | 执行位置 | 进入方式 | 示例 |
| --- | --- | --- | --- |
| **开发机** | 你的电脑终端 | 打开 PowerShell、命令提示符或系统终端 | `hdc list targets`、`hdc file send` |
| **开发板** | M-Robots 开发板终端 | 在开发机执行 `hdc shell`，或直接打开开发板上的 **M-Terminal** | `run python3 main.py`、`hilog` |

### 1.3.1 M-Terminal 说明

**M-Terminal** 是 M-Robots 系统自带的终端程序。打开后会直接进入开发板的 Shell，其命令环境和权限与通过 `hdc shell` 进入后的环境相同。

因此，本手册中标记为“开发板”的命令，都可以选择以下任一种方式执行：

1. 在开发机终端执行 `hdc shell`，再输入开发板命令；
2. 在 M-Robots 的图形界面中打开 **M-Terminal**，直接输入开发板命令。

例如，下面两种操作效果相同：

```shell
# 方式一：在开发机上通过 HDC 进入开发板
hdc shell
run python3 /data/local/my_node.py
```

```shell
# 方式二：打开开发板上的 M-Terminal 后直接执行
run python3 my_node.py
```

> M-Terminal 只能执行开发板端命令。`hdc list targets`、`hdc file send`、`hdc fport` 等用于连接或管理开发板的 HDC 命令，仍应在开发机终端中执行。

> 如果看到尖括号占位符，如 `<本地文件>`、`<设备路径>`，必须替换后再执行，不要原样复制。

### 1.4 安全规则

- 不要随意修改 `/etc`、`/system`、`/data/log` 中的文件。
- 不要执行来源不明的脚本或使用 `killall` 结束不认识的进程。
- 修改自启动配置和重启设备前，先保存代码并确认具备相应的设备管理权限。
- 使用 `hilog -p off` 获取的日志可能包含未脱敏信息；对外分享前必须检查并删除密码、密钥、地址等敏感内容。
- 使用机器人电机、机械臂前，确保急停可用、运动范围内无人和障碍物。

### 1.5 当前设备的路径与工具状态

通过 HDC 对当前开发板进行只读检查后，确认以下状态：

| 项目 | 实际状态 |
| --- | --- |
| 用户文件目录 | `/data/local/` 存在，可作为示例文件存放位置 |
| `/data/local/robot/` | 不存在，本手册不再使用该路径 |
| 临时目录 | `/data/local/tmp/` 存在 |
| M-Robots 运行时根目录 | `/data/local/release/` |
| 崩溃日志 | `/data/log/faultlog/faultlogger/` 存在 |
| 自启动配置 | `/etc/init/` 和 `/system/etc/init/` 存在，但当前设备上均为只读 |
| `run` | `/bin/run`，同时部署在 `/system/bin/run` |
| Python | `/data/local/release/usr/bin/python3`，通过 `run python3` 使用 |
| Dora 和 ROS | 位于 `/data/local/release/usr/bin/`，通过 `run` 使用 |
| X11 工具 | `Xvfb`、`x11vnc` 和 `rviz` 位于运行时中；当前设备没有 `startxvfb` |
| Wi-Fi 工具 | `/bin/sta_test` |
| 系统调试工具 | `hilog` 位于 `/bin/hilog`，`hiperf` 位于 `/bin/hiperf` |

因此，本手册统一使用 `/data/local/` 存放示例程序，使用 `/data/local/release/` 中的 M-Robots 运行时。不要把用户项目写入 `/data/local/release/`，以免污染或破坏运行环境。

---

## 2. 开发环境准备

### 2.1 硬件和软件清单

- M-Robots 开发板及配套电源；
- 可传输数据的 USB 线；
- 一台 Windows、macOS 或 Linux 开发机；
- Visual Studio Code；
- HDC 工具；
- 可选：DevEco Studio、VNC Viewer。

### 2.2 安装 Visual Studio Code

从 [VS Code 官网](https://code.visualstudio.com/) 下载并安装。根据项目语言安装插件：

| 插件 | 用途 |
| --- | --- |
| Python、Pylance、debugpy | Python 编写、补全和远程调试 |
| rust-analyzer | Rust 开发 |
| C/C++ | C/C++ 开发和调试 |
| Remote - SSH | Windows 连接 Ubuntu/WSL 开发环境 |

只有开发 ArkTS 图形应用或 C++ NAPI 扩展时，才需要安装 DevEco Studio。

### 2.3 安装并配置 HDC

HDC 位于 OpenHarmony SDK 的 `toolchains` 目录。可通过 DevEco Studio 安装 SDK，或下载对应版本的 OpenHarmony Public SDK。

可从 [OpenHarmony 版本发布说明](https://gitcode.com/openharmony/docs/tree/master/zh-cn/release-notes) 选择与设备系统版本匹配的 Public SDK。不要混用不同大版本的 HDC 和设备镜像。

Windows 示例路径：

```text
C:\SDK\openharmony\5\toolchains\hdc.exe
```

将 `toolchains` 目录加入系统 `Path`，重新打开终端后验证：

```shell
# 开发机
hdc --version
```

macOS/Linux 可将下面内容加入 `~/.zshrc` 或 `~/.bashrc`：

```shell
export PATH="$PATH:/path/to/sdk/openharmony/5/toolchains"
```

然后执行 `source ~/.zshrc` 或 `source ~/.bashrc`。

macOS/Linux 如果提示没有执行权限，可执行：

```shell
chmod +x /path/to/sdk/openharmony/5/toolchains/hdc
```

Windows 无法识别 USB 设备时，还需检查设备管理器中的驱动状态、USB 调试开关和数据线；只支持充电的 USB 线无法建立 HDC 连接。

---

## 3. 第一次连接开发板

如果开发板已连接显示器并能进入 M-Robots 图形界面，可以直接打开 **M-Terminal** 操作开发板；如果需要从个人电脑远程操作、上传文件或调试，则使用下面介绍的 HDC 连接方式。

### 3.1 USB 连接

1. 给开发板正常供电；
2. 用支持数据传输的 USB 线连接开发机；
3. 在开发机终端执行：

```shell
# 开发机
hdc list targets
```

看到设备序列号或 `IP:Port` 表示连接成功。然后进入设备：

```shell
# 开发机
hdc shell
```

进入后可执行：

```shell
# 开发板
pwd
whoami
cat /proc/version
```

输入 `exit` 可退出开发板 Shell。

### 3.2 网络连接

开发板和开发机位于同一局域网时，可执行：

```shell
# 开发机
hdc tconn <开发板IP>:<HDC端口>
hdc list targets
```

`<HDC端口>` 必须替换为设备实际启用的网络调试端口，常见示例是 `5555`，但不同镜像可能不同。若不确定，请查看当前设备或项目提供的网络调试配置。

若同时连接多台设备，使用设备 ID 指定目标：

```shell
hdc -t <设备ID> shell
```

### 3.3 连接失败

```shell
# 开发机：重启 HDC 服务并重试
hdc kill -r
hdc list targets
```

仍失败时依次检查：开发板供电、USB 线是否支持数据、USB 调试是否开启、网络是否同网段，以及端口是否被占用。

---

## 4. HDC 日常操作

### 4.1 执行单条设备命令

```shell
# 开发机
hdc shell ls /data/local
hdc shell ifconfig
```

### 4.2 上传和下载文件

当前设备不存在 `/data/local/robot/`。本手册将示例文件直接放在实际存在的 `/data/local/`；实际项目较多时，可以自行创建项目子目录，但必须同步修改命令和配置中的路径。

```shell
# 开发机：上传文件或目录
hdc file send <本地文件> /data/local/
hdc file send <本地项目目录> /data/local/

# 开发机：下载文件或日志
hdc file recv /data/local/<文件> <本地目录>
```

上传后检查：

```shell
# 开发机
hdc shell ls -la /data/local
```

### 4.3 端口转发

远程调试或 VNC 可通过 HDC 转发端口：

```shell
# 开发机
hdc fport tcp:5678 tcp:5678
hdc fport ls
hdc fport rm tcp:5678 tcp:5678
```

### 4.4 HAP 应用管理

```shell
# 开发机
hdc install <应用.hap>
hdc uninstall <包名>
hdc shell aa start -a <Ability名称> -b <包名>
hdc shell bm dump -a
```

---

## 5. Shell 基础

M-Robots OS 默认使用轻量级 `mksh`。它与 Bash 相似，但不支持所有 Bash 扩展语法。

### 5.1 常用文件与目录命令

```shell
pwd                       # 当前目录
ls -la                    # 显示文件详情
cd /data/local      # 切换目录
mkdir demo                # 新建目录
cp a.py b.py              # 复制文件
mv old.py new.py          # 移动或重命名
cat main.py               # 查看文本
chmod +x start.sh         # 添加执行权限
```

### 5.2 管道、重定向和后台任务

```shell
command > output.log 2>&1 # 将正常输出和错误写入文件
command | grep "error"    # 过滤输出
command &                 # 后台运行
jobs                      # 查看当前 Shell 后台任务
fg %1                     # 将编号 1 的任务调回前台
kill <PID>                # 结束指定进程
```

按 `Ctrl+C` 通常可停止当前前台程序。

### 5.3 简单脚本

创建 `start_robot.sh`：

```shell
#!/bin/sh
echo "Starting M-Robots..."
run roscore &
sleep 2
run dora up
run dora start /data/local/dataflow.yml
```

运行脚本：

```shell
chmod +x start_robot.sh
./start_robot.sh
```

> mksh 不支持 Bash 的进程替换 `<(...)>`。复杂 Bash 脚本请明确使用已安装的 Bash 运行。

---

## 6. 必须掌握的 `run` 指令

`run` 位于 `/bin/run`，会加载 `/data/local/release/` 中 M-Robots 程序需要的 `PATH`、`LD_LIBRARY_PATH`、`PYTHONPATH` 等环境变量。Python、Dora 和 ROS 命令不会直接出现在基础 HDC Shell 的 `PATH` 中，应通过 `run` 调用。

使用本章前先检查：

```shell
command -v run
run command -v python3
run command -v dora
run command -v roscore
```

当前设备上的预期路径为：

```text
/bin/run
/data/local/release/usr/bin/python3
/data/local/release/usr/bin/dora
/data/local/release/usr/bin/roscore
```

如果检查结果为空，应停止执行后续示例并核对当前镜像或 `/data/local/release/` 运行时。

基本格式：

```shell
run <命令> [参数]
```

运行时部署完成后再验证：

```shell
# 开发板
run echo "M-Robots is ready"
```

常用示例：

```shell
run python3 --version
run python3 /data/local/my_node.py
run pip3 install <包名>

run roscore
run rosnode list
run rostopic list

run dora up
run dora check
run dora start /data/local/dataflow.yml
run dora list
run dora stop <dataflow-id>
```

| 类型 | 是否通常需要 `run` |
| --- | --- |
| ROS、Dora、M-Robots Python 环境 | 是 |
| HDC | 否，在开发机执行 |
| `hilog`、`dmesg` 等系统工具 | 通常否 |

出现 `run: not found` 时检查：

```shell
command -v run
echo $PATH
```

如果 `command -v run` 无输出，或 `run command -v python3`、`run command -v dora` 无输出，应停止执行相关示例并核对当前镜像和 `/data/local/release/`。

---

## 7. 配置 Wi-Fi

> 输入密码时注意周围环境，不要将终端截图公开。

可通过 USB HDC 进入开发板，或直接打开 M-Terminal，然后启动 Wi-Fi 工具。

使用 HDC 时：

```shell
# 开发机
hdc shell
```

进入开发板 Shell 后，或在 M-Terminal 中直接执行：

```shell
sta_test
```

看到网卡选择提示后输入 `0`，进入 `wlan0` 菜单。

### 7.1 推荐连接流程

1. 输入 `1`：开启 Wi-Fi；
2. 输入 `4`：扫描；
3. 等待几秒，输入 `5`：查看扫描结果；
4. 输入 `15`：连接网络；
5. 按提示填写 SSID；
6. 选择安全类型：家用 WPA/WPA2 通常输入 `3`；
7. 填写密码；
8. 普通非隐藏网络输入 `0`；
9. DHCP 自动获取 IP 输入 `0`；
10. 输入 `20` 查看 IP。

出现 `CONNECTED` 表示连接成功。

### 7.2 常用菜单

| 序号 | 功能 |
| --- | --- |
| `1` / `2` | 开启 / 关闭 Wi-Fi |
| `4` / `5` | 扫描 / 查看扫描结果 |
| `12` | 查看已保存网络及 `networkId` |
| `10` | 按 `networkId` 删除已保存网络 |
| `15` | 连接网络 |
| `16` / `17` | 检查连接 / 查看连接信息 |
| `20` | 查看 IP |
| `21` | 断开当前网络，但不删除配置 |

### 7.3 联网检查

```shell
# 开发板
ifconfig
ping <开发机IP>
```

扫描不到网络时，确认 Wi-Fi 已开启、SSID 拼写正确，并检查开发板是否支持目标 5 GHz 网络；可优先尝试 2.4 GHz。

---

## 8. 运行项目

> 本章依赖 M-Robots 运行时。请先确认 `command -v run`、`run command -v python3` 和 `run command -v dora` 均能返回有效路径。

### 8.1 Python 节点

```shell
# 开发机：上传
hdc file send my_node.py /data/local/
hdc shell
```

```shell
# 开发板（通过 HDC Shell 或 M-Terminal）
run python3 /data/local/my_node.py
```

若提示模块不存在：

```shell
# 示例：安装包名和 Python 导入名均为 requests
run pip3 install requests
run python3 -c "import requests; print(requests.__version__)"
```

> 安装包名不一定等于 Python 导入名。例如安装包 `opencv-python` 对应 `import cv2`。请以该软件包的官方说明为准。

### 8.2 Dora Dataflow

```shell
# 开发板
run dora up
run dora start /data/local/dataflow.yml
run dora list
run dora check
run dora logs <dataflow-id>
run dora stop <dataflow-id>
```

完全结束 Dora coordinator 及其管理的所有 Dataflow 时，才执行：

```shell
# 警告：会影响当前设备上的全部 Dora Dataflow
run dora destroy
```

启动失败时先绕过 Dora，直接运行节点看原始错误：

```shell
run python3 /data/local/my_node.py
# 或
run /data/local/my_node
```

检查 YAML 和文件路径：

```shell
run python3 -c "import yaml; yaml.safe_load(open('/data/local/dataflow.yml'))" && echo "OK"
ls -la /data/local/
```

### 8.3 ROS 常用命令

```shell
run roscore
run rosnode list
run rostopic list
```

需要同时运行多个长期任务时，建议打开多个终端窗口，不要把所有程序堆在一个 Shell 中。

---

## 9. VS Code 远程调试 Python

> 本章依赖 Python 和 `run`。当前设备应通过 `run python3` 使用 `/data/local/release/usr/bin/python3`。

### 9.1 准备

开发板只需安装一次：

```shell
run pip3 install debugpy
```

### 9.2 启动调试服务

```shell
# 开发板
run python3 -m debugpy --listen 0.0.0.0:5678 --wait-for-client /data/local/my_node.py
```

如通过 USB 调试，在开发机执行：

```shell
hdc fport tcp:5678 tcp:5678
```

### 9.3 配置 VS Code

在项目中创建 `.vscode/launch.json`：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "M-Robots 远程调试",
      "type": "debugpy",
      "request": "attach",
      "connect": { "host": "localhost", "port": 5678 },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
          "remoteRoot": "/data/local"
        }
      ],
      "justMyCode": false
    }
  ]
}
```

网络直连时将 `localhost` 改为开发板 IP。打开与开发板内容一致的源码，设置断点后按 `F5`；`F10` 单步跳过，`F11` 单步进入。

若断点不命中，重点检查本地与设备源码是否一致，以及 `remoteRoot` 是否正确。连接被拒绝时检查监听：

```shell
run netstat -tlnp | grep 5678
```

---

## 10. 使用 X11、VNC 和 RViz

M-Robots 通过 `Xvfb → x11vnc → VNC 客户端` 显示 X11 图形界面。当前设备的运行时中包含 `Xvfb`、`x11vnc` 和 `rviz`，但没有 `startxvfb` 包装命令。

先在开发板上检查相关命令：

```shell
run command -v Xvfb
run command -v x11vnc
run command -v rviz
```

当前设备的预期路径为 `/data/local/release/usr/bin/Xvfb`、`x11vnc` 和 `rviz`。若命令无输出，需要先核对运行时，不能直接执行下面的启动示例。

### 10.1 开发板端

如果使用远程 HDC，先在开发机执行：

```shell
hdc shell
```

然后在开发板 Shell 中执行；使用 M-Terminal 时直接从这里开始：

```shell
run Xvfb :0 -screen 0 1280x720x24 &
DISPLAY=:0 run x11vnc &
run roscore &
DISPLAY=:0 run rviz
```

其他程序：

```shell
DISPLAY=:0 run rqt
DISPLAY=:0 run rqt_graph
DISPLAY=:0 run rqt_image_view
DISPLAY=:0 run rqt_plot
```

### 10.2 开发机端

USB 连接时先转发端口：

```shell
hdc fport tcp:5900 tcp:5900
```

VNC 客户端连接：

- USB 端口转发：`localhost:5900`
- 同一网络直连：`<开发板IP>:5900`

### 10.3 常见问题

```shell
pgrep -x Xvfb                 # Xvfb 是否运行
pgrep -x x11vnc               # VNC 服务是否运行
echo $DISPLAY                 # 应为 :0
run netstat -tlnp | grep 5900 # 端口是否监听
```

黑屏通常表示 Xvfb 或图形程序未运行；连接被拒绝通常表示 x11vnc 未运行或 5900 端口不可达。

---

## 11. 开机自启动（进阶）

> 本章涉及系统启动配置。当前设备上的 `/etc/init/` 和 `/system/etc/init/` 均为只读，不能通过 HDC 直接写入。本章只介绍配置文件的准备和校验，不执行板端部署。

OpenHarmony 的 init 进程读取 init 配置目录中的 JSON 文件。实际加载目录和集成方式由镜像决定；当前设备可看到 `/etc/init/` 和 `/system/etc/init/`，但两者都不可写。

首先在开发板 Shell 或 M-Terminal 中确认 `run` 的真实位置：

```shell
command -v run
```

当前设备应输出 `/bin/run`。init 服务不能依赖交互式 Shell 的 `PATH`，配置中应填写该绝对路径。

### 11.1 服务示例

创建开发机文件 `robot.cfg`。当前设备使用实测路径 `/bin/run`：

```json
{
  "services": [
    {
      "name": "robot_node",
      "path": ["/system/bin/sh", "-c", "/bin/run python3 /data/local/my_node.py"],
      "uid": "root",
      "gid": ["root", "shell"],
      "once": 1,
      "importance": 0
    }
  ]
}
```

`once: 1` 表示退出后不自动重启，适合首次测试；确认服务稳定且确实需要自动恢复后，再评估是否改为 `0`。

示例使用 `root` 是因为原始环境可能需要较高权限。正式部署前应根据程序访问的设备和文件，评估是否能改用权限更低的账户，并确认当前镜像所需的 SELinux 安全上下文。

### 11.2 配置校验与集成

先在开发机上检查 JSON 语法：

```shell
python -m json.tool robot.cfg
```

确认以下内容均已替换为当前设备的真实值：

1. `run` 的绝对路径 `/bin/run`；
2. Python 节点路径 `/data/local/my_node.py`；
3. 服务所需的用户、用户组和设备权限；
4. 当前镜像使用的 init 配置目录及 SELinux 安全上下文。

当前设备不支持通过下面这类命令直接部署：

```shell
# 当前设备的 /etc/init 为只读，请勿执行
cp robot.cfg /etc/init/robot.cfg
```

需要开机自启动时，应将配置交由 M-Robots OS 镜像构建流程集成，或使用设备供应方明确提供的可写配置机制。不要重新挂载系统分区为可写，也不要为绕过启动限制关闭 SELinux。

---

## 12. 调试与故障排查

### 12.1 推荐排查顺序

1. 记录你执行的完整命令和报错原文；
2. 检查文件路径、权限和占位符是否已替换；
3. 确认命令在开发机还是开发板执行；
4. 确认 ROS、Dora、Python 命令是否带 `run`；
5. 手动运行单个节点，缩小问题范围；
6. 查看 Dora 状态、系统日志或崩溃日志；
7. 最后再检查性能、驱动和网络底层问题。

### 12.2 系统日志

`hilog` 是系统原生日志工具，建议在一个全新的 Shell 中执行：

> `-p off` 会关闭隐私字段脱敏。只在确有需要时使用，保存或分享日志前必须删除敏感信息。

```shell
hilog -b d -p off
hilog -b d | grep "my_node"
hilog -L E -p off
```

保存日志：

```shell
hilog -w start -f /data/log/hi.log
hilog -w stop
```

> 如果当前 Shell 已加载 ROS2 环境脚本，`hilog` 可能因动态库冲突报错。退出该 Shell，重新执行 `hdc shell`，不要加载 ROS2 环境，再运行 `hilog`。

驱动、内存或硬件问题可查看：

```shell
dmesg
dmesg -w
dmesg | grep "oom"
dmesg | grep "usb"
dmesg | grep "camera"
```

### 12.3 进程和资源

```shell
run top
hidumper
hidumper --pid <PID>
dumpchecker -p <PID>
cat /proc/<PID>/status | grep -i vm
cat /proc/<PID>/maps
```

### 12.4 崩溃日志

系统会为 `SIGSEGV`、`SIGILL`、`SIGABRT` 等原生进程崩溃生成报告：

```shell
ls -lt /data/log/faultlog/faultlogger/ | head -20
cat /data/log/faultlog/faultlogger/$(ls -t /data/log/faultlog/faultlogger/ | head -1)
```

在开发机下载：

```shell
hdc file recv /data/log/faultlog/faultlogger/ ./crash_logs/
```

| 信号 | 常见含义 |
| --- | --- |
| `SIGSEGV` | 空指针、越界访问 |
| `SIGILL` | 错误架构指令或内存破坏 |
| `SIGABRT` | 断言失败、`abort()`、重复释放 |
| `SIGBUS` | 地址未对齐等内存访问错误 |

C/C++ 或 Rust 项目应保留带调试符号且与部署版本对应的二进制，再在开发机用地址还原源码位置：

```shell
llvm-addr2line -e my_node_with_symbols -f 0x1234
```

### 12.5 Dora 运行时问题

```shell
run dora check
run dora list
run dora logs <dataflow-id>
RUST_LOG=debug run dora start /data/local/dataflow.yml
run ldd /data/local/my_node
```

`ldd` 输出中的 `not found` 表示缺少动态库。动态 ArkTS 节点应先启动 Dataflow，再启动应用。

### 12.6 CPU 和内存性能

```shell
# 对进程采样 10 秒
hiperf record -p <PID> -d 10 -o /data/local/tmp/perf.data
hiperf report -i /data/local/tmp/perf.data

# 查看系统内存和 OOM
cat /proc/meminfo
dmesg | grep "Out of memory"
```

Python 可用 `time.perf_counter()` 测量处理耗时，或使用 `cProfile` 定位累计耗时较高的函数。

### 12.7 网络问题

```shell
# 开发板
ifconfig
ping <开发机IP>
run netstat -tlnp

# 开发机
ping <开发板IP>
hdc kill -r
hdc list targets
```

---

## 13. 常用命令速查表

| 目的 | 命令 |
| --- | --- |
| 查看设备 | `hdc list targets` |
| 进入设备 | `hdc shell` |
| 网络连接 | `hdc tconn <IP>:<HDC端口>` |
| 上传文件 | `hdc file send <本地> <设备路径>` |
| 下载文件 | `hdc file recv <设备路径> <本地>` |
| 转发端口 | `hdc fport tcp:<本地端口> tcp:<设备端口>` |
| 运行 Python | `run python3 <脚本>` |
| 启动 ROS Master | `run roscore` |
| 启动 Dora | `run dora up` |
| 启动 Dataflow | `run dora start <dataflow.yml>` |
| 查看 Dora 状态 | `run dora check` |
| 查看系统日志 | `hilog -b d -p off` |
| 查看内核日志 | `dmesg` |
| 查看进程 | `run top` |
| 查看 IP | `ifconfig` |

---

## 14. 实践任务与验收

### 任务一：完成设备连接

- `hdc list targets` 能看到设备；
- 能进入 Shell 并输出 `pwd`、`whoami`；
- 能正确退出 Shell。

### 任务二：上传并运行程序

- 将 `hello_robot.py` 上传到 `/data/local/`；
- 使用 `run python3` 正常运行；
- 能解释为什么部分命令需要 `run`。

示例程序：

```python
print("Hello, M-Robots!")
```

### 任务三：完成联网

- 使用 `sta_test` 扫描并连接指定 Wi-Fi；
- 能查看开发板 IP；
- 能从开发机 ping 通开发板或说明网络限制。

### 任务四：完成基础调试

- 能使用 `hilog` 查看日志；
- 能使用 `run dora check` 查看状态；
- 能根据一个“路径错误”或“模块缺失”报错提出排查步骤。

### 提交建议

建议保留一份操作记录，包含设备型号、系统版本、关键命令、结果截图、遇到的问题、解决过程和结果总结。截图前请遮挡 Wi-Fi 密码、设备密钥及其他敏感信息。

---

## 15. 问题反馈模板

向设备管理员或技术支持反馈问题时，可复制下面模板：

```text
【设备型号】
【M-Robots OS 版本】
【开发机系统】
【连接方式】USB / 网络
【目标】我想完成……
【执行命令】
【完整报错】
【已经尝试】
【相关日志或截图】
```

提供完整信息比只说“运行不了”更容易快速定位问题。

---

## 附录：参考资料

- [OpenHarmony HDC 文档](https://docs.openharmony.cn/pages/v5.1/zh-cn/application-dev/dfx/hdc.md)
- [VS Code](https://code.visualstudio.com/)
- [mksh 手册](https://www.mirbsd.org/htman/i386/man1/mksh.htm)
- [Xvfb 手册](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml)
- [x11vnc](https://github.com/LibVNC/x11vnc)
- [RViz 用户指南](https://docs.ros.org/indigo/api/rviz/html/user_guide/)

> 本手册根据目录内 M-Robots OS 工具资料整理。不同开发板型号和系统版本的命令、端口及预装组件可能略有差异，请以实际使用的设备镜像、版本说明和项目要求为准。
