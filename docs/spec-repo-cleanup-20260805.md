# Repo Cleanup Specification — 2026-08-05

## Executive Summary
Apply three minimal structural cleanups to `MRobots-OS-AIY-hackthon` so the repository contains only tracked, relevant source/docs, and runtime artifacts are removed from the working tree.

## Decisions from Interview
| Question | Decision |
|----------|----------|
| Scope | Execute all three proposed changes. |
| Active work | No uncommitted teammate work in target directories; safe to move. |
| Move strategy | Use `git mv` to preserve history, and auto-fix obvious relative paths inside moved scripts/configs. |

## Detailed Steps

### 1. Delete temporary and ignored-on-disk directories
- Delete `_trash/` (trash scripts).
- Delete all `.DS_Store` files.
- Physically remove directories/files that are in `.gitignore` but still on disk:
  - `.venv/`, `.codegraph/`, `.octie/`
  - `0802-meeting-ppt/`, `guizang-ppt-skill/`, `ppt/`
  - `papers/`
  - `softbus-source/`
  - `astra-debug/`
  - `car_output/`, `car_output.zip`
  - `perception/`, `perception.zip`
  - `practice/`, `practice.zip`
  - `yolo训练集1.0/`, `yolo训练集1.0.zip`
  - `grasping/logs/`
  - `teleop/captures/` (if present)
  - `gemini335-web/depth-filter/run*/`, `live*/`, `snapshots/`
  - `yolo-pipeline/__pycache__/`
  - `teleop/__pycache__/`
  - other `__pycache__/` directories

### 2. Rename official source tree
- `git mv "AIY黑客松比赛资料 (深开鸿赛道)/source code" vendor/kaihong-src/`

### 3. Move team modules into `src/`
- Create `src/`.
- `git mv grasping/ src/grasping/`
- `git mv teleop/ src/teleop/`
- `git mv yolo-pipeline/ src/yolo-pipeline/`
- `git mv gemini335-web/ src/gemini335-web/`

### 4. Auto-fix obvious relative paths
After moving, scan and update internal references that point to old top-level locations, such as:
- Shell scripts using relative paths to neighboring directories.
- Python `sys.path` or config references.
- README links.

## Risk Mitigation
- Working tree was confirmed clean before starting.
- Use `git mv` so Git tracks renames and history is preserved.
- Run `git status` after each phase.
- Keep a list of deleted paths in this spec for recovery reference.

## Verification
- `git status --short` shows only intended renames.
- No remaining `.DS_Store` files.
- `_trash/` removed.
- Target modules live under `src/`.
- Official source lives under `vendor/kaihong-src/`.

## Notes
- Valuable ignored directories (e.g. `papers/`, `_audit-cache/`) are removed from the repo working tree per the "delete ignored directories" instruction. Recover from local backups if needed.
