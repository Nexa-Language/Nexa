# Nexa 文档验证报告 v2

> 验证日期: 2026-03-28
> 验证范围: nexa-docs 全部文档

## 📋 验证摘要

| 类别 | 数量 |
|------|------|
| 已验证文档 | 12 个核心文档 |
| 发现问题 | 15 项 |
| 已实现功能 | 35+ 项 |
| 未实现功能 | 15 项 |

---

## ❌ 未实现功能清单

### 1. 核心原语 (高优先级)

| 功能 | 文档位置 | 描述 | 影响 |
|------|----------|------|------|
| `reason()` 原语 | preface_background.md, preface_scenarios.md | 上下文感知推理调用，支持类型推导 | 核心特性，文档重点介绍 |
| `sandbox` 参数 | preface_scenarios.md | Agent 沙箱隔离配置 | 安全特性 |
| `permissions` 参数 | preface_scenarios.md | Agent 权限控制 | 安全特性 |
| `DataStream` | preface_scenarios.md | 动态数据流处理 | 数据处理 |
| `absorb()` | preface_scenarios.md | Agent 吸收数据 | 记忆管理 |
| `wait_for_human()` | preface_scenarios.md | 人在回路（HITL）审批原语 | 企业级特性 |

### 2. CLI 功能 (中优先级)

| 功能 | 文档位置 | 描述 | 影响 |
|------|----------|------|------|
| `--version` 参数 | quickstart.md | CLI 版本检查 | 用户体验 |
| `nexa cache clear` 命令 | part1_basic.md | 清除缓存 | 运维功能 |

### 3. 循环控制 (中优先级)

| 功能 | 文档位置 | 描述 | 影响 |
|------|----------|------|------|
| `runtime.meta.loop_count` | part2_advanced.md | 循环计数器 | 防止无限循环 |
| `runtime.meta.last_result` | part2_advanced.md | 上次循环结果 | 循环优化 |
| `raise SuspendExecution` | part2_advanced.md | 人工拦截异常 | 人在回路 |
| `break` 语句 | reference.md | 循环中断 | 控制流 |

### 4. Agent 属性 (中优先级)

| 功能 | 文档位置 | 描述 | 影响 |
|------|----------|------|------|
| `timeout` 属性 | part3_extensions.md, reference.md | 请求超时时间 | 可靠性 |
| `retry` 属性 | part3_extensions.md, reference.md | 重试次数配置 | 可靠性 |

### 5. 装饰器 (低优先级)

| 功能 | 文档位置 | 描述 | 影响 |
|------|----------|------|------|
| `@timeout` 装饰器 | reference.md | 设置执行超时 | 资源控制 |
| `@retry` 装饰器 | reference.md | 设置最大重试次数 | 可靠性 |
| `@temperature` 装饰器 | reference.md | 设置模型温度参数 | 模型控制 |

---

## ✅ 已实现功能清单

### Agent 系统
- [x] `agent` 关键字定义智能体
- [x] `role` 属性 - Agent 角色描述
- [x] `prompt` 属性 - Agent 任务指令
- [x] `model` 属性 - 模型路由（格式：提供商/模型名）
- [x] `memory` 属性 - 记忆模式（persistent）
- [x] `stream` 属性 - 流式输出
- [x] `cache` 属性 - 智能缓存
- [x] `experience` 属性 - 长期记忆文件
- [x] `fallback` 属性 - 模型灾备降级（多级备用）
- [x] `max_tokens` 属性 - 最大输出 token 数
- [x] `uses` 关键字 - 工具挂载
- [x] `implements` 关键字 - Protocol 实现

### Protocol 系统
- [x] `protocol` 关键字定义输出格式约束
- [x] 自动重试纠偏机制（3次重试）
- [x] 类型验证（string, int, float, bool）

### 控制流
- [x] `flow main` - 主流程入口
- [x] `>>` 管道操作符 - Agent 串联
- [x] `match intent` - 意图路由
- [x] `|>>` 分叉操作符 - Fan-out 并行发送
- [x] `&>>` 合流操作符 - Merge/Fan-in 合并结果
- [x] `??` 条件分支操作符 - 路径选择
- [x] `loop until` - 语义循环
- [x] `semantic_if` - 语义条件判断
- [x] `fast_match` - 正则预过滤
- [x] `try/catch` - 异常处理

### 标准库
- [x] `std.fs` - 文件系统操作
- [x] `std.http` - HTTP 网络请求
- [x] `std.time` - 时间操作
- [x] `std.shell` - 系统命令
- [x] `std.ask_human` - 人机交互
- [x] `std.json` - JSON 处理
- [x] `std.math` - 数学运算
- [x] `std.regex` - 正则表达式
- [x] `std.hash` - 哈希加密

### 其他功能
- [x] `secret()` - 密钥管理
- [x] `img()` - 多模态图像加载
- [x] `include` - 模块引用
- [x] `fallback` 表达式 - 降级机制
- [x] `uses "SKILLS.md"` - Markdown 技能挂载
- [x] `test` 声明 - 测试框架
- [x] `assert` 语句 - 断言验证

---

## 🔧 修复建议

### 第一阶段：核心功能修复

1. **实现 `reason()` 原语**
   - 文件: `src/runtime/core.py` 或新建 `src/runtime/reason.py`
   - 功能: 上下文感知推理，支持类型推导
   - 优先级: 高

2. **实现循环控制变量**
   - 文件: `src/code_generator.py`, `src/runtime/evaluator.py`
   - 功能: `runtime.meta.loop_count`, `runtime.meta.last_result`
   - 优先级: 中

3. **实现 `break` 语句**
   - 文件: `src/nexa_parser.py`, `src/ast_transformer.py`, `src/code_generator.py`
   - 功能: 循环中断
   - 优先级: 中

### 第二阶段：Agent 属性扩展

4. **实现 `timeout` 属性**
   - 文件: `src/runtime/agent.py`
   - 功能: 请求超时控制
   - 优先级: 中

5. **实现 `retry` 属性**
   - 文件: `src/runtime/agent.py`
   - 功能: 可配置的重试次数
   - 优先级: 中

### 第三阶段：CLI 增强

6. **添加 `--version` 参数**
   - 文件: `src/cli.py`
   - 功能: 显示版本号
   - 优先级: 低

7. **添加 `cache clear` 命令**
   - 文件: `src/cli.py`, `src/runtime/cache_manager.py`
   - 功能: 清除缓存
   - 优先级: 低

### 第四阶段：装饰器系统

8. **实现装饰器解析**
   - 文件: `src/nexa_parser.py`, `src/ast_transformer.py`, `src/code_generator.py`
   - 功能: `@limit`, `@timeout`, `@retry`, `@temperature`
   - 优先级: 低

---

## 📝 文档与代码不一致问题

以下功能在文档中描述但代码中未实现或实现不完整：

| 问题 | 文档描述 | 代码现状 | 建议 |
|------|----------|----------|------|
| `reason()` | 核心原语，支持类型推导 | 未实现 | 实现或从文档移除 |
| `sandbox` | Agent 沙箱隔离 | 未实现 | 标记为未来特性 |
| `permissions` | Agent 权限控制 | 未实现 | 标记为未来特性 |
| `wait_for_human()` | HITL 审批原语 | 未实现 | 实现或从文档移除 |
| `timeout` 属性 | 请求超时 | 未在 NexaAgent 中实现 | 添加实现 |
| `retry` 属性 | 重试次数配置 | 硬编码为3 | 添加可配置属性 |
| `@limit` 装饰器 | Token 限制 | 解析器未支持 | 实现装饰器系统 |
| `@timeout` 装饰器 | 超时控制 | 解析器未支持 | 实现装饰器系统 |

---

## 🎯 下一步行动

1. **立即修复**: CLI `--version` 参数（简单快速）
2. **短期修复**: `timeout`、`retry` 属性，循环控制变量
3. **中期修复**: `reason()` 原语，`break` 语句
4. **长期规划**: 装饰器系统，沙箱隔离，权限控制

---

*此报告由 Architect 模式自动生成*