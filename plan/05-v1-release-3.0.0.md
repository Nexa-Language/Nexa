# Nexa 3.0.0 发布执行

用户于 2026-10-23 授权：检查并修复验收问题；满足条件后直接发布 3.0，更新官网与文档。稳定基线为 `v2.4.0` / `c2162637236e4a73feea410c4183672411666521`。

## 范围与前置证据

发布 Python Open Programs 参考实现：目标求解、当前证据接纳、持续修订、准确补丁授权、条件复用、作者协议和诊断 pass 局部自举。2.4 编译及运行入口保留。Linux/macOS 是 3.0 的运行平台，候选执行依赖 Docker/OCI；Rust 保持已公开的 2.4 子集。外部编辑器使用已交付协议文档，其独立 UI 发版不包含在本仓库发行物中。

使用 [设计](03-v1-nexa-3-open-programs.md)、[实现记录](04-v1-open-programs-execution.md)、[本地验收](evidence/2026-10-23-open-programs-validation.md)、[整分支审查](evidence/2026-10-23-open-programs-review.md) 和 [实验报告](evidence/2026-10-23-open-programs-experiment.md)。52 个实现、测试与配置文件的本地验证摘要在发布准备开始时逐项匹配。模型实验已完成，文档和版本修改复用其有效证据。

## 步骤与门禁

- [x] 统一 VERSION、双语 README、安装文档、3.0 规范、Nexa Code 接入说明和官网；正式说明明确支持范围与迁移方式。
- [x] 校验文档示例、链接、静态检查和打包；完成当前源码的本地回归，扫描暂存清单中的凭据与本地状态。
- [ ] 使用 ouyangyipeng 身份按 Pedalboard 模板提交，更新远端并 rebase 最新 main，创建并附加发布 PR。
- [ ] 审查结论满足门禁，托管 Python 3.10/3.12/3.14、Rust 默认/WASM CI 全部通过后 Rebase and merge。
- [ ] 核对合入 SHA 和 CI，以该 SHA 建立不可移动的 v3.0.0 tag；从干净 tag 检出构建 wheel、sdist、SHA256SUMS 与来源记录。
- [ ] 仓库外新环境安装正式 wheel，核对版本、CLI、标准库、3.0 离线检查、OCI 执行和锁定重放；sdist 重建完整。
- [ ] 创建 draft Release、上传并核对附件，再正式发布并设为 Latest；从公开地址重新下载核验 SHA-256 和实际安装。
- [ ] 等待 Release 事件触发 Pages，验收线上首页版本、安装入口、发布文章、文档和移动布局。
- [ ] 保存 PR、源码 SHA、tag、CI、Release、构建哈希与官网的交付对应关系。

## 风险与处理

模型效果由当前检查、预算和审批决定；固定合成矩阵用于公开行为和方法数据。PostgreSQL 服务路径未配置；不纳入本次新增能力。保留原 inode 的工作区应用需要存储空间与人工清理，并有短暂文件名切换窗口。发布说明与使用指南保留这些条件。

GitHub PyPI 同名项目属于他人，安装入口必须指向本项目 Release 附件。官网仅由正式 Release 发布事件部署对应 tag。任何失败记录准确阻塞，修复后重验受影响路径；已公开 tag 保持不变，后续修复使用补丁版本。

发布预检结果见 [记录](evidence/2026-10-23-open-programs-release-preflight.md)。
