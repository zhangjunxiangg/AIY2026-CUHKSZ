# M-Claw / Robot Skill: software-only constraints

Checked through read-only SSH on `mrobots` on 2026-08-04. No robot movement was commanded.

Board paths:

- `SKILL_ROOT=/data/local/tmp/.mclaw/skills/kaihong-robot-operations`
- `MCLAW_ROOT=/data/local/release/opt/mclaw-main/mclaw`
- `ROBOT_ROOT=/data/robot-host`

## Constraint table

A software-only constraint can be checked from command text, arguments, local files, or process state. It does not need to wait for a ROS topic/service, sensor, camera, controller, motor, or another board.

| ID | Kind | Enforcement | What is checked without hardware output | Board location | Code excerpt / rule |
|---|---|---|---|---|---|
| C01 | Skill selection | Model-only | When a task matches a Skill, the model must load it through `skill_view`; `SKILL.md` is primary and evolution is supplementary. | `$MCLAW_ROOT/agent/prompt_builder.py:160-167` | `use skill_view(name)`; `SKILL.md is the main execution basis` |
| C02 | Tool availability | Hard code | A tool/action not available in the current execution context cannot be called. | `$MCLAW_ROOT/tools/dispatch.py:97-114,1072-1090` | `tool_name not in tool_names` → `not available` |
| C03 | File-mutation detection | Hard code | Locally detects `rm/cp/mv/sed -i/truncate/dd/shred`, overwrite redirection, and selected destructive Git/PowerShell commands. | `$MCLAW_ROOT/safety/mutation_detector.py:15-37,58-93` | `_DESTRUCTIVE_TERMINAL_PATTERNS` |
| C04 | Dangerous-delete blocking | Hard code | Blocks recursive deletes, wildcard deletes, and destructive commands whose targets cannot be resolved. | `$MCLAW_ROOT/safety/policy.py:39-60` | `recursive or wildcard delete`; `unresolved targets` |
| C05 | Skill-storage protection | Hard code | Terminal cannot directly mutate active/draft Skill storage; `skill_manage` is required. | `$MCLAW_ROOT/tools/terminal_tool.py:98-140,280-299` | `Do not use terminal to mutate files under {root}` |
| C06 | Credential-file protection | Hard code | Blocks direct access to `.env`, SSH private keys, AWS credentials, and kube config. | `$MCLAW_ROOT/tools/terminal_tool.py:50-55,144-148` | `Credential file access is blocked` |
| C07 | Authorization for real motion | Model-only | Chassis, arm, or gripper movement requires an explicit request from the user in the current session. | `$SKILL_ROOT/SKILL.md:20-22` | `move only when the user explicitly requests real motion` |
| C08 | Chassis-parameter completeness | Model-only | Direction, speed, and duration must be present; missing values should be requested, not invented. | `$SKILL_ROOT/SKILL.md:22-23` | `ask when missing; do not infer defaults` |
| C09 | Finite numeric values | Hard code | Speed and duration cannot be NaN or infinite. | `$SKILL_ROOT/scripts/ros_cmd_vel.py:43-47` | `math.isfinite(number)` |
| C10 | Maximum linear speed | Hard code | `hypot(linear_x, linear_y) <= 0.20 m/s`. | `$SKILL_ROOT/scripts/ros_cmd_vel.py:16-19,129-136` | `linear_magnitude > MAX_LINEAR_MPS` → reject |
| C11 | Maximum angular speed | Hard code | `abs(angular_z) <= 0.50 rad/s`. | `$SKILL_ROOT/scripts/ros_cmd_vel.py:137-140` | `abs(angular_z) > MAX_ANGULAR_RAD_S` |
| C12 | Movement duration | Hard code | `duration` is required and must be within `0.1..10.0 s`. | `$SKILL_ROOT/scripts/ros_cmd_vel.py:18-19,141-144,243-247` | `required=True`; `MIN_DURATION_S <= duration <= MAX_DURATION_S` |
| C13 | Chassis command set | Hard code | The low-level chassis parser allows only `status`, `stop`, and `publish`. | `$SKILL_ROOT/scripts/ros_cmd_vel.py:236-248` | Fixed `subparser` set |
| C14 | Unified Skill command set | Hard code | `robot_ops.py` accepts only predefined chassis, arm, gripper, camera, lidar, auxiliary, health/status, and related commands. | `$SKILL_ROOT/scripts/robot_ops.py:623-659` | `subparsers.add_parser(...)` |
| C15 | Arm servo ID | Hard code | `arm-set-one` accepts only IDs `1..5`; ID10 is reserved for the gripper. | `$SKILL_ROOT/scripts/arm_set_one.py:39-49` | `servo_id not in (1,2,3,4,5)` → reject |
| C16 | Arm target position | Hard code | The arm target must be an integer in `0..1000`. | `$SKILL_ROOT/scripts/arm_set_one.py:40-49` | `0 <= args.position <= 1000` |
| C17 | One servo per operation | Mixed | The Skill requires one ID per operation; the CLI also accepts one `servo-id` and one position. | `$SKILL_ROOT/SKILL.md:26-29`; `arm_set_one.py:40-43` | `modify only one ID at a time` |
| C18 | Gripper target position | Hard code | ID10 target must be in `250..800`; this range is checked before ROS initialization. | `$ROBOT_ROOT/set-gripper-position.py:13-17` | `TARGET < 250 or TARGET > 800` → `TARGET_LIMIT` |
| C19 | Sensitive servos | Model-only | ID5 is wrist rotation and ID10 is the gripper; an explicit request and safe surroundings are required. | `$SKILL_ROOT/SKILL.md:26-29` | `only adjust when explicitly requested and surroundings are safe` |
| C20 | Color sorting cannot move the robot | Model-only | Color sorting is perception/recommendation only; it must not move the chassis, arm, or gripper, or treat camera coordinates as `base_link`. | `$SKILL_ROOT/SKILL.md:30-31`; `skill_evolution.json:10-12` | `perception only; never triggers robot motion` |
| C21 | Auxiliary-board IP source | Model-only | The current IPv4 must be supplied by the user; the model must not guess, scan, or reuse an old IP. | `$SKILL_ROOT/SKILL.md:33-34,92-109` | `ask if missing; do not guess, scan, or reuse` |
| C22 | Auxiliary-board IP format | Hard code | `--aux-ip` must be a literal IPv4, not IPv6 or a hostname. | `$SKILL_ROOT/scripts/robot_ops.py:355-362,649-655` | `ipaddress.ip_address(value)`; `version != 4` → reject |
| C23 | Fixed latest camera files | Model-only / fixed caller | The normal caller overwrites fixed latest files instead of creating timestamped archives. | `$SKILL_ROOT/SKILL.md:32,88-90,115-121`; `robot_ops.py:235-240` | `overwrite fixed latest output; no timestamp archive` |
| C24 | Photo-viewer file allowlist | Hard code | The HTTP viewer serves only four fixed latest files; other paths return 404 and directory listing returns 403. | `$SKILL_ROOT/scripts/latest_photo_server.py:13-34` | `name not in ALLOWED_FILES` → `404` |
| C25 | Photo-viewer TTL | Hard code | TTL must be `60..3600 s`; both wrapper and server validate it. | `robot_ops.py:407-414`; `latest_photo_server.py:38-45` | `60 <= args.ttl <= 3600` |
| C26 | Local-asset existence | Hard code | Before launch, checks whether the chassis client, robot scripts, latest photo, and photo server exist. | `$SKILL_ROOT/scripts/robot_ops.py:132-134,210-216,300-304,387-406` | `exists()` / `is_file()` |
| C27 | Recovery authorization | Model-only | If `/cmd_vel` and wheel telemetry are healthy but wheels do not move, `stop-all/start-all` requires user authorization; `motor_type` must not be resent or polled. | `$SKILL_ROOT/SKILL.md:35-37` | `after user authorization`; `do not resend or poll motor_type` |
| C28 | Do not invent results | Model-only | Report only returned fields; do not fill missing lidar/depth/servo data from model knowledge. | `$SKILL_ROOT/SKILL.md:88-90`; `skill_evolution.json:9-12` | `report real returned fields only` |
| C29 | Output truncation | Hard code | The wrapper truncates stdout/stderr to fixed maximum lengths. | `$SKILL_ROOT/scripts/robot_ops.py:81-100` | `stdout[-6000:]`; `stderr[-3000:]` |
| C30 | `/bin/sh` bypass advice | Model-only and unsafe | This is **not** a safety constraint. Evolution advises changing a blocked script invocation to `/bin/sh <script>`; changing the form does not make the operation safe. | `$SKILL_ROOT/skill_evolution.json:13` | `use the /bin/sh <script> prefix` |

## Rules written in the Skill but not guaranteed by code

| ID | Skill rule | Actual code behavior |
|---|---|---|
| G01 | Direction, speed, and duration are all required. | The CLI requires only `duration`; speed components default to `0.0`. |
| G02 | Run `chassis-status` before every movement. | `publish` does not require a status result/token and can run directly. |
| G03 | Real motion requires user authorization. | Python scripts have no user/session authorization token. |
| G04 | Large arm motion requires clearance confirmation. | Code checks only `--allow-large-delta`; it does not verify who supplied confirmation. |
| G05 | Recovery must be authorized. | `stop-all/start-all` accept no authorization token; the model must follow the prose rule. |

## Excluded: checks that require hardware output

| Check | Why it is excluded | Location |
|---|---|---|
| `chassis-status` | Reads ROS Master and battery topic; battery wait can last 1.5 seconds. | `ros_cmd_vel.py:78-126` |
| `/cmd_vel` subscriber | Waits for a ROS subscriber for up to 3 seconds. | `ros_cmd_vel.py:68-75,164-169` |
| Arm delta `120/250` | Reads three servo-feedback frames before calculating current position and delta. | `arm_set_one.py:21-30,53-80` |
| Arm accuracy | Reads servo feedback again after movement. | `arm_set_one.py:81-110` |
| Gripper accuracy | Waits for service/subscriber and reads original/final position. | `$ROBOT_ROOT/set-gripper-position.py:20-58` |
| Camera/depth validity | Waits for RGB/depth messages, up to 8 seconds each. | `camera_snapshot.py:31-45` |
| Auxiliary publisher identity | Queries ROS Master and publisher IP information. | `robot_ops.py:470-512` |
| Lidar/health/status/interfaces | Runs board/ROS scripts and waits for their output. | `robot_ops.py:295-337` |

## Conclusion

The strongest deterministic pre-hardware limits are: chassis `0.20 m/s / 0.50 rad/s / 0.1..10 s`, arm ID `1..5` and position `0..1000`, gripper `250..800`, literal IPv4, photo TTL `60..3600 s`, and M-Claw tool/file/credential safety. Motion authorization, mandatory status-before-move, clearance confirmation, and recovery permission remain model instructions rather than reliable deterministic safety boundaries.
