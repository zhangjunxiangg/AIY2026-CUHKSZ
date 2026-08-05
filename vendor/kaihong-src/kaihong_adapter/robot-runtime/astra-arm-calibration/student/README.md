# 板载 Astra—机械臂手眼标定

本工具用于固定在车体上的 Astra 与机械臂基座之间的 eye-to-hand 标定。机械臂
驱动和运动学运行在宿主系统，Astra 与 OpenCV 运行在 `rk3588s-vision`
容器。工具只通过 ROS 读取机械臂位姿和相机图像，不直接访问串口。

## 标定物

- 字典：`DICT_APRILTAG_36h11`
- ID：`1`
- 黑色方框边长：`35 mm`
- 标记必须刚性固定在末端，整个采样过程不能移动、弯折或重新粘贴。

生成标记：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh marker
```

生成文件固定覆盖为：

```text
/data/robot-host/astra-arm-calibration/work/marker.png
```

打印时必须关闭“适应页面”，实测黑色方框边长为 35 mm。白色静区不计入尺寸。

流程

开始新数据集：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh reset
```

手动把机械臂移动到一个安全姿态，确认标签完整出现在 Astra 彩色画面中，机械臂
停止后采一组：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh capture
```

每组之间至少平移 20 mm 或旋转 7°。建议采 12～15 组，覆盖画面中心、四周、
远近和不同倾角。不要只转 ID1；总平移跨度必须至少 80 mm，总旋转跨度至少
20°。采样本身不会移动机械臂。

查看覆盖情况：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh status
```

求解候选外参：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh solve
```

要求训练平移 RMSE 不大于 12 mm、旋转 RMSE 不大于 3°。求解后再把机械臂
移动到一个未参与训练的新姿态，执行独立验证：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh verify
```

独立验证要求平移误差不大于 20 mm、旋转误差不大于 5°。只有训练和独立验证
均通过时才能安装：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh install
```

`install` 会重新采集一次独立验证样本，不会盲目安装旧验证结果。候选文件不会
直接覆盖当前参数。原始交付参数固定备份在：

```text
/data/robot-host/astra-arm-calibration/factory-astra-to-base.json
```

恢复交付参数：

```sh
/data/robot-host/astra-arm-calibration/student/student-handeye.sh restore-factory
```

## 安全限制

- 标定采样不自动移动机械臂；学生必须使用受限的单关节或 IK 接口调姿。
- 移动前确认夹爪、标签、相机支架和承托面之间有足够间隙。
- 机械臂移动时不得采样；程序会检查采样前后位姿是否一致。
- 禁止修改标签实际边长来“调误差”。
- 禁止直接编辑或写死 `base_link` 目标坐标。
- `work` 目录只保存一个数据集、候选结果、最近采样图和最近验证图，不按时间戳堆积。
