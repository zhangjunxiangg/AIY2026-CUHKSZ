# Guizang PPT Skill · Swiss Style — Pitfalls & Lessons Learned

## Executive Summary

Using `op7418/guizang-ppt-skill` to generate a Swiss-style HTML PPT works well **only if you treat the actual template CSS as the single source of truth**, not the `references/layouts-swiss.md` documentation. The documentation describes classes that largely **do not exist** in `assets/template-swiss.html`, and the animation recipes are tightly coupled to specific HTML structures that must be matched exactly. This guide documents the mismatch and how to avoid the resulting invisible-content traps.

---

## Architecture Overview

```
SKILL.md (workflow instructions)
  ↓
references/layouts-swiss.md (documentation — NOT source of truth for class names)
  ↓
assets/template-swiss.html (actual template — source of truth for class names)
  ├── <style> block: defines what CSS classes actually exist
  ├── <script> block: defines animation recipes with expected HTML structures
  └── <!-- SLIDES_HERE -->: insertion point for <section class="slide">
  ↓
scripts/validate-swiss-deck.mjs (static + Playwright rendered validation)
```

**Critical insight**: The skill has two disconnected layers:

1. **Documentation layer** (`references/layouts-swiss.md`) — describes idealized layouts with classes like `.cell-6`, `.matrix-fill`, `.four-cards`, `.system-diagram`
2. **Implementation layer** (`assets/template-swiss.html`) — has its own set of classes like `.grid-6`, `.sub-card`, `.h-bar-chart`, `.timeline-h`

These two layers **do not match**. The documentation was written for a different (possibly newer or older) version of the template.

---

## Pitfall 1: Class Name Mismatch (Documentation vs Template)

### The Problem

`references/layouts-swiss.md` documents classes that **do not exist** in `assets/template-swiss.html`:

| Documented in layouts-swiss.md | Actually exists in template |
|---|---|
| `.cell-6`, `.cell`, `.cell-num` | `.grid-6` + `.sub-card` |
| `.matrix-fill`, `.matrix-cell` | `.grid-6` + `.card-fill` |
| `.four-cards`, `.fc-col` | `.grid-4` + `.card-fill` |
| `.system-diagram`, `.sys-text` | `.grid-3` + `.card-fill` (no SVG system diagram class) |
| `.three-forces`, `.force-card` | `.grid-3` + `.card-fill` |
| `.brief-grid`, `.brief-card` | `.grid-6` + `.sub-card` |
| `.manifesto-top`, `.ink-banner-full` | `.h-xl-zh` + `.ink-block` |
| `.h-statement`, `.stmt-anchor` | `.h-xl-zh` + inline styles |
| `.tl-h-node`, `.tl-h-axis`, `.num`, `.lbl` | `.timeline-h` + `.th-node` + `.dot` + `.label` + `.yr` + `.name` + `.desc` |
| `.bar-lbl`, `.bar-fill`, `.bar-num` | `.row-lbl`, `.row-track`, `.row-fill`, `.row-val` |
| `.num-mega`, `.hero-stat-bottom`, `.lbl` | `.kpi-mid` or `.kpi-hero` |
| `.grid-2-9`, `.sub-card-stack` | `.grid-3` + `.sub-card` |
| `.loop-diagram`, `.loop-steps`, `.loop-svg` | **Not implemented** |

### The Impact

Using documented classes results in **completely unstyled content** — text stacks vertically without grid, cards lose borders/backgrounds, timelines don't render as timelines.

### The Fix

**Always grep the template's `<style>` block before using any class:**

```bash
grep -o '\.[a-z][a-z0-9-]*\s*{' assets/template-swiss.html | sort -u
```

Or read the template directly to see what exists. The template's actual classes are the only safe ones to use.

---

## Pitfall 2: Animation Recipe / Markup Structure Mismatch

### The Problem

Even after using correct template classes, the animation recipes in the template's `<script>` block expect **specific HTML structures**. If the structure doesn't match, the recipe can't find elements and the content stays at `opacity:0` (invisible).

Examples:

- `rSystemDiagram` expects SVG `<circle>` and `<text>` elements — if you use `.grid-3` + cards, it finds nothing and exits early
- `rFourCards` expects `[data-anim="line"] > div:first-child` for a top rule — if your hairline is structured differently, it fails
- `rMatrixFill` expects `foot.querySelector('div:nth-child(1) > div:nth-child(2)')` for a big number — if your KPI is structured differently, it fails
- `rThreeForces` expects `grid.querySelector(':scope > div:nth-child(2) > .card-fill')` — if your cards are not nested exactly this way, they don't animate

### The Impact

Content renders in browser as **completely blank** because:
1. Template CSS sets `[data-anim] { opacity: 0 }` when `body.motion-ready` is active
2. The recipe's `animate()` call never fires because selectors don't match
3. Elements never get `opacity: 1`

### The Fix

Two options:

**Option A (recommended for speed)**: Match the recipe's expected structure exactly. Read the recipe implementation in the template's `<script>` block to understand what selectors it uses.

**Option B (pragmatic)**: Remove `data-animate` from problematic slides. Content will be visible immediately without animation, which is better than invisible content.

---

## Pitfall 3: S14 Loop Form Not Implemented

### The Problem

`references/layouts-swiss.md` documents S14 Loop Form with classes `.loop-diagram`, `.loop-steps`, `.loop-svg`, `.loop-step`, `.loop-center`. **None of these exist in the template CSS.**

### The Impact

The page renders as unstyled stacked text, and the validator reports overflow because the content has no height constraints.

### The Fix

Don't use S14. Use S04 (Six Cells) or S17 (System Diagram) instead for similar content.

---

## Pitfall 4: SWISS-COVER-ASCII vs S01

### The Problem

The validator's `isStatement` list includes `SWISS-COVER-ASCII` and `SWISS-CLOSING-ASCII`, but **not** `S01`. If you use `data-layout="S01"` on a cover page with centered/hero styling, the validator flags it as "top heading appears vertically/centrally aligned."

### The Fix

Use `data-layout="SWISS-COVER-ASCII"` for the cover page and `data-layout="S10"` or `SWISS-CLOSING-ASCII` for the closing page.

---

## Pitfall 5: Playwright Validator Setup

### The Problem

The validator script tries to resolve `playwright` from two locations:
1. The skill folder (`import.meta.url`)
2. The current working directory (`process.cwd()` + `package.json`)

If playwright is not installed in either location, it skips rendered measurements with a warning.

### The Fix

Install playwright in the skill folder and download matching browsers:

```bash
cd ~/.agents/skills/guizang-ppt-skill
npm init -y
npm install playwright --save
npx playwright install chromium
```

**Note**: The browser version must match the playwright version. If you see "Executable doesn't exist at ...chromium_headless_shell-1234...", run `npx playwright install` again.

---

## Pitfall 6: Animation Timing for Screenshots

### The Problem

When using Playwright or Chrome DevTools to screenshot slides, content appears invisible if the screenshot is taken before the entrance animation completes.

### The Fix

Wait **at least 2.5 seconds** after each slide navigation before taking the screenshot:

```javascript
await page.keyboard.press('ArrowRight');
await page.waitForTimeout(2500);
await page.screenshot({ path: 'slide.png' });
```

---

## Pitfall 7: Motion.min.js Bundling for Single-File Distribution

### The Problem

The template loads Motion One via dynamic import:

```javascript
motion = await import('./assets/motion.min.js');
```

This requires `motion.min.js` to be in the same directory. To create a single-file HTML for distribution, you need to inline it.

### The Fix

Use a Blob URL to inline the module:

```javascript
const motionCode = `[escaped motion.min.js content]`;
const blob = new Blob([motionCode], { type: 'text/javascript' });
const url = URL.createObjectURL(blob);
motion = await import(url);
```

**Escaping rules**: Backslashes first, then backticks, then template literal syntax:
- `\` → `\\`
- `` ` `` → `` \` ``
- `${` → `\${`

---

## What Worked Well

1. **The validator is genuinely useful** — it caught layout registration, alignment, and overflow issues that would have been embarrassing in a live demo.

2. **Swiss style looks professional** — when rendered correctly, the IKB blue + grid + thin typography creates a polished technical presentation aesthetic.

3. **Single-file HTML is a great deliverable** — no build step, no server, works offline, easy to share.

4. **Playwright screenshots are essential** — code validation alone can't catch visual issues like invisible content, broken grids, or missing bars.

---

## Recommended Workflow

1. **Read the template's `<style>` block first** — know what classes actually exist
2. **Copy the template's example slides as a starting point** — they use real classes and correct structures
3. **Grep the recipe implementation** before assigning `data-animate` — make sure your markup matches what the recipe expects
4. **Run the validator early and often** — don't wait until all 18 pages are written
5. **Take screenshots with 2.5s+ animation wait** — verify visuals, not just code
6. **For distribution, bundle motion.min.js via Blob URL** — creates a truly single-file HTML

---

## Related Files

- `J:/Hackthon-Art/MRobots-OS-AIY-hackthon/guizang-ppt-skill/` — cloned repo
- `J:/Hackthon-Art/MRobots-OS-AIY-hackthon/0802-meeting-ppt/` — generated PPT
- `J:/Hackthon-Art/MRobots-OS-AIY-hackthon/0802-meeting-ppt/dist-single.html` — single-file bundle

---
*Generated: 2026-08-02*
*Source: Conversation — guizang-ppt-skill Swiss style PPT generation for AIY hackathon meeting materials*
