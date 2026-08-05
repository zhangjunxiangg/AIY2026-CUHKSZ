# Implementation Plan: Supervised HIL Validation and Handoff

**Branch**: `junxiang` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-hil-validation-handoff/spec.md`

**Execution status**: Local implementation and offline regression complete; all board/deployment/motion tasks remain `HIL_PENDING`.

## Summary

Provide one supervised, evidence-driven procedure that promotes the motion-control deliverables from offline/source verification to hardware acceptance. It binds every result to one robot, source revision, manifest, and measured configuration; separates read-only preflight from physical cases; requires a new parameter/risk proposal and nearby-operator `走` for every non-zero action; validates primitive directions and lidar/estop safety before visual approach; and ends with deployment, rollback, and team handoff records.

## Technical Context

**Language/Version**: Markdown procedures and JSON Schema Draft 2020-12; actual CLI uses the Python version identified in Spec 003 HIL preflight  
**Primary Dependencies**: Implemented Specs 001-003; board `/bin/run`; ROS1 graph and topics; measured production configuration; phone/video evidence  
**Storage**: Tracked procedure/contracts plus untracked or deliberately selected HIL session records containing JSON, filtered logs, scan/target snapshots, measurements, and media references  
**Testing**: Offline schema/document/source validation tonight; supervised case execution and evidence audit tomorrow  
**Target Platform**: M-Robots OS chassis board and physical robot in a measured cleared test area  
**Project Type**: HIL acceptance protocol and integration handoff  
**Performance Goals**: Every non-zero command has 100% authorization/stop traceability; every mandatory case has complete evidence; stop latency and arrival tolerance are recorded against measured configuration rather than guessed here  
**Constraints**: No HIL execution tonight; explicit `走` per action; constitutional hard limits; first motion <=0.10 m/s for 2.0 s or smaller; no odometry-only arrival; no secrets; no autonomous startup before acceptance  
**Scale/Scope**: One robot/revision/configuration per HIL session; six primitive directions; four directional lidar sectors; persistent estop/reset; ten visual-approach scenario classes; one deploy/rollback/handoff package

## Constitution Check

*GATE: Passed before research and re-checked after design.*

- [x] All files are scoped to `src/robot-control/` and no secret path is accessed.
- [x] Vendor interfaces and hard motion limits are preserved.
- [x] CLI and automatic control share one testable control core.
- [x] Every terminal path has an explicit zero-velocity assertion.
- [x] Missing production evidence fails closed instead of using guessed values.
- [x] Offline, source-verified, and HIL evidence are reported separately.
- [x] HIL tasks retain the operator's explicit physical-motion gate.
- [x] Tests precede implementation and every requirement maps to a task.

No violations require justification. This feature intentionally does not implement or execute physical actions during offline work.

## Verification Boundary

- `OFFLINE_VERIFIED`: Spec/checklist/plan/task completeness, JSON schema validity, case coverage, formulas, and source-contract cross-references.
- `SOURCE_VERIFIED_HIL_PENDING`: Exact interface names and expected result fields after Specs 001-003 source validation.
- `HIL_VERIFIED`: Assigned only to an individual executed case whose prerequisites, nearby-operator authorization, physical observation, explicit stop, identity/digest binding, and required evidence all pass.
- Global promotion requires all mandatory cases to pass in one compatible session context. Partial sessions remain `HIL_PENDING`.
- No command in tonight's validation may contact HDC, SSH, ROS Master, or a robot.

## Local Implementation Completed Before HIL

- Capability-scoped production configuration v2 supports `motion=true` with
  `approach=false`; absent vision fields remain absent and fail-closed.
- Existing v1 full configurations retain their prior behavior and implicitly enable
  both capabilities.
- The CLI gates `approach` with `CAPABILITY_DISABLED` before ROS loading and builds no
  target provider for motion-only status/move/stop/reset paths.
- `board_smoke_test.py` reports target `CAPABILITY_DISABLED` without claiming target
  readiness when approach is disabled.
- `hil_session.py` creates an explicit local session identity with file digests,
  `package_manifest.py` validates the reviewed allowlist and only stages locally when
  requested, and `cmd_vel_observer.py` observes `geometry_msgs/Twist` read-only.
- Offline evidence is the 147-test regression, compile/shell/JSON checks, and a
  successful manifest validation. None promotes physical cases.

The next executable boundary is read-only board preflight. Deployment and any ROS
process start require a separately reported, user-observed test stage; non-zero
motion remains one proposal plus one nearby-operator `走` at a time.

## Project Structure

### Documentation (this feature)

```text
specs/004-hil-validation-handoff/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── case-matrix.md
│   ├── deployment-rollback.md
│   ├── evidence-record.schema.json
│   ├── handoff.md
│   └── supervision.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Deferred HIL Records (`src/robot-control/` root)

```text
control_ws/src/student_tasks/hil/
├── README.md
├── session.template.json
├── case-record.template.json
└── sessions/
    └── <session-id>/
        ├── session.json
        ├── cases/
        ├── logs/
        ├── snapshots/
        └── media-index.json
```

**Structure Decision**: The spec contains stable acceptance contracts. A later supervised execution creates session records under the control package so evidence can be reviewed with the exact implementation. Media may remain outside Git; only a digest/path index is required. Secrets and raw credentials are never captured.

## Execution Design

### Gate Sequence

1. Freeze robot/revision/manifest/configuration identity and record a recoverable previous artifact.
2. Stage only the reviewed candidate manifest and run zero-output identity/smoke checks.
3. Run read-only board, graph, data, ownership, and estop preflight.
4. Demonstrate zero-only stop before any non-zero proposal.
5. Validate six primitive direction signs with one isolated minimum command per proposal.
6. Validate clear/blocked directional lidar decisions and persistent estop/reset.
7. Inspect stationary target and calibration evidence.
8. Validate one-step visual corrections and safe failure cases.
9. Validate bounded arrival using independent physical/vision measurement.
10. Audit evidence, decide production acceptance or rollback, and publish the teammate handoff record.

Failure at a gate blocks dependent gates. Retrying a physical action requires a new case attempt, a new proposal, and a new `走`.

### Motion Authorization

The agent or operator-facing procedure prints a proposal containing exact x/y/angular velocity, duration, maximum theoretical movement, expected robot-relative direction, measured clearance, stop plan, and risk. The person beside the robot either says `走` or declines. Approval is consumed by exactly one non-zero command. Changed parameters, elapsed context, reboot, deploy, or retry invalidate it. Zero/stop commands are always allowed.

### Measurement and Evidence

- Linear upper bound: `sqrt(linear_x^2 + linear_y^2) * duration`.
- Angular upper bound: `abs(angular_z) * duration`.
- Actual physical distance/angle uses a documented method and uncertainty; open-loop odometry is diagnostic only.
- Every executed case stores request/result JSON, start/end times, filtered English logs, stop evidence, relevant scan/target samples, observation, status, and reviewer rationale.
- Direction, obstacle-stop, and arrival cases include photo/video references and digests where required.

### Deployment and Rollback

Candidate staging is allowed only after a backup identity is recorded and the reviewed Spec 003 manifest/configuration digests match the session. Copying, permissions, and read-only smoke occur before movement and are recorded separately. Production acceptance occurs only after mandatory HIL evidence passes. Any revision/digest mismatch, smoke regression, unsafe motion, failed persistent estop, or unexplained owner conflict triggers rollback and a fresh read-only preflight. Autonomous startup remains outside acceptance until the team explicitly schedules it after HIL.

## Complexity Tracking

No constitution violations require justification.
