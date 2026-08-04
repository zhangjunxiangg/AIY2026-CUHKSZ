# Data Model: Supervised HIL Validation and Handoff

## HilSession

Identity fields: schema, session ID, started/ended time, operator/reviewer, robot ID, board IDs, source revision, manifest digest, configuration digest, calibration ID/digest, deployed root, runtime versions, environment notes, and overall status.

States: `CREATED -> PREFLIGHT_PASSED -> PRIMITIVES_PASSED -> SAFETY_PASSED -> APPROACH_PASSED -> HANDOFF_READY`. `FAILED`, `BLOCKED`, and `ROLLED_BACK` are terminal for that deployment context. A changed identity starts a new session rather than mutating accepted evidence.

## ReadinessSnapshot

Contains board/runtime identity, configured/observed topic types, subscriber and publisher nodes, process-lock availability, estop record, latest scan/target source and receive times, target schema/frame/confidence/provenance, configuration findings, smoke result, and zero/non-zero publish counts.

Validation requires every mandatory field and exactly zero non-zero publishes.

## MotionProposal

Fields: proposal ID, case/attempt ID, created time, linear x/y, angular z, duration, planar speed magnitude, predicted maximum displacement/rotation, expected physical direction, measured clearance, active lidar sector, stop method, risks, operator identity, authorization phrase/time, and consumed time.

States: `DRAFT -> PRESENTED -> AUTHORIZED -> CONSUMED`; `DECLINED` and `EXPIRED` are terminal. Any field or context change after presentation expires the proposal. Only exact `走` from the nearby operator can authorize it.

## ValidationCase

Fields: stable case ID, class, priority, prerequisites, procedure revision, attempt list, required evidence, expected safe result, dependency case IDs, mandatory flag, and final status.

Statuses: `NOT_RUN`, `BLOCKED`, `PASS`, or `FAIL`. `BLOCKED` includes a named dependency/reason. Only `PASS` satisfies a gate.

## CaseAttempt

Fields: attempt ID, case ID, proposal ID when non-zero, start/end time, request/result JSON paths, log path, scan/target snapshot paths, media references, observations, measurement IDs, explicit-stop evidence, result code, status, and reviewer rationale.

Every non-zero attempt has exactly one authorized/consumed proposal. A retry creates a new attempt and proposal.

## MeasurementRecord

Fields: measurement ID, quantity, expected value/range, observed value, unit, method, uncertainty, source timestamp, receive timestamp, recorder, provenance, and related evidence path.

Quantities include direction sign, displacement, rotation, clearance, scan range/sample count, stop time, bearing, range, confidence, and freshness age.

## EvidenceIndex

Maps session/case/attempt IDs to structured JSON, filtered English logs, scan/target snapshots, configuration/revision digests, images/videos, and reviewer notes. Each entry includes path, media type, timestamp, digest, capture method, and redaction status. Secret-bearing artifacts are forbidden.

## DeploymentRecord

Fields: deployment ID, source revision, manifest path/digest, configuration path/digest, target root, previous artifact identity/path/digest, copied entries, modes, pre/post smoke results, deployment status, rollback trigger, rollback command/result, and post-rollback readiness snapshot.

States: `PREPARED -> BACKED_UP -> COPIED -> SMOKE_PASSED -> ACCEPTED`; failures transition to `ROLLBACK_REQUIRED -> ROLLED_BACK`.

## HandoffRecord

Fields: handoff ID/time, source/deployment IDs, supported commands, input/output contract versions, verified limits, accepted case IDs, known failure codes, verification level, outstanding blockers, dependency owners, invocation examples, rollback reference, and receiving teammate acknowledgment.

## Compatibility Rule

HIL evidence is compatible only when robot ID, source revision, manifest digest, configuration digest, and required calibration identity all match. A mismatch produces a new session and leaves prior evidence historical rather than current acceptance.
