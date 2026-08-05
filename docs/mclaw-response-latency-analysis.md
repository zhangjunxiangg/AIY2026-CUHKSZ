# M-Claw Response Latency Analysis

## Goal

Make M-Claw answer as quickly as possible without weakening robot safety, losing
important task context, or returning an answer from the wrong provider.

This report is based on the live robot logs and configuration inspected on
2026-08-05. No API keys or account credentials are included.

## Executive conclusion

Shortening `SOUL.md` will help, but it is not the largest problem in the current
Weixin path.

The highest-impact problems are:

1. The existing Weixin conversation restores its old Kimi Coding provider from
   the session database, even though the global configuration now selects
   OpenRouter Kimi K3.
2. That Weixin conversation contains 52 historical messages and tool results.
   Its latest request was estimated at 112,193 tokens.
3. The compression threshold is 50% of a 1,048,576-token context window, so a
   112,193-token conversation is considered too small to compress.
4. The fresh-session system prompt is still large: 13,591 characters and an
   estimated 12,461 total request tokens for the two-character message `hi`.
5. `SOUL.md`, memory, the Skill index, tool guidance, environment information,
   and tool schemas are included before the model sees every request.
6. Kimi K3 reasoning and provider latency can still dominate a small request
   after the context problems are fixed.

The fastest safe first step is therefore: start a new Weixin session after a
provider change, then shorten the always-loaded prompt. Do not begin by deleting
session data or removing safety rules.

## Evidence from the logs

### 1. Fresh OpenRouter request: approximately 23.7 seconds inside the provider call

The direct M-Claw request at 16:14 had only two messages: the system prompt and
`hi`.

| Event | Time |
|---|---:|
| Agent loop started | 16:14:21.748 |
| Request ready for API call | 16:14:21.757 |
| Provider returned token usage | 16:14:45.434 |
| Time between request-ready and provider return | about 23.677 s |

The request contained:

- 2 messages;
- 13,593 message characters;
- 12,461 estimated request tokens;
- 10,261 provider-reported tokens after completion;
- no logged retry or API error.

This delay was therefore primarily inside the OpenRouter/Kimi K3 request. It was
not caused by a robot Skill or a Weixin send operation.

There is no Weixin `inbound message` line associated with this 16:14 request, so
the logs do not prove that this particular 23.7-second test came through Weixin.
It appears to be a direct or separate M-Claw session.

### 2. Actual Weixin overhead is small

For the later Weixin message:

| Event | Time | Elapsed from inbound |
|---|---:|---:|
| Message received | 16:15:46.670 | 0 s |
| Agent turn started | 16:15:47.335 | 0.665 s |
| Text sent | 16:15:53.994 | 7.324 s |

Weixin routing added less than one second before the agent turn. It is not the
main source of the long response time.

### 3. The Weixin session did not switch to OpenRouter

The restarted Weixin gateway loaded the existing session
`weixin_5a3f59baee78d5e5bf845f2e`. M-Claw restores a saved provider snapshot for
each session before using the global startup provider.

The live log at 16:15:48 says:

```text
model=k3 provider=kimi-coding base_url=https://api.kimi.com/coding
```

The call then failed at 16:15:53 with the known Kimi Coding billing-cycle 403.
The global `config.yaml` already selected `openrouter` and
`moonshotai/kimi-k3`, but the existing Weixin session retained the old provider.

This is both a speed problem and a correctness problem: the user can believe a
provider switch succeeded while the channel continues calling the old provider.

### 4. The Weixin history is extremely large

The same Weixin turn loaded:

- 52 historical messages before adding the latest input;
- 54 total messages at API-call time;
- 43,790 message characters;
- 112,193 estimated request tokens;
- previous Skill bodies, tool calls, tool outputs, images, voice metadata,
  diagnostics, and failed robot operations.

The conversation compressor did not run because the current threshold is:

```text
1,048,576 context tokens x 50% = 524,288 tokens
```

The 112,193-token request is large for latency and cost, but still far below that
threshold. A one-word greeting therefore carries the entire old robot-debugging
conversation.

### 5. `SOUL.md` is large, but it is only part of the fresh prompt

The current repository `SOUL.md` is:

- 264 lines;
- 4,334 Unicode characters;
- 11,417 UTF-8 bytes.

The fresh system message logged by M-Claw was 13,591 characters. By character
count, `SOUL.md` contributes approximately 32% of that message. The rest is
assembled by M-Claw from language rules, platform/environment information, tool
guidance, memory guidance and recalled memory, session-search guidance, and the
installed-Skill index.

Shortening `SOUL.md` is worthwhile, especially for first-request latency, but it
cannot by itself fix a 112,193-token Weixin history or a session that uses the
wrong provider.

## What is already loaded lazily

M-Claw already uses progressive disclosure for Skills:

- The initial system prompt contains each enabled Skill's name and short
  description.
- The complete `SKILL.md` is loaded only when the model calls `skill_view` for a
  relevant task.

Therefore, moving detailed behavior from `SOUL.md` into a focused robot Skill or
reference file can reduce the always-loaded prompt without losing the detail.

The Skill index and the general Skill-management instructions are still included
in every request while Skill tools are enabled. Disabling unrelated Skills can
shrink this index, but removing the index entirely would make automatic Skill
selection less reliable.

## What is not currently loaded lazily

The following content is built into every system prompt for the current runtime:

- `SOUL.md`;
- language and platform rules;
- environment information;
- tool-use guidance and exposed tool names;
- memory guidance;
- recalled memory and user profile when enabled;
- session-search guidance;
- the enabled-Skill index and Skill workflow guidance.

Tool schemas are also sent with the model request for the enabled toolsets. The
current configuration enables:

```yaml
toolsets:
  - mclaw-required
  - web
  - vision
  - weixin
```

M-Claw does not currently provide a configuration switch that keeps memory tools
available while omitting recalled memory from the system prompt. In the current
implementation, disabling built-in memory also removes its memory tools. True
on-demand memory requires a small source change, not only a YAML change.

## Problems and solutions

### Problem 1: Existing channel sessions pin the old provider

Impact: wrong provider, failed requests, misleading verification, and wasted
time. This is the first issue to fix.

Solutions:

1. **Immediate:** after changing the global provider, send `/new` in Weixin and
   verify the new session log shows `provider=openrouter` and
   `model=moonshotai/kimi-k3`.
2. **Permanent:** change M-Claw channel session restoration so a provider-config
   fingerprint mismatch either migrates the saved session or clearly asks for a
   new session. Never silently restore a stale provider after an explicit global
   provider switch.

### Problem 2: Weixin history grows without a practical latency boundary

Impact: every short message resends old tool calls, large Skill results, image
metadata, failures, and unrelated discussion.

Solutions:

1. **Immediate:** use `/new` whenever the task changes, after a provider switch,
   and after a long tool-heavy debugging sequence. This preserves the old session
   in storage while giving the next task a small context.
2. **Configuration/code:** lower the compression trigger or add a channel-specific
   token ceiling. A practical starting experiment is compression near 80,000 to
   100,000 tokens, followed by an accuracy check. A better implementation
   summarizes completed tool episodes and keeps the latest user goal, confirmed
   facts, unresolved blockers, and safety state.

### Problem 3: `SOUL.md` repeats detailed operating policy on every request

Impact: first-request latency, repeated input-token cost, and less attention for
the user's actual message.

Solutions:

1. **Immediate:** reduce `SOUL.md` to roughly 800–1,500 characters containing
   only identity, hard safety gates, evidence honesty, authorization, STOP
   behavior, and concise response style.
2. **Progressive disclosure:** move the detailed risk taxonomy, inspection record
   schema, privacy explanation, fallback procedure, stakeholder descriptions,
   and competition narrative into one focused `shian-floor-risk-inspection`
   Skill/reference. Load it only for inspection or robot-action requests.

The compact SOUL must still retain these non-negotiable rules:

- stop immediately on STOP or human entry;
- never move when children are present or presence is unconfirmed;
- require current authorization for physical action;
- use only approved Skills and deterministic control interfaces;
- report only observed or verified results;
- distinguish fact, inference, action result, and unknown state.

### Problem 4: Memory is always injected and includes stale provider information

Impact: extra tokens and potentially wrong answers. The live prompt still included
the old statement that M-Claw used Kimi Coding Plan after the global configuration
had switched to OpenRouter.

Solutions:

1. **Immediate:** replace stale provider facts and reduce memory/user-profile
   limits to the smallest useful summaries. Keep stable robot facts, not temporary
   provider state, one-off errors, or old task progress.
2. **Permanent:** add an `inject_memory_prompt: false` mode that keeps
   `memory_read` available. The model can then retrieve memory only for requests
   that need historical context.

### Problem 5: Too many toolsets are exposed to simple chat requests

Impact: additional tool descriptions and schemas are sent for a message such as
`hi`, even though web, vision, and robot operations are unnecessary.

Solutions:

1. **Immediate:** remove `web` from the always-enabled Weixin toolsets if normal
   robot chat does not need it. Keep `weixin`; keep `vision` only if image messages
   must work without a restart. Measure the prompt-token change after each removal.
2. **Permanent:** add an intent router with a minimal text path and a full robot
   path. Start with chat/channel tools, then enable vision, web, or robot Skills
   only when the message or attachment requires them.

Do not remove deterministic robot safety tools merely to reduce tokens. Tool
minimization must preserve the controls needed for the active operation.

### Problem 6: Kimi K3 reasoning/provider latency is high for trivial messages

Impact: a fresh two-message request still spent about 23.7 seconds between API
request readiness and provider completion.

Solutions:

1. **Immediate experiment:** set OpenRouter reasoning to disabled for simple-chat
   benchmarking. The installed OpenRouter profile supports
   `reasoning.enabled: false`. Compare five identical fresh-session requests before
   keeping the change.
2. **Routing:** use a fast non-reasoning model for greetings and basic status
   requests, while retaining Kimi K3 for planning, ambiguous instructions, and
   robot decisions. Correctness-sensitive physical actions must still pass through
   deterministic validators regardless of model choice.

### Problem 7: Retries can turn a slow response into a multi-minute wait

Impact: earlier logs contain repeated network timeouts with exponential backoff,
including five attempts over several minutes. A user sees typing or silence while
the runtime repeatedly retries.

Solutions:

1. **Immediate:** distinguish authentication/quota failures from transient network
   failures. Quota 403 responses must fail immediately and direct the session to a
   configured healthy provider; they must never retry.
2. **Permanent:** define a channel latency budget. For example, send a short status
   after 8–10 seconds and stop or fail over after a bounded number of attempts.
   Preserve idempotency so a retried robot command cannot execute twice.

### Problem 8: Prompt caching is enabled but not enough by itself

Impact: the first request after restart or prompt change can remain slow. Provider
caching may not help when `SOUL.md`, memory, tool availability, or dynamic context
changes frequently.

Solutions:

1. Keep the stable system prefix small and stable; put changing session facts at
   the end.
2. Record cache-read tokens from provider usage and compare first versus repeated
   requests. Do not claim caching improved latency until the logs show cache hits.

## Two recommended implementation paths

### Path A: Configuration-only fast recovery

Use this first because it is reversible and does not require changing M-Claw
source code.

1. Send `/new` in Weixin after the OpenRouter switch.
2. Verify the new turn logs `provider=openrouter` and a small history count.
3. Replace the 4,334-character SOUL with an 800–1,500-character core version.
4. Move detailed inspection policy into a task-specific Skill/reference.
5. Remove the always-enabled `web` toolset if it is not needed.
6. Prune stale memory and lower its character limits.
7. Benchmark reasoning disabled versus the current default on five fresh requests.

Expected result: the largest correctness bug disappears immediately, and fresh
simple messages should become materially faster. Exact latency must be measured;
it is not guaranteed by prompt size alone.

### Path B: Proper fast-path architecture

Implement this after Path A measurements identify the remaining bottleneck.

1. Add a lightweight intent classifier before the main model call.
2. Route greetings/status to a minimal prompt, minimal tools, no recalled memory,
   and a fast non-reasoning model.
3. Route robot/inspection tasks to the compact SOUL plus the relevant Skill,
   current safety state, and only the necessary tools.
4. Retrieve memory on demand instead of injecting all memory.
5. Automatically invalidate or migrate channel session provider snapshots when
   global provider configuration changes.
6. Summarize completed tool episodes at a practical token ceiling.

This path gives the best long-term latency while retaining accuracy, but it
requires source changes and regression tests for session routing, tool exposure,
memory behavior, and physical-action safety.

## Acceptance measurements

Record at least five runs per scenario and compare median and worst-case time:

| Scenario | What to record |
|---|---|
| Fresh Weixin `hi` | inbound, turn start, API-ready, first text sent, provider/model, input tokens |
| Second `hi` in same session | same fields plus cache-read tokens |
| Robot status question | tool count, tool duration, total response time, correctness |
| Image message | image download, vision call, final response time |
| Provider switch | global config, new-session provider, saved-session provider |

Suggested initial targets, to be validated against real OpenRouter behavior:

- simple fresh text: median under 5 seconds;
- simple repeated text: median under 3 seconds when caching applies;
- robot status without motion: median under 10 seconds;
- no request uses an unexpected provider;
- no physical action bypasses authorization, safety checks, or deterministic
  validation.

## Recommended order

1. Create a new Weixin session and confirm OpenRouter is actually active.
2. Benchmark the clean session before changing more variables.
3. Shorten `SOUL.md` and move details into a Skill/reference.
4. Reduce stale memory and unused toolsets.
5. Test reasoning/model routing.
6. Only then consider M-Claw source changes for true lazy context.

This order fixes correctness first, produces a clean latency baseline, and avoids
attributing improvements to the wrong change.
