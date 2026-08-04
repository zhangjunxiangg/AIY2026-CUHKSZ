# 辅助相机的两套独立标定

辅助相机可连接学生电脑或另一块计算板。相机移动、支架松动或焦距/分辨率改变后
必须重新标定。不要把一次比赛现场得到的目标坐标写入程序。

## 1. 地面与小车移动标定

用途：把辅助深度相机测得的三维点转换到 `competition_ground`，用于目标地面
位置、小车中心和车头朝向。它不能直接替代机械臂手眼标定。

文件：

```text
aux-ground-calibration.py
```

准备至少 6 个不共线地面控制点，覆盖两个水平方向各至少 0.20 m。每个样本记录：

- `camera_xyz_m`：辅助相机深度坐标；
- `ground_xyz_m`：现场测量的地面坐标，地面点通常 `z=0`。

示例：

```sh
python3 aux-ground-calibration.py init --dataset ground-dataset.json
python3 aux-ground-calibration.py add --dataset ground-dataset.json \
  --cx 0.12 --cy -0.08 --cz 1.25 --gx 0.40 --gy 0.20 --gz 0
python3 aux-ground-calibration.py status --dataset ground-dataset.json
python3 aux-ground-calibration.py solve \
  --dataset ground-dataset.json --output aux-ground.json
```

要求 RMSE 不大于 20 mm，最大误差不大于 40 mm。运行时用两个固定在小车上的
前后标记点可计算小车中心和 yaw：

```sh
python3 aux-ground-calibration.py chassis --calibration aux-ground.json \
  --fx FX --fy FY --fz FZ --rx RX --ry RY --rz RZ
```

## 2. 辅助相机与机械臂标定

用途：把辅助相机中的三维物体点转换到机械臂 `base_link`，用于 IK 和抓取。

文件：

```text
aux-arm-handeye.py
```

使用与 Astra 相同的 35 mm、ID1、`DICT_APRILTAG_36h11` 标签，刚性固定到
机械臂末端。每个姿态需要同时保存：

- 板端 `base_to_gripper`；
- 辅助相机检测到的 `camera_to_marker`。

板端读取当前机械臂位姿：

```sh
/data/robot-host/student/tools/read-arm-pose-json.sh
```

辅助相机电脑端先保存 RGB 图片和相机内参 JSON，再检测标签：

```sh
python3 aux-arm-handeye.py detect \
  --image frame.jpg --camera-info camera-info.json \
  --output camera-to-marker.json
```

相机内参 JSON 至少包含：

```json
{"K":[600,0,320,0,600,240,0,0,1],"D":[0,0,0,0,0]}
```

建立数据集并加入同步采集的一组：

```sh
python3 aux-arm-handeye.py init --dataset arm-dataset.json
python3 aux-arm-handeye.py add --dataset arm-dataset.json \
  --arm-pose arm-pose.json --marker-pose camera-to-marker.json
```

采集 12～15 个姿态后：

```sh
python3 aux-arm-handeye.py status --dataset arm-dataset.json
python3 aux-arm-handeye.py solve \
  --dataset arm-dataset.json --output aux-arm.json
```

至少需要 10 组，总平移跨度不小于 80 mm、旋转跨度不小于 20°。训练平移
RMSE 不大于 12 mm、旋转 RMSE 不大于 3°。

## 安装到板端

学生确认两个结果均为 `PASS` 后，复制为：

```text
/data/robot-host/student/calibration/installed/aux-ground.json
/data/robot-host/student/calibration/installed/aux-arm.json
```

地面移动只使用 `aux-ground.json`；机械臂抓取只使用 `aux-arm.json`。辅助相机
重新安装后两个结果都失效。标定工具支持其他 RGB-D 相机，不要求电脑路径、
设备序列号或板端 IP 写死在源码中。
