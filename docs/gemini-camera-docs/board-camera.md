# 已连接主板与相机检查

检查日期：2026-08-05（Asia/Shanghai）

下文使用的证据标签：

- **VERIFIED-LIVE**：在本次检查期间从已连接的主板、正在运行的容器或实时 ROS 消息中读取。
- **SOURCE-VERIFIED**：从项目提供的文件或驱动源代码中读取。
- **NOT VERIFIED**：根据当前证据无法得出结论。

没有重启任何服务，没有修改相机属性，没有移动机器人硬件，也没有向主板写入文件。

## 结论摘要

**VERIFIED-LIVE：** 已连接设备是 M-Robots 主板，型号为基于 RK3588S 的 `KaihongBoard-3588S`。Ubuntu 笔记本可以通过现有 SSH 别名 `mrobots` 访问它，地址为 `172.20.10.5:2223`。

当前运行的 ROS1 相机是 **Orbbec Astra Pro Plus** 结构光 RGB-D 相机。它的 RGB 和 IR 流以约 30 Hz 正常工作。深度话题也以约 30 Hz 发布，但当前测试的每个深度像素都是 0。生成的点云为空。因此，相机已连接并且部分功能正常，但**可用深度目前为 FAIL**。

这块主板还暴露出一个独立的 icSpring UVC 相机，对应 `/dev/video20` 和 `/dev/video21`。它在物理上存在，但不是当前 Astra ROS 启动配置所选择的设备。

## 主板身份

| 属性 | 已验证值 |
|---|---|
| 产品 | `KaihongBoard-3588S` |
| 设备树型号 | `RK3588S CoolPi 4B Board` |
| 制造商 / 品牌 | `Kaihong` / `Kaihong` |
| 硬件版本 | `V1.0` |
| OS 产品版本 | `KaihongOS 4.1.2 C12` |
| OpenHarmony 版本 | `OpenHarmony-4.1.7.5` |
| OpenHarmony API | `11` |
| 内核 | Linux `5.10.110-ab52`，构建日期 2025-04-11 |
| 架构 | 64 位 `aarch64` |
| CPU | 8 个 ARM 核心：4 个 Cortex-A55 级别（`0xd05`）和 4 个 Cortex-A76 级别（`0xd0b`） |
| 主板 CPU 序列号 | `88d7e5a3c4ed07c5` |
| 内存 | 总计 8,111,664 kB（约 7.7 GiB） |
| Swap | 1.0 GiB，检查时未使用 |
| 10:19 CST 时的运行时间 | 1 小时 7 分钟 |

### 存储

| 挂载点 | 大小 | 已用 | 可用 | 使用率 | 含义 |
|---|---:|---:|---:|---:|---|
| `/` | 2.8 GiB | 2.7 GiB | 143 MiB | 96% | 根文件系统几乎已满；避免在这里保存采集文件。 |
| `/data` | 51 GiB | 9.0 GiB | 42 GiB | 18% | 主要可写数据区域。 |
| `/vendor` | 240 MiB | 68 MiB | 172 MiB | 29% | 厂商分区。 |
| `/sys_prod` | 300 MiB | 42 MiB | 258 MiB | 14% | 系统产品分区。 |
| `/chip_prod` | 240 MiB | 27 MiB | 212 MiB | 12% | 芯片产品分区。 |

## 连接性

| 属性 | 已验证值 |
|---|---|
| 笔记本入口 | `ssh mrobots` |
| SSH 目标 | `root@172.20.10.5`，端口 `2223` |
| 主板 Wi-Fi 接口 | `wlan0` |
| 主板 IPv4 | `172.20.10.5/28` |
| Wi-Fi 驱动 | `aicwf_sdio` |
| 链路状态 | `UP`、`RUNNING`；检查时未报告 RX/TX 错误 |
| 从笔记本使用 HDC | 找到了已安装的客户端，但本次检查期间实时 HDC 查询超时。 |

提供的 `exp-openharmony-wifi-sta-test.md` 仅作为背景资料使用。由于 Wi-Fi 当时已经连接，因此没有启动 `sta_test`，也没有修改网络设置。

## 相机硬件

### 当前使用的 Astra Pro Plus RGB-D 设备

当前使用的 ROS 驱动组合了两个 USB 接口：

| 功能 | USB VID:PID | USB 描述符 | 速度 |
|---|---|---|---|
| 深度/IR 传感器 | `2bc5:060f` | `Orbbec(R) ORBBEC Depth Sensor` | USB 2.0，480 Mb/s |
| RGB 传感器 | `2bc5:050f` | `Sonix Technology Co., Ltd. USB 2.0 Camera`，USB 序列号 `SN0001` | USB 2.0，480 Mb/s |

ROS 驱动自身报告：

| 属性 | 已验证值 |
|---|---|
| 型号 | `Astra Pro Plus` |
| 相机序列号 | `ACRL16401WF` |
| 类型 | `structured light monocular camera` |
| 固件 | `RD2510` |
| Orbbec SDK | `1.9.1` |
| ROS 相机封装 | `1.4.3` |
| 驱动日志中的设备 UID | `1-1.4.1-6` |
| LDP 设置 | `true` |
| 深度曝光 | `1049` |
| 深度增益 | `8000` |
| IR 曝光 | `1049` |
| IR 增益 | `8000` |
| 彩色自动曝光 | `true` |
| 彩色增益 | `0` |
| 自动白平衡结果 | `1` |
| 白平衡 | `4600` |

`LDP=true` 表示驱动的 LDP 功能已启用。提供的源代码读取 `OB_PROP_LDP_BOOL` 开关；仅凭这一结果，无法证明保护机制当前确实被触发。

### 独立的 icSpring UVC 设备

| 属性 | 已验证值 |
|---|---|
| USB VID:PID | `32e6:9005` |
| 制造商/产品 | `icSpring` / `icspring camera` |
| 速度 | USB 2.0，480 Mb/s |
| Linux 节点 | `/dev/video20`、`/dev/video21` |
| 是否为当前 Astra ROS 源 | 否；这些节点位于 USB 路径 `1-1.3.1`，而 Astra 深度设备位于 `1-1.4.1`。 |

主板还具有内部 RK ISP/CIF 视频节点 `/dev/video0` 至 `/dev/video19`。这些节点存在，并不能证明它们是当前使用的图像源。

## 相机软件栈

| 层级 | 已验证状态 |
|---|---|
| 容器 | `rk3588s-vision`，运行中，重启次数为 0 |
| 镜像 | `rk3588s-ros1-vision:noetic` |
| 容器网络 | Host network（主机网络） |
| 容器权限 | Privileged（特权模式） |
| ROS | ROS1 Noetic |
| 容器内 Python | 3.8.10 |
| 相机进程 | `orbbec_camera_node` |
| 启动文件 | `/vision_ws/src/orbbec_camera/launch/astra_pro_plus.launch` |
| ROS 节点 | `/astra_camera/camera` |
| 检测器 | 已禁用（`DETECTOR=0`） |
| Web 相机界面 | 已禁用（`WEB=0`） |

已配置的数据流：

| 数据流 | 设备格式 | ROS 编码 | 分辨率 | 配置/实际速率 |
|---|---|---|---|---|
| RGB | MJPG | `rgb8` | 640x480 | 30 fps / 约 30 Hz |
| 深度 | Y11 | `16UC1` | 640x480 | 30 fps / 约 30 Hz |
| IR | Y10 | `mono16` | 640x480 | 30 fps / 约 30 Hz |
| 深度点云 | XYZ 浮点字段 | `sensor_msgs/PointCloud2` | 根据深度生成 | 消息约 30 Hz，但为空 |

驱动参数显示：`enable_depth=true`、`enable_ir=true`、`enable_color=true`、`enable_point_cloud=true`、`enable_colored_point_cloud=true`、`enable_soft_filter=true`，以及 `depth_registration=false`。

驱动日志还显示 `ALIGN_D2C_HW_MODE`，但公开的 ROS 参数显示 `depth_registration=false`；注册点云话题没有发布消息。在非零深度帧出现并且显式对齐测试通过之前，不要假设 RGB 与深度像素已经有效对齐。

## 当前相机健康状态

| 能力 | 结果 | 证据 |
|---|---|---|
| RGB 图像 | **PASS** | 640x480 `rgb8`；约 30 Hz；变化中的像素统计值。 |
| IR 图像 | **PASS** | 640x480 `mono16`；采样帧中 100% 像素非零；约 30 Hz。 |
| 深度消息传输 | **PASS** | 640x480 `16UC1`，每帧 614,400 字节，约 30 Hz。 |
| 可用深度距离 | **FAIL** | 连续 4 秒内的 89 帧都包含 0 个有效像素；最小值=最大值=中心值=0。 |
| 未注册点云 | **FAIL** | 消息到达，但宽度为 0、负载为 0 字节、点数为 0。 |
| 已注册点云 | **FAIL / 未发布** | 公开的话题超时；`depth_registration=false`。 |
| 相机标定文件 | **FAIL / 缺失** | 驱动日志：未找到 `astra_camera_color.yaml` 和 `astra_camera_ir.yaml`。驱动发布的是回退/默认矩阵。 |
| 手眼标定 | **NOT VERIFIED** | 未进行物理标定或变换验证。 |

### 健康检查的重要限制

`/data/robot-host/healthcheck-depth-camera-4.1.sh` 只检查某个话题是否发布消息，以及 `rostopic hz` 是否检测到发布频率。它不会检查深度像素值或点数量。在当前全为 0 的数据情况下，该脚本可能错误地报告深度/点云为 PASS。可靠的验收检查还必须要求：

- 至少有一个非零深度像素，最好还要检查合理的有效像素百分比；
- 深度值（单位为毫米）处于合理范围；
- 点云的 `width > 0`、负载非零，并且 XYZ 点为有限值；
- 如果需要已注册数据，则已注册话题上确实有实际消息。

## 发现的驱动警告

- 缺少彩色标定文件：`/root/.ros/camera_info/astra_camera_color.yaml`。
- 缺少 IR 标定文件：`/root/.ros/camera_info/astra_camera_ir.yaml`。
- 在当前设备/驱动组合中，部分曝光/自动曝光属性不受支持。
- 在检查的日志中，没有发现明确的 USB 断开或相机进程崩溃。

## 安全的后续诊断步骤

以下内容仅为建议；由于它们会改变硬件/软件状态或需要现场确认，本次检查没有执行。

1. 检查是否有物体直接遮挡或接触 Astra 的 IR 投影器/深度窗口。LDP 已启用，而被遮挡或距离过近的目标可能会抑制结构光深度。
2. 目视确认哪一台物理设备是 Astra Pro Plus，哪一台是独立的 icSpring 相机。
3. 在不移动机器人底盘或机械臂的前提下，将 Astra 的视野对准正常工作范围内的有纹理物体，然后重复非零深度检查。
4. 如果深度仍然为 0，询问组织方是否允许仅重启 `rk3588s-vision`、重新插拔 Astra USB 线缆，或修改 LDP/激光状态。这些都是会改变状态的操作，本次检查特意没有执行。
5. 在使用相机坐标进行导航或机械臂控制之前，获取或创建经过验证的相机标定文件。
6. 修复所提供的健康检查，使全零深度图像和空点云无法通过验收。

## 证据边界

本报告证明的是检查时刻的软件和传感器数据流状态。它不能证明机械准备就绪、安全的机器人运动、正确的三维标定、场地精度，或抓取/导航成功。
