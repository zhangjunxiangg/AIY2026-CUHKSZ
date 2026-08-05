# M-Claw / Robot Skill：纯软件约束

已于 2026-08-04 通过 SSH 在 `mrobots` 上完成检查。机器人没有移动；整个过程只读取了文件。

板端当前生效的路径：

- `SKILL_ROOT=/data/local/tmp/.mclaw/skills/kaihong-robot-operations`
- `MCLAW_ROOT=/data/local/release/opt/mclaw-main/mclaw`
- `ROBOT_ROOT=/data/robot-host`

当前生效的 `SKILL.md` 和全部六个 Python 脚本的 `cksum`，均与本地源文件
`vendor/kaihong-src/kaihong_adapter/mclaw-skill/` 一致。当前生效的 gripper 脚本也与
`src/grasping/` 中的文件一致。因此，下面 Skill/runtime 脚本的行号同时对应板端当前文件和本地副本。

## 本文所说的 software-only constraint 是什么

它是指 M-Claw、模型或本地代码能够仅根据命令文本、参数、本地文件或进程完成的检查。
它不需要等待 ROS topic/service、传感器、控制器、电机、相机或另一块板的响应。

约束执行级别：

- **Hard**——确定性代码会拒绝该操作。
- **Model-only**——规则写在 `SKILL.md` 中；模型应当遵守，但代码不提供保证。
- **Mixed**——一部分由模型检查，另一部分由代码强制执行。

## 纯软件约束表

| ID | 类型 | 执行级别 | 无需等待硬件即可检查的内容 | 板端位置 | 代码片段 / 规则 |
|---|---|---|---|---|---|
| C01 | Skill 选择 | Model-only | 如果任务明显匹配已安装的 Skill，模型必须先通过 `skill_view` 加载它；`SKILL.md` 是主要依据，evolution 仅作补充。 | `$MCLAW_ROOT/agent/prompt_builder.py:160-167` | `任务明显匹配 ... 使用 skill_view(name)`；`SKILL.md 是主要执行依据` |
| C02 | tool 可用性 | Hard | 不允许调用不存在的 tool/action，也不允许调用当前上下文中未获授权的 tool/action。 | `$MCLAW_ROOT/tools/dispatch.py:97-114`, `1072-1090` | `if tool_name not in tool_names: ... not available`；`if tool_name not in whitelist: ... not allowed` |
| C03 | 文件变更分类 | Hard | 在调用 terminal 之前，本地会识别 `rm`、`cp`、`mv`、`sed -i`、`truncate`、`dd`、`shred`、通过 `>` 覆盖文件，以及部分破坏性 Git/PowerShell 命令。 | `$MCLAW_ROOT/safety/mutation_detector.py:15-37`, `58-93` | `_DESTRUCTIVE_TERMINAL_PATTERNS`；`is_destructive_terminal_command(raw)` |
| C04 | 阻止目标无法解析或递归操作 | Hard | 阻止递归/通配符删除，以及 M-Claw 无法确定精确目标的破坏性命令。 | `$MCLAW_ROOT/safety/policy.py:39-60` | `recursive or wildcard delete`；`destructive command with unresolved targets` |
| C05 | Skill 存储保护 | Hard | Terminal 不能修改当前生效或 draft Skill 存储区中的文件；必须使用 `skill_manage`。 | `$MCLAW_ROOT/tools/terminal_tool.py:98-140`, `280-299` | `Do not use terminal to mutate files under {root}` |
| C06 | 凭据文件保护 | Hard | 如果 terminal 命令直接引用 `.env`、SSH 私钥、AWS credentials 或 kube config，则命令会被阻止。 | `$MCLAW_ROOT/tools/terminal_tool.py:50-55`, `144-148` | `Credential file access is blocked; use secret_request_many...` |
| C07 | 真实运动授权 | Model-only | 只有用户在当前会话中明确要求时，才允许移动底盘、机械臂或 gripper。 | `$SKILL_ROOT/SKILL.md:20-22` | `仅在用户当前会话明确要求真实运动时移动...` |
| C08 | 底盘命令的语义完整性 | Model-only | 模型必须找到 direction、speed 和 duration；如果缺少任何一项，应询问用户，而不是猜测默认值。 | `$SKILL_ROOT/SKILL.md:22-23` | `缺少时询问，不推测默认值` |
| C09 | 有限数值 | Hard | 速度/时间中的 `NaN`、`inf` 和 `-inf` 会在初始化 ROS node 前由本地 parser 拒绝。 | `$SKILL_ROOT/scripts/ros_cmd_vel.py:43-47`, `236-248` | `if not math.isfinite(number): raise ... "value must be finite"` |
| C10 | 最大线速度 | Hard | 检查整体平面速度 `hypot(linear_x, linear_y) <= 0.20 m/s`，而不是分别检查每个分量。 | `$SKILL_ROOT/scripts/ros_cmd_vel.py:16-19`, `129-136` | `linear_magnitude = math.hypot(...)`；`> MAX_LINEAR_MPS` → reject |
| C11 | 最大角速度 | Hard | 检查 `abs(angular_z) <= 0.50 rad/s`。 | `$SKILL_ROOT/scripts/ros_cmd_vel.py:16-19`, `137-140` | `if abs(angular_z) > MAX_ANGULAR_RAD_S ... raise ValueError` |
| C12 | 运动时间 | Hard | Duration 为必填项，并且必须是 `0.1..10.0 s` 范围内的有限数值。 | `$SKILL_ROOT/scripts/ros_cmd_vel.py:18-19`, `141-144`, `243-247` | `--duration ... required=True`；`MIN_DURATION_S <= duration <= MAX_DURATION_S` |
| C13 | 底层 chassis 命令集合 | Hard | Parser 只允许 `status`、`stop` 或 `publish`；未知命令/参数会被拒绝。 | `$SKILL_ROOT/scripts/ros_cmd_vel.py:236-248` | `subparsers = ... required=True`；三个固定 subparser |
| C14 | 统一 Skill 命令集合 | Hard | `robot_ops.py` 只允许预先列出的命令：chassis、arm、gripper、camera、lidar、health/status/interfaces、aux 和 color sorting。 | `$SKILL_ROOT/scripts/robot_ops.py:623-659` | `subparsers.add_parser(...)`；未知命令由 `argparse` 拒绝 |
| C15 | 机械臂静态 ID | Hard | `arm-set-one` 仅接受 servo ID `1..5`；ID10 在此处被禁止并专用于 gripper。该检查在 `rospy.init_node` 前执行。 | `$SKILL_ROOT/scripts/arm_set_one.py:39-49` | `if args.servo_id not in (1, 2, 3, 4, 5): ... ID10 is the gripper` |
| C16 | 机械臂静态位置 | Hard | 机械臂 Target 必须是 `0..1000` 范围内的整数；在获取 hardware feedback 前就会拒绝无效值。 | `$SKILL_ROOT/scripts/arm_set_one.py:40-49` | `if not 0 <= args.position <= 1000: ...` |
| C17 | 每次操作一个 servo | Mixed | Skill 要求一次只能更改一个 ID；CLI 只接受一个 `--servo-id` 和一个 `--position`。 | `$SKILL_ROOT/SKILL.md:26-29`；`$SKILL_ROOT/scripts/arm_set_one.py:40-43` | `每次只修改一个 ID`；单个标量 `--servo-id` |
| C18 | gripper 静态位置 | Hard | ID10 的 Target 必须是 `250..800` 范围内的整数；此项检查在 ROS/service feedback 前执行。 | `$ROBOT_ROOT/set-gripper-position.py:13-17` | `if TARGET < 250 or TARGET > 800: raise SystemExit("... TARGET_LIMIT")` |
| C19 | 特别敏感的 servo | Model-only | ID5 是手腕旋转，ID10 是 gripper；Skill 要求用户明确提出请求，并确认周围空间安全。 | `$SKILL_ROOT/SKILL.md:26-29` | `只有用户明确要求且周围安全时才调整` |
| C20 | Color sorting 不产生运动 | Model-only | Color sorting 仅允许用于 perception/recommendation：不得移动底盘、机械臂或 gripper，也不得把 camera coordinates 当作 `base_link` 坐标。 | `$SKILL_ROOT/SKILL.md:30-31`；`$SKILL_ROOT/skill_evolution.json:10-12` | `仅做感知...不自动移动`；`Color sorting is perception-only` |
| C21 | 辅助板 IP：来源 | Model-only | 辅助板当前 IPv4 必须由用户明确提供；不得猜测、扫描网络或使用旧 IP。 | `$SKILL_ROOT/SKILL.md:33-34`, `92-109` | `未提供时先询问，不猜测、不扫描网络、不沿用旧 IP` |
| C22 | 辅助板 IP：语法 | Hard | 在 XML-RPC/ROS 操作前检查是否提供了 `--aux-ip`，以及该值是否为字面 IPv4，而不是 IPv6 或任意 hostname。 | `$SKILL_ROOT/scripts/robot_ops.py:355-362`, `649-655` | `ipaddress.ip_address(value)`；`address.version != 4` → reject |
| C23 | 固定的 latest 相机输出 | Model-only / fixed caller | Skill 禁止 timestamp archive；标准 caller 使用固定的 latest 路径，因此新照片会覆盖旧照片。 | `$SKILL_ROOT/SKILL.md:32`, `88-90`, `115-121`；`$SKILL_ROOT/scripts/robot_ops.py:235-240` | `覆盖固定 latest 输出，不创建时间戳归档`；`remote_prefix = "/tmp/mclaw-camera-latest"` |
| C24 | photo viewer 文件限制 | Hard | HTTP viewer 只提供四个固定的辅助相机 latest 文件；任何其他 URL 返回 404，directory listing 返回 403。 | `$SKILL_ROOT/scripts/latest_photo_server.py:13-34` | `candidate.name not in ALLOWED_FILES` → `404`；`list_directory` → `403` |
| C25 | photo viewer 的 TTL | Hard | temporary viewer 的生存时间必须为 `60..3600 s`；`robot_ops.py` 和 server 自身都会检查该范围。 | `$SKILL_ROOT/scripts/robot_ops.py:407-414`；`$SKILL_ROOT/scripts/latest_photo_server.py:38-45` | `if not 60 <= args.ttl <= 3600` → reject |
| C26 | 本地 executable/assets 是否存在 | Hard | 启动前检查 chassis client、robot scripts、latest photo 和 photo server 是否存在。这些是 filesystem 检查，不依赖 hardware。 | `$SKILL_ROOT/scripts/robot_ops.py:132-134`, `210-216`, `300-304`, `387-406` | `if not ...exists()/is_file(): return ... "missing..."` |
| C27 | 受限的恢复指令 | Model-only | 当 `/cmd_vel` 和 wheel telemetry 正常但机器人不移动时，Skill 只允许在用户授权后执行 `stop-all`/`start-all`，并禁止重新发送或轮询 `motor_type`。 | `$SKILL_ROOT/SKILL.md:35-37` | `经用户授权后运行...`；`不要重新发送或轮询 motor_type` |
| C28 | 禁止编造结果 | Model-only | M-Claw 只能报告实际返回的字段，不能用模型知识补全缺失的 lidar/depth/servo 数据。规则本身是本地规则，但会应用于已经获取的结果。 | `$SKILL_ROOT/SKILL.md:88-90`；`$SKILL_ROOT/skill_evolution.json:9-12` | `只报告真实返回字段，不补全缺失...`；`Never infer missing...` |
| C29 | 固定的输出截断 | Hard | Wrapper 将 JSON 中包含的 stdout 限制为最后 6000 个字符，stderr 限制为最后 3000 个字符；对已解析 JSON，stderr 限制为 2000 个字符。 | `$SKILL_ROOT/scripts/robot_ops.py:81-100` | `completed.stdout[-6000:]`；`completed.stderr[-3000:]` |
| C30 | 错误的 bypass 建议 | Model-only，不安全 | 这**不是约束**。Evolution 建议遇到 safety block 后，把启动形式改成 `/bin/sh <script>`。改变调用形式并不会让操作更安全，反而可能对 lexical safety analysis 隐藏命令的真实含义。 | `$SKILL_ROOT/skill_evolution.json:13` | `需改用 /bin/sh <脚本> 前缀方式运行` |

## 重要缺口：Skill 中有要求，但代码不能保证的内容

| Gap | Skill 的预期 | 在接触 hardware 前，代码实际保证的内容 |
|---|---|---|
| G01 | Direction、speed 和 duration 都是必填项 | CLI 只要求 `duration`；三个速度的 default 都是 `0.0`。完全为零的“运动命令”可以通过 validation。 |
| G02 | 每次运动前必须执行 `chassis-status` | `publish` 不需要 status token/result，可以直接调用。这只是 model workflow。 |
| G03 | 只有用户明确请求后才能进行真实运动 | Python 脚本不会收到 user/session authorization token。一旦 M-Claw 调用了脚本，代码就把该调用视为已授权。 |
| G04 | 机械臂大幅移动需要 clearance 确认 | 代码只接收一个简单的 `--allow-large-delta` 标志；它不检查确认由谁、在何时给出。此外，只有获得 hardware feedback 后才能计算 delta。 |
| G05 | Skill 中的 gripper 范围是 `250..800` | 静态代码同样允许 `250..800`，但之前从硬件读取到的 ID10 limit 是 `0..700`；software-only 检查不知道当前硬件限制。 |
| G06 | 恢复操作必须经过授权 | `stop-all/start-all` 不接收 authorization token。是否遵守要求完全由模型负责。此外，Evolution 第 13 行还建议使用 bypass 形式启动。 |

## 有意不纳入主表的检查

以下检查需要等待 ROS/hardware/network 输出：

| 检查 | 为什么不是 software-only | 所在位置 |
|---|---|---|
| `chassis-status` | 读取 ROS Master，并等待 battery topic，最长 1.5 s。 | `$SKILL_ROOT/scripts/ros_cmd_vel.py:78-126` |
| 是否存在 `/cmd_vel` subscriber | Publisher 等待 ROS subscriber，最长 3 s。 | `$SKILL_ROOT/scripts/ros_cmd_vel.py:68-75`, `164-169` |
| Arm delta `120/250` | 先等待三帧 servo feedback，然后计算当前位置和 delta。 | `$SKILL_ROOT/scripts/arm_set_one.py:21-30`, `53-80` |
| Arm subscriber 和最终精度 | 等待 command subscriber，执行运动，然后再次读取 feedback。 | `$SKILL_ROOT/scripts/arm_set_one.py:81-110` |
| Gripper feedback/精度 | 等待 service 和 subscriber，读取初始位置和最终位置。 | `$ROBOT_ROOT/set-gripper-position.py:20-58` |
| Camera/depth 有效性 | 分别等待 RGB 和 depth message，每项最长 8 s。 | `$SKILL_ROOT/scripts/camera_snapshot.py:31-45` |
| 辅助 publisher 身份 | 查询 ROS Master/node URI，并将 publisher IP 与用户提供的 IP 比较。 | `$SKILL_ROOT/scripts/robot_ops.py:470-512` |
| Lidar、health、status、interfaces | 运行板端/ROS 脚本并等待其输出。 | `$SKILL_ROOT/scripts/robot_ops.py:295-337` |

## 结论

当前最重要的完全确定性 pre-hardware 限制如下：

1. Chassis：有限数值、平面速度 `<=0.20 m/s`、角速度 `<=0.50 rad/s`、持续时间 `0.1..10 s`。
2. Arm：ID `1..5`、target `0..1000`。
3. Gripper：target `250..800`。
4. Auxiliary camera：必须提供字面 IPv4。
5. Viewer：仅允许四个文件，TTL 为 `60..3600 s`。
6. M-Claw：tool/action 可用性、文件变更策略、Skill 存储保护和凭据文件阻止规则。

运动授权、direction/speed/duration 必填、运动前先检查 status、clearance 确认、
恢复授权以及禁止 color sorting 产生运动，目前仍是 model-only 规则。在它们被迁移到确定性的
action schema/validator 之前，都不能作为可靠的安全边界。
