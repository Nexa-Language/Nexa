# Nexa 3.0.0 发布预检

来源基线为 `v2.4.0` / `c2162637236e4a73feea410c4183672411666521`，分支 `feat/nexa-3-open-programs-plan`。完整实现与此前 52 文件验收摘要一致；发布准备修改版本、文档、官网、打包清单和一条历史版本断言，运行时代码保持不变。

- macOS arm64 / Python 3.12.13：最终完整回归 2322 passed、1 failed、5 skipped、3 deselected，247.07 秒。唯一失败是旧测试只接受 v1/v2 前缀；修改为核对 VERSION 后，原测试模块和打包测试合计 32 passed，15.47 秒。
- 5 个 skipped 为未配置 PostgreSQL 路径，3 个 deselected 为 benchmark。16 个警告来自已有 JWT/受限网络测试。
- 维护范围 Ruff、isort、ty 通过；uv locked/offline 校验通过，77 个依赖包，CLI 输出 `Nexa v3.0.0`。
- 133 个 Open Programs 测试均已在完整回归中通过。固定模型矩阵与六阶段演示沿用对应源码摘要下的记录。
- 16 个文档/页面：9 段完整 `.nx` 示例、162 个本地或 v3.0.0 文件链接检查通过。
- IAB 本地首页：1280 px 视口、文档宽 1274 px，console error 0。安装按钮复制内容与 3.0.0 wheel URL 完全一致。
- 390 × 844 px iframe 视口：首页和文章的文档宽均 384 px，截图无横向溢出；移动菜单可展开。这里验证 CSS 响应布局，未模拟触摸设备。
- 待发布门禁：托管 Python/Rust CI、干净 tag 正式构建与安装、公开附件回下载、Release 事件官网部署。

本地原始输出和截图位于 `.superpowers/sdd/03-v1-nexa-3-open-programs/release-*`。原有审查问题及修复见 [审查记录](2026-10-23-open-programs-review.md)，正式交付对应关系随 Release 保存。


推送时 GitHub 返回两项 AnyIO 历史告警（GHSA-82r6-8w77-94w6、GHSA-5p39-cfhj-2xmp），均修复于 4.14.2。锁文件和测试环境已使用 4.15.1；进一步给 wheel 元数据添加 `anyio>=4.14.2,<5`，避免已有环境保留受影响的旧传递依赖。77 个锁定包的版本逐项保持不变，打包回归 2 passed；安装元数据拒绝 4.14.1、接受当前 4.15.1。完整托管 CI 使用该最终约束。


GitHub Code Quality 的四条诊断已逐项检查：CandidateExecutor 的两个 `...` 是 typing.Protocol 的方法签名，保留标准声明；前端在已有语法诊断后无法提取符号表、临时文件已被并发移除后的幂等清理两处添加原因注释，异常处理行为不变。托管 Copilot review 由于账号额度未运行；本地独立整分支审查及其回归证据保持有效。


## 合入前前端修复

最终 PR 检查全绿后，Codex 审查提出两项 P2：版本声明可省略导致离线检查与 build/run 路由不一致；重复 ensure/review 通过离线检查后被策略模型拒绝。额外核对发现内置 typecheck 重名也触发相同策略冲突。新增 6 条回归（含合法多条款组合）：修复前 5 failed、16 passed；修复后前端 21 passed。完整 Open Programs 与示例回归为 **206 passed，95.31 秒**，包含 139 个 Open Programs 用例及 67 个示例检查；Ruff/isort/ty 与文档预检通过。

前端要求显式版本、定位重复条款并保留不同证据种类的独立名称。已保存模型响应在修复后的完整链路中重放通过；既有矩阵使用显式版本和唯一条款，模型求解、执行与验收路径保持原行为。托管全量 CI 在最终修复提交上重新执行。
