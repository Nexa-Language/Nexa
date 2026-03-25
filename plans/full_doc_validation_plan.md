# 完整文档验证与编译器同步计划

## 目标
1. 验证所有文档示例代码能够正确解析和编译
2. 同步语法修复到 Rust AVM，确保 Python 和 Rust 编译器行为一致
3. 更新项目文档（MEMORY_BANK.md, README.md, roadmap）

## 当前状态
- Python 编译器已支持 31/31 文档示例（100% 通过率）
- 新增语法支持：
  - DAG 链式操作符 (`|>>`, `&>>`, `??`)
  - semantic_if 表达式形式
  - 字符串拼接运算符 (`+`)
  - 传统 if 语句和比较运算符
  - fallback 语法
  - flow 参数声明
  - 整数/布尔属性值
  - print 语句
  - 标准库调用

---

## Phase 1: 剩余文档验证

### 1.1 待验证文档列表
| 文档 | 状态 | 示例数量估计 |
|------|------|-------------|
| reference.md | 待验证 | ~50 |
| stdlib_reference.md | 待验证 | ~30 |
| cli_reference.md | 待验证 | ~10 |
| part5_compiler.md | 待验证 | ~5 |
| part5_enterprise.md | 待验证 | ~10 |
| part6_best_practices.md | 待验证 | ~15 |

### 1.2 需提取的示例类型
- 词法结构示例（标识符、关键字、字面量）
- 顶层声明示例（agent, tool, protocol, flow, test）
- 表达式系统示例（管道、DAG、fallback）
- 语句示例（赋值、控制流、异常处理）
- 标准库调用示例
- CLI 命令示例

### 1.3 新发现的语法特性（来自 reference.md）
从 reference.md 中发现的新语法：
1. **Agent 修饰器**: `@limit(max_tokens=2048)`, `@timeout(seconds=30)`, `@retry(max_attempts=3)`
2. **Tool MCP 声明**: `tool WebSearch { mcp: "..." }`
3. **Tool Python 声明**: `tool MyTool { python: "..." }`
4. **正则表达式字面量**: `r"\d{4}-\d{2}-\d{2}"`
5. **枚举类型标注**: `status: "active|inactive|pending"`
6. **DAG 操作符 `||`**: 并行执行，不等待结果
7. **DAG 操作符 `&&`**: 共识合流
8. **文档注释**: `/// 文档注释`

---

## Phase 2: Rust AVM 同步

### 2.1 需修改的文件
| 文件 | 修改内容 |
|------|----------|
| `avm/src/compiler/lexer.rs` | 新增 token 类型：`\|\|`, `&&`, `??`, `r"..."`, `@` |
| `avm/src/compiler/parser.rs` | 新增语法规则：DAG 操作符、semantic_if、if 语句等 |
| `avm/src/compiler/ast.rs` | 新增 AST 节点类型 |

### 2.2 语法规则对照表
| 语法特性 | Python (lark) | Rust (nom/chumsky) |
|----------|---------------|-------------------|
| DAG 分叉 `A \|>> [B, C]` | `dag_fork_expr` | 待实现 |
| DAG 合流 `[A, B] &>> C` | `dag_merge_expr` | 待实现 |
| DAG 链式 `A \|>> [B] &>> C` | `dag_chain_expr` | 待实现 |
| DAG 条件 `A ?? { ... }` | `dag_branch_expr` | 待实现 |
| semantic_if 表达式 | `semantic_if_expr` | 待实现 |
| 字符串拼接 `A + B` | `binary_expr` | 待实现 |
| if 语句 | `if_stmt` | 待实现 |
| 比较运算符 | `comparison_op` | 待实现 |
| fallback 列表 | `fallback_list` | 待实现 |
| Agent 修饰器 | `agent_modifier` | 待实现 |
| 正则字面量 | `REGEX_LITERAL` | 待实现 |

### 2.3 实现优先级
1. **P0 - 核心语法**: DAG 操作符、if 语句、比较运算符
2. **P1 - 重要特性**: semantic_if 表达式、字符串拼接、fallback
3. **P2 - 增强特性**: Agent 修饰器、正则字面量、MCP tool

---

## Phase 3: 文档更新

### 3.1 MEMORY_BANK.md 更新
新增章节记录：
- v1.0.x 语法特性完成列表
- DAG 操作符实现细节
- Python/Rust 编译器同步状态

### 3.2 README.md 更新
- 更新语法特性列表
- 添加新操作符示例
- 更新测试覆盖率

### 3.3 roadmap 更新
- 标记已完成特性
- 更新 Rust AVM 进度
- 添加下一阶段目标

---

## Phase 4: 测试与验证

### 4.1 测试矩阵
| 编译器 | 单元测试 | 集成测试 | 文档示例测试 |
|--------|----------|----------|--------------|
| Python | ✅ 28 | ✅ 15 | ✅ 31+ |
| Rust | ✅ 110 | 待添加 | 待添加 |

### 4.2 验收标准
- [ ] Python 编译器：所有文档示例通过
- [ ] Rust AVM：所有语法特性与 Python 一致
- [ ] 文档更新完成
- [ ] Git commit 提交

---

## 执行计划

### Step 1: 提取剩余文档示例 (Code 模式)
1. 读取 reference.md, stdlib_reference.md 等文件
2. 提取所有 Nexa 代码块
3. 更新 tests/test_doc_examples.py

### Step 2: 修复 Python 编译器 (Code 模式)
1. 添加缺失的语法规则
2. 更新 AST transformer
3. 更新 code generator

### Step 3: 同步 Rust AVM (Code 模式)
1. 更新 lexer.rs
2. 更新 parser.rs
3. 更新 ast.rs
4. 运行 Rust 测试

### Step 4: 更新文档 (Code 模式)
1. 更新 MEMORY_BANK.md
2. 更新 README.md
3. 更新 roadmap

### Step 5: 最终验证 (Code 模式)
1. 运行所有测试
2. Git commit

---

## 预估工作量
- Phase 1: 提取剩余文档示例
- Phase 2: Rust AVM 同步
- Phase 3: 文档更新
- Phase 4: 测试验证

**总计**: 完整文档验证与编译器同步