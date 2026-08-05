# Local-only M-Claw update notes

This update was prepared and tested on the Ubuntu laptop from M-Claw commit
`a793b14`. It has not been deployed to a robot board. Passing software tests do
not prove current robot or hardware readiness.

## Change 1: use WeChat's voice transcript

Purpose: let M-Claw understand voice messages when WeChat already supplies
recognized text.

- `mclaw/channels/weixin/adapter.py` uses non-empty `voice_item.text` as the
  message content.
- The same transcribed voice is no longer attached as unsupported SILK audio.
- Voices without recognized text keep the existing audio fallback.
- Images, videos, files, and other media behavior is unchanged.
- `tests/test_weixin_voice_transcript.py` covers transcript use, mixed media,
  untranscribed voice fallback, and the adapter-to-agent handoff.

## Change 2: show the prompt before optional startup work

Purpose: reduce perceived CLI startup time without weakening first-command
readiness.

- `mclaw/cli/app.py` no longer scans all installed Skills before the terminal
  interface appears.
- The Skill registry loads when slash completion is first requested.
- Detached-process recovery runs after the prompt's first paint.
- An immediately submitted command waits for recovery before execution, so the
  process registry is consistent.
- The core agent still initializes before the prompt. Fully deferring it would
  require a separate starting state, queued input, and retryable error handling.
- `tests/test_startup_deferred.py` verifies deferred, one-time recovery and lazy
  Skill loading.

## Change 3: add an opt-in low-overhead robot-control profile foundation

Purpose: reduce model input and accidental long loops for latency-sensitive
robot requests without narrowing normal development sessions.

- `mclaw/tools/toolsets.py` adds an opt-in `robot-control` preset that exposes
  only the `terminal` tool. It is not enabled by default.
- `mclaw/agent/builtin_memory_provider.py` no longer prefetches memory when both
  memory targets are explicitly disabled.
- `examples/robot-control.mclaw.yaml` shows a three-turn budget, disabled broad
  memory/reviews, and the narrow WeChat tool list. The example is inert until
  approved values are copied to a real `.mclaw.yaml`.
- `tests/test_robot_control_profile.py` verifies the exact tool boundary and
  that disabled memory contributes no prefetched context.

This partially addresses P8/P10. It does not yet implement P16 request-mode
classification or P2's atomic `battery-status` workflow. Those require the
active Robot Skill and an approved side-effect contract, which are not present
in the local snapshot.

## Files in this update

```text
LOCAL_ONLY.md
mclaw/channels/weixin/adapter.py
mclaw/cli/app.py
mclaw/agent/builtin_memory_provider.py
mclaw/tools/toolsets.py
examples/robot-control.mclaw.yaml
tests/test_startup_deferred.py
tests/test_weixin_voice_transcript.py
tests/test_robot_control_profile.py
```

These are repository-relative paths and should be placed at the root of an
existing M-Claw checkout.

## Verification

- Robot-control profile plus existing focused update tests: `8 passed`.
- Robot-control profile plus adjacent config/runtime/tool/memory tests:
  `133 passed`.
- WeChat and startup focused tests together: `6 passed`.
- WeChat plus adjacent lifecycle tests: `42 passed`.
- Startup/CLI/runtime tests from the startup session: `51 passed`.
- Network tests with the laptop proxy bypassed: `20 passed`.
- Full-suite observation from the startup session: `802 passed`; four unrelated
  process-cancellation tests failed in untouched modules.

No SSH, ROS command, robot movement, or board deployment is part of this update.
