"""
IAL Engine Tests — Intent Assertion Language 引擎测试

测试覆盖:
1. Vocabulary 术语存储和模式匹配
2. Resolve 递归术语重写引擎
3. Primitives 原语类型定义
4. Execute 原语执行引擎
5. Standard 标准词汇定义
"""

import pytest
from src.ial.primitives import (
    CheckOp, Check, AgentAssertion, ProtocolCheck, PipelineCheck,
    SemanticCheck, Http, Cli, ReadFile, FunctionCall, PropertyCheck,
    InvariantCheck, CheckResult, ScenarioResult, FeatureResult
)
from src.ial.vocabulary import Vocabulary, TermEntry
from src.ial.resolve import resolve, resolve_scenario_assertions, MAX_RECURSION_DEPTH
from src.ial.execute import execute_primitive, execute_primitives
from src.ial.standard import create_standard_vocabulary
from src.ial import create_vocabulary


# ========================================
# 1. Primitives Tests
# ========================================

class TestCheckOp:
    """CheckOp 枚举测试"""
    
    def test_all_check_ops_exist(self):
        """所有 CheckOp 都存在"""
        expected_ops = [
            "equals", "not_equals", "contains", "not_contains",
            "matches", "exists", "not_exists", "less_than", "greater_than",
            "in_range", "starts_with", "ends_with", "is_type", "has_length"
        ]
        for op_name in expected_ops:
            assert hasattr(CheckOp, op_name.upper()) or CheckOp(op_name) in CheckOp
    
    def test_check_op_values(self):
        """CheckOp 值正确"""
        assert CheckOp.Equals.value == "equals"
        assert CheckOp.Contains.value == "contains"
        assert CheckOp.InRange.value == "in_range"


class TestCheck:
    """Check 原语测试"""
    
    def test_check_creation(self):
        """创建 Check 原语"""
        check = Check(op=CheckOp.Contains, target="output", expected="weather")
        assert check.op == CheckOp.Contains
        assert check.target == "output"
        assert check.expected == "weather"
    
    def test_check_repr(self):
        """Check repr 输出"""
        check = Check(op=CheckOp.Equals, target="status", expected=200)
        assert "equals" in repr(check)
        assert "status" in repr(check)
    
    def test_check_with_range(self):
        """Check with InRange"""
        check = Check(op=CheckOp.InRange, target="response.status", expected=(200, 299))
        assert check.expected == (200, 299)


class TestAgentAssertion:
    """AgentAssertion 原语测试"""
    
    def test_agent_assertion_creation(self):
        """创建 AgentAssertion"""
        assertion = AgentAssertion(
            agent_name="WeatherBot",
            input_text="What is the weather?",
            checks=[Check(op=CheckOp.Contains, target="output", expected="weather")]
        )
        assert assertion.agent_name == "WeatherBot"
        assert assertion.input_text == "What is the weather?"
        assert len(assertion.checks) == 1
    
    def test_agent_assertion_repr(self):
        """AgentAssertion repr"""
        assertion = AgentAssertion(agent_name="TestBot", input_text="hello")
        assert "TestBot" in repr(assertion)


class TestProtocolCheck:
    """ProtocolCheck 原语测试"""
    
    def test_protocol_check_creation(self):
        """创建 ProtocolCheck"""
        check = ProtocolCheck(protocol_name="WeatherReport")
        assert check.protocol_name == "WeatherReport"
    
    def test_protocol_check_with_field_checks(self):
        """ProtocolCheck with field checks"""
        check = ProtocolCheck(
            protocol_name="WeatherReport",
            field_checks=[
                Check(op=CheckOp.Exists, target="city", expected=None),
                Check(op=CheckOp.Contains, target="temperature", expected="°")
            ]
        )
        assert len(check.field_checks) == 2


class TestSemanticCheck:
    """SemanticCheck 原语测试"""
    
    def test_semantic_check_creation(self):
        """创建 SemanticCheck"""
        check = SemanticCheck(actual="It is sunny", intent="weather information")
        assert check.intent == "weather information"
    
    def test_semantic_check_repr(self):
        """SemanticCheck repr"""
        check = SemanticCheck(actual="", intent="weather information")
        assert "weather" in repr(check)


# ========================================
# 2. Vocabulary Tests
# ========================================

class TestVocabulary:
    """Vocabulary 术语存储和模式匹配测试"""
    
    def test_register_exact_term(self):
        """注册精确术语"""
        vocab = Vocabulary()
        vocab.register("response is valid", "protocol check passes", entry_type="expansion")
        
        result = vocab.lookup("response is valid")
        assert result is not None
        entry, params = result
        assert entry.term == "response is valid"
        assert params == {}
    
    def test_register_pattern_term(self):
        """注册模式术语（含参数）"""
        vocab = Vocabulary()
        vocab.register("they see {text}", "body contains {text}", entry_type="expansion")
        
        result = vocab.lookup("they see hello")
        assert result is not None
        entry, params = result
        assert entry.term == "they see {text}"
        assert params == {"text": "hello"}
    
    def test_register_multiple_params(self):
        """注册多参数模式"""
        vocab = Vocabulary()
        vocab.register("{user} asks {question}", "agent {user} run with input {question}", entry_type="expansion")
        
        result = vocab.lookup("Alice asks weather")
        assert result is not None
        entry, params = result
        assert params == {"user": "Alice", "question": "weather"}
    
    def test_lookup_no_match(self):
        """查找无匹配"""
        vocab = Vocabulary()
        vocab.register("they see {text}", "body contains {text}", entry_type="expansion")
        
        result = vocab.lookup("unknown assertion")
        assert result is None
    
    def test_case_insensitive_lookup(self):
        """大小写不敏感查找"""
        vocab = Vocabulary()
        vocab.register("Response Is Valid", "protocol check", entry_type="expansion")
        
        result = vocab.lookup("response is valid")
        assert result is not None
    
    def test_expand_with_params(self):
        """带参数展开术语"""
        vocab = Vocabulary()
        vocab.register("they see {text}", "body contains {text}", entry_type="expansion")
        
        lookup_result = vocab.lookup("they see hello")
        assert lookup_result is not None
        entry, params = lookup_result
        
        expanded = vocab.expand_with_params(entry, params)
        assert expanded == ["body contains hello"]
    
    def test_expand_list_with_params(self):
        """带参数展开列表术语"""
        vocab = Vocabulary()
        vocab.register("success response", ["status 2xx", "body contains 'ok'"], entry_type="expansion")
        
        lookup_result = vocab.lookup("success response")
        assert lookup_result is not None
        entry, params = lookup_result
        
        expanded = vocab.expand_with_params(entry, params)
        assert expanded == ["status 2xx", "body contains 'ok'"]
    
    def test_all_terms(self):
        """获取所有术语"""
        vocab = Vocabulary()
        vocab.register("exact term", "expansion", entry_type="expansion")
        vocab.register("pattern {x}", "expansion {x}", entry_type="expansion")
        
        all_terms = vocab.all_terms()
        assert len(all_terms) == 2
    
    def test_term_count(self):
        """术语计数"""
        vocab = Vocabulary()
        vocab.register("term1", "exp1", entry_type="expansion")
        vocab.register("term2", "exp2", entry_type="expansion")
        vocab.register("pattern {x}", "exp {x}", entry_type="expansion")
        
        assert vocab.term_count() == 3


# ========================================
# 3. Resolve Tests
# ========================================

class TestResolve:
    """递归术语重写引擎测试"""
    
    def test_resolve_with_vocabulary(self):
        """通过词汇表解析术语"""
        vocab = Vocabulary()
        vocab.register("they see {text}", {"type": "Check", "op": "Contains", "target": "response.body", "expected": "{text}"}, entry_type="primitive")
        
        primitives = resolve("they see hello", vocab)
        assert len(primitives) == 1
        assert isinstance(primitives[0], Check)
        assert primitives[0].op == CheckOp.Contains
        assert primitives[0].target == "response.body"
        assert primitives[0].expected == "hello"
    
    def test_resolve_expansion_chain(self):
        """递归解析展开链"""
        vocab = Vocabulary()
        vocab.register("success response", ["status 2xx", "body contains 'ok'"], entry_type="expansion")
        
        primitives = resolve("success response", vocab)
        # "status 2xx" → Check(InRange, "response.status", (200, 209))
        # "body contains 'ok'" → Check(Contains, "response.body", "ok")
        assert len(primitives) == 2
    
    def test_resolve_standard_assertion_status(self):
        """解析标准断言 — status 2xx"""
        vocab = Vocabulary()
        primitives = resolve("status 2xx", vocab)
        assert len(primitives) == 1
        assert primitives[0].op == CheckOp.InRange
        assert primitives[0].target == "response.status"
    
    def test_resolve_standard_assertion_contains(self):
        """解析标准断言 — output contains 'text'"""
        vocab = Vocabulary()
        primitives = resolve("output contains 'weather'", vocab)
        assert len(primitives) == 1
        assert primitives[0].op == CheckOp.Contains
        assert primitives[0].expected == "weather"
    
    def test_resolve_standard_assertion_equals(self):
        """解析标准断言 — output equals 'hello'"""
        vocab = Vocabulary()
        primitives = resolve("output equals 'hello'", vocab)
        assert len(primitives) == 1
        assert primitives[0].op == CheckOp.Equals
    
    def test_resolve_standard_assertion_matches(self):
        """解析标准断言 — output matches 'pattern'"""
        vocab = Vocabulary()
        primitives = resolve("output matches '^success'", vocab)
        assert len(primitives) == 1
        assert primitives[0].op == CheckOp.Matches
    
    def test_resolve_standard_assertion_exists(self):
        """解析标准断言 — field exists"""
        vocab = Vocabulary()
        primitives = resolve("output exists", vocab)
        assert len(primitives) == 1
        assert primitives[0].op == CheckOp.Exists
    
    def test_resolve_semantic_fallback(self):
        """无法解析时生成语义检查"""
        vocab = Vocabulary()
        primitives = resolve("the output is about weather patterns", vocab)
        assert len(primitives) == 1
        assert isinstance(primitives[0], SemanticCheck)
        assert primitives[0].intent == "the output is about weather patterns"
    
    def test_resolve_max_depth(self):
        """超过最大递归深度时报错"""
        vocab = Vocabulary()
        # 创建循环定义: A → B, B → A
        vocab.register("term A", ["term B"], entry_type="expansion")
        vocab.register("term B", ["term A"], entry_type="expansion")
        
        with pytest.raises(RecursionError):
            resolve("term A", vocab)
    
    def test_resolve_scenario_assertions(self):
        """解析 Scenario 的多个断言"""
        vocab = Vocabulary()
        assertions = [
            "the agent responds with 'weather'",
            "the response is valid"
        ]
        primitives = resolve_scenario_assertions(assertions, vocab)
        assert len(primitives) >= 2
    
    def test_resolve_with_standard_vocabulary(self):
        """使用标准词汇表解析"""
        vocab = create_standard_vocabulary()
        
        # "the agent responds with 'weather'" → Check(Contains, "output", "weather")
        primitives = resolve("the agent responds with 'weather'", vocab)
        assert len(primitives) >= 1
        # 应包含 Contains check
        contains_checks = [p for p in primitives if isinstance(p, Check) and p.op == CheckOp.Contains]
        assert len(contains_checks) >= 1
    
    def test_resolve_standard_vocabulary_they_see(self):
        """标准词汇表 — they see"""
        vocab = create_standard_vocabulary()
        
        primitives = resolve("they see hello", vocab)
        assert len(primitives) >= 1


# ========================================
# 4. Execute Tests
# ========================================

class TestExecute:
    """原语执行引擎测试"""
    
    def test_execute_check_contains_pass(self):
        """执行 Contains 检查 — 通过"""
        check = Check(op=CheckOp.Contains, target="output", expected="weather")
        context = {"output": "The weather in Beijing is sunny"}
        
        result = execute_primitive(check, context)
        assert result.passed
        assert "weather" in result.message
    
    def test_execute_check_contains_fail(self):
        """执行 Contains 检查 — 失败"""
        check = Check(op=CheckOp.Contains, target="output", expected="error")
        context = {"output": "Everything is fine"}
        
        result = execute_primitive(check, context)
        assert not result.passed
    
    def test_execute_check_equals_pass(self):
        """执行 Equals 检查 — 通过"""
        check = Check(op=CheckOp.Equals, target="status", expected=200)
        context = {"status": 200}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_equals_fail(self):
        """执行 Equals 检查 — 失败"""
        check = Check(op=CheckOp.Equals, target="status", expected=200)
        context = {"status": 404}
        
        result = execute_primitive(check, context)
        assert not result.passed
    
    def test_execute_check_in_range_pass(self):
        """执行 InRange 检查 — 通过"""
        check = Check(op=CheckOp.InRange, target="response.status", expected=(200, 299))
        context = {"response": {"status": 200}}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_in_range_fail(self):
        """执行 InRange 检查 — 失败"""
        check = Check(op=CheckOp.InRange, target="response.status", expected=(200, 299))
        context = {"response": {"status": 500}}
        
        result = execute_primitive(check, context)
        assert not result.passed
    
    def test_execute_check_exists(self):
        """执行 Exists 检查"""
        check = Check(op=CheckOp.Exists, target="output", expected=None)
        context = {"output": "some data"}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_not_exists(self):
        """执行 NotExists 检查"""
        check = Check(op=CheckOp.NotExists, target="missing_field", expected=None)
        context = {}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_matches(self):
        """执行 Matches 检查"""
        check = Check(op=CheckOp.Matches, target="output", expected="^success")
        context = {"output": "success response"}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_less_than(self):
        """执行 LessThan 检查"""
        check = Check(op=CheckOp.LessThan, target="count", expected=10)
        context = {"count": 5}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_greater_than(self):
        """执行 GreaterThan 检查"""
        check = Check(op=CheckOp.GreaterThan, target="score", expected=80)
        context = {"score": 95}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_target_not_found(self):
        """目标值不存在 → 失败"""
        check = Check(op=CheckOp.Equals, target="missing.target", expected="value")
        context = {}
        
        result = execute_primitive(check, context)
        assert not result.passed
        assert "not found" in result.message
    
    def test_execute_nested_target(self):
        """嵌套目标值提取"""
        check = Check(op=CheckOp.Equals, target="response.status", expected=200)
        context = {"response": {"status": 200, "body": "OK"}}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_agent_assertion_skipped(self):
        """Agent 断言 — 无 runtime 时 skipped"""
        assertion = AgentAssertion(agent_name="WeatherBot", input_text="hello")
        context = {}
        
        result = execute_primitive(assertion, context)
        assert result.passed  # skipped counts as not failed
        assert "skipped" in result.message.lower()
    
    def test_execute_protocol_check_basic(self):
        """Protocol 检查 — 基本验证"""
        check = ProtocolCheck(protocol_name="WeatherReport")
        context = {"output": {"city": "Beijing"}}
        
        result = execute_primitive(check, context)
        assert result.passed  # basic check: data exists
    
    def test_execute_protocol_check_no_data(self):
        """Protocol 检查 — 无数据"""
        check = ProtocolCheck(protocol_name="WeatherReport")
        context = {}
        
        result = execute_primitive(check, context)
        assert not result.passed
    
    def test_execute_semantic_check_heuristic(self):
        """语义检查 — 启发式匹配"""
        check = SemanticCheck(actual="The weather is sunny", intent="'weather' and 'sunny'")
        context = {}
        
        result = execute_primitive(check, context)
        # 启发式匹配应该能找到关键词
        assert result.passed
    
    def test_execute_primitives_list(self):
        """执行原语列表"""
        primitives = [
            Check(op=CheckOp.Contains, target="output", expected="hello"),
            Check(op=CheckOp.Equals, target="count", expected=5),
        ]
        context = {"output": "hello world", "count": 5}
        
        results = execute_primitives(primitives, context)
        assert len(results) == 2
        assert all(r.passed for r in results)
    
    def test_execute_check_starts_with(self):
        """执行 StartsWith 检查"""
        check = Check(op=CheckOp.StartsWith, target="output", expected="success")
        context = {"output": "success response"}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_ends_with(self):
        """执行 EndsWith 检查"""
        check = Check(op=CheckOp.EndsWith, target="output", expected="done")
        context = {"output": "task done"}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_is_type(self):
        """执行 IsType 检查"""
        check = Check(op=CheckOp.IsType, target="output", expected="str")
        context = {"output": "hello"}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_has_length(self):
        """执行 HasLength 检查"""
        check = Check(op=CheckOp.HasLength, target="output", expected=5)
        context = {"output": "hello"}
        
        result = execute_primitive(check, context)
        assert result.passed
    
    def test_execute_check_not_contains(self):
        """执行 NotContains 检查"""
        check = Check(op=CheckOp.NotContains, target="output", expected="error")
        context = {"output": "Everything is fine"}
        
        result = execute_primitive(check, context)
        assert result.passed


# ========================================
# 5. Standard Vocabulary Tests
# ========================================

class TestStandardVocabulary:
    """标准词汇定义测试"""
    
    def test_create_standard_vocabulary(self):
        """创建标准词汇表"""
        vocab = create_standard_vocabulary()
        assert vocab.term_count() > 0
    
    def test_standard_agent_terms(self):
        """标准 Agent 术语"""
        vocab = create_standard_vocabulary()
        
        # "the agent responds with 'text'" → Contains check
        result = vocab.lookup("the agent responds with hello")
        assert result is not None
    
    def test_standard_protocol_terms(self):
        """标准 Protocol 术语"""
        vocab = create_standard_vocabulary()
        
        result = vocab.lookup("the response is valid")
        assert result is not None
    
    def test_standard_http_terms(self):
        """标准 HTTP 术语"""
        vocab = create_standard_vocabulary()
        
        result = vocab.lookup("success response")
        assert result is not None
    
    def test_standard_they_see_term(self):
        """标准 they see 术语"""
        vocab = create_standard_vocabulary()
        
        result = vocab.lookup("they see hello")
        assert result is not None
    
    def test_standard_pipeline_terms(self):
        """标准 Pipeline 术语"""
        vocab = create_standard_vocabulary()
        
        result = vocab.lookup("the pipeline produces weather")
        assert result is not None
    
    def test_standard_semantic_terms(self):
        """标准语义术语"""
        vocab = create_standard_vocabulary()
        
        result = vocab.lookup("output is about weather")
        assert result is not None
    
    def test_standard_clean_output(self):
        """标准 clean output 术语"""
        vocab = create_standard_vocabulary()
        
        result = vocab.lookup("clean output")
        assert result is not None
    
    def test_create_vocabulary_api(self):
        """公共 API create_vocabulary"""
        vocab = create_vocabulary()
        assert vocab.term_count() > 0


# ========================================
# 6. Result Types Tests
# ========================================

class TestResultTypes:
    """结果类型测试"""
    
    def test_check_result_creation(self):
        """创建 CheckResult"""
        result = CheckResult(
            passed=True,
            primitive=Check(op=CheckOp.Contains, target="output", expected="hello"),
            message="Contains: 'hello' in 'hello world'"
        )
        assert result.passed
        assert "hello" in result.message
    
    def test_check_result_repr_pass(self):
        """通过结果 repr"""
        result = CheckResult(
            passed=True,
            primitive=Check(op=CheckOp.Equals, target="status", expected=200),
            message="OK"
        )
        assert "✓" in repr(result)
    
    def test_check_result_repr_fail(self):
        """失败结果 repr"""
        result = CheckResult(
            passed=False,
            primitive=Check(op=CheckOp.Equals, target="status", expected=200),
            message="Failed"
        )
        assert "✗" in repr(result)
    
    def test_scenario_result(self):
        """ScenarioResult"""
        result = ScenarioResult(
            scenario_name="Weather query",
            feature_id="feature.weather_bot"
        )
        assert result.scenario_name == "Weather query"
        assert result.passed  # default True
    
    def test_feature_result(self):
        """FeatureResult"""
        result = FeatureResult(
            feature_id="feature.weather_bot",
            feature_name="Weather Bot"
        )
        assert result.feature_id == "feature.weather_bot"