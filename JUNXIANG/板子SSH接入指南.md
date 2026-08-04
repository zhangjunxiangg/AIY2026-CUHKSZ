# 开发板 SSH 接入指南（小车板）

> 来源：队内共享的 `README.md` + `id_ed25519`（微信下发）
> 本文已根据 **2026-08-04 18:1x 实测**修正，与原始 README 有出入的地方在文末「与原 README 的差异」列出。

## 1. 连接信息

| 项目 | 值 | 状态 |
|---|---|---|
| 板子 IP | `172.20.10.5` | 实测；跟 WiFi 走，**换网必变** |
| SSH 端口 | **`2223`** | 实测；22 端口是空的（Connection refused） |
| 用户名 | `root` | 实测 uid=0 |
| 认证方式 | **仅公钥** | 实测；密码认证不可用，手册里的 `123456` 走不通 |
| Host key | ED25519 | 已记入本机 known_hosts |

## 2. 密钥位置

同一把私钥（指纹 `SHA256:YmVs2O84KH8a2aH/xD/VK+n8rNbIILpKlMmN+aRqeNk`，源自 `lenovo@DESKTOP-URBD1J4`）存了两份：

| 路径 | 用途 |
|---|---|
| `~/.ssh/aiy_mrobots_ed25519` | **主副本**，日常连接用这个 |
| `JUNXIANG/secrets/aiy_mrobots_ed25519` | 仓库内备份，**已 gitignore，禁止 `git add -f`** |

两份权限都必须是 `600`，否则 SSH 会直接忽略密钥。

> ⚠️ **给队友：不要照抄原 README 的 `cp id_ed25519 ~/.ssh/`。**
> 大多数人 `~/.ssh/id_ed25519` 已经被自己的 GitHub / 服务器密钥占用，这条命令会**静默覆盖**它。
> 一定要用独立文件名，例如 `~/.ssh/aiy_mrobots_ed25519`，再用 `-i` 指定。

## 3. 连接命令

```bash
ssh -p 2223 -i ~/.ssh/aiy_mrobots_ed25519 -o IdentitiesOnly=yes root@172.20.10.5
```

`IdentitiesOnly=yes` 必加，否则 ssh 会先把你本机其它密钥挨个试一遍，可能触发服务端 `MaxAuthTries` 直接被拒。

非交互执行单条命令（脚本/agent 用法）：

```bash
ssh -p 2223 -i ~/.ssh/aiy_mrobots_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes \
    root@172.20.10.5 'run rostopic list'
```

传文件：

```bash
scp -P 2223 -i ~/.ssh/aiy_mrobots_ed25519 本地文件 root@172.20.10.5:/data/local/robot/
```

## 4. 免输路径（可选）

追加到 `~/.ssh/config`：

```
Host mrobots
    HostName 172.20.10.5
    Port 2223
    User root
    IdentityFile ~/.ssh/aiy_mrobots_ed25519
    IdentitiesOnly yes
```

之后 `ssh mrobots` / `scp -P 2223 ... mrobots:/path` 即可。

> 原 README 建议加 `StrictHostKeyChecking no` + `UserKnownHostsFile /dev/null`。
> 不推荐：那样等于关掉主机身份校验。IP 变了导致的 host key 冲突，用
> `ssh-keygen -R "[172.20.10.5]:2223"` 清掉旧记录就行。

## 5. 板子 IP 变了怎么办

热点 DHCP 会重新分配，重连后 IP 大概率不同。

1. 板上查：`ifconfig wlan0`（需要 hdc 或已有 SSH 会话）
2. 本机扫：iPhone 热点是 `/28`，只有 13 个地址，`nmap -sn 172.20.10.0/28` 几秒扫完
3. 清旧 host key：`ssh-keygen -R "[旧IP]:2223"`

## 6. sshd 不是开机自启 ⚠️

按官方《SSH 配置操作手册》§3，**板子每次重启后 SSH 都会消失**，需要重新执行：

```sh
run mkdir /var/empty      # 每次开机都要重建
run /data/local/release/usr/sbin/sshd
```

**待办：把这两步写进 `init.cfg` 或启动脚本**，和「演示上电自启」一起做掉。

## 7. 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `Connection refused` (2223) | 板子没开机、没连同一 WiFi，或 sshd 没启动（见 §6） |
| `Connection refused` (22) | 正常，服务就不在 22 上，记得加 `-p 2223` |
| `Permission denied (publickey)` | 密钥权限不是 600，或没加 `-i` / `IdentitiesOnly` |
| 密码提示都不出现 | 正常，服务端关闭了密码认证，只能用密钥 |
| `Host key verification failed` | `ssh-keygen -R "[172.20.10.5]:2223"` 后重连 |

## 8. 与原 README 的差异

| 原 README | 实测 / 修正 |
|---|---|
| `cp id_ed25519 ~/.ssh/` | **会覆盖个人密钥**，改用独立文件名 + `-i` |
| 未提 `IdentitiesOnly` | 不加可能因多密钥重试被拒 |
| 建议关闭 host key 校验 | 改为用 `ssh-keygen -R` 清旧记录 |
| 未提 sshd 开机不自启 | 补充 §6，重启后必须手动拉起 |
| 引用 `docs/板端开发参考/板端开发速查与踩坑手册.md` | 本仓库对应文件是 `docs/M-Robots开发踩坑与参考库.md` |

---

*实测时间：2026-08-04 18:1x｜实测环境：Mac `172.20.10.7` ↔ 板子 `172.20.10.5`，同一 iPhone 热点 `/28` 网段*
