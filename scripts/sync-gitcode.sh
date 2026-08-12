#!/usr/bin/env bash
# sync-gitcode.sh — 把 main 的干净内容以"嫁接提交"同步到 GitCode 社区仓。
#
# 背景：GitCode 项目钩子限制单文件 ≤10MiB，开发历史中遗留的超限文件导致无法
# 直接推完整历史。本脚本以 gitcode/main 最新提交为父、当前 main 的文件树为内容，
# 生成单个同步提交推送（fast-forward），GitHub 主仓历史不受任何影响。
#
# 与主仓内容的差异（社区仓过滤清单）：
#   1. README.md 替换为 docs/社区仓README.md（公开版，无内部协作/历史重写说明）
#   2. 剔除内部协作文档（只对团队有意义，且含历史重写等内部操作说明）
#
# 用法：bash scripts/sync-gitcode.sh "一句话说明本次同步内容"
set -euo pipefail
cd "$(dirname "$0")/.."

MSG="${1:-sync: 同步主仓最新内容}"

# 社区仓不携带的内部文件（除 .gitignore 豁免内容外）
EXCLUDE_PATHS=(
  "docs/双仓库同步指引.md"
  "docs/社区仓README.md"
  "docs/分支同步与敏感数据清理指南.md"
  "prep/git协作约定.md"
)

git fetch gitcode --quiet
GC_HEAD=$(git rev-parse gitcode/main)

TMP_INDEX=$(mktemp)
trap 'rm -f "$TMP_INDEX"' EXIT

# 用临时 index 构造社区仓树：先取 main 全量，再做替换与剔除
export GIT_INDEX_FILE="$TMP_INDEX"
git read-tree main
git rm -q --cached "${EXCLUDE_PATHS[@]}"

# 换 README：把社区版 README 作为 blob 写进 README.md 路径
README_BLOB=$(git hash-object -w "docs/社区仓README.md")
git update-index --cacheinfo 100644,"$README_BLOB",README.md

TREE=$(git write-tree)
unset GIT_INDEX_FILE

NEW=$(git commit-tree "$TREE" -p "$GC_HEAD" -m "$MSG")
git branch -f gitcode-release "$NEW"
git push gitcode gitcode-release:main
echo " synced -> gitcode main: $NEW"
