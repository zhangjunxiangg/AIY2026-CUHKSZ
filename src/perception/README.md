# src/perception/ — 学生感知节点包（角色C）

运行环境：本机调试用 Windows + Python 3.13 + opencv-python + numpy；
板端目标为 KaihongBoard-3588S 的 `rk3588s-vision` Docker 容器（Python 3.11 + ROS1 Noetic + cv2 + numpy）。
代码仅依赖 cv2/numpy/标准库（ros 模式另加 rospy/std_msgs/sensor_msgs），兼容 Python 3.11。
**板上日志一律英文**（mksh 终端中文乱码），代码注释可中文。

## 文件清单

| 文件 | 用途 |
|---|---|
| `detectors.py` | 纯算法库（不依赖 ROS）：颜色+形状（block/ball/cylinder/ring）、路锥、多尺度模板、QR；总入口 `run_pipeline` |
| `decode.py` | sensor_msgs/Image 手工解码（np.frombuffer，不用 cv_bridge）：rgb8/bgr8/mono8、16UC1/mono16、压缩 JPEG |
| `perception_node.py` | 主节点：`--sim` 本机图片模式 / `--ros` 板上订阅模式（支持 Astra / Gemini335） |
| `geometry3d.py` | 纯几何换算：像素+深度 → 相机坐标 → base_link/map |
| `blind_spot.py` | 盲区策略：深度有效性判断、单目测深、盲区标记 |
| `target_3d_node.py` | 3D 定位节点：2D 目标 → base_link/map 坐标（供角色 D 抓取） |
| `fusion_node.py` | 双相机融合：合并 Astra 与 Gemini335 的 3D 目标，盲区优先用辅助相机 |
| `config.json` | 全部可调参数（HSV 阈值、面积、形状阈值、模板、相机内外参、盲区、融合） |
| `calib_hsv.py` | 现场 HSV 取样工具（本机 GUI）：点图取色，输出 config 片段 |
| `make_template.py` | 模板裁剪工具（本机 GUI）：框选 ROI 存模板，输出 config 片段 |
| `sim_test.py` | 验收测试：对 practice/ 五张合成场景端到端跑 sim 模式并断言 |
| `test_geometry.py` | 离线单元测试：几何换算、盲区策略、3D 定位、双相机融合 |
| `templates/human_board.png` | 人形立牌模板（复制自 practice/template.png，与 tpl_scene.png 配套） |
| `sample_targets_3d_fused.json` | 给角色 D 的示例输出（含 camera/mono/aux 三种精度） |
| `mock_output_publisher.py` | 模拟发布器：把示例 JSON 发到 `/student/perception/targets_3d_fused`，供 D 无硬件调试 |
| `gripper_camera_node.py` | 把夹爪 USB 摄像头 `/dev/video20` 发布为 ROS 话题 `/gripper_camera/image_raw` |
| `GRIPPER_CAMERA.md` | 夹爪摄像头硬件说明、启用方法、调试命令 |
| `capture_dataset_frames.py` | 从 ROS 相机话题自动抓拍，生成 YOLO 训练用的原始图片 |
| `collect_yolo_dataset.py` | 用现有感知管线自动生成 YOLO 格式标签 |
| `yolo_detect.py` | YOLO 检测后端包装（Ultralytics / ONNX / RKNN） |
| `make_letter_templates.py` | 生成 A–D 字母模板 |
| `YOLO_TRAINING.md` | YOLO 训练、导出、部署流程 |
| `ROLE_C_TO_D.md` | 给角色 D 的盲区抓取与全局定位接口文档 |

## 输出格式（两种模式一致）

```json
{"ts": 1785768927.734, "status": "ok", "frame": [640, 480],
 "targets": [{"category": "red_block", "center": [110, 130], "confidence": 0.98,
              "bbox": [60, 80, 101, 101], "depth_mm": null}]}
```

- `status`：`ok` 正常检测（此时空 `targets` 数组 = 确实没看到目标）；
  故障心跳 `no_frame`（相机超时断流）/ `stale_frame`（帧过期）/ `decode_error`（解码失败）——
  故障时节点也会按频率发布，targets 为空，**下游据此区分"没目标"和"链路故障"**

- `category`：`red_block`/`green_ball`/`blue_cylinder`/`red_ring`（颜色_形状）、`cone`、模板名（如 `human_board`）、`qr:<解码内容>`（如 `qr:A`）
- `depth_mm`：深度开启时为目标 bbox 中心区域（`sample_fraction` 倍）的深度中位数，
  过滤 0 值与 <600mm/>8000mm 无效值；无有效深度或无深度源时为 `null`

## 本机用法（今晚跑通）

```bash
cd perception
python perception_node.py --sim --images ../practice/color_scene.png   # 单图
python perception_node.py --sim --images ../practice/ --loop 3         # 目录 + 重复
python sim_test.py                                                      # 验收测试（应 5/5 PASS）
python calib_hsv.py 现场照片.jpg --slot red                             # HSV 取样（GUI）
python make_template.py 现场照片.jpg letter_A                           # 裁模板（GUI）
```

## 板上运行命令速查（容器内，假设代码在 /data/local/perception/）

```bash
# 代码进容器（宿主机执行一次；若 /data/local 已挂载进容器则跳过）
docker cp /data/local/perception rk3588s-vision:/data/local/perception

# 进容器
docker exec -it rk3588s-vision bash

# 容器内：环境 + 确认相机驱动已起（官方摄像头 launch 先跑起来）
source /opt/ros/noetic/setup.bash
rostopic list | grep astra
rostopic hz /astra_camera/rgb/image_raw        # 确认有帧率

# 跑感知节点（默认 2Hz，无深度）
cd /data/local/perception
python3 perception_node.py --ros

# 带深度（每个目标附 depth_mm）
python3 perception_node.py --ros --depth

# 自定义配置
python3 perception_node.py --ros --config config.json

# 观察输出（另开一个 docker exec 终端）
rostopic echo /student/perception/targets
cat /tmp/perception_targets.json
```

- 发布话题：`/student/perception/targets`（std_msgs/String，JSON 字符串，latch=False）
- 落盘文件：`/tmp/perception_targets.json`（每帧覆盖写最新结果）
- 检测频率：config.json `ros.rate_hz`（1–5 按需）；取数用 `rospy.wait_for_message` + 时间戳新鲜度检查（`ros.freshness_s`）

## 3D 定位与双相机融合（给角色 D）

- 启动 Astra 3D 定位：`python3 target_3d_node.py --ros --camera astra`
- 启动 Gemini335 3D 定位：`python3 target_3d_node.py --ros --camera aux`
- 启动融合节点：`python3 fusion_node.py --ros`
- 角色 D 订阅最终话题：`/student/perception/targets_3d_fused`
- 无硬件调试 D 的代码：`python3 mock_output_publisher.py --ros --file sample_targets_3d_fused.json --rate 2`

盲区策略、输出格式和比赛日标定步骤详见 `ROLE_C_TO_D.md`。

## YOLO 训练与夹爪摄像头

- 自动抓拍原始图：`python3 capture_dataset_frames.py --topic /astra_camera/rgb/image_raw --out /data/local/dataset/aimaterials_raw`
- 生成 YOLO 标签：`python3 collect_yolo_dataset.py --images ../dataset_raw --out ../datasets/aimaterials`
- 训练/导出流程：`YOLO_TRAINING.md`
- 启动夹爪摄像头：`python3 gripper_camera_node.py --device /dev/video20 --topic /gripper_camera/image_raw`

夹爪摄像头在板上是 `/dev/video20`（`icSpring camera`），如果画面全黑，先检查夹爪是否张开/镜头盖是否取下。

## 与官方 aux_target_relay.py 的对接说明

官方 relay（`student/interfaces/aux_target_relay.py`）默认读 `/tmp/d435i-target.json`，
可用环境变量 `AUX_TARGET_FILE` 或 ros 参数 `~target_file` 改指到我们的
`/tmp/perception_targets.json`。**但注意**：relay 要求 JSON 里有 `base_center_m: [x,y,z]`
（base_link 坐标系，单位米，范围 ±2m、z 0.05~2m），而我们的文件是像素坐标 + depth_mm 格式，
relay 直接读会因 `missing base_center_m` 拒绝发布。因此：

- 主接口就是 `/student/perception/targets` 话题，角色D 直接订阅它做坐标转换；
- 若确需走 relay，需由坐标转换节点把像素+深度转成 base_link 后，
  以含 `base_center_m` 的格式写另一份文件（或直接写到 relay 的默认路径），再让 relay 读那份。

## 现场标定流程（比赛日）

1. 拍现场物料照片（或直接板上存帧）→ 本机 `calib_hsv.py 照片 --slot red` 取样，把 JSON 片段合进 `config.json` 的 `hsv_colors`。
2. 路锥若是橙白锥：`cone_detect.color` 改成 `cone_orange` 并标定该槽位。
3. 木制圆柱：`hsv_colors.wood` 当前是估计值，标定后把它加进 `color_detect.colors` 列表才会参与检测。
4. 字母牌/人形立牌：现场拍照 → `make_template.py 照片 letter_A` 裁模板，把片段加进 `template_detect.templates`，按远近调 `scales`。
5. 改完配置先 `python perception_node.py --sim --images 现场照片.jpg` 验证，再上板。

## 已知事项

- 全管线同跑时存在跨检测器重复命中（例：蓝色路锥也会出 `blue_block/blue_ball` 碎片，
  颜色环目标也会出在同名颜色里）。下游按 `category` 过滤即可；需要的话也可用 config 开关关掉部分检测器。
- QR category 格式为 `qr:<内容>`（如 `qr:A`），与 practice 脚本的 `point_A` 命名不同，是本包规范。
- sim 模式无深度源，`depth_mm` 恒为 `null`。
- Windows 中文路径下 `cv2.imread` 会失败，包内统一用 `imread_safe`（np.fromfile + imdecode）读图，板端无此问题。
