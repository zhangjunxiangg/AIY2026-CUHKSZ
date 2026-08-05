# Gemini 335 辅助相机板

这套部署用于独立辅助板上的 Orbbec Gemini 335。相机节点在 Docker 中运行，向 ROS1 提供彩色图、配准深度图和相机内参；目标坐标与标定结果不得写死。

## 已验证配置

- 设备：Gemini 335，序列号 `CP0E1630003S`，USB 3.2。
- 固件：1.4.60。
- 驱动：OrbbecSDK ROS1 v2.2.4，内含 SDK 2.2.8，与该固件代际匹配。
- 彩色：640×480、15 fps、MJPG。
- 深度：640×480、15 fps、Y16，软件配准到彩色相机。
- 激光能量：1 档。板载 USB 直连在默认高档出现重连；若要提高激光能量，先使用满足 5 V、1.5 A 的独立供电 USB 3.x 集线器重新验证。
- 点云默认关闭，避免无谓占用 CPU、内存和网络。

## 板端命令

```sh
/data/gemini335/start-gemini335.sh
/data/gemini335/status-gemini335.sh
/data/gemini335/capture-gemini335.sh
/data/gemini335/stop-gemini335.sh
```

启动脚本会用真实深度帧做自检，必要时自动重启容器一次。状态命令最后应显示：

```text
DEPTH_FRAME=PASS
COMPRESSED_COLOR_FRAME=PASS
```

辅助板没有 M-Claw。配置、启动和状态命令在辅助板终端执行。

快照固定覆盖以下文件，不累积垃圾文件：

```text
/data/gemini335/output/latest-color.jpg
/data/gemini335/output/latest-depth.png
/data/gemini335/output/latest-depth-preview.jpg
/data/gemini335/output/latest-metadata.json
```

`latest-depth.png` 是 16UC1 毫米深度图，0 表示无效深度。

## 接入小车 ROS Master

先确认辅助板和小车在同一局域网，再执行：

```sh
/data/gemini335/configure-car-ros.sh <小车IP>
/data/gemini335/start-gemini335.sh
```

脚本会动态读取辅助板 IP，小车 IP 只写入运行配置，不写死在源码中。网络变化后重新执行即可。小车侧可订阅：

```text
/aux_camera/color/image_raw/compressed
/aux_camera/depth/image_raw
/aux_camera/color/camera_info
/aux_camera/depth/camera_info
```

配置成功后，在小车的 M-Claw 中提供辅助板当前地址：

```text
连接辅助相机 <辅助板IPv4>
```

小车核对图像话题发布源后接收真实 RGB-D。M-Claw 不运行在辅助板上。

ROS1 只在存在订阅者时传输图像。比赛程序应优先订阅压缩彩色图，并按需订阅深度；更推荐在辅助板本地完成识别，只向小车发布小数据量的目标像素、深度或 `PointStamped`。

兼容版驱动不自带压缩传输插件，因此部署中附带轻量 JPEG 节点，将彩色流限制为最高 5 fps、质量 75；原始彩色和深度话题仍保留用于本地处理与按需调试。

## 标定边界

相机内部的彩色—深度配准由驱动完成，但相机到机械臂基座、相机到小车底盘的外参必须由学生按实际安装姿态重新标定。辅助相机重装后应重新标定，不得复用旧外参。
