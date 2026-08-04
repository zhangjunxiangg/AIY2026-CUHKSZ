#!/system/bin/sh
# 开机自启 SSH 服务（端口 22）
# 配合 /etc/init/sshd.cfg 使用
set -eu

SSHD_CONFIG="/usr/etc/sshd_config"
SSHD="/data/local/release/usr/sbin/sshd"

# 确保必要目录存在
mkdir -p /var/empty /var/run /var/log /usr/etc

# 确保 host key 存在
if [ ! -f /usr/etc/ssh_host_rsa_key ]; then
    /bin/run ssh-keygen -A
fi

# 测试配置
/bin/run "$SSHD" -t -f "$SSHD_CONFIG"

# 前台运行，由 init 监督
exec /bin/run "$SSHD" -D -f "$SSHD_CONFIG"
