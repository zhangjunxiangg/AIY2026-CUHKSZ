# CLI Contract: Robot Control v1

## Invocation

```text
robot_control_cli.py [--backend fake|ros] [--config PATH] status
robot_control_cli.py [--backend fake|ros] [--config PATH] move --linear-x X --linear-y Y --angular-z Z --duration S [--operation-id ID]
robot_control_cli.py [--backend fake|ros] [--config PATH] stop
```

`fake` is the only backend delivered by this feature. Selecting `ros` before the integration feature returns `BACKEND_UNAVAILABLE`; it never silently falls back to fake.

## Streams

- Standard output: exactly one compact JSON object matching `motion-result.schema.json`, followed by one newline.
- Standard error: optional English diagnostics only.
- No progress output is written to standard output.

## Exit Classes

| Code | Meaning |
|---|---|
| `0` | Operation completed successfully |
| `2` | CLI usage, malformed input, or safety validation failure |
| `3` | Backend/configuration/ownership unavailable |
| `4` | Execution cancelled, timed out, or failed at runtime |
| `5` | Explicit zero-velocity sequence could not be confirmed |

## Compatibility

- Schema identifier is `robot-control/v1`.
- Consumers MUST ignore unknown fields but MUST reject an unknown major schema identifier.
- Error `code` and exit class are stable; `detail` is informational and may gain context.
