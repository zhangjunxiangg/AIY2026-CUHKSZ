# Data Model: Board ROS Integration

## ProductionConfiguration

Top-level schema: `robot-control/production-config/v1`.

| Group | Required content |
|---|---|
| `provenance` | `kind=measured`, source, `measured_at`, robot identity |
| `ros` | Master URI policy, node name prefix, cmd/scan/target topics, target schema |
| `motion` | x/y/angular direction signs, publish rate, zero count, zero interval, subscriber timeout |
| `ownership` | absolute lock path, absolute estop path, exact publisher allowlist |
| `safety` | scan ages, four sector centers/widths/clearances/sample counts, reset frames |
| `target` | source/receive ages, confidence floor, allowed source schema, optional calibration requirement |
| `approach` | bounded speeds/duration, bearing and distance tolerances, stand-off, stable frames, timeout, iterations |
| `calibration` | required mode, record source/time, transform when pixel-depth mode is enabled |

Validation rejects nulls, synthetic provenance, future measurement times, relative runtime paths, unknown schema, topic names without a leading slash, unsafe numeric limits, non-unit direction signs, duplicate sectors, non-empty allowlist entries without dated evidence, and internally inconsistent timeouts.

## MotionLock

Fields: path, descriptor, `held`, owner PID, process start time, operation ID, and metadata read from a contended record. Transitions: `RELEASED -> ACQUIRED -> RELEASED`; acquire is non-blocking.

## PublisherSnapshot

Fields: topic, current node, ordered all-publisher list, measured allowlist, conflict list, source time, and graph error. Missing graph data is a conflict for non-zero motion.

## RosBackendStatus

Extends `BackendStatus` details with Master state, subscriber nodes/count, publisher snapshot, lock availability, configuration findings, and data-provider readiness. Verification is always `SOURCE_VERIFIED_HIL_PENDING` until an external HIL record is explicitly supplied in a later feature.

## RosScanEnvelope

Contains a `LaserScanSnapshot`, ROS source stamp, monotonic receipt time, configured topic, publisher/source metadata when available, and conversion error.

## RosTargetEnvelope

Contains raw contract JSON, parsed target observation, separate valid state, ROS/source timestamp, monotonic receipt time, topic names, contract version, and conversion error. Missing confidence or provenance is invalid.

## SignalCancellationState

Fields: installed signal set, first received signal name/number, cancellation boolean, installed/restored flags, and optional pre-ownership interruption.

## PersistentEstopRecord

Schema `robot-control/estop-state/v1`; fields: latched boolean, trigger code/detail/time, last safety evidence digest, reset-requested boolean, clear-frame counter, updated time, and writer PID. Corrupt/unreadable state maps to a synthetic latched record with code `ESTOP_STATE_INVALID`.

## DeploymentManifestEntry

Fields: source path below `src/robot-control/control_ws`, absolute target path below `/data/local/robot/jx/control_ws`, file mode, purpose, and whether the file is allowed in production. Secret paths and synthetic configuration are forbidden entries.
