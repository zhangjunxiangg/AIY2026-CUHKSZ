<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Added principles: workspace isolation; vendor interfaces; shared core; fail closed;
  single motion owner; guaranteed stop; test first; structured contracts;
  measured configuration; verification levels; supervised HIL
- Added sections: Safety and Interface Constraints; Development Workflow
- Templates updated:
  - .specify/templates/plan-template.md: constitution gates and verification boundary
  - .specify/templates/spec-template.md: verification boundary requirements
  - .specify/templates/tasks-template.md: verification labels and TDD rules
- Deferred items: none
-->
# JUNXIANG Motion Control Constitution

## Core Principles

### I. Workspace Isolation

All specifications, source code, tests, configuration, generated artifacts, and
verification records MUST remain under `JUNXIANG/`. Work MUST stay on the
`junxiang` branch. Shared team files, vendor source, `robot-sdk/`, and `main`
MUST NOT be modified without new explicit authorization. This prevents an
individual control module from destabilizing the team's integration baseline.

### II. Vendor Interfaces First

The implementation MUST reuse the documented ROS interfaces and the behavior of
the official M-Claw tools. It MUST NOT rewrite the chassis driver, publish
`motor_type`, call `/ros_robot_controller/set_motor`, or treat command-integrated
`/odom` as physical feedback. Source examples are evidence, not permission to
copy obsolete topic names or unsafe limits.

### III. Shared Control Core

Manual CLI commands, simulated workflows, and autonomous approach behavior MUST
invoke the same validation, limiting, state transition, and stop semantics. A
closed-loop controller MUST remain in one process for its full operation and
MUST NOT spawn a new movement CLI process for every correction.

### IV. Fail Closed

Missing or stale perception, missing calibration, invalid numeric input,
unconfirmed directional configuration, missing obstacle thresholds, competing
motion publishers, and unavailable safety data MUST reject non-zero motion.
No implementation may silently substitute guessed production values.

### V. Single Motion Owner

Only one project process may own motion at a time. Production integration MUST
use an inter-process lock and inspect `/cmd_vel` publishers before motion. If
exclusive ownership cannot be established, the only permitted output is zero
velocity and a structured failure result.

### VI. Guaranteed Stop

Successful completion, validation failure, exception, timeout, cancellation,
target loss, emergency stop, and SIGINT/SIGTERM/SIGHUP MUST all converge on an
explicit zero-velocity sequence. The chassis watchdog is a fallback and MUST NOT
replace active stopping. Tests MUST assert the stop event on every terminal path.

### VII. Test First

Tests MUST be written before the corresponding behavior. Pure domain logic MUST
not import ROS. Fake and mock backends MUST be deterministic and incapable of
network or hardware access. Every implemented requirement MUST map to at least
one task and one automated or explicitly deferred HIL verification.

### VIII. Structured Contracts

The CLI MUST accept explicit arguments or versioned structured input, write one
machine-readable JSON result to stdout, write diagnostics to stderr, and use
stable exit codes. Vision observations, motion results, errors, and verification
levels MUST have versioned contracts and deterministic validation.

### IX. Measured Production Configuration

Hardware direction signs, obstacle distances, camera calibration, grasp
stand-off, and final tolerances MUST be traceable to a dated measurement.
Synthetic values MAY be used in files clearly marked for tests, but those files
MUST be rejected by the production backend.

### X. Verification Levels Are Distinct

Artifacts MUST use exactly one applicable verification level:
`OFFLINE_VERIFIED`, `SOURCE_VERIFIED_HIL_PENDING`, or `HIL_VERIFIED`. Offline
simulation and source inspection MUST NOT be represented as physical validation.
Only supervised, recorded robot testing may assign `HIL_VERIFIED`.

### XI. Supervised HIL

Specification and implementation approvals may be autonomous, but physical
motion may not. Before every real movement, the operator MUST be beside the
robot, receive the proposed parameters and risk, and explicitly say "走". The
first test MUST use the smallest practical bounded command. HIL work remains
deferred whenever those conditions cannot be met.

## Safety and Interface Constraints

- Linear planar magnitude MUST be at most `0.20 m/s`; angular speed MUST be at
  most `0.50 rad/s`; one bounded command MUST last between `0.1` and `10.0`
  seconds.
- Production movement MUST use the board `run` environment and deploy only
  under `/data/local/robot/jx/control_ws/` after HIL authorization.
- Automatic approach MUST use fresh perception and directional `/scan` safety
  decisions. Open-loop odometry may be logged but not used to declare arrival.
- `base_link` uses x forward, y left, and z up. Chassis arrival uses x/y and
  bearing; base-frame z MUST NOT be treated as forward depth.
- Runtime logs MUST be English to remain readable on the board. Documentation
  may be Chinese.
- Secrets, tokens, keys, and the existing `JUNXIANG/secrets/` directory MUST NOT
  be read, copied, documented, staged, or committed by this project workflow.

## Development Workflow

Each feature MUST follow constitution -> specify -> clarify -> plan -> tasks ->
analyze -> implement. Specification and plan review gates are self-approved only
after their checklists pass. Analysis is read-only; findings are remediated by
returning to the owning stage and rerunning analysis. CRITICAL or HIGH findings,
unmapped requirements, incomplete checklists, and unresolved clarification
markers block implementation.

Commits MUST be small, logical, and test-backed. Generated Spec Kit bootstrap
assets may retain their upstream formatting; project-authored files MUST pass
`git diff --check`. Incorrect work is corrected with traceable follow-up commits,
not hidden with destructive history rewriting.

## Governance

This constitution supersedes feature plans and implementation convenience.
Amendments require a documented Sync Impact Report, semantic version change,
and propagation to dependent templates and active specifications. A MAJOR bump
changes or removes a non-negotiable principle, a MINOR bump adds or materially
expands one, and a PATCH bump clarifies wording without changing obligations.
Every Spec Kit analysis and implementation gate MUST verify compliance.

**Version**: 1.0.0 | **Ratified**: 2026-08-05 | **Last Amended**: 2026-08-05
