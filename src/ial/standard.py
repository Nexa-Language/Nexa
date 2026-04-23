"""
IAL Standard Vocabulary — 标准词汇定义

定义 Nexa IAL 的默认术语映射。
这些术语让常见的自然语言断言可以直接使用，无需自定义 Glossary。

设计原则：
- IAL引擎是固定的，新断言是词汇条目（不需要改代码）
- 标准词汇覆盖 HTTP、Agent、Protocol、Pipeline、Code 等领域
- 用户可通过 .nxintent Glossary 覆盖或扩展标准词汇
"""

from src.ial.vocabulary import Vocabulary
from src.ial.primitives import (
    Check, CheckOp, AgentAssertion, ProtocolCheck, PipelineCheck,
    SemanticCheck, Http
)


def create_standard_vocabulary() -> Vocabulary:
    """
    创建并返回包含标准术语的 Vocabulary
    
    标准词汇覆盖以下领域:
    1. Agent 验证 — "a user asks X", "the agent responds with X"
    2. Protocol 验证 — "the response is valid", "protocol check passes"
    3. Pipeline 验证 — "the pipeline produces X"
    4. HTTP 验证 — "status 2xx", "body contains X"
    5. 输出验证 — "output contains X", "output equals X"
    6. 语义验证 — "response mentions X", "output is about X"
    """
    vocab = Vocabulary()
    
    # ========================================
    # Agent 验证术语
    # ========================================
    
    vocab.register(
        term="a user asks {question}",
        means={"type": "AgentAssertion", "input": "{question}"},
        entry_type="primitive",
        description="Call the agent with the given input"
    )
    
    vocab.register(
        term="the agent responds with {text}",
        means={"type": "Check", "op": "Contains", "target": "output", "expected": "{text}"},
        entry_type="primitive",
        description="Check that agent output contains the given text"
    )
    
    vocab.register(
        term="the agent says {text}",
        means={"type": "Check", "op": "Contains", "target": "output", "expected": "{text}"},
        entry_type="primitive",
        description="Check that agent output contains the given text (alias)"
    )
    
    vocab.register(
        term="the agent output equals {text}",
        means={"type": "Check", "op": "Equals", "target": "output", "expected": "{text}"},
        entry_type="primitive",
        description="Check that agent output exactly equals the given text"
    )
    
    # ========================================
    # Protocol 验证术语
    # ========================================
    
    vocab.register(
        term="the response is valid",
        means={"type": "ProtocolCheck"},
        entry_type="primitive",
        description="Check that output conforms to the declared protocol"
    )
    
    vocab.register(
        term="protocol check passes",
        means={"type": "ProtocolCheck"},
        entry_type="primitive",
        description="Check that protocol validation passes"
    )
    
    vocab.register(
        term="the response follows {protocol}",
        means={"type": "ProtocolCheck", "protocol": "{protocol}"},
        entry_type="primitive",
        description="Check that output follows the named protocol"
    )
    
    vocab.register(
        term="valid protocol output",
        means=["the response is valid"],
        entry_type="expansion",
        description="Expand to protocol check"
    )
    
    # ========================================
    # Pipeline 验证术语
    # ========================================
    
    vocab.register(
        term="the pipeline produces {text}",
        means={"type": "Check", "op": "Contains", "target": "output", "expected": "{text}"},
        entry_type="primitive",
        description="Check that pipeline output contains the given text"
    )
    
    vocab.register(
        term="pipeline output contains {text}",
        means={"type": "Check", "op": "Contains", "target": "output", "expected": "{text}"},
        entry_type="primitive",
        description="Check that pipeline output contains the given text (alias)"
    )
    
    # ========================================
    # HTTP 验证术语 (继承 NTNT)
    # ========================================
    
    vocab.register(
        term="success response",
        means=["status 2xx", "body contains 'ok'"],
        entry_type="expansion",
        description="Standard success response pattern"
    )
    
    vocab.register(
        term="component.success_response",
        means=["status 2xx", "body contains 'ok'"],
        entry_type="expansion",
        description="Component expansion for success response"
    )
    
    vocab.register(
        term="error response",
        means=["status 4xx"],
        entry_type="expansion",
        description="Standard error response pattern"
    )
    
    vocab.register(
        term="they see {text}",
        means={"type": "Check", "op": "Contains", "target": "response.body", "expected": "{text}"},
        entry_type="primitive",
        description="Check that response body contains the given text (NTNT style)"
    )
    
    vocab.register(
        term="they see success response",
        means=["they see 'ok'", "status 2xx"],
        entry_type="expansion",
        description="NTNT-style success response assertion"
    )
    
    vocab.register(
        term="returns status {code}",
        means={"type": "Check", "op": "Equals", "target": "response.status", "expected": "{code}"},
        entry_type="primitive",
        description="Check HTTP status code"
    )
    
    vocab.register(
        term="returns {code}",
        means={"type": "Check", "op": "Equals", "target": "response.status", "expected": "{code}"},
        entry_type="primitive",
        description="Check HTTP status code (short form)"
    )
    
    # ========================================
    # 输出验证术语
    # ========================================
    
    vocab.register(
        term="response mentions {text}",
        means={"type": "SemanticCheck", "intent": "output should mention {text}"},
        entry_type="primitive",
        description="Semantic check that output mentions the given topic"
    )
    
    vocab.register(
        term="output is about {topic}",
        means={"type": "SemanticCheck", "intent": "output should be about {topic}"},
        entry_type="primitive",
        description="Semantic check that output is about the given topic"
    )
    
    vocab.register(
        term="output contains {text}",
        means={"type": "Check", "op": "Contains", "target": "output", "expected": "{text}"},
        entry_type="primitive",
        description="Check that output contains the given text"
    )
    
    vocab.register(
        term="output equals {text}",
        means={"type": "Check", "op": "Equals", "target": "output", "expected": "{text}"},
        entry_type="primitive",
        description="Check that output exactly equals the given text"
    )
    
    vocab.register(
        term="output matches {pattern}",
        means={"type": "Check", "op": "Matches", "target": "output", "expected": "{pattern}"},
        entry_type="primitive",
        description="Check that output matches the given regex pattern"
    )
    
    vocab.register(
        term="response contains {text}",
        means={"type": "Check", "op": "Contains", "target": "response.body", "expected": "{text}"},
        entry_type="primitive",
        description="Check that response body contains the given text"
    )
    
    vocab.register(
        term="clarification response",
        means={"type": "SemanticCheck", "intent": "agent asks for clarification or more details"},
        entry_type="primitive",
        description="Semantic check for clarification response"
    )
    
    # ========================================
    # Code Quality 术语
    # ========================================
    
    vocab.register(
        term="no errors",
        means={"type": "Check", "op": "NotContains", "target": "output", "expected": "error"},
        entry_type="primitive",
        description="Check that output does not contain 'error'"
    )
    
    vocab.register(
        term="no warnings",
        means={"type": "Check", "op": "NotContains", "target": "output", "expected": "warning"},
        entry_type="primitive",
        description="Check that output does not contain 'warning'"
    )
    
    vocab.register(
        term="clean output",
        means=["no errors", "no warnings"],
        entry_type="expansion",
        description="Check that output has no errors or warnings"
    )
    
    # ========================================
    # 组合术语（展示递归重写能力）
    # ========================================
    
    vocab.register(
        term="weather information",
        means={"type": "SemanticCheck", "intent": "output contains weather data like temperature, conditions, forecast"},
        entry_type="primitive",
        description="Semantic check for weather-related output"
    )
    
    vocab.register(
        term="helpful response",
        means={"type": "SemanticCheck", "intent": "response is helpful, informative, and addresses the user's question"},
        entry_type="primitive",
        description="Semantic check for helpful response quality"
    )
    
    vocab.register(
        term="structured output",
        means={"type": "Check", "op": "IsType", "target": "output", "expected": "dict"},
        entry_type="primitive",
        description="Check that output is a structured dict/object"
    )
    
    return vocab