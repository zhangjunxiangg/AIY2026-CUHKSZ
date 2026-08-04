# HDC 连接中断排查记录

> 记录时间：2026-08-04 16:32（UTC+8）
> 记录人：Kimi Code CLI
> 关联任务：板端联调 / 传感器数据规格回填 / Octie 任务 check off

## 1. 本次排查背景

在完成以下工作后，执行 `hdc list targets` 发现板端设备突然无法识别：

- 已把 Dora / ROS1 / 执行器 Demo 的 dry-run 数据格式回填到 `docs/传感器数据规格手册.md`。
- 已完成 `git commit && git push`。
- 已在 Octie 中 approve 了 3 个 `in_review` 任务（机器人本体控制方案、Dora Demo、ROS1 Demo）。

## 2. 本次执行过的命令与输出

所有命令均**只读取 HDC 状态或重启 HDC 服务**，没有下发任何会断开 USB/重启板子的指令。

### 2.1 第一次检查

```bash
hdc list targets
[Empty]

hdc -v
Ver: 3.1.0e
```

### 2.2 重启 HDC 服务后再次检查

```bash
hdc start && sleep 2 && hdc list targets
[Empty]
```

## 3. 为什么这些操作不会导致板子断开

| 操作 | 作用 | 是否会影响硬件连接 |
|------|------|-------------------|
| `hdc list targets` | 查询当前已连接的设备列表 | 否，纯只读 |
| `hdc -v` / `hdc version` | 显示 HDC 客户端版本 | 否，纯只读 |
| `hdc start` | 启动/重启本地 HDC 守护进程 | 否，仅操作 PC 端服务 |
| `hdc kill` | 停止本地 HDC 守护进程 | 否，仅操作 PC 端服务 |

结论：**HDC 客户端命令本身不会断开 USB 连接或重启开发板**。`[Empty]` 表示 PC 端没有枚举到该 USB 设备，属于物理层或板端状态问题。

## 4. 可能原因 checklist（按发生概率排序）

- [ ] USB 公对公线松动或接触不良（尤其移动过板子/电脑后）。
- [ ] 插到了没有数据的 USB 口，或 Hub 供电不足。
- [ ] 板子进入休眠/黑屏，USB 调试模式被关闭。
- [ ] USB 线本身只有充电线芯，无法传数据（此前连上过，可能性较低）。
- [ ] 板端 HDC 守护进程异常（可通过网络 HDC 或重新上电验证）。

## 5. 建议的恢复步骤

1. **先看屏幕**：确认板子还亮着，显示 KaihongOS 桌面/终端，不是黑屏或休眠。
2. **重新插拔 USB 线**：两端都拔下再插紧，优先使用电脑主板直连的 USB3.0（蓝色）口。
3. **换线/换口交叉验证**：用另一根确认可用的 USB-A 公对公数据线和另一个 USB 口。
4. **电源确认**：确认板子电源适配器还插着且指示灯亮。
5. **如果之前已配过 WiFi**：
   ```bash
   hdc tconn <板子IP>:5555
   hdc list targets
   ```
6. **Windows 设备管理器验证**：查看是否有 OpenHarmony/ADB/Android 设备出现。
   ```powershell
   Get-PnpDevice -Class USB | Where-Object {$_.FriendlyName -match "ADB|OpenHarmony|Android|Kaihong"}
   ```

## 6. 进一步诊断（2026-08-04 16:42）

### 6.1 `hdc list targets -v` 输出

```bash
hdc list targets -v
COM20		UART	Ready	unknown...	hdc
COM21		UART	Ready	unknown...	hdc
COM3		UART	Ready	unknown...	hdc
COM4		UART	Ready	unknown...	hdc
```

说明 HDC 服务在扫描 UART 端口，但**没有 USB 目标**。

### 6.2 Windows 设备管理器发现 HDC Device，但驱动异常

```powershell
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*HDC*'}
```

输出：

```
Status  FriendlyName Class     InstanceId
------  ------------ -----     ----------
Unknown "HDC Device" USBDevice USB\VID_2207&PID_5000\EC29004133314D38433031A523403C00
```

- 设备序列号 `EC29004133314D38433031A523403C00` 与之前一致，说明 USB 线物理连接是通的。
- 但状态为 `Unknown`，说明 **Windows 没有正确加载 HDC 设备的 USB 驱动**。

### 6.3 根本原因判断

`hdc list targets` 之前能连上，现在连不上，最可能的原因：

1. **Windows 端 HDC USB 驱动丢失/被重置**：
   - 可能换过 USB 口，Windows 对新端口重新枚举后没有正确绑定驱动；
   - 或某些安全/清理软件把驱动状态清掉了；
   - 或之前驱动只是临时生效（例如通过 `DriverAssistant` 安装但本次没启动/没生效）。

2. **板端 USB 调试模式未变，但 PC 端驱动未就绪**：
   - 板子本身没有重启，序列号还在；
   - 问题在 PC 端驱动层，不在板子端。

> 不是 `hdc start/kill/list` 这些命令导致的；这些命令只操作本机 HDC 服务，不会卸载 USB 驱动。

## 7. 解决方案：安装/修复 HDC USB 驱动

### 7.1 已下载工具

已把 Zadig 放到：

```
D:\AIY-Hackathon\tools\zadig\zadig.exe
```

Zadig 用于给 USB 设备安装通用 WinUSB 驱动，解决设备被识别但驱动未加载的问题。

### 7.2 操作步骤

1. 保持板子通过 USB 公对公线连着电脑。
2. 双击打开 `D:\AIY-Hackathon\tools\zadig\zadig.exe`。
3. 菜单栏点击 **Options → List All Devices**。
4. 下拉框里找到 **"HDC Device"**（如果看不到，确认板子亮着、USB 线插好）。
5. Driver 那一行选择 **WinUSB**（默认就是它）。
6. 点击 **Replace Driver**（或 Install Driver）。
7. 等进度条跑完，关闭 Zadig。
8. 回到命令行执行：
   ```bash
   hdc kill
   hdc start
   hdc list targets
   ```

### 7.3 备选方案

如果 Zadig 装不上或提示签名问题：

- 重启电脑，按 F8 进入“禁用驱动程序签名强制”模式，再运行 Zadig；
- 或者去华为开发者官网下载 **Command Line Tools for HMOS**（老师给的链接），里面通常带 `DriverAssistant`，用官方驱动助手重新安装一遍 USB 驱动。

## 8. 当前状态

- 物理连接：USB 已通，设备管理器能看到 `HDC Device`。
- 驱动状态：**未加载（Unknown）**。
- 下一步：用 Zadig 安装 WinUSB 驱动，然后重新 `hdc list targets`。
