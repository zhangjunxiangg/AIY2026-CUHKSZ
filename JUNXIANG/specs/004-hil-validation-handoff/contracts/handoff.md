# Motion-Control Handoff Contract

The handoff record must give the Skill integrator enough information to consume the accepted capability without private context.

## Required Fields

- Source revision, deployment ID, manifest/configuration/calibration digests.
- Supported `status`, `stop`, `move`, `approach`, and `estop-reset` invocation contracts,
  including the `CAPABILITY_DISABLED` result when v2 approach is not enabled.
- Target observation schema/frame/confidence/freshness/provenance requirements.
- Verified hard limits, measured signs, lidar sectors, clearances, tolerances, and publish/zero behavior.
- Accepted HIL case IDs and evidence-index path.
- Stable result/exit/failure codes and which failures latch estop.
- Current verification level and explicit `NOT_RUN`, `BLOCKED`, or failed cases.
- Rollback record and known-good previous artifact.
- Named owner for vision/calibration, gripper, Skill integration, and remaining control work.

For the current motion-only handoff, the public supported capability is chassis motion
plus zero-only stop/reset. Visual approach remains deferred until the target schema,
calibration, and the required visual HIL cases are accepted in the same session context.

## Acceptance

The receiving teammate must be able to perform read-only status, identify when non-zero motion is forbidden, form a versioned target observation, interpret one result, locate evidence, and identify rollback without reading source code. This acknowledgment does not authorize physical motion.
