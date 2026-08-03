# M-Claw 安装 Artifacts 记录

> 安装时间：2026-08-03（本地时间约 17:56）
> 安装机器：Windows（Git Bash 环境），用户 LENOVO
> 安装方式：源码安装（editable / `pip install -e .` 等效，用 uv 执行）
> 来源仓库：`https://atomgit.com/m-robots/mclaw.git`（镜像：`https://gitcode.com/m-robots/mclaw`）
> 安装结果：`mclaw doctor` 13/13 检查通过，状态"可运行"

## 1. Artifacts 位置清单

| # | 位置 | 是什么 | 大小/说明 |
|---|------|--------|-----------|
| 1 | `J:\Hackthon-Art\mclaw\` | 克隆的源码仓库（atomgit） | 577 个文件；editable 安装的代码本体，改这里的代码直接生效 |
| 2 | `J:\Hackthon-Art\mclaw\.venv\` | 专用 Python 3.12 虚拟环境（uv 创建） | 约 1.1 GB；含全部依赖（openai/anthropic/PySide6/playwright/mcp 等） |
| 3 | `J:\Hackthon-Art\mclaw\.venv\Scripts\mclaw.exe` | **CLI 入口**，安装出的可执行文件 | 直接运行即可启动 M-Claw |
| 4 | `J:\Hackthon-Art\mclaw\m_claw.egg-info\` | editable 安装的包元数据 | 由 setuptools 生成，删了会导致安装失效 |
| 5 | `J:\Hackthon-Art\mclaw\.venv\Lib\site-packages\__editable__.m_claw-1.0.0.pth` 及同目录 `__editable___m_claw_1_0_0_finder.py`、`m_claw-1.0.0.dist-info\` | editable 安装的钩子文件 | 把 venv 的 import 指回源码目录 |
| 6 | `C:\Users\LENOVO\.mclaw\` | **M-Claw 运行时主目录**（首次运行 CLI 时自动创建） | 内含 `SOUL.md`、`logs\`、`memories\`、`sessions\`；后续还会产生 `state.db`、`skills\`、`delegations\`、`process_logs\` 等 |
| 7 | `C:\Users\LENOVO\AppData\Local\uv\cache\` | uv 下载的 wheel 缓存 | 全局共享缓存，非本次独占；删了只是下次装包变慢 |
| 8 | `C:\Users\LENOVO\AppData\Local\ms-playwright\` | Playwright 浏览器（chromium 等） | ⚠️ **是机器上原有的**，不是这次装的；M-Claw 的 browser 工具会直接复用 |

## 2. 没有产生的 artifacts

- **未配置模型/凭据**：还没跑 `mclaw setup`，所以 `.mclaw\` 下还没有模型配置和 API Key 文件。
- **未装新 Playwright 浏览器**：复用了系统已有浏览器。如果 browser 工具报错，手动执行：
  `J:\Hackthon-Art\mclaw\.venv\Scripts\python.exe -m playwright install chromium`
- **未配置微信/钉钉通道**（doctor 显示 not configured，属可选项）。

## 3. 日常使用

```bash
# 启动（Git Bash）
/j/Hackthon-Art/mclaw/.venv/Scripts/mclaw.exe

# 首次配置模型（交互式，支持 Anthropic Messages / OpenAI-compatible 自定义 endpoint）
/j/Hackthon-Art/mclaw/.venv/Scripts/mclaw.exe setup

# 环境自检
/j/Hackthon-Art/mclaw/.venv/Scripts/mclaw.exe doctor
```

也可以在 PowerShell 里先激活环境再用：

```powershell
J:\Hackthon-Art\mclaw\.venv\Scripts\Activate.ps1
mclaw
```

## 4. 相关环境变量

- `MCLAW_HOME`：设置后可把运行时主目录从 `C:\Users\LENOVO\.mclaw` 改到别的位置（见源码 `mclaw/constants.py:15`）。

## 5. 如何完全卸载

按顺序删除即可，无注册表/系统级残留：

1. `J:\Hackthon-Art\mclaw\`（源码 + venv + egg-info，全在这里）
2. `C:\Users\LENOVO\.mclaw\`（运行时数据：会话/记忆/日志）
3. 可选：`C:\Users\LENOVO\AppData\Local\uv\cache\`（共享缓存，不影响其他工具可不清）
4. 不要动 `ms-playwright`（其他工具在用，非本次安装产物）
