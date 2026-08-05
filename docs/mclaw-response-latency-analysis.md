# M-Claw Response Latency Analysis

## Goal

Get the fastest possible response while keeping the correct provider, accurate
context, robot authorization, and deterministic safety checks.

Evidence source: live M-Claw and Weixin logs inspected on 2026-08-05. No secrets
are included.

## Main conclusion

Shortening `SOUL.md` will help, but the first problems to fix are the stale
Weixin provider and oversized Weixin history.

## Measured timing

| Test | Evidence | Result |
|---|---|---:|
| Fresh OpenRouter M-Claw request | API ready `16:14:21.757`; provider returned `16:14:45.434` | **23.677 s** inside provider call |
| Weixin routing | Inbound `16:15:46.670`; agent start `16:15:47.335` | **0.665 s** |
| Later Weixin turn | Inbound `16:15:46.670`; text sent `16:15:53.994` | **7.324 s**, but it used old Kimi and ended in 403 |

The 23.7-second request contained only the system prompt and `hi`, but M-Claw
estimated 12,461 request tokens. No retry or API error was logged for that call.
There is no matching Weixin inbound line, so this particular test appears to be
a direct or separate M-Claw session.

## Problems and solutions

| Priority | Problem | Log/config evidence | Why it matters | Solution 1 | Solution 2 |
|---:|---|---|---|---|---|
| **P0** | Existing Weixin session keeps the old provider | Global config is `openrouter` + `moonshotai/kimi-k3`, but the 16:15 Weixin turn restored `provider=kimi-coding`, `model=k3` | The channel calls the wrong provider and receives the exhausted Kimi-plan 403 | Send `/new` in Weixin after every provider switch; verify the next log says `provider=openrouter` | Change session restoration to migrate or invalidate saved provider snapshots when global provider configuration changes |
| **P0** | Weixin history is far too large | 52 historical messages; 54 messages at API call; 43,790 message characters; estimated **112,193 tokens** | A short message resends old tool calls, Skill bodies, image/voice metadata, failures, and unrelated work | Use `/new` after a task change, provider switch, or long debugging sequence | Add a channel token ceiling and summarize completed tool episodes while preserving the current goal, facts, blockers, and safety state |
| **P1** | Compression starts too late | Threshold is 50% of a 1,048,576-token window = **524,288 tokens**; 112,193 tokens did not trigger compression | Context can become expensive and slow long before it reaches 524k | Test a lower threshold around 80k–100k tokens | Replace percentage-only policy with a practical channel-specific token ceiling |
| **P1** | Fresh system prompt is oversized | Fresh system message: 13,591 characters; estimated request: 12,461 tokens for `hi` | High first-response latency and repeated token cost | Compact always-loaded instructions | Add a true fast path with a minimal prompt for greetings and status questions |
| **P1** | `SOUL.md` is too detailed for always-loaded identity | 264 lines, 4,334 characters, 11,417 UTF-8 bytes; about 32% of the fresh system-message characters | Detailed product policy is resent on every request | Reduce SOUL to about 800–1,500 characters containing identity and hard rules only | Move risk taxonomy, report schema, privacy detail, stakeholder detail, and fallback procedures into a task-specific Skill/reference |
| **P1** | Memory is always injected and contains stale runtime facts | Memory limits: 2,200 + 1,375 characters; prompt still stated that M-Claw used Kimi Coding after OpenRouter became global | Extra tokens and potentially incorrect answers | Remove temporary provider facts, prune stale entries, and reduce limits | Add `inject_memory_prompt: false` while keeping `memory_read` available for on-demand retrieval |
| **P2** | Too many toolsets are available for simple chat | Always configured: `mclaw-required`, `web`, `vision`, `weixin` | Tool descriptions and schemas are sent even when the user only says `hi` | Remove always-on `web` if normal robot chat does not need it; measure token change | Add intent-based tool routing: minimal chat tools first, then vision/web/robot tools only when required |
| **P2** | Kimi K3 reasoning/provider latency is high for trivial input | Fresh two-message OpenRouter request spent about 23.7 seconds in the provider call | Prompt reduction alone may not reach fast-chat targets | Benchmark `reasoning.enabled: false` on five fresh simple requests | Route greetings/basic status to a faster non-reasoning model; keep K3 for planning and ambiguous robot tasks |
| **P2** | Network retries can create multi-minute waits | Earlier logs show repeated timeouts and exponential retry delays; quota 403 errors also occurred | User sees typing or silence for a long time | Fail immediately on authentication/quota errors and use a healthy fallback | Add a channel latency budget, bounded retries, and idempotency so robot commands cannot run twice |
| **P3** | Prompt caching cannot fix the first call by itself | Prompt cache is enabled, but the first request after restart/prompt change was still slow | Cache benefit may disappear when prompt, memory, or tools change | Keep a small stable system prefix and dynamic context at the end | Record cache-read tokens and compare first versus repeated requests before claiming improvement |

## Can context be loaded later?

| Context | Current behavior | Can it load later? | Recommended change |
|---|---|---|---|
| Full Skill instructions | Only Skill name/description is initially included; full `SKILL.md` loads through `skill_view` | **Yes, already lazy** | Move detailed inspection policy from SOUL into a focused Skill/reference |
| Skill index and Skill workflow rules | Included whenever Skill tools are enabled | Partly | Disable unrelated Skills or add intent-filtered Skill indexing |
| Memory and user profile | Automatically included when enabled | **Not with config alone** | Add separate controls for memory tools and automatic memory injection |
| Tool schemas | Sent for enabled toolsets | Not automatically | Use smaller startup toolsets or implement intent-based tool activation |
| Core system/language/safety rules | Always included | Should remain mostly always-loaded | Compact wording, but keep authorization, STOP, evidence honesty, and deterministic safety |
| Detailed product and inspection policy | Currently in SOUL and always included | **Yes** | Move to the relevant inspection Skill/reference |

## Minimum safe SOUL content

The compact SOUL must keep these rules:

1. Stop immediately on STOP or human entry.
2. Never move when children are present or their absence is unconfirmed.
3. Require current authorization for physical action.
4. Use only approved Skills and deterministic control interfaces.
5. Report only observed or verified results.
6. Separate facts, inference, action results, and unknown state.

## Two solution paths

| Path | Steps | Advantage | Limitation |
|---|---|---|---|
| **A. Configuration-first recovery** | `/new` in Weixin; verify OpenRouter; shorten SOUL; move details to a Skill; prune stale memory; remove unused `web`; benchmark reasoning disabled | Fast, reversible, no M-Claw source changes | Does not provide fully dynamic tool or memory loading |
| **B. Proper fast-path architecture** | Add intent router; minimal prompt/model/tools for chat; task-specific Skill/tools/memory for robot work; migrate stale provider snapshots; summarize old tool episodes | Best long-term speed and correctness | Requires source changes and regression tests |

## Recommended order

| Order | Action | Verification |
|---:|---|---|
| 1 | Send `/new` in Weixin | New log shows `provider=openrouter`, `model=moonshotai/kimi-k3`, and small history |
| 2 | Benchmark five clean `hi` messages | Record inbound, API-ready, provider-return, text-sent, input tokens, and cache tokens |
| 3 | Replace SOUL with a compact core | Confirm safety rules remain; compare prompt tokens and latency |
| 4 | Move details into a robot-inspection Skill/reference | Confirm the full policy loads only for relevant tasks |
| 5 | Prune stale memory and unused toolsets | Confirm correct provider facts and required robot capabilities |
| 6 | Benchmark reasoning/model routing | Compare median and worst-case latency plus answer quality |
| 7 | Implement lazy memory/tools only if needed | Add tests for provider routing, tools, memory, and physical-action safety |

## Initial performance targets

| Scenario | Target |
|---|---:|
| Fresh simple Weixin text | Median under 5 s |
| Repeated simple text with cache hit | Median under 3 s |
| Robot status without motion | Median under 10 s |
| Provider correctness | 100% of requests use the expected provider |
| Physical safety | No action bypasses authorization or deterministic validation |

These are initial targets, not promises. Real OpenRouter measurements must decide
whether prompt reduction is enough or model routing is also required.
