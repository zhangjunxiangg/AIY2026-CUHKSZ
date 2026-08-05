# Gemini 335 Web 双流监视（gemini335-web）

> 日期：2026-08-05
> 设备：辅助开发板 KaihongBoard-3588S（KaihongOS 4.1.2.11C12）+ Orbbec Gemini 335（SN CP0E1630003S，固件 1.4.60）
> 本目录同时存在于：辅助板 `/data/gemini335-web/` ↔ 电脑 `J:\Hackthon-Art\MRobots-OS-AIY-hackthon\gemini335-web\`
> 两侧同名同内容，cksum 已逐一核对一致（见文末清单）。

## 功能

启动服务后，在电脑浏览器打开一个页面即可同时看到 Gemini 335 的**彩色视频流**和**深度流**（TURBO 伪彩，0–5000 mm 固定量程，无效深度为黑色），页面顶部实时显示两路 FPS 和帧龄。

- 数据源：ROS1 话题 `/aux_camera/color/image_raw`（640×480 MJPG）和 `/aux_camera/depth/image_raw`（640×480 16UC1 毫米深度，软件配准到彩色）
- Web 服务：`gemini_web_stream.py`，运行在相机驱动容器（`rk3588s-gemini335`）内，监听 `0.0.0.0:8080`
- 传输：经 USB HDC 端口转发到电脑，不依赖任何 Wi-Fi/网络

## 日常使用

```powershell
# 电脑（Git Bash / CMD / PowerShell 均可）
hdc fport tcp:8080 tcp:8080     # 建转发；hdc 服务重启后需重跑
# 浏览器打开 http://localhost:8080
```

```sh
# 板端（hdc shell 或 M-Terminal）
sh /data/gemini335-web/start-web.sh     # 一键启动相机栈 + Web 服务（含自检）
sh /data/gemini335-web/status-web.sh    # 状态与帧统计
sh /data/gemini335-web/stop-web.sh      # 只停 Web 服务，相机继续跑
sh /data/gemini335/stop-gemini335.sh    # 停相机栈
```

Web 服务端点：`/`（监视页，滤波深度）、`/raw`（未滤波对比页）、`/color.mjpeg`、`/depth.mjpeg`（滤波）、`/depth_raw.mjpeg`（原始）、`/snapshot/*.jpg`、`/health`（JSON，含滤波器状态）。

## 深度滤波（2026-08-05 v2 抗残影版，depth-filter 子管线验证）

深度流经**展示层滤波**后输出：散斑清理（3×3 形态学开运算）→ 掩膜中值（5×5，保边）→ 时间域 EMA（α=0.15）。**抗残影（v2）**：以 15×15 局部密度判别"成片变化"——空间上连贯的深度跳变（真实运动）**当帧 snap**，孤立跳变（噪点）仍需连续 3 帧；无效像素保持缩短为 3 帧，物体离开后旧深度快速消退。原始 ROS 话题不动；原始深度对比在 `/raw` 页。

实测指标（板端 CPU，gate 全 PASS）：

| 指标 | 原始 | v1（纯平滑） | v2（抗残影） |
|---|---|---|---|
| 时间抖动（std 中位数，run2 剧烈运动序列） | 314.1 mm | 44.8 mm | 127.8 mm（-59.3%） |
| **残影不一致率（ghost disagreement）** | — | 0.224 | **0.059（v1 的 27%）** |
| 有效像素率 | 90.7% | 96.6% | 96.2% |
| 散斑连通域/帧 | 7.1 | 0.25 | 0.28（-96%） |
| 滤波耗时 p95 | — | 15.8ms | 16.8ms（极端运动序列；在线 27–31ms） |

run1 低运动序列上 v1/v2 平滑效果一致（std -79.7%）；v2 的代价仅是在剧烈运动时平滑略保守，换取残影消失。
证据视频：`run2/compare_ghost.mp4`（raw|v1|v2 三联，可见 v1 残留 1–2 秒的橙色斑块在 v2 中当帧跟随）、`live2/live_compare.mp4`（浏览器路径实录）、`run1/compare_depth.mp4`。

滤波参数可用环境变量调：`DF_ALPHA / DF_GATE_MM / DF_HOLD_FRAMES / DF_SNAP_FRAMES / DF_MEDIAN_KSIZE / DF_SNAP_DENSITY / DF_BOX_KSIZE`。
滤波器源码以 `depth-filter/util_filter.py` 为准（`gemini_web_stream.py` 内嵌副本保持同步）；
子管线方法学与目标态见 `depth-filter/MANIFEST.md`。

可调环境变量（启动容器前导出）：`GEMINI_WEB_PORT`（默认 8080）、`GEMINI_WEB_MAX_FPS`（默认 10）、`GEMINI_JPEG_QUALITY`（默认 80）、`GEMINI_DEPTH_MAX_MM`（默认 5000）。

## 稳定性设计

- Web 服务由容器 entrypoint 启动并带 `until` 守护循环：进程崩溃自动拉起，**容器重启也会自动恢复**
- 相机容器本身 `--restart unless-stopped`
- `start-web.sh` 可重复执行，每次重建容器并自检真实深度帧 + Web 健康检查，失败即非零退出
- ROS1 只在有订阅者时传图；Web 服务默认限 10 fps 编码，CPU 开销小

## 本次排障记录（2026-08-05）

接手时状态：驱动镜像/部署已存在（8/3 验证过），但容器崩溃循环、相机换插了 USB 口、板端无网络。

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | 容器崩溃循环 `RLException: cannot resolve host address for machine [localhost]` | ① `/data/gemini335/gemini335.env` 残留小车网络配置（ROS_IP=172.70.2.36 已失效）；② KaihongOS 的 Docker 生成**空 /etc/hosts**，回退到 127.0.0.1 后 roslaunch 无法解析 localhost | env 移作 `gemini335.env.car-ros-stale.bak`（接小车时由 `configure-car-ros.sh` 重新生成）；entrypoint 开头补写 localhost hosts 条目 |
| 2 | 无 wlan0 时启动脚本直接退出 | 原 `start-gemini335.sh` 强制要求 wlan0 IP | 增加回退：无 wlan0 时用 `127.0.0.1` 单机模式（原脚本备份为 `start-gemini335.sh.orig`） |
| 3 | 相机换插 USB 口后驱动看不到设备 | 原 `create-usb6-nodes.sh` 只建 bus 006 节点，相机实际枚举在 bus 001（USB2 口） | 新增 `create-usb-nodes.sh`：按 `/sys/bus/usb/devices` 动态创建全部总线节点 |
| 4 | Web 服务启动即退 `No module named 'cv_bridge'` | cv_bridge 在工作区（vision_ws/gemini_ws）里，仅 source `/opt/ros/noetic` 不够 | 改由容器 entrypoint 启动 Web 服务（entrypoint 已 source 全部工作区） |
| 5 | Git Bash 下 `hdc file send` 静默失败 | MSYS 把 `/data/...` 转成 Windows 路径 | 推送时 `export MSYS_NO_PATHCONV=1` |

Wi-Fi 备注：板端 `sta_test` 可配网（流程见《M-Robots OS 操作手册》§7）。实测 **iPhone 热点（WPA2/WPA3 混合）与该板驱动无法关联**（WPA-PSK 与 SAE 均失败）；建议用电脑 Windows 移动热点。配网成功后也可走 SSH 隧道看页面：`ssh -L 8080:127.0.0.1:8080 root@<板IP> -p 2223`。

## 验证记录（2026-08-05）

- `start-web.sh` 输出 `camera_frame_check=PASS` + `web_stream=UP port=8080`
- `/health`：color ≈7.5 fps、depth ≈7.5 fps、帧龄 <0.1 s
- `snapshots/color.jpg`、`snapshots/depth.jpg`：真实场景帧，深度结构与彩色画面吻合
- `snapshots/webpage-live.png`：电脑浏览器实测截图，双流同页正常渲染

## 文件清单（cksum 双侧一致）

| 文件 | 板端位置 | 说明 |
|---|---|---|
| `gemini_web_stream.py` | `/data/gemini335-web/` | Web 双流服务源码 |
| `start-web.sh` / `stop-web.sh` / `status-web.sh` | `/data/gemini335-web/` | Web 服务启停/状态 |
| `start-gemini335.sh` | `/data/gemini335/`（原件 .orig 备份） | 相机栈启动脚本（回退补丁版） |
| `container-entrypoint.sh` | `/data/gemini335/runtime/` | 容器入口（hosts 修复 + Web 守护） |
| `create-usb-nodes.sh` | `/data/gemini335/runtime/` | 全总线 USB 节点创建 |
| `snapshots/` | 双侧 | 验证截图（webpage-live.png 仅电脑侧，浏览器截图） |

## 注意事项

- 激光能量固定 1 档：板载 USB 直供在高档位会重连（8/3 已验证）。要提档需 5V/1.5A 独立供电 Hub 并重新验证
- 相机当前插在 USB2 口（bus 001），640×480@15 双流工作正常；若需更高帧率/分辨率，换 USB3 口（蓝口）
- 深度图单位是**毫米**，0 = 无效；网页伪彩量程固定 0–5000 mm（`GEMINI_DEPTH_MAX_MM` 可调）
- 相机到机械臂/底盘的外参需按实际安装重新标定，不得复用旧值
- `hdc fport` 转发在 hdc 服务重启后失效，重跑 `hdc fport tcp:8080 tcp:8080` 即可
