#!/usr/bin/env bash
# 同步本地 grasping/ → 板端 /data/local/grasping/（同名目录）
set -euo pipefail
BOARD=${BOARD:-root@172.20.10.5}
SSH_OPT="-P 2223 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
ssh -p 2223 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$BOARD" "mkdir -p /data/local/grasping"
scp $SSH_OPT -r "$(dirname "$0")/." "$BOARD:/data/local/grasping/"
echo "synced -> $BOARD:/data/local/grasping/"
