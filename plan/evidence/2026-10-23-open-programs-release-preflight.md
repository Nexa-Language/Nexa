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
