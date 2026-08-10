# board_scripts/ — 机器车板端部署与运维脚本

本目录存放直接在 KaihongBoard-3588S（宿主机或 `rk3588s-vision` Docker 容器）上运行的脚本，用于摄像头发现、UVC 取流、感知管线启动与保活。

## 运行环境

- 宿主机：KaihongBoard-3588S，OpenHarmony / Linux 机器人宿主系统
- 容器：`rk3588s-vision`（ROS1 Noetic + Python 3.11 + cv2）
- 典型部署路径：`/data/robot-host/board_scripts/`

## 文件清单

| 文件 | 运行位置 | 用途 |
|---|---|---|
| `find_astra.py` | 容器内 | 扫描 `/dev/video*`，按 `USB 2.0 Camera` 名称找到 Astra UVC 设备索引 |
| `cap_astra_uvc.py` | 容器内 | 读取 `astra_dev.txt` 中的设备号，抓取一帧 RGB 存为 `/out/astra_uvc_latest.jpg` |
| `capture-astra-uvc.sh` | 宿主机 | 一键发现 Astra UVC 设备并抓拍一张 JPG，输出到 `/data/robot-host/student/output/` |
| `uvc_astra_publisher.py` | 容器内 | 把 Astra UVC 流发布为 ROS 话题 `/astra_camera/rgb/image_raw`，带自动重连与看门狗 |
| `supervise-perception.sh` | 宿主机 | 守护 `uvc_astra_publisher.py` + `perception_node.py`，进程/话题卡死时自动重启 |
| `astra_watchdog.sh` | 宿主机 | 轻量独立看门狗：仅监控 `/astra_camera/rgb/image_raw` 是否有帧，卡死时重启 vision 容器 |

## 快速用法

```bash
# 宿主机：抓一张 Astra 当前画面（输出到 student/output/astra_uvc_latest.jpg）
./capture-astra-uvc.sh

# 宿主机：启动完整感知管线守护（publisher + perception_node）
./supervise-perception.sh

# 宿主机：仅启动 Astra 话题看门狗
./astra_watchdog.sh
```

## 注意事项

- `capture-astra-uvc.sh` 会先在容器内杀掉旧的 `uvc_astra_publisher.py`，释放摄像头后再抓拍。
- `uvc_astra_publisher.py` 设置 `CAP_PROP_BUFFERSIZE=1` 并预热 10 帧，避免发布缓存旧帧。
- `supervise-perception.sh` 在 120 秒内最多重启 5 次，超过则退出，防止无限崩溃循环。
- `astra_watchdog.sh` 通过 `docker exec` 在容器内运行一次 4 秒等帧检查，拿不到帧就调用宿主机上的 `stop-vision-4.1.sh` / `start-vision-4.1.sh` 重启整个 vision 容器。
