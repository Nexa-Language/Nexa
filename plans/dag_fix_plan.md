# DAG 功能修复计划

## 问题分析

### 1. 语法解析问题

**现状**：当前 grammar 定义存在优先级歧义：

```lark
?expression: fallback_expr | pipeline_expr | dag_expr | base_expr

dag_expr: dag_fork_expr | dag_merge_expr | dag_branch_expr

dag_fork_expr: base_expr ("|>>" | "||") identifier_list_as_expr
dag_merge_expr: identifier_list_as_expr ("&>>" | "&&") base_expr
dag_branch_expr: base_expr "??" base_expr ":" base_expr
```

**问题**：
- `dag_fork_expr` 和 `dag_merge_expr` 使用 `base_expr` 而非 `expression`，导致无法嵌套
- 链式表达式 `topic |>> [Researcher, Analyst] &>> Writer >> Reviewer` 无法正确解析
- `identifier_list_as_expr` 定义为独立的非终结符，可能与 `base_expr` 冲突

**解决方案**：
1. 调整 grammar 优先级，使用 `%left` 声明操作符优先级
2. 允许 DAG 表达式嵌套
3. 统一处理链式 DAG 操作

### 2. AST Transformer 问题

**现状**：
```python
def dag_fork_expr(self, args):
    input_expr = args[0]
    operator = str(args[1]) if len(args) > 1 and hasattr(args[1], 'type') else "|>>"
    agents = args[-1] if isinstance(args[-1], list) else []
```

**问题**：
- `identifier_list_as_expr` 返回的是 Token 列表，需要正确转换
- 操作符提取逻辑可能不正确（Lark 会将 literal token 作为字符串传递）

**解决方案**：
1. 修复 `identifier_list_as_expr` 返回正确的字符串列表
2. 正确处理 Lark 传递的 Token 类型

### 3. 代码生成器问题

**现状**：
```python
elif ex_type == "DAGForkExpression":
    input_str = self._resolve_expression(expr["input"])
    agents_list_str = "[ " + ", ".join([a for a in expr["agents"]]) + " ]"
    return f"dag_fanout({input_str}, {agents_list_str})"
```

**问题**：
- 无法处理链式 DAG 表达式（如 `A |>> [B, C] &>> D`）
- 需要支持 DAG 表达式的嵌套解析

**解决方案**：
1. 修改 `_resolve_expression` 支持嵌套 DAG 表达式
2. 实现正确的链式调用代码生成

### 4. 运行时模块导出问题

**现状**：`src/runtime/__init__.py` 未导出 DAG 函数

```python
__all__ = ["NexaAgent", "nexa_semantic_eval", "nexa_intent_routing", 
           "join_agents", "nexa_pipeline", "global_memory"]
```

**解决方案**：添加 DAG 相关函数的导出

---

## 修复步骤

### Step 1: 修复语法解析 (nexa_parser.py)

```lark
// 调整表达式优先级，从低到高
?expression: dag_merge_expr
           | dag_fork_expr  
           | dag_branch_expr
           | fallback_expr
           | pipeline_expr
           | base_expr

// 分叉表达式: expr |>> [Agent1, Agent2]
dag_fork_expr: expression ("|>>" | "||") identifier_list_as_expr

// 合流表达式: [Agent1, Agent2] &>> Merger
dag_merge_expr: identifier_list_as_expr ("&>>" | "&&") expression

// 条件分支: expr ?? TrueAgent : FalseAgent
dag_branch_expr: expression "??" expression ":" expression
```

### Step 2: 修复 AST Transformer (ast_transformer.py)

```python
@v_args(inline=False)
def identifier_list_as_expr(self, args):
    """将方括号内的标识符列表转换为列表"""
    # args 来自 identifier_list 规则
    return [str(arg).strip('"') for arg in args]

@v_args(inline=False)
def dag_fork_expr(self, args):
    # args[0] = input expression
    # args[1] = operator (|>> or ||)
    # args[2] = agent list
    input_expr = args[0]
    operator = str(args[1]) if len(args) > 1 else "|>>"
    agents = args[2] if len(args) > 2 else []
    
    return {
        "type": "DAGForkExpression",
        "input": input_expr,
        "agents": agents if isinstance(agents, list) else [],
        "operator": operator,
        "wait_all": operator == "|>>"
    }
```

### Step 3: 修复代码生成器 (code_generator.py)

确保 `_resolve_expression` 能处理嵌套的 DAG 表达式。

### Step 4: 更新运行时导出 (runtime/__init__.py)

```python
from .dag_orchestrator import dag_fanout, dag_merge, dag_branch, dag_parallel_map, SmartRouter

__all__ = [..., "dag_fanout", "dag_merge", "dag_branch", "dag_parallel_map", "SmartRouter"]
```

### Step 5: 编写测试

1. 单元测试每个 DAG 函数
2. 测试语法解析
3. 测试 AST 转换
4. 测试代码生成
5. 端到端测试编译和运行

---

## 测试用例

### 基础 DAG 测试

```nexa
// 简单分叉
result1 = input |>> [Agent1, Agent2];

// 简单合流  
result2 = [Agent1, Agent2] &>> Merger;

// 条件分支
result3 = input ?? TrueAgent : FalseAgent;
```

### 复杂 DAG 测试

```nexa
// 链式: 分叉后合流
result = topic |>> [Researcher, Analyst] &>> Writer;

// 嵌套: 分叉后管道
result = topic |>> [Agent1, Agent2] >> Reviewer;

// 复杂: 多层嵌套
result = input |>> [A, B] &>> C >> D;
```

---

## 执行顺序

1. ✅ 分析问题根源
2. 🔧 修复 `src/nexa_parser.py` - grammar 定义
3. 🔧 修复 `src/ast_transformer.py` - AST 转换逻辑
4. 🔧 修复 `src/code_generator.py` - 代码生成逻辑（如需要）
5. 🔧 更新 `src/runtime/__init__.py` - 导出函数
6. 🧪 编写并运行单元测试
7. 🧪 测试编译 `examples/15_dag_topology.nx`
8. 🧪 测试运行所有新功能模块
9. 📝 更新文档

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Grammar 修改可能影响现有语法 | 高 | 保持向后兼容，只添加新规则 |
| 链式表达式优先级冲突 | 中 | 使用明确的优先级声明 |
| 运行时依赖缺失 | 低 | 确保 __init__.py 正确导出 |