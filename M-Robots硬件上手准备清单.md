# M-Robots 硬件上手前准备清单

> 来源：[M-Robots robot_docs 官方文档仓库](https://gitcode.com/m-robots/robot_docs)
> 调研日期：2026-07-28，经三路独立信源交叉核验后修订
>
> 说明：深开鸿官方文档中心（developer.kaihong.com）的 M-Robots 页面目前仅有目录、正文尚未上线，当前以 robot_docs 仓库为最权威信源。

## 总体路线

上手前准备分两条路线：

- **快速路线（推荐新手）**：下载官方预编译固件 → RKDevTool 烧录 → HDC 验证。全程只需 Windows，无需编译环境。
- **编译路线**：自行编译 M-Robots OS 源码。需要 Ubuntu 22.04 开发机（磁盘 ≥ 400 GB、内存 ≥ 32 GB），门槛高得多。**注意：官方编译文档目前只支持 RK3588A（`khd_rk3588_a`），3588S 用户只能走预编译固件路线。**

---

## 1. 硬件准备

### 开发板（必须 aarch64 + KaihongOS / OpenHarmony 标准系统）

| 型号 | 适用场景 | 特点 |
|------|---------|------|
| [KHD-3588A](https://mall.kaihong.com/productDetail?skuId=1838843977558724610&goodsId=1838843977013465090)（RK3588） | 工业场景、多外设 | USB / HDMI / 音频 / RS485 / 以太网，Wi-Fi/蓝牙内置，可选 5G 模块；**唯一支持自行编译的型号** |
| [KaihongBoard-3588S-SBC](https://mall.kaihong.com/productDetail?skuId=1923320571576188929&goodsId=1923320571030929409)（RK3588S） | 快速原型、端侧 AI | 85×56mm 小尺寸（10 层 PCB），8 核最高 2.4GHz，Mali-G610 MP4，NPU 6 TOPS；Mini HDMI（8K@60）/ Mini DP（4K@60），预留 MIPI CSI/DSI（接摄像头/屏） |

- 其他满足 aarch64 + KaihongOS 的开发板理论上兼容，需自行适配。
- **存储要求**：`/data` 分区可用空间 ≥ 2 GB。
- **网络要求**：开发板与电脑在同一局域网（VNC 远程显示、远程调试需要）。

### 配件

- USB 公对公**数据线**（连 USB3.0 OTG 口烧录用，**充电线不行**——无法传输数据）
- 镊子（短接 GND 与 LOADER 触点进入烧录模式）
- **稳定的电源适配器**（固件 README 明确建议，供电不稳会导致烧录/启动异常）
- HDMI 显示器 + 网线（非必须但推荐：固件为 HDMI 输出版本，首次开机排障和配网时很实用）

## 2. 烧录工具与固件（Windows）

| 工具 | 用途 |
|------|------|
| [RKDevTool v2.84](https://gitcode.com/open-source-toolkit/0d69c) | Rockchip 图形化烧录工具（M-Robots 官方流程） |
| [DriverAssistant v5.1.1](https://gitcode.com/open-source-toolkit/a045e) | Windows USB 驱动，识别不到设备时重装 |
| [M-Robots_release 固件仓库](https://atomgit.com/m-robots/M-Robots_release)（[GitCode 镜像](https://gitcode.com/m-robots/M-Robots_release)） | 预编译固件，3588A / 3588S 各一份，**务必核对与开发板型号匹配** |

> **Git LFS 注意**：固件 zip 通过 Git LFS 管理。git clone 方式下载后必须执行 `git lfs install && git lfs pull`，否则拿到的只是指针文件（新手高频踩坑）；也可以直接网页下载 zip 避开此问题。

> **Linux 烧录**：Rockchip 官方另有 Linux 命令行工具 `Linux_Upgrade_Tool`（upgrade_tool）及开源版 [rkdeveloptool](https://github.com/rockchip-linux/rkdeveloptool)，可烧录同一 `.img` 固件，只是不在 M-Robots 官方流程内、未经其验证。macOS 无官方工具（社区有跨平台封装）。

> **SN 备份（重要）**：烧录前备份原机 SN（设备标签或"关于本机"读取），否则可能 License 激活失败。需要时可用 RKDevInfoWriteTool 重新写入 18 位 SN。

## 3. HDC 调试工具（必备，Windows/macOS/Linux 均可用）

HDC（OpenHarmony Device Connector）是开发机与开发板之间的核心桥梁，类似 Android 的 adb。

- 来源：OpenHarmony Public SDK 的 `toolchains/` 目录（三平台均有二进制），或随 DevEco Studio 安装
- 配置：将 `toolchains` 目录加入 `PATH`，验证 `hdc version`（或 `hdc -v`）
- 端口冲突/多设备时：设置 `HDC_SERVER_PORT` 环境变量（如 `export HDC_SERVER_PORT=7035`）
- 常用命令：
  - `hdc list targets` — 列出已连接设备
  - `hdc tconn <IP:Port>` — 网络连接设备
  - `hdc kill -r` — 重启 HDC 服务（识别不到设备时也可 `hdc kill && hdc start`）
  - `hdc shell` — 进入设备 shell
  - `hdc file send <src> <dst>` / `hdc file recv` — 文件传输
  - `hdc fport tcp:<本地> tcp:<设备>` — 端口转发（远程调试用）
  - `hdc shell hilog` — 查看系统日志
- 注意：M-Robots 上运行 ROS / Dora 命令需要加 `run` 前缀

## 4. 开发环境（PC 端）

### VSCode（主力，Python / Rust / C++ 节点开发，全平台）

推荐插件：

| 插件 | 用途 |
|------|------|
| Python / Pylance | Python 语法补全、类型推断 |
| debugpy | Python 远程断点调试（板上先 `run pip3 install debugpy`） |
| rust-analyzer | Rust 补全、类型提示 |
| C/C++ | C/C++ 补全、调试 |
| Remote - SSH | Windows 用户连接 Ubuntu 开发机 |

### DevEco Studio（可选，仅 Windows / macOS，无 Linux 版）

- 系统要求：Windows 10/11 64 位（内存 16GB+）；macOS 11+（Apple 芯片 12+）
- 仅做 ArkTS 图形界面开发（机器人控制面板、C++ NAPI 扩展）才需要；纯节点开发不需要。

## 5. 编译路线（可选）

仅当自己编译系统时需要：

- **开发机**：Ubuntu 22.04.5 LTS（x86_64），磁盘 ≥ 400 GB，内存 ≥ 32 GB
- **产品名**：目前官方编译文档只有 `khd_rk3588_a`（RK3588A），3588S 无编译指引
- **步骤**（详见 [03-安装M-Robots环境.md](https://gitcode.com/m-robots/robot_docs/blob/master/docs/0-安装/03-安装M-Robots环境.md)）：
  1. `sudo dpkg-reconfigure dash` 选 No，将 `/bin/sh` 指向 bash
  2. 安装编译依赖（gcc、ccache、git-lfs、scons、python3 等一整套）
  3. Python 环境：`requests`、必要时 `json5==0.9.6`；脚本调用 `python` 而系统没有时做软链接
  4. 安装 repo 工具并加入 PATH
  5. 配置 GitCode SSH 公钥（官方**推荐 HTTPS 方式拉取**，无需登录或 Token，可跳过此步）
  6. 拉源码：
     ```bash
     repo init -u https://gitcode.com/m-robots/mrobots_manifest.git \
       -b M-Robots_6.1_Release -m default.xml --no-repo-verify
     repo sync -c -j8
     repo forall -c 'git lfs pull'
     ```
  7. 下载预编译工具链：`./build/prebuilts_download.sh --no-check-certificate`
  8. 编译：`./build.sh --product-name khd_rk3588_a --ccache`
     （实时版本：`--gn-args preempt_rt=true`，切换前先 `rm -rf out/kernel/khd_rk3588_a`）
  9. 实时内核编译后验证配置：
     `grep -E '^CONFIG_(PREEMPT_RT|HIGH_RES_TIMERS|HZ_1000)=y$' out/kernel/khd_rk3588_a/OBJ/*/.config`
  10. 打包：`./package.sh`。产物路径两份官方文档说法不一（robot_docs 说在 `out/arm64/khd_rk3588_a/packages/phone/images`，manifest README 说需进 images 目录执行、产物在 `pack/` 子目录）——**以实际输出为准**

### WSL2 注意事项（Windows 用户编译时）

WSL2 不在 OpenHarmony 官方支持环境内，社区实践可行但有坑：

- 源码必须放在 WSL 原生文件系统（ext4），**不要放 `/mnt/c`**（NTFS 不区分大小写，编译会出错）
- 提前扩容 WSL2 虚拟磁盘至 ≥ 400 GB（默认容量不够，常见 `No space left on device`）
- 配置足够内存与 swap
- 追求稳妥首选物理 Ubuntu 机或远程服务器

## 6. 烧录与验证流程

1. 板子断电 → 镊子短接 GND + LOADER 触点 → **保持短接并接通电源，然后松开镊子** → USB 公对公数据线连接 **USB3.0 OTG 口**与 PC
2. RKDevTool 左下角显示"发现一个 LOADER 设备"（显示 MASKROM 也可以正常烧录）
3. 「升级固件」页选择解压后的 `.img` → 点「升级」→ 等待"下载固件成功"，自动重启
4. HDC 验证：USB 连接后 `hdc list targets` 能看到设备即成功（等 30~60 秒让板子完全重启）
5. 板上环境验证：
   - `run echo "M-Robots is ready"`
   - `run python3 --version`（应为 3.11.x）
   - `run python3 -c "import dora; print(dora.__version__)"` 及 `run dora up` / `run dora check`
   - `run roscore &` / `run rostopic list`

### 烧录常见问题（官方 FAQ）

- **识别不到设备**：检查是否数据线（非充电线）、是否接 OTG 口而非 USB Host 口、重装 DriverAssistant、重新进 Loader 模式
- **烧录中途失败**：不断电不拔线，重新点"升级"；反复失败可在"高级功能"页先烧 Loader 再烧固件
- **烧录后 `hdc list targets` 无输出**：等板子完全重启、重新插拔 USB、`hdc kill && hdc start` 重置服务

## 7. 各操作系统兼容性

| 环节 | Windows | macOS | Linux（Ubuntu） |
|------|---------|-------|----------------|
| 固件烧录 | ✅ M-Robots 官方流程 | ❌ 无官方工具（社区有跨平台封装） | ⚠️ M-Robots 官方流程未覆盖；Rockchip 官方有 Linux 命令行工具（upgrade_tool / rkdeveloptool），可自行烧录 |
| HDC 工具 | ✅ | ✅ | ✅ |
| VSCode 节点开发 + debugpy 远程调试 | ✅ | ✅ | ✅ |
| DevEco Studio（ArkTS） | ✅ | ✅ | ❌（华为官方仅提供 Windows/macOS 版） |
| 源码编译 | ❌（WSL2 可行但有坑，见第 5 节） | ❌ | ✅ 仅 Ubuntu 22.04（x86_64），且仅 RK3588A |
| 开发板本身 | — | — | 必须 KaihongOS（OpenHarmony 标准系统），aarch64 |

**结论**：

- **纯上手体验（烧录 + 节点开发）**：Windows 最顺，官方流程全部覆盖；Linux 用户可用 Rockchip 官方命令行工具烧录（不在 M-Robots 官方流程内）；macOS 烧录最麻烦，建议借一台 Windows 机器。
- **想编译源码**：必须有 Ubuntu 22.04 + RK3588A 开发板，Windows 用户可用 WSL2（注意第 5 节的坑）或远程服务器（配 VSCode Remote-SSH）。

## 8. 建议行动顺序

1. 先走快速路线（预编译固件），不要一上来就编译
2. 下单开发板（按场景选 [3588A](https://mall.kaihong.com/productDetail?skuId=1838843977558724610&goodsId=1838843977013465090) 或 [3588S](https://mall.kaihong.com/productDetail?skuId=1923320571576188929&goodsId=1923320571030929409)；想自己编译源码必须选 3588A）+ 备 USB 数据线、镊子、稳定电源，最好再备 HDMI 显示器和网线
3. Windows 上预装：RKDevTool + DriverAssistant 驱动 + HDC（配 PATH）+ VSCode（含插件）
4. 下载对应型号固件（git clone 方式记得 `git lfs pull`），记录原机 SN
5. 板子到手 → 烧录 → HDC 验证 → 跑第一个 Demo（**ROS1 或 ROS2 Jazzy 任选**，官方均有 talker/listener 快速入门文档）

## 9. 系统选型结论（速查列表）

**开发机（你的电脑）**：

- 快速体验（烧录 + 跑 Demo + 节点开发）→ **Windows**（官方流程全覆盖，最省事）
- 日常开发（HDC、VSCode、debugpy 远程调试）→ Windows / macOS / Linux 均可
- ArkTS 图形界面开发（DevEco Studio）→ Windows 或 macOS（**无 Linux 版**）
- 自行编译 M-Robots 源码 → **只能 Ubuntu 22.04（x86_64）**
  - Windows 用户可走 WSL2（注意：源码放 WSL 原生 ext4，不放 `/mnt/c`；磁盘扩至 ≥ 400 GB）或远程服务器
  - 编译目前**仅支持 RK3588A**，3588S 无编译指引

**烧录环节的跨平台情况**：

- Windows → ✅ 官方 RKDevTool 流程
- Linux → ⚠️ 官方流程未覆盖，可用 Rockchip 官方 `upgrade_tool` / `rkdeveloptool` 自行烧录
- macOS → ❌ 无官方工具，建议借一台 Windows 机器烧录（烧完后开发不受影响）

**开发板系统（无选择余地）**：

- 必须是 **KaihongOS**（基于 OpenHarmony 标准系统、Linux 内核）
- 必须是 **aarch64** 架构
- 不能换 Ubuntu / Debian 等其他发行版跑 M-Robots

**一句话**：Windows 做快速体验完全够用；想编译源码才需要 Ubuntu 22.04（WSL2 可行），且编译只支持 RK3588A。

## 参考文档

- [robot_docs 文档仓库](https://gitcode.com/m-robots/robot_docs)
- [开发板选型](https://gitcode.com/m-robots/robot_docs/blob/master/docs/0-安装/01-开发板选型.md)
- [HDC 工具安装及使用](https://gitcode.com/m-robots/robot_docs/blob/master/docs/0-安装/02-HDC工具安装及使用.md)
- [安装 M-Robots 环境（编译）](https://gitcode.com/m-robots/robot_docs/blob/master/docs/0-安装/03-安装M-Robots环境.md)
- [镜像烧录](https://gitcode.com/m-robots/robot_docs/blob/master/docs/0-安装/04-镜像烧录.md)
- [开发工具](https://gitcode.com/m-robots/robot_docs/blob/master/docs/1-开发板和工具使用/01-开发工具.md)
- [M-Robots_release 固件仓库](https://atomgit.com/m-robots/M-Robots_release)（[GitCode 镜像](https://gitcode.com/m-robots/M-Robots_release)）
- [OpenHarmony HDC 官方文档](https://docs.openharmony.cn/pages/v5.1/zh-cn/application-dev/dfx/hdc.md)
- [Rockchip rkdeveloptool（Linux 开源烧录工具）](https://github.com/rockchip-linux/rkdeveloptool)
