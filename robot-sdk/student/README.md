# Kaihong 4.1 源码总入口

从本目录开始阅读。交付件提供底层 ROS 源码、硬件接口、标定工具和场景
框架，不提供完整抓取/运输参考 Demo。参赛者需要自己实现比赛状态机，并在实车上
逐级验证。

## 30 秒快速上手：先用 M-Claw

小车板端已经安装统一机器人操作 Skill。启动交互式 M-Claw：

```sh
mclaw
```

仅在模型、凭据尚未配置时执行一次 `mclaw setup`。进入 M-Claw 后直接说自然语言，
不需要输入脚本路径。建议先说：

```text
返回底盘、雷达和机械臂状态
```

> **辅助相机注意：** M-Claw 只在小车上运行，辅助板没有 M-Claw。先在辅助板终端
> 用小车 IP 配置并启动相机；再向小车 M-Claw 提供**辅助板当前 IPv4**，例如
> `连接辅助相机 192.168.1.88`。不要让 M-Claw 猜测或沿用旧 IP。

### M-Claw 可以做什么

| 能力 | 可以直接说 | 结果与限制 |
|---|---|---|
| 控制小车运动 | `以 0.1 m/s 的速度向前移动 10秒` | 必须同时说清方向、速度和持续时间； |
| 返回舵机值并控制机械臂 | `返回机械臂当前舵机值`；把机械臂舵机 ID3 调整到 xxx值` | 一次只调整一个 ID；ID5 是腕部旋转，ID10 是夹爪，夹爪必须单独明确要求 |
| 返回雷达检测值 | `返回雷达状态和一帧扫描检测值` | 只读取 `/scan`，不会移动底盘 |
| 拍摄深度相机内容 | `用深度相机拍一张彩色图和深度图，并显示拍摄结果` | 固定覆盖最新 RGB、16 位深度、深度预览和 JSON，不累计图片 |
| 运行颜色分类 Demo | `运行颜色分类`、`运行 color sorting demo` 或 `运行 colorsorting 的 demo` | 检测红、黄、绿、蓝并返回置信度和建议收纳区；当前 Demo 只感知、不执行抓取 |
| 连接辅助相机 | 在小车的 M-Claw 中说 `连接辅助相机 <辅助板IPv4>` | 用户必须提供辅助板当前 IP；小车核对发布源并收到真实 RGB-D 才算成功 |
| 查看辅助相机照片 | `查看最新照片` 或 `返回最新辅助相机照片的浏览器地址` | 返回同一局域网可打开的 JPG 地址；仅共享固定最新文件，默认 10 分钟后自动关闭 |

常用补充说法：

```text
停止底盘
检查辅助相机状态，辅助板 IP 是 <辅助板IPv4>
拍一张辅助相机的 RGB-D，辅助板 IP 是 <辅助板IPv4>
查看最新照片
列出比赛可用的 ROS 接口
```

颜色分类demo固定覆盖输出：

```text
/data/robot-host/student/output/color-sorting/latest-color-sorting.jpg
/data/robot-host/student/output/color-sorting/latest-color-sorting-depth-preview.jpg
/data/robot-host/student/output/color-sorting/latest-color-sorting.json
```

M-Claw 只安装并运行在小车板上。`kaihong-robot-operations` 统一提供整机状态、比赛
接口、底盘、机械臂、Astra、雷达、Gemini 335 辅助相机和非运动四色分类 Demo。
Gemini 335 辅助板没有 M-Claw；连接时不得猜测或沿用旧 IP。

辅助相机电脑端 Python 依赖：

```sh
python -m pip install -r requirements-pc.txt
```

## 源码位置

| 内容 | 板端路径 |
|---|---|
| 本手册、场景模板、辅助标定 | `/data/robot-host/student` |
| 底盘、控制板、舵机驱动 | `/data/robot-host/src` |
| 机械臂、运动学、消息与服务 | `/data/robot-host/host_arm` |
| SLAM 与导航配置 | `/data/robot-host/navigation_runtime` |
| 辅助相机动态目标接口 | `/data/robot-host/student/interfaces` |
| Astra—机械臂标定 | `/data/robot-host/astra-arm-calibration/student` |
| M-Claw 统一机器人 Skill | `/data/local/tmp/.mclaw/skills/kaihong-robot-operations` |


## Docker

进入 Astra 视觉容器：

```sh
docker ps
docker exec -it rk3588s-vision bash
cd /vision_ws/src
ls -la
```

## Gemini 335 跨板辅助相机

Gemini 驱动和图像预处理运行在独立辅助板，小车作为 ROS Master。更换 Wi-Fi
后，在辅助板用小车当前 IP 重新配置一次：

```sh
/data/gemini335/configure-car-ros.sh <小车当前IP>
/data/gemini335/start-gemini335.sh
/data/gemini335/status-gemini335.sh
```

`start-gemini335.sh` 会检查是否真的收到深度帧；USB 端点未及时恢复时会自动重启
容器一次。`status-gemini335.sh` 显示 `DEPTH_FRAME=PASS` 和
`COMPRESSED_COLOR_FRAME=PASS` 才表示辅助相机数据链路可用。

辅助板没有 M-Claw。完成上面的配置、启动和状态检查后，回到小车运行 M-Claw，
并提供辅助板当前地址：

```text
连接辅助相机 <辅助板IPv4>
检查辅助相机状态，辅助板 IP 是 <辅助板IPv4>
拍一张辅助相机的 RGB-D，辅助板 IP 是 <辅助板IPv4>
```

小车上的 M-Claw 只核对图像话题发布源并接收真实彩色帧、深度帧，不执行辅助板
本地命令。

小车侧可直接使用：

```text
/aux_camera/color/image_raw/compressed   JPEG 彩色图，默认最高 5 fps
/aux_camera/depth/image_raw              配准深度，16UC1，单位 mm
/aux_camera/color/camera_info            彩色内参
/aux_camera/depth/camera_info            深度内参
```

一次性接收并解码 RGB-D：

```sh
/data/robot-host/student/tools/receive-aux-rgbd-once.sh
```

固定覆盖输出到 `/data/robot-host/student/output`，不会按时间戳累积文件。比赛
程序宜在辅助板完成视觉识别，只向小车发布目标坐标、时间戳和置信度；原始深度
仅在标定、调试或按需定位时订阅。

输出包含 JPEG 彩色图、16 位 PNG 深度图、PGM 深度预览和 JSON 元数据。接收
工具不依赖小车宿主 OpenCV，避免与板端 Python/OpenCV ABI 版本冲突。


## 深度相机四颜色分拣 Demo

位置student/demo/color_sorting
功能：检测红、黄、绿、蓝并返回置信度和建议收纳区；

```sh
/data/robot-host/student/demo/color_sorting/run-color-sorting-demo.sh
```

结果固定覆盖到 `student/output/color-sorting`，并在运行期间以 JSON 字符串发布到
`/student/color_sorting/decision`。其中 `recommendation_ready` 只表示颜色分拣建议
可用；由于没有使用当前实车手眼外参，`pick_ready` 恒为 `false`。

## 相机手眼标定
在使用相机获取位置的时候，需要将参数进行转化，以下标定非绝对全部需要，参赛者可以根据自由场景进行

参赛者须自主标定相机
1. 板载 Astra 到机械臂：

```text
/data/robot-host/astra-arm-calibration/student/README.md
```

2. 辅助相机到比赛地面/小车移动坐标：
   `student/calibration/auxiliary/aux-ground-calibration.py`

3. 辅助相机到机械臂 `base_link`：
   `student/calibration/auxiliary/aux-arm-handeye.py`

辅助相机说明：

```text
/data/robot-host/student/calibration/auxiliary/README.md
```

二维地面移动参数不能用于机械臂三维抓取，两套辅助标定必须分开验收。相机位置、
角度或支架改变后，对应外参必须重新标定。

## 参赛建议
建议新建自己的 catkin 工作区和 ROS 包，状态机至少包含：

1. 启动健康检查；
2. 目标检测、深度对齐和时间戳新鲜度；
3. 辅助相机地面定位或机械臂定位的正确外参选择；
4. 导航/底盘对齐；
5. 抓取前重新检测、IK 和碰撞/行程检查；
6. 夹取、抬升、运输、放置；
7. 每一步超时、失败重试和零速停车。

建议的最小 ROS 包结构：

```text
student_tasks/
├─ CMakeLists.txt
├─ package.xml
├─ config/
│  └─ my-scene.yaml
├─ launch/
│  └─ task.launch
└─ scripts/
   └─ task_node.py
```

参赛者节点通过 Topic、Service 和 Action 调用现有底层功能，不重新编写 STM32、
雷达、相机或舵机驱动。
