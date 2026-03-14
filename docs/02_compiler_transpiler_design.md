# Nexa v0.1 转译器架构设计 (Compiler/Transpiler - QA 审计版)

在 v0.1 阶段，Nexa 的核心是一个 Source-to-Source 的转译器（Nexa -> Python），直接基于成熟的 LLM SDK（例如 OpenAI Python SDK、Pydantic、Tenacity）来提供严格、容错的执行环境。

## 1. 词法与语法分析 (Frontend)

### 解析器选型：Lark (Python)
**选型理由：**
为了保证 MVP 阶段的极快迭代速度和代码的极简主义，采用 Python 编写的 **Lark** 作为解析器。
1. **无需编译配置：** Lark 纯 Python 实现，随写随测，符合 "Start Small" 策略。
2. **Earley 算法：** Lark 默认的 Earley 算法能处理任何上下文无关文法，开发者无需处理左递归等繁琐问题。
3. **AST 自动生成：** Lark 直接输出 Python 的类结构 AST，我们定义了明确的 Statement 和 Expression 边界，分离赋值、调用和逻辑判断。

## 2. AST (抽象语法树) 设计

以 `result = Researcher.run("...")` 为例，经过修订后的 AST 采用严密的二元分离设计：

```json
{
  "type": "AssignmentStatement",
  "target": "result",
  "value": {
    "type": "MethodCallExpression",
    "object": "Researcher",
    "method": "run",
    "arguments": [
      {
        "type": "StringLiteral",
        "value": "Search the latest news..."
      }
    ]
  }
}
```

## 3. 代码生成 (Backend) 与防幻觉健壮性机制

转译器后端使用 Visitor 模式遍历 AST，并生成健壮的 Python 代码。这是 v0.1 最关键的一环：不能只生成“玩具代码”，必须生成**生产级脚本**。

### 1. 注入机制 (Boilerplate Injection)
生成的 Python 脚本顶部会自动注入以下组件：
*   OpenAI Client 初始化代码。
*   基于 `@retry` (比如 `tenacity` 库) 的异常重试装饰器。
*   通用的 Agent Runtime Class (`__NexaAgent`)，负责管理 `messages` 对话流和自动化工具调度（Tools Binding & Function calling）。

### 2. `tool` 与 `agent` 的映射
*   `tool` 被映射为一个 Python 占位函数（需由开发者在生成的 Python 侧补充真实逻辑），并附带 Pydantic `BaseModel` 描述参数，生成 OpenAI 兼容的 schema。
*   `agent` 实例化为 `__NexaAgent` 的对象，注入 system prompt 和相关 tool schemas。

### 3. `semantic_if` 的防瘫痪机制 (Resilience)
LLM 不是确定的 CPU，API 可能会抛出超时，模型可能没有按 Structured Outputs 规范返回。Nexa 必须在底层消化这些恶劣情况。

代码生成器在遇到 `semantic_if` 时，会在 Python 侧生成一个挂载了**重试策略与降级兜底**的求值函数：
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10), retry=retry_if_exception_type(Exception))
def __nexa_semantic_eval_with_retry(condition: str, target_text: str) -> bool:
    try:
        # 强制结构化输出解析
        resp = openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Evaluate condition: {condition}"},
                {"role": "user", "content": target_text}
            ],
            response_format=SemanticEvalSchema,
            timeout=10.0
        )
        return resp.choices[0].message.parsed.matched
    except Exception as e:
        # 重试 3 次后抛出异常，触发兜底
        raise e

def __nexa_semantic_eval(condition: str, target_text: str) -> bool:
    try:
        return __nexa_semantic_eval_with_retry(condition, target_text)
    except Exception:
        # 降级：如果不可服务或彻底幻觉，默认判定失败，保障主流程不断。
        return False
```

通过这套机制，Nexa 的代码能够在复杂且不稳定的现实大模型网络环境中，保持高可用性。这标志着语言从“伪概念”走向了真正的“架构设计”。
