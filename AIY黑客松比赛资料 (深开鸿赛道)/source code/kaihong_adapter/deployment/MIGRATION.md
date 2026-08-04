# Kaihong 4.1 迁移入口

迁移分为小车板和 Gemini 335 辅助板。IP、M-Claw 凭据、SSH 公钥及标定结果不写入
公开 ZIP；部署时按目标板填写。

## 1. 生成轻量迁移包

```powershell
.\build-migration-package.ps1
```

ZIP 包含小车运行文件、统一 M-Claw Skill、学生 README、颜色分类 Demo、辅助相机脚本
和校验脚本。Astra、Gemini Docker 镜像及 M-Claw runtime 作为独立大文件保存。

## 2. 迁移小车板

```powershell
.\migrate-board.ps1 `
  -BoardHdcTarget <小车HDC目标> `
  -AuthorizedKeyFile <authorized_keys公钥文件> `
  -MclawRuntimeArchive <mclaw-host-runtime.tar.gz> `
  -VisionImageArchive <rk3588s-vision镜像.tar> `
  -VisionArchiveIsRootfs

.\validate-board.ps1 -BoardHdcTarget <小车HDC目标>
```

部署过程不会复制现有板的 M-Claw 凭据。需要复用配置时显式传入
`-MclawConfigDirectory <受控配置目录>`。

## 3. 迁移辅助板

如果尚无 Gemini 镜像归档，先从已验证辅助板导出一次：

```powershell
.\export-gemini335-image.ps1 -SourceBoardHdcTarget <旧辅助板HDC目标>
```

再部署到新辅助板：

```powershell
.\migrate-gemini335-board.ps1 `
  -BoardHdcTarget <新辅助板HDC目标> `
  -GeminiImageArchive <rk3588s-gemini335-driver-sdk2.2.8.tar> `
  -CarIp <新小车当前IP>

.\validate-gemini335-board.ps1 -BoardHdcTarget <新辅助板HDC目标>
```

如果新辅助板执行 `docker load` 时报告 `invalid diffID`，改用单层 rootfs 兼容归档：

```powershell
.\export-gemini335-image.ps1 `
  -SourceBoardHdcTarget <旧辅助板HDC目标> `
  -Rootfs

.\migrate-gemini335-board.ps1 `
  -BoardHdcTarget <新辅助板HDC目标> `
  -GeminiImageArchive <rk3588s-gemini335-driver-sdk2.2.8-rootfs.tar> `
  -GeminiArchiveIsRootfs `
  -SkipStart
```

rootfs 模式保留相同镜像标签，并补回容器运行所需的 `PATH` 和 UTF-8 环境变量。
板端脚本仍负责设置入口、ROS 地址和 Gemini 启动命令。

辅助板开机或网络地址改变后，在辅助板终端执行：

```sh
/data/gemini335/configure-car-ros.sh <小车当前IP>
/data/gemini335/start-gemini335.sh
/data/gemini335/status-gemini335.sh
```

确认深度和彩色均为 `PASS` 后，在小车 M-Claw 输入：

```text
连接辅助相机 <辅助板当前IP>
```
