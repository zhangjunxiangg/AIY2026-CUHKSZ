# Git 协作约定

> 用途：5 人团队在 36 小时黑客松期间的代码协作规则  
> 仓库：https://github.com/zhangjunxiangg/AIY2026-CUHKSZ.git（private）

## 分支策略

- `main`：稳定分支，仅合并已验证的功能，**比赛期间由队长控制合并**
- `dev`：集成分支，各人功能分支合并到这里做联调
- `feature/<姓名缩写>-<功能>`：个人开发分支，如 `feature/lyl-perception`

## 提交规范

```
<type>(<scope>): <简短描述>

Types:
- feat: 新功能
- fix: 修复
- docs: 文档
- chore: 配置/脚本/工具
- refactor: 重构
```

## 协作流程

1. 各人始终在 `feature/*` 分支开发
2. 功能自测通过后，向 `dev` 发起 Pull Request
3. 队长或模块负责人 review 后合并到 `dev`
4. 关键里程碑（如 Demo 跑通）由队长从 `dev` 合并到 `main`
5. **至少每小时提交一次**，代码是换板恢复的唯一权威备份

## 目录责任

| 目录/模块 | 负责人 | 说明 |
|---|---|---|
| `src/control/` | 张峻翔 | 底盘/机械臂控制 |
| `src/perception/` | 应露 | 视觉/雷达感知 |
| `src/agent/` | 山茶 | M-Claw 与决策状态机 |
| `src/integration/` | 张宇辰 | 系统集成、接口约定 |
| `deploy/` | 刘昱麟 | 一键部署、换板恢复 |

## 换板恢复

- 所有代码必须 push 到 GitHub
- 换板时使用 `prep/换板恢复SOP.md`（待补充）从空板恢复到跑通
- 目标：15 分钟内完成换板恢复
