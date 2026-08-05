# Data Model: Motion Domain Core

## VerificationLevel

Allowed values are exactly:

- `OFFLINE_VERIFIED`
- `SOURCE_VERIFIED_HIL_PENDING`
- `HIL_VERIFIED`

An object carries only one value. Offline execution cannot construct `HIL_VERIFIED` evidence.

## Velocity

| Field | Type | Rules |
|---|---|---|
| `linear_x` | number | finite; metres per second |
| `linear_y` | number | finite; metres per second |
| `angular_z` | number | finite; radians per second |

Validation: `hypot(linear_x, linear_y) <= 0.20` and `abs(angular_z) <= 0.50`. `is_zero` uses exact canonical zero after numeric normalization.

## MotionRequest

| Field | Type | Rules |
|---|---|---|
| `operation_id` | string | non-empty, at most 128 characters |
| `velocity` | Velocity | validated value |
| `duration_s` | number | finite and `0.1..10.0` |
| `publish_rate_hz` | number | finite and `2.0..50.0`; default 20.0 |

Lifecycle: `VALIDATED -> OWNED -> RUNNING -> STOPPING -> SUCCEEDED` or a terminal failure. Ownership and running are runtime events, not mutable request fields.

## BackendStatus

| Field | Type | Rules |
|---|---|---|
| `ready` | boolean | false when any blocking reason exists |
| `backend` | string | stable backend identifier |
| `production` | boolean | true only for a real transport |
| `configuration_kind` | enum | `synthetic`, `measured`, or `missing` |
| `blocking_reasons` | list[string] | deterministic ordering |
| `details` | object | read-only backend evidence |

Non-zero movement requires ready status. A production backend additionally requires measured configuration.

## ControlError

| Field | Type | Rules |
|---|---|---|
| `code` | string | stable uppercase identifier |
| `category` | enum | `usage`, `validation`, `unavailable`, `runtime`, `stop_safety` |
| `detail` | string | non-empty English runtime-safe text |
| `retryable` | boolean | deterministic by failure type |

Primary codes: `INVALID_INPUT`, `LIMIT_EXCEEDED`, `BACKEND_UNAVAILABLE`, `PRODUCTION_CONFIG_REQUIRED`, `MOTION_BUSY`, `CANCELLED`, `TIMEOUT`, `BACKEND_FAILURE`, and `STOP_FAILED`.

## MotionResult

| Field | Type | Rules |
|---|---|---|
| `schema` | string | `robot-control/v1` |
| `operation` | enum | `status`, `move`, or `stop` |
| `operation_id` | string/null | request identifier when applicable |
| `ok` | boolean | true only on complete success |
| `backend` | string | backend identifier |
| `verification` | VerificationLevel | one approved value |
| `zero_velocity_attempted` | boolean | whether active stopping was attempted |
| `zero_velocity_confirmed` | boolean | backend accepted the required sequence |
| `elapsed_s` | number | non-negative monotonic duration |
| `data` | object | operation-specific evidence |
| `error` | ControlError/null | required when `ok` is false |

## BackendEvent

| Field | Type | Rules |
|---|---|---|
| `sequence` | integer | starts at 1 and strictly increases |
| `kind` | enum | `acquire`, `velocity`, `release`, `status`, `sleep` |
| `at_s` | number | fake or monotonic time |
| `velocity` | Velocity/null | present for velocity events |
| `metadata` | object | deterministic auxiliary evidence |

Fake-backend event order is the authoritative offline proof for stop semantics, not physical proof.
