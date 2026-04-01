# Nexa 语法特性全面测试计划

## 概述

本文档详细描述了 Nexa 语言所有语法特性的测试计划，每个语法特性都需要编写专门的测试文件，包含不少于 10 个测试点，覆盖各种边界条件和极端情况。

## 发现的问题

### 1. 多行 prompt `"""` 功能未实现

**位置**: `src/nexa_parser.py` 第 170 行

**问题**: 当前 `STRING_LITERAL` 定义为 `/ "[^"]*" /`，只能匹配单行字符串，不支持三引号多行字符串。

**修复方案**: 需要添加 `MULTILINE_STRING` 词法规则，支持 `"""..."""` 语法。

---

## 测试计划清单

### 1. 多行 prompt 测试 (`test_multiline_prompt.nx`)

**优先级**: 🔴 最高（上一个 agent 卡死的地方）

**测试点**:
1. 基本三引号字符串
2. 包含换行的多行 prompt
3. 包含特殊字符的多行 prompt
4. 包含引号的多行 prompt
5. 空多行 prompt
6. 多行 prompt 与其他属性组合
7. 多行 prompt 中包含代码块
8. 多行 prompt 中包含 JSON
9. 多行 prompt 中包含中文
10. 多行 role 属性
11. 多行 experience 文件路径
12. 嵌套三引号边界情况

---

### 2. Agent 基础属性测试 (`test_agent_basic_attributes.nx`)

**测试点**:
1. `role` 属性 - 基本用法
2. `role` 属性 - 空值
3. `role` 属性 - 超长文本
4. `prompt` 属性 - 必填验证
5. `model` 属性 - 正确格式 (`provider/model`)
6. `model` 属性 - 错误格式（缺少提供商前缀）
7. `memory` 属性 - `persistent` 模式
8. `memory` 属性 - `local` 模式
9. `stream` 属性 - `true`
10. `stream` 属性 - `false`
11. `cache` 属性 - 开启
12. `cache` 属性 - 关闭

---

### 3. Agent 修饰器测试 (`test_agent_decorators.nx`)

**测试点**:
1. `@limit(max_tokens=N)` - 基本用法
2. `@timeout(seconds=N)` - 基本用法
3. `@retry(max_attempts=N)` - 基本用法
4. `@temperature(value=N)` - 基本用法
5. 多个修饰器组合
6. 修饰器与属性等价验证
7. 修饰器优先级测试
8. 无效修饰器参数
9. 修饰器值边界（max_tokens=0）
10. 修饰器值边界（timeout=1）

---

### 4. Protocol 和 implements 测试 (`test_protocol_implements.nx`)

**测试点**:
1. 基本 Protocol 定义
2. Agent implements Protocol
3. Protocol 类型验证 - `string`
4. Protocol 类型验证 - `int`
5. Protocol 类型验证 - `float`
6. Protocol 类型验证 - `boolean`
7. Protocol 类型验证 - `list[string]`
8. Protocol 类型验证 - `dict`
9. Protocol 验证失败自动重试
10. 多个 Agent 实现同一 Protocol
11. Protocol 字段缺失错误
12. Protocol 类型不匹配错误

---

### 5. 管道操作符 `>>` 测试 (`test_pipeline_operator.nx`)

**测试点**:
1. 基本管道: `A >> B`
2. 三阶段管道: `A >> B >> C`
3. 四阶段管道
4. 输入字符串开始: `input >> A >> B`
5. 管道与方法调用混合
6. 管道结果赋值
7. 管道作为参数传递
8. 空管道边界情况
9. 管道中包含 Protocol Agent
10. 管道中包含带 uses 的 Agent

---

### 6. 意图路由 `match intent` 测试 (`test_match_intent.nx`)

**测试点**:
1. 基本 match 语句
2. 多个 intent 分支
3. 默认分支 `_`
4. intent 中文描述
5. intent 英文描述
6. 路由到 Agent.run()
7. 路由到管道表达式
8. match 结果赋值
9. 无匹配情况
10. 嵌套 match 语句

---

### 7. DAG 操作符测试 (`test_dag_operators.nx`)

**测试点**:
1. 分叉操作符 `|>>` - 2 个 Agent
2. 分叉操作符 `|>>` - 4 个 Agent
3. 合流操作符 `&>>` - 基本用法
4. 条件分支操作符 `??` - 基本用法
5. Fire-forget 操作符 `||`
6. 共识操作符 `&&`
7. 链式 DAG: `expr |>> [...] &>> Agent`
8. 多阶段 DAG 拓扑
9. DAG 与管道组合
10. DAG 中包含 Protocol Agent
11. 并发安全性测试
12. 超时处理

---

### 8. 语义循环 `loop until` 测试 (`test_loop_until.nx`)

**测试点**:
1. 基本 loop until 语法
2. 自然语言终止条件
3. `runtime.meta.loop_count` 访问
4. `runtime.meta.last_result` 访问
5. 最大迭代次数保护
6. break 语句退出
7. 循环内变量更新
8. 嵌套循环
9. 循环内包含 DAG 操作
10. 循环内包含 match 语句

---

### 9. 语义条件判断 `semantic_if` 测试 (`test_semantic_if.nx`)

**测试点**:
1. 基本 semantic_if 语法
2. `fast_match` 正则预过滤
3. `against` 变量指定
4. else 分支
5. 中文条件描述
6. 英文条件描述
7. JSON 格式检测
8. 日期格式检测
9. 复杂条件组合
10. semantic_if 与 Agent 调用组合

---

### 10. 异常处理 `try/catch` 测试 (`test_try_catch.nx`)

**测试点**:
1. 基本 try/catch 语法
2. catch 块接收错误信息
3. try 块正常执行
4. try 块抛出异常
5. catch 块中使用 fallback Agent
6. 嵌套 try/catch
7. try/catch 与管道组合
8. try/catch 与 DAG 组合
9. catch 后继续执行
10. 多种异常类型

---

### 11. 标准库 `uses` 测试 (`test_stdlib_uses.nx`)

**测试点**:
1. `uses std.fs` - 文件读取
2. `uses std.http` - HTTP GET
3. `uses std.time` - 获取时间
4. `uses std.json` - JSON 解析
5. `uses std.text` - 文本处理
6. `uses std.math` - 数学计算
7. `uses std.shell` - Shell 命令
8. `uses std.ask_human` - 人机交互
9. 多命名空间: `uses std.fs, std.http`
10. 命名空间工具调用
11. 无效命名空间处理
12. 权限控制

---

### 12. secret 密钥管理测试 (`test_secret_management.nx`)

**测试点**:
1. `secret("KEY")` 基本用法
2. 密钥文件 `secrets.nxs` 读取
3. 密钥不存在错误
4. 密钥注入 Agent
5. 多个密钥使用
6. 密钥与 fallback 组合
7. 密钥安全日志验证
8. 空密钥处理
9. 密钥值包含特殊字符
10. 密钥在 DAG 中传递

---

### 13. include 模块化测试 (`test_include_module.nx`)

**测试点**:
1. 基本 include 语句
2. `.nxlib` 文件导入
3. 导入 Agent 使用
4. 导入 Protocol 使用
5. 多文件 include
6. 嵌套 include
7. 循环 include 检测
8. 文件不存在错误
9. 相对路径 include
10. 导入命名冲突

---

### 14. img 多模态测试 (`test_img_multimodal.nx`)

**测试点**:
1. `img("path/to/image.jpg")` 基本用法
2. 支持 JPEG 格式
3. 支持 PNG 格式
4. 支持 GIF 格式
5. 支持 WebP 格式
6. 图片传递给 Agent
7. 图片与文本混合输入
8. 图片不存在错误
9. 无效图片格式
10. 图片在管道中传递
11. 图片在 DAG 中传递
12. Base64 编码验证

---

### 15. flow 参数传递测试 (`test_flow_params.nx`)

**测试点**:
1. 基本参数: `flow main(input: string)`
2. 多参数: `flow process(a: string, b: int)`
3. 参数类型验证
4. 参数在 flow 内使用
5. 参数传递给 Agent
6. 参数默认值
7. 可选参数
8. 参数在 match 中使用
9. 参数在 DAG 中使用
10. 复杂类型参数

---

### 16. tool 自定义工具测试 (`test_custom_tool.nx`)

**测试点**:
1. 基本 tool 定义
2. tool 参数定义
3. tool description
4. tool uses 绑定
5. MCP tool 定义
6. Python tool 定义
7. tool 调用验证
8. tool 参数验证
9. tool 返回值处理
10. tool 错误处理

---

## 执行策略

1. **按优先级顺序执行**: 从最高优先级开始，确保每个测试文件至少有 10 个测试点
2. **每个测试文件独立运行**: 使用 `nexa run test_xxx.nx` 命令
3. **记录失败测试**: 详细记录每个失败的测试点
4. **修复后重新测试**: 修复问题后重新运行所有相关测试
5. **回归测试**: 每次修复后运行所有已通过的测试

## 测试命令

```bash
# 运行单个测试
nexa run examples/test_multiline_prompt.nx

# 运行所有测试
for f in examples/test_*.nx; do echo "=== Running $f ==="; nexa run "$f"; done
```

## 里程碑

- [ ] 阶段 1: 修复多行 prompt 功能
- [ ] 阶段 2: Agent 属性和修饰器测试
- [ ] 阶段 3: Protocol 和管道操作测试
- [ ] 阶段 4: DAG 操作符测试
- [ ] 阶段 5: 控制流测试（loop, match, semantic_if）
- [ ] 阶段 6: 异常处理测试
- [ ] 阶段 7: 标准库和模块化测试
- [ ] 阶段 8: 多模态和高级功能测试