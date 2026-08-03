# Mac 开发环境装配记录（张峻翔）

> 执行日期：2026-08-04 ｜ 机器：MacBook Apple Silicon（arm64）/ macOS 26.5.2 / zsh
> 目标状态：明天（8/5）下午到现场，插板即干活

## 1. 装了什么

### HDC（OpenHarmony Device Connector）⭐ 核心
- **是什么**：Mac ↔ 开发板的桥（相当于鸿蒙版 adb）。连板、进 shell、推文件全靠它
- **来源**：华为官网 command-line-tools（**mac-arm64** 版 6.1.1.300，需华为账号登录下载）
- **安装方式**：桌面解压包中的 `sdk/default/openharmony/toolchains/` **整目录**拷贝到稳定位置（不能只拷 hdc 二进制，它依赖同目录的 `lib/` 和 `libusb_shared.dylib`）
- **安装位置**：`~/AIY-Hackathon/tools/hdc/`
- **关键一步**：`xattr -dr com.apple.quarantine ~/AIY-Hackathon/tools/hdc` —— 网络下载的文件带 Gatekeeper 隔离属性，不去除首次运行会被拦
- **PATH**：`~/.zshrc` 末尾追加 `export PATH="$HOME/AIY-Hackathon/tools/hdc:$PATH"`
- **验证**：新开终端 `hdc version` → `Ver: 3.2.0d` ✅；`hdc list targets` → 空列表（无板，正常）✅
- **备份**：桌面 `command-line-tools/` 原件与 zip 保留未动

### Python PC 端依赖（辅助相机工具用）
- 仓库根建虚拟环境：`.venv/`（已被 .gitignore 忽略，不进库）
- 安装：`pip install -r "AIY黑客松比赛资料 (深开鸿赛道)/source code/kaihong_adapter/robot-runtime/student/requirements-pc.txt"`
- **验证**：numpy 2.5.1 + cv2 4.14.0 + yaml 导入 OK ✅（Python 3.14 无兼容问题）
- 用法：跑辅助相机 PC 端工具前 `source .venv/bin/activate`

## 2. 本来就有（确认过，未动）

| 软件 | 版本 | 说明 |
|------|------|------|
| VSCode | 已装 | 插件已齐：Python / Pylance / **debugpy**（板上远程断点调试）/ Remote-SSH |
| Git | 2.51.0（brew） | — |
| Python | 3.14.6（brew） | 本机辅助脚本用；板上是 Python 3.11，别混 |
| 屏幕共享（VNC） | macOS 自带 | 看 RViz：Finder `Cmd+K` → `vnc://localhost:5900`（USB 时先 `hdc fport tcp:5900 tcp:5900`）或 `vnc://板子IP:5900` |
| Rosetta 2 | 已装 | 本次未用上（HDC 是 ARM64 原生） |

## 3. 明确不装

- ❌ Mac 版 ROS / Ubuntu 虚拟机——代码推到板上跑，本机不跑机器人程序
- ❌ RKDevTool 烧录工具——比赛板预制镜像（且 Mac 无此工具）
- ❌ DevEco Studio——不做 ArkTS 界面

## 4. 排障备注

- `hdc` 命令找不到 → 检查是否**新开了终端**（PATH 改完旧终端不生效）
- 运行 hdc 弹"无法验证开发者" → 隔离属性没去干净，重跑第 1 节的 `xattr -dr` 命令
- 连不上板子 → `hdc kill && hdc start`（万能重置）
