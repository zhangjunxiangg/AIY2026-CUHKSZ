# M-Robots 社区贡献流程总结

> 扫描日期：2026-08-06（GitCode API 在线读取全文）
> 信息来源（m-robots/M-Robots 仓库 main 分支 + 社区群公告）：
> - [基础研习_无开发板贡献攻略](https://gitcode.com/m-robots/M-Robots/blob/main/贡献攻略/基础研习_无开发板贡献攻略.md)
> - [创新实践_有开发板贡献攻略](https://gitcode.com/m-robots/M-Robots/blob/main/贡献攻略/创新实践_有开发板贡献攻略.md)
> - [贡献指南/基础贡献](https://gitcode.com/m-robots/M-Robots/blob/main/贡献指南/基础贡献.md)（CLA、Issue、PR 流程细则）
> - [贡献指南/进阶贡献](https://gitcode.com/m-robots/M-Robots/blob/main/贡献指南/进阶贡献.md)（SIG、三方件引入、角色晋升）
> - 社区群公告（@yc）："遇到疑问、发现 bug、有新功能都可以提 issue，入口 https://gitcode.com/org/m-robots/repos，有专业答复+积分+礼品；**需要建仓的项目名称提供给社区**"

---

## 1. 社区结构速览

- 运营方：开放原子开源基金会孵化，KaihongOS/OpenHarmony 底座。
- 治理：工作委员会 → TSC（技术）/ PMC（项目）/ 运营 / 战略咨询 / 合作委员会 → **13 个 SIG**。
- 与我们贡献直接相关的 SIG：
  - **SIG9 M-Claw 与多机协同** → `mclaw-*` 四个 issue
  - **SIG11 开发者工具链与工程体系** → `robot-docs-*` 文档 PR、HDC/工具链类
  - **SIG3 确定性软总线** → 软总线相关（本次未涉及）
  - **SIG12 仿真、测试与兼容性认证** → 板端稳定性/健康检查类（board-13/14）
- 社区联系邮箱：**M-RobotsOS@kaihong.com**（SIG 申请、建仓申请等正式渠道）。

## 2. 贡献流程（按官方指南提炼）

### 第 0 步：前置条件

1. 注册 AtomGit/GitCode 账号；
2. **签署 CLA**——首次提交 PR 时签署助手自动触发，个人贡献选"个人 CLA"；**未签 CLA 的 PR 无法合并**；
3. 读目标仓库 README / 贡献说明 / Issue 模板 / 分支策略。

### 第 1 步：提 Issue

- 整体项目问题 → [org 级 Issues 页](https://atomgit.com/org/m-robots/issues)；单仓库问题 → **到该仓库下提**（我们的做法：按 `社区贡献issues/` 里的目标仓库字段逐一投递）。
- 规范：先搜重；标题简洁；Bug 报告带"问题描述/复现步骤/期望行为/实际行为/环境信息"；加 Label；解决后及时关闭。

### 第 2 步：提 PR

```
fork 仓库 → clone 个人空间 → 功能分支（feature/xxx 或 fix/xxx）
→ 修改 + 测试 + 文档 → push → 新建 PR（目标 m-robots/<仓库>:master）
→ 描述中关联 Issue（Fixes #编号） → 响应评审意见 → 合入
```

- **一个 PR 只解决一个问题**（我们的原子化拆分正好符合）；
- 大改动先发 RFC 讨论；
- 推荐**两段式验证描述**：
  - `Host Verified`：主机上已完成的验证（Demo/单测/离线数据）；
  - `Device Pending`：需要板端接力验证的部分——**不假装做过硬件验证**。

### 第 3 步：持续参与（积分/晋升）

- 贡献积分 → 社区定制礼品（成长路径文档）；
- 进阶：参与 SIG 会议 → 核心贡献者 →（3 个月+、~10 个有效 PR、L5）可被提名 **Committer**（仓库审查/合并权限）；
- 引入第三方开源软件需走 `third-party-request` issue 评审（许可证须与 Apache-2.0 兼容）。

## 3. 有板/无板两条路径的差异

| | 无开发板（基础研习） | 有开发板（创新实践）——**我们是这条** |
|---|---|---|
| 切入点 | 文档/Demo/测试/工具/Agent | 烧录体验 → 跑通 ROS/Dora → 调试修复 → 贡献 |
| 验证要求 | 主机可复现即可，设备相关标 Device Pending | 可直接做设备侧验证 |
| 典型贡献 | 文档修复、Mock/fixture、单元测试、Skill | Issue、源码 PR、软件包、兼容性测试、踩坑内容创作 |

非代码类贡献也被官方认可：**教程、方案解析、踩坑记录**（文章/视频/直播）——我们的 `docs/板端开发参考/` 系列天然符合。

## 4. 我们的 17 个 issue 怎么落地（映射）

| 我们的文件 | 走哪个流程 | 备注 |
|---|---|---|
| `mclaw-01~04` | m-robots/mclaw 仓库 Issue | 对应 SIG9；01/04 可附补丁转 PR |
| `robot-docs-05/06/07` | robot_docs 仓库 PR（fork→分支→PR） | 对应 SIG11；文档 PR 最适合作为首贡献（CLA 首签会在这时触发） |
| `middleware-17` | robot_middleware 仓库 Issue/讨论 | 询问 ROS1 时间表 |
| `board-08~16` | ⚠️ 无公开源码仓——**这正是 @yc 说的"需要建仓"场景** | 见下节 |

## 5. 建仓申请（回复 @yc 的素材）

我们核实的空缺：机器车源码（`ros_ws` + `kaihong_adapter`，含 mclaw-skill、robot-runtime、驱动、启动脚本）只以 zip 分发，无公开仓库，导致 9 个 board 类 issue 无处投递。

可向社区提议的建仓名称（按现状命名习惯）：

1. `robot_car_host`（或 `robot-host`）——板端 `/data/robot-host` 运行时源码（对应 board-08/09/10/11/13/14）
2. `kaihong_adapter`——M-Claw 机器人 Skill 与适配层（对应 board-15/16，含我们拟贡献的 `gripper_camera_node.py`）

替代方案（若社区暂不建仓）：issue 提至 `M-Robots_release`（固件仓）并在正文注明实际组件；或先在讨论区发帖。

## 6. 提交纪律（结合官方规范 + 我们的实际情况）

1. 每个 issue/PR 单独提交，先搜重；
2. 提交前隐去内网 IP、密钥、WiFi 密码（官方行为准则同样要求脱敏）；
3. board 类标注实测环境（KaihongBoard-3588S + M-Robots OS 4.1），主机未验证的部分写清 Device Pending；
4. 标注 ⚠️ 的三条（robot-docs-06、board-11、board-16）先完成补充核验再提；
5. 首个 PR 建议从 `robot-docs-05`（HDC 排查指南）入手——证据最完整、评审成本最低。
