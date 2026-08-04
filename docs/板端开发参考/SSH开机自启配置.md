# SSH 开机自启配置

> 配置时间：2026-08-04  
> 板子：KaihongBoard-3588S-SBC  
> 效果：板子重启后 SSH 自动可用，无需手动启动

---

## 1. 自启服务说明

板端现有两个 SSH 服务：

| 服务 | 端口 | 配置文件 | 自启方式 | 用途 |
|---|---|---|---|---|
| `mclaw_sshd` | 2223 | `/data/robot-host/mclaw-sshd/sshd_config` | `/etc/init/mclaw_sshd.cfg` | M-Claw 官方 SSH（仅密钥） |
| `sshd` | 22 | `/usr/etc/sshd_config` | `/etc/init/sshd.cfg`（本次新增） | 通用 SSH（密码/密钥） |

**两个服务均已在开机自启配置中**，板子重启后自动拉起。

---

## 2. 新增文件

| 文件 | 位置 | 说明 |
|---|---|---|
| 自启脚本 | `/data/robot-host/sshd-foreground.sh` | 端口 22 SSH 前台运行脚本 |
| Init 配置 | `/etc/init/sshd.cfg` | OpenHarmony 开机服务注册 |

**本地备份**：
- `scripts/sshd-foreground.sh`
- `scripts/sshd.cfg`

---

## 3. 验证方式

板子重启后，开发机执行：

```bash
# 端口 2223（M-Claw 官方，密钥认证）
ssh -p 2223 -i ~/.ssh/id_ed25519 root@172.20.10.5

# 端口 22（通用，当前密码 123456 或密钥）
ssh root@172.20.10.5
```

两个端口都应能连接。

---

## 4. 故障排查

| 问题 | 排查 |
|---|---|
| 重启后 2223 不通 | 检查 `/etc/init/mclaw_sshd.cfg` 是否存在 |
| 重启后 22 不通 | 检查 `/etc/init/sshd.cfg` 和 `/data/robot-host/sshd-foreground.sh` |
| 密钥认证失败 | 检查 `/var/empty/mclaw_authorized_keys` 是否包含公钥 |
| 密码认证失败 | 检查 `/etc/passwd` 和 `/etc/shadow` 密码哈希 |

---

## 5. 安全提醒

- 端口 2223 仅密钥认证，更安全，推荐队友使用。
- 端口 22 允许密码认证，密码 `123456` 为弱密码，比赛后建议修改或关闭密码认证。
- 私钥文件不要上传到公共仓库。

---

*配置完成，板子重启后 SSH 自动可用。*
