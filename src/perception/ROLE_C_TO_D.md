# 角色 C → 角色 D：低矮物料盲区抓取与全局定位接口

## 1. 问题：Astra 深度相机的盲区

Astra 结构光深度相机有两个天然盲区：

- **近距离盲区**：深度有效范围约 **0.6 m – 8 m**，小于 0.6 m 的目标 `depth_mm` 为 `null`。
- **低矮盲区**：相机装在车头上方，俯角有限；贴近地面、离车很近的物料会跑到画面下边缘之外，或虽然能在 RGB 里看到，但深度已经失效。

**后果**：只靠 Astra，角色 D 拿不到这些低矮/近距物料的准确 `base_link` 坐标，直接抓会抓空。

---

## 2. 解决策略（今晚已在 PC 实现）

优先级从高到低：

1. **Astra 真实深度**（首选）
   - 目标在 0.6–8 m 范围内，直接用 `depth_mm` 换算三维坐标。
   - `depth_source = "camera"`。

2. **单目测深**（应急，精度较低）
   - 当 Astra 能看到 RGB 但深度失效时，用**物料真实尺寸 + bbox 像素大小**估算距离：
     `depth = fx * real_width / bbox_width`（高度同理，取平均）。
   - 精度约 ±10–20%，只能用于“靠近”，不建议直接精抓。
   - `depth_source = "mono"`，角色 D 看到后要谨慎。

3. **Gemini335 辅助相机**（盲区主力）
   - 辅助相机装在高处/侧向，俯角覆盖 Astra 的低矮盲区。
   - 它提供独立的 RGB + 深度，能把 Astra 里 `depth_mm=null` 或 `blind_spot=true` 的目标**替换成真实深度**。
   - `depth_source = "camera"`，但 `camera` 字段为 `"aux"`。

4. **航位推算**（未实现，比赛日可选）
   - 目标刚进入盲区前记住 `base_center_m`，结合底盘 odometry 更新位置。
   - 需要稳定的里程计，今晚没写代码，现场如果 1–3 都不够再补。

---

## 3. 数据流（板上最终形态）

```text
Astra RGB+depth ──► perception_node --ros ──► /student/perception/targets
                                                    │
                                                    ▼
                                            target_3d_node --camera astra
                                                    │
                                                    ▼
                                    /student/perception/targets_3d ──┐
                                                                     ├──► fusion_node ──► /student/perception/targets_3d_fused
                                    /student/perception/targets_3d_aux─┘
                                                     ▲
                                            target_3d_node --camera aux
                                                     ▲
Gemini335 RGB+depth ──► perception_node --ros (aux) ──┘
```

- **角色 D 只订阅最终话题**：`/student/perception/targets_3d_fused`
- 中间话题可用于调试，但不必依赖。

---

## 4. 输出格式（给 D 的契约）

```json
{
  "ts": 1785849000.123,
  "stamp": 1785849000.123,
  "status": "ok",
  "frame_id": "base_link",
  "targets": [
    {
      "category": "red_block",
      "center": [320, 400],
      "confidence": 0.95,
      "bbox": [294, 374, 52, 52],
      "depth_mm": 480,
      "depth_m": 0.48,
      "depth_source": "camera",
      "precision": "high",
      "object_size_m": {"width_m": 0.05, "height_m": 0.05},
      "blind_spot": false,
      "camera_point_m": [0.0, 0.12, 0.48],
      "base_center_m": [0.51, 0.01, 0.10],
      "map_center_m": [2.31, 1.05, 0.10]
    }
  ]
}
```

字段说明（D 必须知道的）：

- `status`：`ok` 正常；`no_intrinsics` 表示还没收到 camera_info，此时不要抓。
- `stamp` / `ts`：时间戳（秒），用于对齐和超时判断。
- `category`：物料类别（`red_block`、`cone`、`human_board` 等）。
- `base_center_m`：**抓取坐标**（base_link 系，单位米）。角色 D 直接用它做 IK。
- `map_center_m`：全局坐标（map 系）。导航/对齐用；如果 SLAM TF 没起来就是 `null`。
- `depth_source`：
  - `camera`：真实深度，可放心抓取；
  - `mono`：单目估算，只能靠近，不能精抓；
  - `none`：没有可用深度，`base_center_m` 为 `null`。
- `precision`：`high`（camera）/ `low`（mono）/ `none`，D 可据此决定抓取策略。
- `object_size_m`：物料真实尺寸（宽/高，米），用于设置夹爪开口。
- `blind_spot`：`true` 表示该目标在 Astra 盲区，已经由辅助相机接管（如果取到了）。

**没有相机也能调试 D 的代码**：用 `mock_output_publisher.py` 把示例数据发到 `/student/perception/targets_3d_fused`：

```bash
python3 src/perception/mock_output_publisher.py --ros --file src/perception/sample_targets_3d_fused.json --rate 2
```

---

## 5. 今晚 PC 已完成的工作

代码都在 `src/perception/` 下，**本机 sim 测试已全部通过**：

- `geometry3d.py`：像素+深度 → 相机坐标 → base_link/map 的纯几何换算。
- `blind_spot.py`：深度有效性判断、单目测深、盲区标记。
- `target_3d_node.py`：把 perception_node 的 2D 目标转成 3D（支持 Astra / aux 两种相机）。
- `fusion_node.py`：合并 Astra 和 Gemini335 的 3D 目标，盲区目标优先用辅助相机。
- `test_geometry.py`：离线单元测试，跑 `python src/perception/test_geometry.py` 应输出 `ALL PASSED`。

---

## 6. 比赛日还需要现场做的事（按顺序）

1. **辅助相机外参标定**
   - 在板上跑 `/data/robot-host/student/calibration/auxiliary/aux-arm-handeye.py`，生成 `aux-to-base.json`。
   - 把生成文件的路径填进 `src/perception/config.json` 的 `camera.aux.extrinsics_json`。
   - Astra 外参用现成的 `astra-arm-calibration/astra-to-base.json`，已经填好。

2. **确认 camera_info 话题**
   - Astra：`/astra_camera/rgb/camera_info`
   - Gemini335：`/aux_camera/color/camera_info`
   - `target_3d_node` 会实时订阅；如果话题不存在，就用 `config.json` 里的默认内参（精度会差）。

3. **启动顺序**
   ```bash
   # 终端1：Astra 感知
   run python3 /data/local/perception/perception_node.py --ros

   # 终端2：Gemini335 感知（辅助相机就位后）
   run python3 /data/local/perception/perception_node.py --ros --config config_aux.json

   # 终端3：Astra 3D 定位
   run python3 /data/local/perception/target_3d_node.py --ros --camera astra

   # 终端4：Gemini335 3D 定位
   run python3 /data/local/perception/target_3d_node.py --ros --camera aux

   # 终端5：融合
   run python3 /data/local/perception/fusion_node.py --ros
   ```

4. **角色 D 订阅**
   ```bash
   rostopic echo /student/perception/targets_3d_fused
   ```
   看到 `base_center_m` 非 null、`depth_source=camera` 再抓。

---

## 7. 给 D 的抓取建议

- `depth_source=camera`：正常抓。
- `depth_source=mono`：只用于**靠近到 0.8–1.0 m**，然后重新检测；不要直接闭环比抓。
- `blind_spot=true` 且 `camera=aux`：这是辅助相机救回来的目标，精度取决于 aux 外参标定质量，抓之前建议再确认一次。
- 任何时刻 `status!=ok` 或 `targets` 为空：停车等待，不要盲抓。

---

## 8. 已知限制

- 单目测深依赖 `config.json` 里 `blind_spot.mono_size` 的物料真实尺寸，**尺寸填错会直接导致距离错**。
- 辅助相机融合按“同类 + base_link 距离 < 0.12 m”去重，如果两个相机外参都没标准，可能误合并。
- 今晚没做航位推算；如果现场 Astra 和 Gemini335 同时失效，需要 D 那边保守处理（停车/重试）。
