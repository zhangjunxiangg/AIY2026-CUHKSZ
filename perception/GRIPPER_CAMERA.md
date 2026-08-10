# 夹爪摄像头说明（icSpring UVC 相机）

> 照片位置：`C:\Users\15728\Desktop\AIY黑客松\机器车相机\`
> - `抓夹相机1.jpg` / `抓夹相机2.jpg`：夹爪摄像头特写
> - `机器人车.jpg`：整机侧面，可见夹爪摄像头与 Astra 深度相机安装位置
> - `深度相机（车）.jpg`：Astra Pro Plus 深度相机特写

---

## 1. 硬件信息

| 项目 | 内容 |
|---|---|
| 型号 | icSpring camera（标准 UVC 摄像头） |
| USB VID:PID | `32e6:9005` |
| 驱动 | Linux 内核自带 `uvcvideo`，插上即用 |
| 视频节点 | `/dev/video20`（图像流）、`/dev/video21`（元数据） |
| 安装位置 | 机械臂腕部、夹爪上方，朝下安装 |
| 用途 | 近距离精定位 / 夹取前确认 |

---

## 2. 板端现状

- **没有专用驱动代码**：该相机是标准 UVC 设备，系统只识别到 `/dev/video20`，没有针对它的 ROS 包或 launch 文件。
- **容器里没有通用 UVC 包**：`rk3588s-vision` 容器内没有 `usb_cam`、`uvc_camera` 等通用节点，`/vision_ws/src/` 下只有 `orbbec_camera`（Astra/Gemini 专用）等。
- **唯一相关文件**：`/data/robot-host/probe-all-cameras-4.1.sh` 只是诊断脚本，不会启动它。
- **当前在跑的相机节点**：只有 `/astra_camera/camera`（Astra Pro Plus）。

---

## 3. 如何启用

### 方式 A：使用本仓库的 `gripper_camera_node.py`（推荐）

在板端执行：

```bash
run python3 /data/local/perception/gripper_camera_node.py \
  --device /dev/video20 \
  --topic /gripper_camera/image_raw \
  --width 640 \
  --height 480 \
  --fps 15
```

D 侧订阅：

```bash
rostopic echo /gripper_camera/image_raw
```

### 方式 B：安装 ros-noetic-usb-cam（需联网 apt）

```bash
apt update && apt install -y ros-noetic-usb-cam
rosrun usb_cam usb_cam_node \
  _video_device:=/dev/video20 \
  _image_width:=640 \
  _image_height:=480 \
  _pixel_format:=yuyv \
  _camera_frame_id:=gripper_camera_optical_frame
```

> 比赛现场通常无 apt 网络，建议直接用方式 A。

---

## 4. 当前画面问题

临时用 `cv2.VideoCapture(20, cv2.CAP_V4L2)` 抓取到的画面：

- 自动曝光参数：`auto_exposure=3`，`exposure=313`
- 画面整体偏白/过曝，20 帧后均值仍有 201
- 画面底部有两个黑团，疑似夹爪本体

**可能原因**：

1. 镜头正对着很近的白色桌面/物体，导致自动曝光压不下来。
2. 镜头被夹爪结构部分遮挡。
3. 镜头上有保护膜/污渍（看照片镜头是裸露的，无明显保护膜）。

**现场确认建议**：

- 让夹爪张开，放一张深色/有图案的纸在夹爪下方 10–20 cm 处，再抓图。
- 如果仍然过曝，尝试把相机拆下/转动，确认它到底朝向哪里。
- 检查镜头是否有红外截止滤光片缺失导致的异常亮度（icSpring 相机部分型号无 IRCUT，白天会过曝）。

---

## 5. 调试命令速查

```bash
# 查看设备
lsusb | grep 32e6
ls -l /dev/video20 /dev/video21

# 快速抓一张图验证（容器内）
run python3 - <<'PY'
import cv2, time
cap = cv2.VideoCapture('/dev/video20', cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
time.sleep(1)
ok, frame = cap.read()
if ok:
    cv2.imwrite('/tmp/gripper_check.jpg', frame)
    print('saved /tmp/gripper_check.jpg, mean=', frame.mean())
cap.release()
PY

# 拉回电脑看
# scp mrobots:/tmp/gripper_check.jpg ./
```

---

## 6. 与主感知链路的关系

夹爪摄像头不是主感知链路的一部分，它的定位是：

- **粗定位**：Astra + Gemini335（已部署）
- **精定位 / 抓取确认**：夹爪摄像头（待现场确认可用性）

如果夹爪摄像头画面可用，后续可以在 `gripper_camera_node.py` 基础上加：

- 内参标定（`camera_info` 话题）
- 手眼标定（`gripper_camera_optical_frame` → `gripper_link`）
- 末端目标检测（复用 `perception_node.py` 的检测器）

但当前第一优先级是：**确认它看到的不是白色噪点**。
