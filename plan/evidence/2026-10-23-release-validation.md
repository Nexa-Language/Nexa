# Nexa 2.4.0 发布前验证

日期：2026-10-23，Asia/Singapore。环境：macOS 26.6.2 arm64、Python 3.12.13。基线为 `c1ec8af8e2151c293fce76da29469f24699a0c58`，分支为 `feat/nexa-runtime-modernization`。本记录覆盖冻结后的 2.4 实现、会话与编辑器增量、发布文档和官网。

## 结果

| 范围 | 实测结果与证据 |
|---|---|
| Python 全套 | `.venv/bin/pytest -q -rs -m 'not benchmark'`：**2160 passed / 5 skipped / 3 deselected**，16 warnings，154.57 s；[日志](2026-10-23-release-python-tests.log.txt) |
| 冻结验证 | 测试前后源码、标准库、测试和打包依赖的 SHA-256 一致；[文件快照](2026-10-23-release-source-snapshot.json) |
| Rust 默认 / WASM | **140 / 143 passed**；37 个 Rust 源码、锁文件及共同语义 fixture 与此前验证快照一致，复用[原始命令与日志](2026-10-23-verification.md) |
| 打包及示例定向验证 | 66 passed；完整 suite 也包含仓库外 CLI/标准库与 sdist 重建测试 |
| Python 静态检查 | CI maintained files 的 Ruff/isort/ty 均通过；最后修改的 conversations.py、agent_runner.py 再次通过三项检查 |
| 文档和部署预检 | 11 个完整 Nexa 代码块编译、66 个本地页面引用存在、两份 workflow YAML 解析及 release-tag checkout 断言通过；[日志](2026-10-23-release-preflight.log.txt) |
| 浏览器 | 无头 Edge，1440/960/769/390/320 px × 首页/博客/发行文章共 15 场景 HTTP 200，无横向溢出或页面脚本异常；安装命令复制、移动导航、搜索、正反排序通过；[数据](2026-10-23-site-browser.json)、[脚本](2026-10-23-site-check.cjs.txt) |
| 提交清单 | 无缓存、构建目录、个人配置和凭据文件；候选文件的私钥、GitHub token 和模型 key 特征扫描零命中；`git diff --check` 通过 |

5 个 skipped 均因缺少可选 `psycopg2` 驱动。3 个 deselected 为独立性能实验。warnings 来自既有 JWT 短密钥 fixture 和隔离器拦截的 OAuth DNS 尝试。真实模型调用未发生。

## 独立审查与修复

基础运行时的 9 类实质发现与修复见[实施记录](../01-v1-execution.md)。发布改动审查和新增运行时审查分别针对不同范围进行。

- 发布审查发现首次模型配置缺少可执行指引，已补 endpoint/model 的 `.nxs` 模板、凭据来源说明及安装文档入口，并用实际配置解析器验证。
- 浏览器复现博客排序选择器错误和移动端网格溢出，修正后 15 场景通过；390 px 页面原 629 px 横向宽度恢复为 390 px。
- 会话与编辑器增量独立审查发现 1 个 Important：合法 `tool_calls: null` 历史使 `continue_run()` 和既有 `run()` 第二轮失败。新增两项回归在修复前均出现 TypeError；统一空列表归一化后 21 项会话测试通过，最终全套 2160 项通过。该发现已关闭。
- 增量审查同时核对新轮预算/期限/审批/journal、原生 provider 历史、父子 ID、未知副作用阻断、声明位置和就近配置优先级。该限定范围没有其他未解决的实质发现。

## 已验证边界与待验收渠道

语言探测复现了历史 struct/enum 构造、flow requires/ensures、defer 的生成代码执行缺口。控制流末尾的 flow 返回 `None`，`std.json.parse` 返回文本；[探测源码与实际结果](2026-10-23-language-probes.json) 和[运行契约](../../docs/runtime-v2.4.md#语言执行范围)记录了使用边界。示例清单的 63 compiled / 75 total 统计针对编译阶段。

真实 provider 的鉴权、服务端兼容性、质量、费用和延迟、PostgreSQL 集成及 MCP HTTP server 端到端仍待独立验证。MCP stdio、文件副作用、审批、跨进程恢复和验证子进程已经在本地实际执行。Rust 的支持子集及 Clippy 历史 warnings 见原始验证记录。

本文件写入发行源码之前，远端 PR CI、合入 main CI、干净 tag 的正式构建、公开下载安装及 Pages 部署仍属于发布后续门禁。最终 PR、源码 SHA、tag、CI、发行物哈希与官网的对应关系将在 GitHub Release 交付记录中保存。
