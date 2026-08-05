# Research: Motion Domain Core

## Decision 1: Shared controller instead of CLI-per-correction

- **Decision**: Put validation, execution, stop, and result semantics in one reusable controller called directly by both CLI and later automatic logic.
- **Rationale**: A visual feedback loop must preserve state and stop ownership inside one process. Subprocess-per-correction creates latency, fragmented cancellation, and ambiguous motion ownership.
- **Alternatives considered**: Repeated CLI calls were rejected for feedback control; a permanent ROS service node was deferred because it adds lifecycle and deployment complexity before the contract is stable.

## Decision 2: Standard-library Python domain layer

- **Decision**: Use Python 3.11-compatible standard-library code and `unittest`.
- **Rationale**: Official board guidance permits pure Python packages but cannot guarantee installation of new compiled dependencies. Standard-library tests also run on the Mac and board.
- **Alternatives considered**: `pytest` and schema-validation libraries would improve ergonomics but add deployment dependencies; dataclass-based explicit validation is sufficient for this bounded domain.

## Decision 3: Injectable clock and deterministic fake backend

- **Decision**: The backend supplies monotonic time and sleep behavior; fake mode advances virtual time and records events.
- **Rationale**: Duration, cadence, cancellation, timeout, and final-stop assertions become fast and deterministic. Tests never need ROS or wall-clock sleeps.
- **Alternatives considered**: Monkey-patching `time` is global and brittle; using real sleeps would make tests slow and timing-sensitive.

## Decision 4: Planar-magnitude limiting

- **Decision**: Validate `hypot(linear_x, linear_y) <= 0.20`, `abs(angular_z) <= 0.50`, and duration `0.1..10.0`.
- **Rationale**: This matches the current official `ros_cmd_vel.py`; axis-by-axis limiting would allow diagonal motion above the chassis linear limit.
- **Alternatives considered**: Automatic clamping was rejected because it hides unsafe caller errors. Requests fail with explicit codes.

## Decision 5: Explicit stop sequence and stop-failure precedence

- **Decision**: Once ownership is acquired, all exits run multiple zero-velocity events before release. A failed stop is surfaced as the safety-critical terminal failure while retaining the initiating error as context.
- **Rationale**: The vendor watchdog is only a fallback. Callers must know when active stopping could not be confirmed.
- **Alternatives considered**: A single zero event is less robust to publisher connection timing; silently preserving only the original error would hide the more important safety state.

## Decision 6: Versioned result envelope and stable exit classes

- **Decision**: All CLI outcomes use contract version `robot-control/v1`, one JSON object on stdout, diagnostics on stderr, and exit classes 0, 2, 3, 4, and 5.
- **Rationale**: Skills and scripts can branch on stable machine fields without parsing logs.
- **Alternatives considered**: Human-readable stdout was rejected because it is fragile for automation; separate per-command payloads without an envelope make compatibility unclear.

## Source Evidence

- Official current publisher: `vendor/kaihong-src/kaihong_adapter/mclaw-skill/scripts/ros_cmd_vel.py`
- Official safety policy: `vendor/kaihong-src/kaihong_adapter/mclaw-skill/SKILL.md`
- Local measured interface record: `JUNXIANG/机器人控制对接文档.md`

Source inspection supports design constraints only. It does not assign `HIL_VERIFIED`.
