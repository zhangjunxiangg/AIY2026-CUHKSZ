#!/usr/bin/env bash
# 一键推送 prep/demo代码 到比赛板并校验
# 用法：bash prep/deploy.sh [板子 HDC target]

set -euo pipefail

TARGET=${1:-}
HDC="hdc"
if [ -n "$TARGET" ]; then
    HDC="hdc -t $TARGET"
fi

ROBOT_DIR="data/local/robot"

echo "==> 0. 准备扁平临时目录（避开 hdc file send 保留本地目录结构的问题）"
TMP_DIR=$(mktemp -d)
cp prep/demo代码/* "$TMP_DIR/"

echo "==> 1. 确保板端目录存在"
$HDC shell "mkdir -p /$ROBOT_DIR"

echo "==> 2. 推送 Demo 节点与数据流文件"
# 注意：此版本 hdc file send 目标路径不能带前导 '/'，否则会被解析到本地
for f in "$TMP_DIR"/*; do
    $HDC file send "$f" "$ROBOT_DIR/"
done

echo "==> 3. 校验 YAML 可解析"
$HDC shell "cat > data/local/tmp/check_yaml.sh << 'EOF'
#!/system/bin/sh
export PATH=/data/local/release/usr/bin:/data/local/release/bin:/system/bin
export LD_LIBRARY_PATH=/data/local/release/usr/lib:/data/local/release/lib
export LD_PRELOAD=/data/local/release/usr/lib/libpython3.12.so.1.0
ln -sf /data/local/release/usr/bin/python3.12 /data/local/release/usr/bin/python3
. /data/local/release/usr/setup.sh
cd /data/local/robot
python3 -c \"import yaml; yaml.safe_load(open('dataflow_hello.yml')); yaml.safe_load(open('dataflow_sensor.yml')); print('YAML OK')\"
EOF
sh data/local/tmp/check_yaml.sh"

echo "==> 4. 列出板端文件"
$HDC shell "ls -l /$ROBOT_DIR"

echo "==> 部署完成"
rm -rf "$TMP_DIR"
