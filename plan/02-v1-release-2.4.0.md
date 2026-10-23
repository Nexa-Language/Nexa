# Nexa 2.4.0 完整发布

日期：2026-10-23。状态：全部发布验收完成。用户已批准源码提交、推送、PR、Rebase and merge、tag、GitHub Release 和官网发布。

## 最终交付

以下记录在发布完成后补入规划分支；已发布的 `v2.4.0` tag 保持不变。

| 项目 | 验收结果 |
|---|---|
| 源码 | [PR #2](https://github.com/Nexa-Language/Nexa/pull/2) 通过 Rebase and merge 合入 |
| 稳定基线 | [v2.4.0](https://github.com/Nexa-Language/Nexa/tree/v2.4.0)，`c2162637236e4a73feea410c4183672411666521` |
| GitHub Release | [Nexa 2.4.0](https://github.com/Nexa-Language/Nexa/releases/tag/v2.4.0)，正式版本，发布时设为 Latest |
| 发行物 | wheel、sdist、SHA256SUMS、BUILDINFO.json 齐全；回下载内容和哈希一致 |
| 安装 | 仓库外新环境从公开 wheel URL 安装成功，版本、Hello World、标准库解析与计算通过；sdist 重建 wheel 与正式 wheel 哈希一致 |
| CI | [发布源码矩阵](https://github.com/Nexa-Language/Nexa/actions/runs/39931776442) 与 [CodeQL](https://github.com/Nexa-Language/Nexa/actions/runs/39931776856) 通过 |
| 官网 | [www.nexa-lang.com](https://www.nexa-lang.com/) 已展示 2.4.0；[Release 事件部署](https://github.com/Nexa-Language/Nexa/actions/runs/39932974844) 成功，源码与 tag 一致 |
| 浏览器 | 1440/960/769/390/320 px × 3 页面共 15 个线上场景通过，复制、导航、搜索和排序正常 |

冻结源码验证为 **Python 2187 passed / 5 skipped / 3 deselected**，Rust 默认 **141 passed**、WASM **144 passed**。5 项 PostgreSQL 测试缺少可选驱动；真实 provider 与 MCP HTTP server 的端到端范围见发行说明。完整交付对应关系与构建信息已补入公开 Release。

正式 wheel SHA-256：`3a9e23c754704718cb7ca08644c30248a92fa2c9bb9bbeaa287057f50ee0544d`。
正式 sdist SHA-256：`b5c1bdb8bf3bc9eba24780a996ffc10e3a8d132c496ee6fae85dfb031836991d`。

## 目标与基线

发布渠道为 GitHub Release 与 https://www.nexa-lang.com/ 。发行物包含 wheel、sdist、SHA256SUMS 和 GitHub 源码归档；Rust AVM 随源码交付。PyPI 的 `nexa-lang` 属于另一项目，所有安装入口使用本仓库发行物的明确 URL。

基线：`c1ec8af8e2151c293fce76da29469f24699a0c58`；分支：`feat/nexa-runtime-modernization`。
前置实现与审查记录见 [2.4 实施记录](01-v1-execution.md)，有效测试见 [本地验证](evidence/2026-10-23-verification.md)。发布准备开始时，验证快照中的 295 个文件全部一致。

## 执行步骤与验收

1. 补全发行说明、双语 README、安装指南、Nexa Code 文档和官网。同步真实能力、示例、兼容变化及未实测范围；部署使用 `release.published` 和手动触发，检出相应 tag。
2. 定向验证文档示例、静态页面、工作流和打包；复用未变化源码的测试证据。独立审查新增发布改动，修复实质发现。
3. 核对提交文件与敏感内容，按 Pedalboard 模板提交。fetch 后 rebase 最新 main，推送并创建、附加 PR。
4. 等待审查和 Python 3.10/3.12/3.14、Rust 默认/WASM CI；仅用 Rebase and merge 合入。核对合入 main 的 SHA 与 CI。
5. 在已验证 SHA 创建 `v2.4.0`。从 tag 的干净检出构建 wheel/sdist，保存构建环境、源码 SHA 和 SHA-256；仓库外新环境验证安装、CLI、Hello World、标准库和 sdist 重建。
6. 创建 draft Release，上传并核对发行物，再发布 stable Latest；公开下载后核对哈希，并从公开 wheel URL 安装验证。
7. 等待 Release 触发的 Pages 部署。验收线上版本、安装命令、下载链接、发布文章及桌面/移动端布局；记录 PR、CI、tag、源码、产物与官网的对应关系。

完成条件：上述七步的实际验收全部通过。部分渠道失败时记录具体阻塞并继续修复；正式发布 tag 保持不变，后续修复使用补丁版本。

## 风险与审查重点

- 发布安装入口必须指向 Nexa-Language/Nexa，避免安装同名的其他项目。
- 官网示例必须通过当前编译器；宿主工具、协作取消、未知副作用、Rust 子集和真实 provider 未实测范围须准确说明。
- 页面部署必须发生在正式附件就绪之后，并使用同一发行 tag。
- 干净构建必须包含 VERSION 与标准库；sdist 必须能独立重建 wheel。
- 复用测试证据以源码哈希一致为前提；远端 CI 是合入门禁。

## 执行记录

- 2026-10-23：开始执行。已有运行时独立审查及 2130 项 Python 测试证据复用；本轮审查聚焦新增发行与官网改动。
- 2026-10-23：按全局 skill compatibility，文档与低风险配置使用解析、编译、安装和浏览器检查；保留既有计划/日志体系。
- 2026-10-23：用户明确批准将并行生态任务新增的会话续接和公共接口纳入 2.4.0，并授权跨任务协调。发布基线等待该任务完成及审查，之后重跑 Python 全套；旧 Rust 证据仍按文件哈希复用。
- 2026-10-23：发布准备定向检查通过：66 项打包/示例测试、11 个完整 Nexa 文档代码块编译、66 个本地网页资源引用及两份工作流 YAML。版本输出为 `Nexa v2.4.0`。
- 2026-10-23：独立无头 Edge 在 1440、390、320 px 检查首页、博客列表与发行文章共 9 个场景，均 HTTP 200 且无页面横向溢出；首页复制命令及移动导航通过。修复了博客列表仍使用桌面双栏造成的 390 px 横向溢出（629 px → 390 px）。
- 2026-10-23：发布改动独立审查完成。执行者将首次模型配置缺口按实际影响列为应修复项：新用户需要 endpoint/model/credential 的具体配置才能运行 README Agent。已补 `.nxs` 模板与直接导航；博客排序失败已复现并修正选择器。扩展的 1440/960/769/390/320 px、搜索与排序检查全部通过，共 15 个页面场景。
- 审查范围说明：运行时新增接口等待独立审查与全套回归；公开附件、tag 构建及线上部署由后续发布步骤实测；真实 provider、PostgreSQL 和 MCP HTTP 保持已公开的未实测范围；历史博客按发布日期保留原文，新发布页面使用当前能力与证据。
- 发布配置核对：Pages 环境当前仅允许 `main` branch，且无人工审批 protection rule。为执行已批准的 release tag 部署，需要在正式发布前增加精确的 `v2.4.0` tag policy；保留现有 main policy，后续版本逐次确认对应 tag。

发布准备完成记录：冻结后的完整 Python suite 为 **2160 passed / 5 skipped / 3 deselected**，源码哈希前后一致。运行时增量审查的唯一 Important 已通过两项 null tool-call 回归关闭。既有语言执行缺口经离线复现后同步进入运行契约、发行说明与博客。详细结果见 [发布前验证](evidence/2026-10-23-release-validation.md)。当前进入提交、PR 与远端 CI 阶段。

PR [#2](https://github.com/Nexa-Language/Nexa/pull/2) 已创建。首轮 CI 的 Python 3.10/3.12 与 Rust 通过；Python 3.14 发现 Option 类型测试依赖显示格式，已改为类型比较，本地 79 项类型系统测试通过。继续等待更新后的完整 CI，再按 Rebase and merge 合入。

最后一批编译器修复：顺序管道保留全部 Agent；整数历史上限、输出 token 和 limit/timeout/retry 装饰器进入真实执行配置。历史块式条件路由改为明确编译错误。122 项定向测试与 **2171 passed / 5 skipped / 3 deselected** 全套通过，源码哈希一致；两次独立增量审查无剩余实质发现。更新同一发布 PR 后等待最后一轮 CI。

最终远端审查的 5 个问题已复现并修复：工具额度耗尽后的请求、结构化输出有限修正、错误 hook 变量、工具 hook 名称筛选、AVM 工具声明编译诊断。修正请求保留真实用户回合和原始合同输入，兼容原生 provider 与审批恢复；49 项相关测试通过，独立复核 Ready: Yes。Rust 重新运行，默认 141 项、WASM 144 项通过。Pages 已添加精确 `v2.4.0` tag policy（ID 64071499），保留 main 分支 policy。

最终冻结源码完整回归：**2187 passed / 5 skipped / 3 deselected**，150.71 s，源码哈希一致。最后 15 个浏览器场景通过。

## 发布后恢复 3.0 规划

以 `v2.4.0` 为稳定基线，完成 Open Programs 的详细设计。允许破坏性升级，Python 参考实现优先，旗舰场景为持续维护代码仓库。首发贯通目标求解、在线修改、证据失效和有条件的跨任务实现复用。

Docker/OCI 为隔离基线，沙盒内自主执行，应用到用户工作区前审批。确定性检查、模型评审和人工确认分别记录，由显式验收策略决定完成条件。

LLM/Agent 作为编译环境的标准能力：编译器与作者共同澄清目标、生成实现、解释诊断和改进程序；语言与编译器自身的演进使用版本化提案、语义测试和自举验证。本次发布完成后再展开设计与关键 trade-off 讨论。
