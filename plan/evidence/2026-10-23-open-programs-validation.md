# Nexa Open Programs 本地验收记录

日期：2026-10-23。稳定基线为 `v2.4.0` / `c2162637236e4a73feea410c4183672411666521`。本地开发分支为 `feat/nexa-3-open-programs-plan`；本轮实现尚未提交、推送或发布。源码对应关系见 [文件摘要](2026-10-23-open-programs-source.json)。

## 功能与测试

| 检查 | 环境与范围 | 实测结果 |
|---|---|---|
| 完整 Python 回归 | macOS arm64 / CPython 3.12.13，`pytest -m 'not benchmark' -q` | 2320 passed、5 skipped、3 deselected；221.54 秒 |
| 最后 CLI 证据消费修复 | Python 3.12，admission/workspace/maintenance CLI | 28 passed；20.98 秒 |
| 兼容 Python 3.10 | 既有完整快照 + 修复后的全部 Open Programs 和示例 | 2305 passed、5 skipped、3 deselected；受影响路径 197 passed，90.72 秒；末次 CLI 28 passed |
| 兼容 Python 3.14 | 既有完整快照 + 修复后的全部 Open Programs 和示例 | 2305 passed、5 skipped、3 deselected；受影响路径 197 passed，81.36 秒；末次 CLI 28 passed，17.78 秒 |
| Linux 执行器契约 | Python 3.12 Linux arm64，可信测试驱动使用 Colima VM 的 Docker Engine | Open Programs 130 passed，33.12 秒；末次 CLI 28 passed，4.82 秒；存储退出测试 4 passed，1.26 秒 |
| 静态检查 | Open Programs 源码/测试、benchmark、示例登记文件 | Ruff、isort、ty 通过 |
| 版本化 schema | 已安装模型生成的 schema 与公开 JSON 逐项比对 | 通过，包含 application 的 retained-file 恢复字段 |
| 实际发行包安装 | 仓库外新 uv 环境安装实际 wheel；从 sdist 重建 wheel | 11 个安装检查通过，运行时代码逐文件相同；锁定运行输出 43、模型请求 0 |
| 官网开发文章 | 本地 IAB，1280 px 宽 | 无水平溢出、无 console error；稳定版链接仍指向 2.4.0；文内 `.nx` 示例离线检查通过 |

完整回归的 5 个跳过项为未配置 PostgreSQL 的集成路径，3 个排除项为 benchmark。Python 3.12 的 16 个警告来自既有测试中的短 JWT 测试密钥和受限网络等路径。Linux 的两个警告来自既有 parser 的转义字面量。新增实现没有改变 Rust 源码；沿用 2.4 的默认/WASM 验证证据。

最后两个 CLI 回归晚于完整测试，分别覆盖当前证据解释和 capsule 导出。这些路径的验证单列，其他未变化代码复用完整快照。另补充 SQLite 提交前后真实进程退出：Python 3.10/3.12/3.14 及 Linux 各 4 项存储测试通过。实验矩阵拥有自己的启动时源码摘要；最终源码相较第二轮矩阵补充了 CLI 消费路径及反事实样本的前序接纳条件过滤，矩阵使用的求解、执行、工作区和 oracle 逻辑保持一致。

## 模型与演示

选择用户已有阿里云标准兼容端点，模型 `qwen3.8-max-0902`。凭据从用户指定 shell 配置中的阿里云变量读取，只在测试进程内存中使用；产品配置仅声明环境变量名称。变更文件检查未发现该实际凭据。

六阶段真实演示完整通过：作者澄清、精确授权应用、独立进程恢复、目标修订、跨任务复用、依赖重验和编译器 advice pass 演进。顺序以实际记录为准。11 次请求、12075 input tokens、1486 output tokens、46.537 秒。C1/C2 锁定自举一致，生成请求为 0。模型响应记录可在真实 OCI 中离线回放。详见 [演示证据](2026-10-23-open-programs-flagship.json)。

之前的四次失败演示保留：配置夹具重复 endpoint 派生依赖；模型评审缺少当前输入；候选返回包装器且旧 Patch 类型检查过宽；候选将字典当作属性访问。前两类的输入/夹具与类型边界已修复，后者通过维护示例明确字典访问契约。成功记录只统计最后一次完整运行。

10 个合成任务 × 3 阶段 × 3 次重复 × 4 组的矩阵保存逐阶段记录与失败，见 [实验结果](2026-10-23-open-programs-experiment.md)。第二轮 Open Programs 为 73/90，2.4 适配基线为 70/90，关闭复用为 68/90，关闭反馈为 41/90。首轮基线缺少同等 Patch 输出 schema，作为方法调试数据保留。模型价格基准尚未核对，费用为 null，token 消耗单独报告。

## OCI 和安装产物

候选镜像为 `python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704`。Linux 测试驱动的 Docker CLI 来自 `docker@sha256:5e6baf67325a79f64ed3bed6863954d5e05d0f3d4e57cbdb14809346814bbfdb`。macOS 控制器和 Linux 驱动共用 Colima 的 Linux engine；候选容器始终无宿主挂载、无 Docker socket、无密钥和无外网。

本地测试包仍按项目 `VERSION` 标识为 2.4.0，包含本开发分支实现；这些文件与公开的 2.4 发布附件完全分开。SHA-256 与安装检查见 [包验收证据](2026-10-23-open-programs-package.json)。只验证本地开发产物，3.0 正式编号和公开下载地址由独立发布流程确定。

## 发布前剩余项

正式 3.0 RC 仍需提交 PR 后的托管 Linux Python 3.10/3.12/3.14 CI、版本及发布范围审定、独立发行与公开下载验收。官网开发文章尚未部署；移动端发布验收留在部署流程。外部编辑器已获得协议与集成文档，其 UI 适配和发布按对应仓库范围推进。

原始日志与本地截图保存在 `.superpowers/sdd/03-v1-nexa-3-open-programs/`。本文件、公开模型记录和内容摘要提供可提交的脱敏交付记录。
