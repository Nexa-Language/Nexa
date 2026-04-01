# Semantic Types 实施计划

## 背景

根据论文 `dsl_design.tex` 第 78 行描述：
> Semantic Types like `Summary = str @ "A concise summary"` combine base types with semantic constraints for automatic validation and guided generation.

论文 `appendix/grammar.tex` 第 273-286 行定义了语法：
```
semantic_type   ::= base_type "@" semantic_constraint
base_type       ::= "str" | "int" | "float" | "bool" 
                  | "list" "[" type "]" 
                  | "dict" "[" type "," type "]"
semantic_constraint ::= STRING_LITERAL  (* Natural language constraint *)
```

## 目标

实现语义类型系统，允许开发者定义带有语义约束的类型，用于：
1. 自动验证 LLM 输出是否符合语义约束
2. 引导 LLM 生成符合约束的内容
3. 与 protocol 系统集成，增强类型安全

## 语法设计

### 类型定义语法
```nexa
// 基本语义类型
type Summary = str @ "A concise summary of the content"
type Sentiment = str @ "One of: positive, negative, neutral"
type Confidence = float @ "A value between 0.0 and 1.0"

// 复合语义类型
type AnalysisResult = {
    summary: Summary,
    sentiment: Sentiment,
    confidence: Confidence
}
```

### 使用语法
```nexa
protocol AnalysisReport {
    summary: Summary,
    sentiment: Sentiment,
    confidence: Confidence
}

agent Analyzer implements AnalysisReport {
    prompt: "Analyze the given text and provide structured output."
}
```

## 实施步骤

### Phase 1: Parser 层扩展

**文件**: `src/nexa_parser.py`

添加新的 EBNF 规则：
```python
// 语义类型定义
type_decl: "type" IDENTIFIER "=" semantic_type

semantic_type: base_type "@" STRING_LITERAL
             | base_type  // 普通类型

base_type: "str" | "int" | "float" | "bool"
         | "list" "[" type_ref "]"
         | "dict" "[" type_ref "," type_ref "]"
         | IDENTIFIER  // 引用已定义的类型

type_ref: IDENTIFIER
```

### Phase 2: AST Transformer 扩展

**文件**: `src/ast_transformer.py`

添加新的 AST 节点：
```python
@v_args(inline=False)
def type_decl(self, args):
    """语义类型声明"""
    name = str(args[0])
    type_def = args[1]
    return {
        "type": "TypeDeclaration",
        "name": name,
        "definition": type_def
    }

@v_args(inline=False)
def semantic_type(self, args):
    """语义类型定义"""
    base_type = args[0]
    if len(args) > 1:
        constraint = str(args[1]).strip('"')
        return {
            "type": "SemanticType",
            "base_type": base_type,
            "constraint": constraint
        }
    return base_type
```

### Phase 3: Code Generator 扩展

**文件**: `src/code_generator.py`

生成 Pydantic 验证器：
```python
def _generate_type_definition(self, type_decl):
    """生成语义类型的 Pydantic 验证器"""
    name = type_decl["name"]
    definition = type_decl["definition"]
    
    if definition.get("type") == "SemanticType":
        base_type = definition["base_type"]
        constraint = definition["constraint"]
        
        # 生成带有语义约束的 Pydantic 字段
        return f'''
class {name}(str):
    """Semantic type with constraint: {constraint}"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        # 语义验证将由 LLM 在运行时执行
        return v
'''
```

### Phase 4: 运行时验证器

**文件**: `src/runtime/semantic_types.py` (新建)

```python
from pydantic import BaseModel, validator
from typing import Type, Any

class SemanticTypeValidator:
    """语义类型验证器"""
    
    def __init__(self, base_type: Type, constraint: str):
        self.base_type = base_type
        self.constraint = constraint
    
    def validate(self, value: Any, llm_client=None) -> bool:
        """验证值是否符合语义约束"""
        # 基本类型检查
        if not isinstance(value, self.base_type):
            return False
        
        # 如果提供了 LLM 客户端，进行语义验证
        if llm_client:
            prompt = f"""
            Does the following value satisfy this constraint: "{self.constraint}"
            Value: {value}
            Answer only: true or false
            """
            result = llm_client.generate(prompt)
            return "true" in result.lower()
        
        return True  # 没有 LLM 时只做基本类型检查

# 内置语义类型
SUMMARY_TYPE = SemanticTypeValidator(str, "A concise summary")
SENTIMENT_TYPE = SemanticTypeValidator(str, "One of: positive, negative, neutral")
CONFIDENCE_TYPE = SemanticTypeValidator(float, "A value between 0.0 and 1.0")
```

## 示例代码

### 示例 1: 基本语义类型
```nexa
type Summary = str @ "A concise summary"
type Sentiment = str @ "positive, negative, or neutral"

agent SentimentAnalyzer implements SentimentReport {
    prompt: "Analyze sentiment of the input text."
}

protocol SentimentReport {
    summary: Summary,
    sentiment: Sentiment
}

flow analyze_sentiment(text: str) {
    result = text >> SentimentAnalyzer
    return result
}
```

### 示例 2: 与 Protocol 集成
```nexa
type ResearchTopic = str @ "A specific research topic"
type PaperCount = int @ "Number between 1 and 100"

protocol ResearchQuery {
    topic: ResearchTopic,
    max_papers: PaperCount
}

agent ResearchAssistant implements ResearchQuery {
    prompt: "Search for papers on the given topic."
}
```

## 测试计划

1. **Parser 测试**: 验证语义类型语法正确解析
2. **AST 测试**: 验证 AST 节点正确生成
3. **Code Generator 测试**: 验证生成的 Python 代码
4. **Runtime 测试**: 验证语义约束在运行时正确执行
5. **集成测试**: 验证与 protocol 和 agent 系统的集成

## 时间估计

- Parser 层: 1-2 小时
- AST Transformer: 1-2 小时
- Code Generator: 2-3 小时
- Runtime Validator: 2-3 小时
- 测试编写: 2-3 小时
- 文档更新: 1 小时

**总计**: 约 10-15 小时

## 优先级

**高优先级** - 这是论文中明确描述但尚未实现的关键特性，对论文的完整性很重要。