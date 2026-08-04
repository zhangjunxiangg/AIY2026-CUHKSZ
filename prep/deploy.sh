#!/usr/bin/env bash
# 一键推送 prep/demo代码 到比赛板并校验
# 用法：bash prep/deploy.sh [板子 HDC target]

set -euo pipefail

TARGET=${1:-}
HDC="hdc"
if [ -n "$TARGET" ]; then
    HDC="hdc -t $TARGET"
fi

ROBOT_DIR="/data/local/robot"

echo "==> 1. 确保板端目录存在"
$HDC shell "mkdir -p $ROBOT_DIR"

echo "==> 2. 推送 Demo 节点与数据流文件"
$HDC file send prep/demo代码/hello_node.py "$ROBOT_DIR/"
$HDC file send prep/demo代码/sensor_node.py "$ROBOT_DIR/"
$HDC file send prep/demo代码/filter_node.py "$ROBOT_DIR/"
$HDC file send prep/demo代码/dataflow_hello.yml "$ROBOT_DIR/"
$HDC file send prep/demo代码/dataflow_sensor.yml "$ROBOT_DIR/"

echo "==> 3. 校验 YAML 可解析"
$HDC shell "cat > /data/local/tmp/check_yaml.sh << 'EOF'
#!/system/bin/sh
export PATH=/data/local/release/usr/bin:/data/local/release/bin:/system/bin
export LD_LIBRARY_PATH=/data/local/release/usr/lib:/data/local/release/lib
. /data/local/release/usr/setup.sh
python3 -c \"import yaml; yaml.safe_load(open('/data/local/robot/dataflow_hello.yml')); yaml.safe_load(open('/data/local/robot/dataflow_sensor.yml')); print('YAML OK')\"
EOF
sh /data/local/tmp/check_yaml.sh"

echo "==> 4. 列出板端文件"
$HDC shell "ls -l $ROBOT_DIR"

echo "==> 部署完成"
