# Deployment and Rollback Contract

## Before Copying

- Record current board artifact path, source identity/digest, modes, and read-only smoke output.
- Create or identify a recoverable backup outside the new target tree.
- Match the Spec 003 reviewed manifest and measured configuration to the HIL session.
- Reject secrets, synthetic configuration, unlisted files, unknown IP assumptions, and any automatic-start entry.

## Deployment

Copy only manifest entries to `/data/local/robot/jx/control_ws/`, set documented modes, compute deployed digests, and run only read-only smoke/status. Deployment itself does not authorize movement.

## Rollback Triggers

- Manifest or digest mismatch.
- Import, permission, wrapper, status, or smoke regression.
- Unexpected direction or continuing motion.
- Stop, lidar, ownership, persistent-estop, reset, or approach safety failure.
- Unknown publisher, changed configuration, or unexplained board state.

## Rollback Completion

Restore the exact recorded previous artifact, restore its documented configuration, run read-only identity/status/smoke checks, and mark the new deployment `ROLLED_BACK`. No post-rollback movement is implied; it requires a new session/preflight/proposal.

## Startup Boundary

Do not install `init.cfg` or another autonomous startup path as part of this feature. Startup acceptance is a separate team decision after manual HIL and rollback are complete.
