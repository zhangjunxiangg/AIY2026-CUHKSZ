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

## 6. 状态

- HDC 客户端：正常（Ver: 3.1.0e）。
- 板端枚举：**当前不可见**。
- 下一步：按第 5 节进行物理层排查，恢复后再继续 end-to-end mini 集成测试。
