# Data Model: Safe Approach Simulation

## ConfigurationProvenance

| Field | Type | Rules |
|---|---|---|
| `kind` | enum | `synthetic` or `measured` |
| `source` | string | non-empty file/record identifier |
| `measured_at` | number/null | Unix timestamp required for `measured` |

## LaserScanSnapshot

| Field | Type | Rules |
|---|---|---|
| `observed_at` | number | finite timestamp |
| `angle_min` | number | finite radians |
| `angle_increment` | number | finite and non-zero radians |
| `range_min` | number | finite, positive metres |
| `range_max` | number | finite and greater than range_min |
| `ranges` | sequence[number] | non-empty; individual invalid values are filtered |

## SectorRule

| Field | Type | Rules |
|---|---|---|
| `name` | enum | `front`, `rear`, `left`, or `right` |
| `center_rad` | number | finite, normalized for comparison |
| `half_width_rad` | number | finite and `(0, pi/2]` |
| `min_clearance_m` | number | positive measured/synthetic threshold |
| `min_samples` | integer | at least 1 |

## SafetyConfiguration

Contains exactly one rule per direction, `max_scan_age_s`, `future_tolerance_s`, `reset_clear_frames`, and `ConfigurationProvenance`. Production integration accepts only `measured`.

## SectorEvidence

`name`, `sample_count`, `minimum_m`, `threshold_m`, `clear`, and optional failure reason. A missing minimum is never interpreted as infinity.

## SafetyDecision

`allowed`, requested velocity, required sectors, ordered sector evidence, `latched`, latch reason, scan age, and stable decision code. Zero velocity may be allowed while `latched=true`.

## EmergencyStopLatch

State transitions:

```text
CLEAR --unsafe/unavailable non-zero request--> LATCHED
LATCHED --explicit reset request--> RESET_PENDING
RESET_PENDING --invalid/blocked frame--> RESET_PENDING(counter=0)
RESET_PENDING --N consecutive all-clear frames--> CLEAR
```

Clear scans without a reset request do not change `LATCHED`.

## BaseTargetObservation

`observed_at`, `frame_id`, x/y/z metres, `valid`, confidence `[0,1]`, source ID, and optional calibration provenance. The accepted frame is exactly `base_link`.

## PixelDepthObservation

`observed_at`, pixel u/v, `depth_m`, confidence, valid state, camera frame, and source ID. Depth is camera-forward before transform.

## CameraIntrinsics

Positive `fx`, `fy`; finite `cx`, `cy`; positive image width/height; pixel must lie inside the image.

## RigidTransform

Source frame, target frame `base_link`, nine-element row-major rotation, three-element translation, validity interval, and provenance. Rotation must be orthonormal with determinant approximately +1.

## NormalizedTarget

Base x/y/z, `planar_distance_m`, `bearing_rad`, confidence, observation time, source ID, and calibration provenance. z remains height and is not used as forward depth.

## ApproachConfiguration

Bounded angular/linear speeds, correction duration, target age, confidence floor, bearing tolerance, stand-off distance/tolerance, stable-frame count, target-loss allowance, total timeout, iteration limit, and provenance.

## ApproachState and ApproachResult

States: `IDLE`, `PRECHECK`, `ROTATE`, `TRANSLATE`, `VERIFY`, `STOPPING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `ESTOPPED`.

Result contains schema, terminal state, ordered state history, correction `MotionResult` values, final target/safety evidence, elapsed time, stop result, verification level, and optional stable error.
