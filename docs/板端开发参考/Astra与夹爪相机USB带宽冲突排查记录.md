# Astra 与夹爪相机 USB 带宽冲突排查记录

> 记录时间：2026-08-06 上午
> 结论：**根因已定位为 USB2 总线等时带宽耗尽（不是 ROS 传输问题）**；Astra 相机带宽预留失败后固件卡死，软件手段未能恢复，问题未完全闭环

---

## 1. 现象

teleop 拍照时两相机轮流失效：

```
📷 20260806_095317 gripper✗ astra✓   # 重启板后，夹爪相机节点未启动
📷 20260806_095617 gripper✓ astra✗   # 夹爪相机启动后，Astra 随即断流
```

## 2. 根因

内核日志关键证据（dmesg）：

```
usb 1-1.4.2: usbfs: usb_submit_urb returned -28
```

- `-28` = `-ENOSPC`：**USB 等时（isochronous）带宽预留失败**
- 整机所有 USB 外设共用 **Bus 001（USB2，480Mbps）**：Astra 深度口（2bc5:060f @1-1.4.1）+ RGB 口（2bc5:050f @1-1.4.2）、icSpring 夹爪相机（32e6:9005）、雷达、串口全在上面
- 夹爪相机原始流 640×480@15fps ≈ **12MB/s**（rostopic bw 实测），UVC 等时带宽按最大包预留，直接把 Astra RGB 的预留挤爆
- ROS 走本机 loopback TCP，12MB/s 毫无压力 —— **瓶颈在 USB 物理层，不在 ROS**

## 3. 时间线

| 时刻 | 事件 |
|---|---|
| 09:46 | 板子重启，Astra 正常（健康检查 RGB/DEPTH/点云全 PASS） |
| 09:55 | 启动夹爪相机节点（`run python3 gripper_camera_node.py`） |
| 09:56 | Astra 断流（dmesg 出现 `submit_urb -28`） |
| 之后 | 杀掉夹爪节点，Astra 仍不恢复：节点打开设备句柄后挂在 futex，无日志输出；固件已卡死 |

## 4. 尝试过的恢复手段（均未成功）

1. `docker restart rk3588s-vision` —— 无效
2. 停 vision 栈 + `authorized 0/1` 重新授权 —— 设备号不变，未真正重枚举，无效
3. `USBDEVFS_RESET` ioctl 重置两个接口 —— 返回 ok 但无效
4. 父 hub `1-1.4` unbind/bind —— 真正重枚举（006/008→011/012），仍无效
5. **物理拔插 Astra USB**（重枚举为 017/019）后重建容器 —— **仍无效**，节点初始化挂死

上次有效的是**整块板重启**（09:46 重启后 Astra 工作正常，直到夹爪相机启动）。拔插未恢复的原因待查（可能需更长时间断电，或相机固件/配置状态需全机复位）。

## 5. 第二次重启后的新事实（2026-08-06 下午）

1. **整板自启完全跑通**：master 绑 0.0.0.0:11311、chassis/lidar/arm/vision 全 READY（自启竞态这次没触发，属运气）
2. **Astra 在开机 201s 就再次 `-28` 卡死** —— 此时**夹爪相机节点根本没启动**。说明冲突方不只是 gripper：开机时 mclaw weixin 服务会做相机快照（日志里有 `mclaw_camera_snapshot_*`），总线本身就处于临界状态
3. **MJPEG 路线判死刑**：`camera rejected MJPEG, got 'YUYV'`。查 `icspring_report.txt`：icSpring **只支持 YUYV 一种格式、只有 640×480 一种分辨率**（fps 5/10/15/20/25/30 可调）
4. **根文件系统曾 100% 满**：/tmp/kaihong-ros-log 涨到 131M，roscore 的 rosout 因 `No space left on device` 起不来，master 进入"getUri 能回、getSystemState 卡死"的半死状态，且孤儿 rosmaster 占着 11311 导致后续 roscore 全部启动失败。已清理（101M 可用）。**教训：栈起不来先查 `df -h /` 和 roscore.log，再查 master**
5. **恢复 Astra 唯一已验证手段仍是整板重启**，且重启后也可能在开机阶段再次被挤死

## 6. 解决方案备选（2026-08-06 下午评审，待定）

### 方案 A：icSpring 换 USB3 口（硬件隔离，推荐）

- 板子有独立 xHCI 控制器（lsusb 的 Bus 005/006，`1d6b:0003` = USB3 root hub）
- 把夹爪相机从 USB2 口拔下插到 USB3 口，两相机物理分总线，带宽冲突**根除**
- 成本：插拔一次线；改 `gripper_camera_node.py` 的 `--device`（重枚举后 video 节点号可能变，需用 `icspring camera` 名称反查 `/sys/class/video4linux/*/name`）
- 风险：USB3 口位置/可用性需现场确认

### 方案 B：gripper 降到 5fps（软件唯一可调项）

- icSpring 只有 fps 可调：启动加 `--fps 5`，UVC 等时带宽预留约降到 1/3
- 优点：不改硬件；缺点：**开机时 Astra 无 gripper 也卡死过，说明余量本来就薄，降 fps 未必够**；5fps 画面偏卡
- 可与方案 A/C 叠加

### 方案 C：双相机分时复用（最保守）

- 不共存：用 Astra 时 `pkill` gripper 节点；用 gripper 时停 vision 栈
- teleop 拍照逻辑改成"拍哪边前先把另一边停掉"
- 优点：零硬件改动、绝对可靠；缺点：抓取流程需要 gripper 常开，Astra 深度就用不了，功能受限

### 方案 D：先恢复 Astra 单相机基线（止血）

- gripper 保持关闭，拔插/重启恢复 Astra，跑通 healthcheck-all 单相机基线
- 共存问题挂起，比赛流程先不依赖双相机同时出流

### 关联待办

- [ ] 选定方案后执行并回填验证结果
- [ ] Astra 侧降分辨率/帧率（astra_pro_plus.launch 参数），任何方案下都值得做
- [ ] **根文件系统空间监控**：/tmp/kaihong-ros-log 会随 ROS CLI 调用无限增长，建议在 autostart 或 cron 里定期清理，2.8G 根分区只剩 101M
- [ ] 板端自启竞态（autostart 不等 wlan0 IP）仍未修，见 [[板端开发速查与踩坑手册]]

## 6.1 操作踩坑：pkill 自杀

SSH 远程命令里直接 `pkill -f gripper_camera_node` 会**把执行命令的 shell 自己杀掉**（远程 sh 的命令行里含同样字符串），表现为 ssh exit 255。即使写成 `gripper_camera_nod[e]`，若同一条命令的 setsid 启动部分含纯文本 `gripper_camera_node.py` 仍会自杀。**正确做法：杀和启分两条 ssh 命令执行**：

```bash
ssh ... 'pkill -f "gripper_camera_nod[e]"'          # 第一条：只杀
ssh ... '. /data/robot-host/robot-env.sh; setsid sh -c "run python3 ..." &'   # 第二条：只启
```

截至记录时板端状态：gripper 旧节点已确认杀掉（`ps` 无进程）；新 MJPEG 节点启动命令因会话中断**执行状态未知**，Astra 仍为断流状态。

## 7. 复现与诊断命令

```bash
# 看 USB 带宽错误
dmesg | grep submit_urb        # -28 = ENOSPC 带宽预留失败

# 测话题带宽
rostopic bw /gripper_camera/image_raw

# 查 USB 拓扑（所有设备是否都在 Bus 001）
lsusb
```
