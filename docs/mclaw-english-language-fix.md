# M-Claw Replies in Chinese — Cause and Fix

**Applies to:** M-Claw v1.0.0 (source install from `m-robots/mclaw`)

## TL;DR

M-Claw has a **hardcoded, unconditional Simplified-Chinese language rule** injected into every system prompt. There is no config option to turn it off in v1.0.0. The fix is a 5-line source edit — and because M-Claw is installed in editable mode, the change takes effect immediately, no reinstall needed.

## Why this happens

Every time M-Claw builds its system prompt, it appends this block (file `mclaw/agent/prompt_builder.py`, around lines 424–430, in the `build_system_prompt()` function):

```python
    # 1b. Language enforcement
    sections.append(
        "语言规定 / Language Rule:\n"
        "你必须全程使用简体中文（Simplified Chinese）回复所有用户可见的内容，"
        "包括：所有文字输出、工具描述、错误信息、状态提示。\n"
        "不要用英文回复，除非用户明确用英文提问。"
    )
```

Translation of the rule:

> **Language Rule: You must use Simplified Chinese for ALL user-visible content, including all text output, tool descriptions, error messages, and status prompts. Do not reply in English unless the user explicitly asks in English.**

Three things make this unavoidable without a code change:

1. **It is unconditional** — appended to every system prompt, for every model, every session.
2. **No config switch exists** — nothing in `config.yaml` controls it.
3. **Editing `SOUL.md` does not help** — the identity file (`~/.mclaw/SOUL.md`, also written in Chinese) is user-editable, but this language rule is injected separately and stays even if you rewrite SOUL.md in English.

The rule does contain an escape hatch ("unless the user explicitly asks in English"), but in practice the whole system prompt is in Chinese and the mandate comes first — so the model keeps drifting back to Chinese even in English conversations.

## The fix (5 minutes)

Edit `mclaw/agent/prompt_builder.py` in your cloned repo. Find the `# 1b. Language enforcement` section (search for `Language enforcement` or `语言规定`) and **replace the whole block** with an English rule:

```python
    # 1b. Language rule
    sections.append(
        "Language Rule:\n"
        "Always respond in the same language the user is using. "
        "Default to English when the user's language is unclear. "
        "This applies to all user-visible content: text output, tool "
        "descriptions, error messages, and status prompts."
    )
```

(Or simply delete the block entirely — then the model just follows your language naturally.)

Then:

1. Save the file. **No reinstall needed** — the source install is editable, so the running CLI picks it up on next launch.
2. Restart `mclaw`.
3. Optional but recommended: rewrite `~/.mclaw/SOUL.md` in English. The default is a Chinese identity paragraph; an English version further reduces Chinese bias. Example:

   ```markdown
   You are the M-Claw Agent, running in a CLI environment. Answer questions,
   modify files, run tools, analyze information, and deliver results based on
   the user's goals. Be clear and direct; when uncertain, state your reasoning
   and gaps; use tools when real action is needed. Format output as plain
   terminal-friendly text.
   ```

## Verify

Start `mclaw` and ask something in English without any language instructions, e.g.:

```
Summarize what tools you have in one sentence.
```

The reply should now come back in English.

## Notes

- **Temporary workaround (no code change):** saying "Always reply in English" in the session works short-term, but the hardcoded rule often wins in longer conversations. The source edit above is the real fix.
- **If you ever reinstall or `git pull`**, check whether this file changed — your edit may need to be re-applied (or may conflict if upstream refactors this section).
- **Worth reporting upstream:** this should be a `config.yaml` option (e.g. `language: en`) rather than a hardcoded rule. If you open an issue at the `m-robots/mclaw` repo, point them to `mclaw/agent/prompt_builder.py`, the `# 1b. Language enforcement` block in `build_system_prompt()`.

---
*Written: 2026-08-03 · Based on M-Claw v1.0.0 source inspection*
