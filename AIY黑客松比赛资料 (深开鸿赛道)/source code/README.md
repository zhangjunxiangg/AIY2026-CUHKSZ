# Kaihong 4.1 完整参赛源码包

本包用于参赛开发、教学和二次开发，包含上层示例、底盘、机械臂、雷达、深度相机，以及 M-Claw 和 Gemini 335 辅助板适配源码。

## 目录

- `ros_ws/src/`：完整 ROS1 catkin 工作空间源码。
  - `example/`：颜色分类等参赛示例。
  - `controller/`、`interfaces/`：控制节点和自定义消息/服务。
  - `third_party/OrbbecSDK_ROS1/`：Orbbec 深度相机 ROS1 驱动源码、launch、消息和所需 arm64 库。
  - `third_party/image_pipeline/depth_image_proc/`：深度图处理节点源码。
  - `peripherals/launch/depth_cam.launch`：深度相机统一启动入口。
  - 其他导航、SLAM、仿真、感知和第三方驱动源码。
- `kaihong_adapter/robot-runtime/`：鸿蒙小车板运行适配源码，包括底盘、电机/舵机、机械臂、雷达和里程计节点。
- `kaihong_adapter/mclaw-skill/`：M-Claw 小车操作 Skill 和脚本。
- `kaihong_adapter/gemini335-companion/`：Gemini 335 相机辅助板连接、启动、状态检查和取图脚本。
- `kaihong_adapter/deployment/`：小车板与相机板迁移、校验脚本和说明。

## ROS1 编译

在 Ubuntu/ROS1 环境中，将本包放到工作目录后执行：

```bash
cd ros_ws
source /opt/ros/noetic/setup.bash
catkin_make
source devel/setup.bash
```

实际 ROS 发行版和系统依赖应以目标板镜像为准。Python 节点通常不需要编译成机器码；catkin 会注册包、消息、服务和可执行脚本。

## 深度相机

深度相机节点已经包含在源码包中，不只包含 launch 文件。主要内容如下：

```text
ros_ws/src/third_party/OrbbecSDK_ROS1
ros_ws/src/third_party/image_pipeline/depth_image_proc
ros_ws/src/peripherals/launch/depth_cam.launch
kaihong_adapter/gemini335-companion
```

相机可以位于小车板本机，也可以运行在独立 Gemini 335 辅助板。使用辅助板时，需要先让小车板和辅助板连接到同一网络，再把小车板 IP 和辅助板 IP 提供给 M-Claw，由小车板上的 M-Claw 完成远端连接和取图。

## 说明

- 本包是源码包，不包含 Docker 镜像、M-Claw 可执行二进制和运行时输出。
- 已排除 Git 元数据、缓存、日志、PID、临时录音和凭据类文件。
- 部分第三方源码和二进制库遵循各自目录中的许可证。
