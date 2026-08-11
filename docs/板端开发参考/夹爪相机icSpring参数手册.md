# 夹爪相机（icSpring UVC）参数手册

> 检查日期：2026-08-05
> 检查方式：SSH 上板 → `rk3588s-vision` 容器内用 V4L2 ioctl 直接枚举（脚本：`src/perception/icspring_query.py`，原始输出：`docs/板端开发参考/icspring_report.txt`）
> 检查过程只读，未修改相机属性、未重启服务、未移动机器人。

## 1. 设备身份

| 属性 | 值 |
|---|---|
| 设备名 | `icspring camera` |
| 驱动 | `uvcvideo`（标准 UVC） |
| USB VID:PID | `32e6:9005` |
| USB 位置 | `usb-fc800000.usb-1.3.1`（USB 2.0） |
| 出图节点 | `/dev/video20` |
| 另一节点 | `/dev/video21`（不可读图，元数据节点） |
| 物理位置 | 夹爪上方（眼在手上，eye-in-hand） |

容器 `rk3588s-vision` 已映射 `/dev/video20` 和 `/dev/video21`，OpenCV 4.2.0 可直接 `cv2.VideoCapture(20, cv2.CAP_V4L2)` 打开出图。

## 2. 输出格式（只有一档）

| 像素格式 | 分辨率 | 可选帧率 |
|---|---|---|
| YUYV 4:2:2（无压缩） | 640×480 | 30 / 25 / 20 / 15 / 10 / 5 fps |

注意：只有一个分辨率，**没有 MJPEG** 等压缩格式。USB 2.0 下 640×480@30fps YUYV 约 18MB/s，带宽够用，但无法提供更高分辨率图像。

## 3. 可调参数（V4L2 控制项，共 9 个）

| 参数 | 类型 | 范围 | 默认值 | 检查时值 | 说明 |
|---|---|---|---|---|---|
| Brightness 亮度 | int | -128..127 | 0 | 0 | 手动亮度偏移 |
| Saturation 饱和度 | int | 0..128 | 25 | 25 | 默认偏低，颜色偏淡 |
| White Balance Temperature, Auto | bool | 0/1 | 1 | 1 | 自动白平衡开关 |
| White Balance Temperature 色温 | int | 2800..6500K | 4000 | 4000 | 自动 WB 开启时 **INACTIVE** 不可调 |
| Gamma | int | 1..500 | 67 | 67 | 伽马曲线 |
| Power Line Frequency 防频闪 | menu | 0=Disabled / 1=50Hz / 2=60Hz | 1 | 1 | 国内灯光环境保持 **50Hz** |
| Backlight Compensation 逆光补偿 | int | 0..1 | 0 | 0 | 仅开关两档 |
| Exposure, Auto 曝光模式 | menu | 1=Manual / 3=Aperture Priority | 3 | 3 | 当前自动曝光 |

## 4. 缺口与注意点

- **无手动曝光细调**：驱动未暴露 `Exposure (Absolute)`，手动曝光档下也没有曝光值接口；弱光/强光只能靠 Brightness 和 Gamma 补偿。
- **无对比度/锐度控制**：没有 Contrast、Sharpness 项，图像风格调整只能在软件端（OpenCV）做。
- **首帧过曝**：打开相机后自动曝光需要收敛时间，实测首帧接近全白（均值 250.9/255），连续读 10–20 帧后正常（均值 ~201）。**采图程序必须丢弃前 10–20 帧。**
- **饱和度默认 25 偏低**：对 HSV 颜色分割兜底方案，若颜色区分度差可考虑拉高 Saturation。

## 5. ROS 接入方式

- 容器内未安装 `usb_cam` / `uvc_camera` 包；出厂 ROS 图中只有 Astra 的 `orbbec_camera`（话题前缀 `/astra_camera/`）。
- 该相机已通过**自写 OpenCV 发布节点**接入 ROS，见 §6，直接可用。
- 备选方案（一般不需要）：容器内 `apt install ros-noetic-usb-cam`（需容器联网），标准方案，直接出 `/usb_cam/image_raw`。

## 6. ROS 接入：gripper_camera_node.py（已可用）

相机已通过自写 OpenCV 发布节点接入 ROS（方案 2，零依赖）。**无需安装 usb_cam。**

### 文件位置

| 位置 | 路径 |
|---|---|
| 板端（实际运行） | `/data/local/perception/gripper_camera_node.py` |
| 仓库（本地副本） | `src/perception/gripper_camera_node.py` |

### 启动（SSH 上板后执行）

```sh
cd /data/local/perception
run python3 gripper_camera_node.py --device /dev/video20 --topic /gripper_camera/image_raw
```

输出话题：`/gripper_camera/image_raw`（`sensor_msgs/Image`，bgr8，640×480 @ 15fps，frame_id=`gripper_camera_optical_frame`）。

可选参数：`--width --height --fps --frame-id`，均有默认值，一般不用改。

### 停止

节点已实现优雅退出，`Ctrl+C`（SIGINT）或直接 `kill <pid>`（SIGTERM）都会正常释放相机并打日志，不会残留占用 `/dev/video20`：

```
[GRIPPER_CAM] camera /dev/video20 released, node stopped
```

### 使用注意

- **打开后先丢 10–20 帧**（自动曝光收敛，首帧接近全白，见 §4）。
- 画面底部两个深色圆斑是夹爪自己的手指，属正常现象。
- 若画面全黑/异常，先确认夹爪张开、镜头无遮挡。
- **测试完务必停掉节点**，不要让它挂在后台占着相机（其他程序再想开 `/dev/video20` 会冲突）。

## 7. 实测样张

- `icspring_video20.jpg`：打开后首帧，过曝近全白，底部可见夹爪两指阴影。
- `icspring_settled.jpg`：连续读 20 帧后，曝光收敛，画面为近距离浅色平面 + 夹爪两指（画面底部约 27%、67% 宽度处）。

两张样张在 `docs/板端开发参考/` 本目录，查询脚本在 `src/perception/icspring_query.py`。
