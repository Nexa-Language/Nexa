"""
Nexa Error Propagation Tests — ? 操作符和 otherwise 内联错误处理

测试覆盖:
1. NexaResult/NexaOption 创建和操作
2. ? 操作符传播测试（成功路径 + 失败传播）
3. otherwise 内联处理测试（值 fallback + 变量 fallback + Agent fallback + 块 fallback）
4. ErrorPropagation 异常捕获测试
5. 与 try/catch 共存测试
6. 与 NexaResult.ok/err 集成测试
7. 向后兼容测试（字符串结果自动包装）
8. propagate_or_else 函数测试
9. try_propagate 函数测试
10. wrap_agent_result 函数测试
"""

import pytest
from src.runtime.result_types import (
    NexaResult, NexaOption, ErrorPropagation,
    propagate_or_else, try_propagate, wrap_agent_result,
    _handle_otherwise
)


# ============================================================
# 1. NexaResult 创建和操作测试
# ============================================================

class TestNexaResultCreation:
    """NexaResult 创建和基本属性测试"""
    
    def test_ok_creation(self):
        result = NexaResult.ok("success data")
        assert result.is_ok is True
        assert result.is_err is False
        assert result.value == "success data"
    
    def test_err_creation(self):
        result = NexaResult.err("something went wrong")
        assert result.is_ok is False
        assert result.is_err is True
        assert result.error == "something went wrong"
    
    def test_ok_with_none_value(self):
        result = NexaResult.ok(None)
        assert result.is_ok is True
        assert result.value is None
    
    def test_err_with_none_error(self):
        result = NexaResult.err(None)
        assert result.is_err is True
        assert result.error is None
    
    def test_ok_with_complex_value(self):
        data = {"key": "value", "count": 42}
        result = NexaResult.ok(data)
        assert result.is_ok is True
        assert result.value == data
    
    def test_repr(self):
        ok_result = NexaResult.ok("hello")
        err_result = NexaResult.err("fail")
        assert "ok" in repr(ok_result)
        assert "err" in repr(err_result)
    
    def test_str(self):
        ok_result = NexaResult.ok("hello")
        err_result = NexaResult.err("fail")
        assert str(ok_result) == "hello"
        assert "Error" in str(err_result)
    
    def test_equality(self):
        r1 = NexaResult.ok("same")
        r2 = NexaResult.ok("same")
        r3 = NexaResult.ok("diff")
        r4 = NexaResult.err("same")
        assert r1 == r2
        assert r1 != r3
        assert r1 != r4


class TestNexaResultUnwrap:
    """NexaResult unwrap 操作测试（? 操作符核心）"""
    
    def test_unwrap_ok_returns_value(self):
        """? 操作符在 NexaResult.ok 上 unwrap 成功返回值"""
        result = NexaResult.ok("success")
        assert result.unwrap() == "success"
    
    def test_unwrap_err_raises_error_propagation(self):
        """? 操作符在 NexaResult.err 上触发 ErrorPropagation early-return"""
        result = NexaResult.err("error message")
        with pytest.raises(ErrorPropagation) as exc_info:
            result.unwrap()
        assert exc_info.value.error == "error message"
    
    def test_unwrap_or_ok_returns_value(self):
        """otherwise 核心：成功返回值"""
        result = NexaResult.ok("success")
        assert result.unwrap_or("default") == "success"
    
    def test_unwrap_or_err_returns_default(self):
        """otherwise 核心：失败返回默认值"""
        result = NexaResult.err("error")
        assert result.unwrap_or("default") == "default"
    
    def test_unwrap_or_else_ok_returns_value(self):
        result = NexaResult.ok("success")
        assert result.unwrap_or_else(lambda e: f"fallback: {e}") == "success"
    
    def test_unwrap_or_else_err_calls_handler(self):
        result = NexaResult.err("error msg")
        assert result.unwrap_or_else(lambda e: f"fallback: {e}") == "fallback: error msg"


class TestNexaResultTransformations:
    """NexaResult 转换操作测试"""
    
    def test_map_ok(self):
        result = NexaResult.ok(10)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_ok
        assert mapped.value == 20
    
    def test_map_err_stays_err(self):
        result = NexaResult.err("error")
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_err
        assert mapped.error == "error"
    
    def test_map_err_err(self):
        result = NexaResult.err("original")
        mapped = result.map_err(lambda e: f"wrapped: {e}")
        assert mapped.is_err
        assert mapped.error == "wrapped: original"
    
    def test_map_err_ok_stays_ok(self):
        result = NexaResult.ok(10)
        mapped = result.map_err(lambda e: f"wrapped: {e}")
        assert mapped.is_ok
        assert mapped.value == 10
    
    def test_and_then_ok(self):
        result = NexaResult.ok(5)
        chained = result.and_then(lambda x: NexaResult.ok(x + 3))
        assert chained.is_ok
        assert chained.value == 8
    
    def test_and_then_ok_to_err(self):
        result = NexaResult.ok(0)
        chained = result.and_then(lambda x: NexaResult.err("zero not allowed") if x == 0 else NexaResult.ok(x))
        assert chained.is_err
    
    def test_and_then_err_stays_err(self):
        result = NexaResult.err("original")
        chained = result.and_then(lambda x: NexaResult.ok(x + 3))
        assert chained.is_err
    
    def test_or_else_err(self):
        result = NexaResult.err("error")
        recovered = result.or_else(lambda e: NexaResult.ok(f"recovered from {e}"))
        assert recovered.is_ok
        assert "recovered from error" in recovered.value
    
    def test_or_else_ok_stays_ok(self):
        result = NexaResult.ok("original")
        recovered = result.or_else(lambda e: NexaResult.ok("recovered"))
        assert recovered.is_ok
        assert recovered.value == "original"


# ============================================================
# 2. NexaOption 创建和操作测试
# ============================================================

class TestNexaOptionCreation:
    """NexaOption 创建和基本属性测试"""
    
    def test_some_creation(self):
        opt = NexaOption.some("value")
        assert opt.is_some is True
        assert opt.is_none is False
        assert opt.value == "value"
    
    def test_none_creation(self):
        opt = NexaOption.none()
        assert opt.is_some is False
        assert opt.is_none is True
    
    def test_some_with_none_value(self):
        opt = NexaOption.some(None)
        assert opt.is_some is True
        assert opt.value is None
    
    def test_repr(self):
        some_opt = NexaOption.some("hello")
        none_opt = NexaOption.none()
        assert "some" in repr(some_opt)
        assert "none" in repr(none_opt)


class TestNexaOptionUnwrap:
    """NexaOption unwrap 操作测试"""
    
    def test_unwrap_some_returns_value(self):
        opt = NexaOption.some("value")
        assert opt.unwrap() == "value"
    
    def test_unwrap_none_raises_error_propagation(self):
        opt = NexaOption.none()
        with pytest.raises(ErrorPropagation) as exc_info:
            opt.unwrap()
        assert exc_info.value.error is None
    
    def test_unwrap_or_some_returns_value(self):
        opt = NexaOption.some("value")
        assert opt.unwrap_or("default") == "value"
    
    def test_unwrap_or_none_returns_default(self):
        opt = NexaOption.none()
        assert opt.unwrap_or("default") == "default"
    
    def test_unwrap_or_else_some(self):
        opt = NexaOption.some("value")
        assert opt.unwrap_or_else(lambda: "fallback") == "value"
    
    def test_unwrap_or_else_none(self):
        opt = NexaOption.none()
        assert opt.unwrap_or_else(lambda: "fallback") == "fallback"


class TestNexaOptionTransformations:
    """NexaOption 转换操作测试"""
    
    def test_map_some(self):
        opt = NexaOption.some(10)
        mapped = opt.map(lambda x: x * 2)
        assert mapped.is_some
        assert mapped.value == 20
    
    def test_map_none_stays_none(self):
        opt = NexaOption.none()
        mapped = opt.map(lambda x: x * 2)
        assert mapped.is_none
    
    def test_and_then_some(self):
        opt = NexaOption.some(5)
        chained = opt.and_then(lambda x: NexaOption.some(x + 3))
        assert chained.is_some
        assert chained.value == 8
    
    def test_and_then_none_stays_none(self):
        opt = NexaOption.none()
        chained = opt.and_then(lambda x: NexaOption.some(x + 3))
        assert chained.is_none
    
    def test_or_else_none(self):
        opt = NexaOption.none()
        recovered = opt.or_else(lambda: NexaOption.some("recovered"))
        assert recovered.is_some
        assert recovered.value == "recovered"
    
    def test_to_result_some(self):
        opt = NexaOption.some("value")
        result = opt.to_result("no value")
        assert result.is_ok
        assert result.value == "value"
    
    def test_to_result_none(self):
        opt = NexaOption.none()
        result = opt.to_result("no value")
        assert result.is_err
        assert result.error == "no value"


# ============================================================
# 3. ErrorPropagation 异常捕获测试
# ============================================================

class TestErrorPropagation:
    """ErrorPropagation 异常测试"""
    
    def test_error_propagation_creation(self):
        ep = ErrorPropagation("test error")
        assert ep.error == "test error"
        assert str(ep) == "test error"
    
    def test_error_propagation_with_none(self):
        ep = ErrorPropagation(None)
        assert ep.error is None
    
    def test_error_propagation_is_exception(self):
        ep = ErrorPropagation("error")
        assert isinstance(ep, Exception)
    
    def test_error_propagation_catchable(self):
        """ErrorPropagation 可以被 try/catch 捕获"""
        try:
            raise ErrorPropagation("caught error")
        except ErrorPropagation as e:
            assert e.error == "caught error"
    
    def test_error_propagation_not_generic_exception(self):
        """ErrorPropagation 不是通用的 Exception"""
        try:
            raise ErrorPropagation("specific error")
        except Exception as e:
            # 可以作为通用 Exception 捕获
            assert isinstance(e, ErrorPropagation)


# ============================================================
# 4. propagate_or_else 函数测试
# ============================================================

class TestPropagateOrElse:
    """propagate_or_else 统一处理 ? 和 otherwise 逻辑测试"""
    
    def test_propagate_ok_result_no_handler(self):
        """? 操作符模式：成功→返回值"""
        result = NexaResult.ok("success")
        value = propagate_or_else(result)
        assert value == "success"
    
    def test_propagate_err_result_no_handler_raises(self):
        """? 操作符模式：失败→抛出 ErrorPropagation"""
        result = NexaResult.err("error")
        with pytest.raises(ErrorPropagation) as exc_info:
            propagate_or_else(result)
        assert exc_info.value.error == "error"
    
    def test_propagate_ok_result_with_handler(self):
        """otherwise 模式：成功→返回值（handler 不执行）"""
        result = NexaResult.ok("success")
        value = propagate_or_else(result, "fallback")
        assert value == "success"
    
    def test_propagate_err_result_with_value_handler(self):
        """otherwise 模式：失败→返回 handler 值"""
        result = NexaResult.err("error")
        value = propagate_or_else(result, "fallback value")
        assert value == "fallback value"
    
    def test_propagate_some_option_no_handler(self):
        """? 操作符模式 on NexaOption：有值→返回值"""
        opt = NexaOption.some("value")
        value = propagate_or_else(opt)
        assert value == "value"
    
    def test_propagate_none_option_no_handler_raises(self):
        """? 操作符模式 on NexaOption：无值→抛出 ErrorPropagation"""
        opt = NexaOption.none()
        with pytest.raises(ErrorPropagation):
            propagate_or_else(opt)
    
    def test_propagate_none_option_with_handler(self):
        """otherwise 模式 on NexaOption：无值→返回 handler"""
        opt = NexaOption.none()
        value = propagate_or_else(opt, "fallback")
        assert value == "fallback"
    
    def test_propagate_non_result_value(self):
        """向后兼容：非 NexaResult/NexaOption 值视为成功"""
        value = propagate_or_else("plain string")
        assert value == "plain string"
    
    def test_propagate_with_callable_handler(self):
        """otherwise 模式：handler 是函数"""
        result = NexaResult.err("error")
        value = propagate_or_else(result, lambda e: f"recovered: {e}")
        assert value == "recovered: error"
    
    def test_propagate_with_dict_handler(self):
        """otherwise 模式：handler 是字典"""
        result = NexaResult.err("error")
        handler_dict = {"result": "fallback from dict"}
        value = propagate_or_else(result, handler_dict)
        assert value == "fallback from dict"


# ============================================================
# 5. try_propagate 函数测试
# ============================================================

class TestTryPropagate:
    """try_propagate — flow 函数中捕获 ErrorPropagation 测试"""
    
    def test_normal_function_returns_ok(self):
        """正常函数执行 → NexaResult.ok"""
        def normal_func():
            return "success"
        result = try_propagate(normal_func)
        assert result.is_ok
        assert result.value == "success"
    
    def test_error_propagation_caught_returns_err(self):
        """ErrorPropagation 被 try_propagate 捕获 → NexaResult.err"""
        def failing_func():
            raise ErrorPropagation("propagated error")
        result = try_propagate(failing_func)
        assert result.is_err
        assert result.error == "propagated error"
    
    def test_generic_exception_caught_returns_err(self):
        """通用异常也被捕获 → NexaResult.err"""
        def crashing_func():
            raise ValueError("value error")
        result = try_propagate(crashing_func)
        assert result.is_err
        assert "value error" in result.error
    
    def test_contract_violation_not_caught(self):
        """ContractViolation 不被 try_propagate 转换"""
        from src.runtime.contracts import ContractViolation
        def contract_func():
            raise ContractViolation("contract failed", clause_type="requires", clause="test", context={}, is_semantic=False)
        with pytest.raises(ContractViolation):
            try_propagate(contract_func)
    
    def test_nexa_result_passed_through(self):
        """如果函数返回 NexaResult，直接传递"""
        def result_func():
            return NexaResult.ok("already wrapped")
        result = try_propagate(result_func)
        assert result.is_ok
        assert result.value == "already wrapped"
    
    def test_with_arguments(self):
        """带参数的函数"""
        def add(a, b):
            return a + b
        result = try_propagate(add, 3, 4)
        assert result.is_ok
        assert result.value == 7
    
    def test_with_keyword_arguments(self):
        """带关键字参数的函数"""
        def greet(name="world"):
            return f"hello {name}"
        result = try_propagate(greet, name="nexa")
        assert result.is_ok
        assert result.value == "hello nexa"


# ============================================================
# 6. wrap_agent_result 函数测试
# ============================================================

class TestWrapAgentResult:
    """wrap_agent_result — Agent.run() 返回值包装测试"""
    
    def test_string_wrapped_as_ok(self):
        """字符串结果 → NexaResult.ok"""
        result = wrap_agent_result("agent output")
        assert result.is_ok
        assert result.value == "agent output"
    
    def test_already_nexa_result_passthrough(self):
        """已经是 NexaResult → 直接返回"""
        original = NexaResult.ok("already wrapped")
        result = wrap_agent_result(original)
        assert result == original
    
    def test_dict_wrapped_as_ok(self):
        """字典结果 → NexaResult.ok"""
        data = {"key": "value"}
        result = wrap_agent_result(data)
        assert result.is_ok
        assert result.value == data
    
    def test_none_wrapped_as_ok(self):
        """None 结果 → NexaResult.ok(None)"""
        result = wrap_agent_result(None)
        assert result.is_ok
        assert result.value is None
    
    def test_int_wrapped_as_ok(self):
        """数字结果 → NexaResult.ok"""
        result = wrap_agent_result(42)
        assert result.is_ok
        assert result.value == 42


# ============================================================
# 7. ? 操作符链式传播测试
# ============================================================

class TestTryOperatorChaining:
    """? 操作符链式传播测试 — 模拟 flow 函数中的 ? 链"""
    
    def test_chain_all_ok(self):
        """全部成功 → 链式 ? 正常执行"""
        def flow_func():
            r1 = NexaResult.ok("step1").unwrap()  # ? 操作符
            r2 = NexaResult.ok(f"{r1} + step2").unwrap()  # ? 操作符
            r3 = NexaResult.ok(f"{r2} + step3").unwrap()  # ? 操作符
            return r3
        
        result = try_propagate(flow_func)
        assert result.is_ok
        assert "step1" in result.value
        assert "step2" in result.value
        assert "step3" in result.value
    
    def test_chain_first_error_propagates(self):
        """链中第一个错误 → early-return 错误"""
        def flow_func():
            r1 = NexaResult.err("step1 failed").unwrap()  # ? 操作符 → ErrorPropagation
            # 后面的代码不会执行
            r2 = NexaResult.ok("step2").unwrap()
            return r2
        
        result = try_propagate(flow_func)
        assert result.is_err
        assert result.error == "step1 failed"
    
    def test_chain_second_error_propagates(self):
        """链中第二个错误 → early-return 错误"""
        def flow_func():
            r1 = NexaResult.ok("step1 ok").unwrap()  # ? → 成功
            r2 = NexaResult.err("step2 failed").unwrap()  # ? → ErrorPropagation
            # 后面的代码不会执行
            r3 = NexaResult.ok("step3").unwrap()
            return r3
        
        result = try_propagate(flow_func)
        assert result.is_err
        assert result.error == "step2 failed"


# ============================================================
# 8. otherwise 与 ? 共存测试
# ============================================================

class TestOtherwiseAndTryOpCoexistence:
    """otherwise 和 ? 操作符共存测试"""
    
    def test_otherwise_prevents_propagation(self):
        """otherwise 阻止错误传播"""
        result = NexaResult.err("error")
        # otherwise 模式：不抛 ErrorPropagation，而是返回 fallback
        value = propagate_or_else(result, "fallback")
        assert value == "fallback"
    
    def test_try_op_propagates_without_otherwise(self):
        """没有 otherwise 时 ? 传播错误"""
        result = NexaResult.err("error")
        with pytest.raises(ErrorPropagation):
            propagate_or_else(result)  # ? 操作符模式
    
    def test_otherwise_value_handler(self):
        """otherwise 值 handler"""
        result = NexaResult.err("DB error")
        value = propagate_or_else(result, "No results found")
        assert value == "No results found"
    
    def test_otherwise_callable_handler(self):
        """otherwise 函数 handler"""
        result = NexaResult.err("parse error")
        value = propagate_or_else(result, lambda e: f"Recovered: {e}")
        assert "Recovered" in value
        assert "parse error" in value
    
    def test_otherwise_dict_handler(self):
        """otherwise 字典 handler"""
        result = NexaResult.err("error")
        handler = {"result": "fallback from block"}
        value = propagate_or_else(result, handler)
        assert value == "fallback from block"


# ============================================================
# 9. 与 DAG ?? 操作符不冲突测试
# ============================================================

class TestDAGBranchNoConflict:
    """验证 ? 和 ?? DAG 分支操作符不冲突"""
    
    def test_try_op_single_char(self):
        """? 是单字符后缀操作符"""
        # 在 Nexa 语法中: expr?  → 错误传播
        result = NexaResult.ok("data")
        value = propagate_or_else(result)
        assert value == "data"
    
    def test_dag_branch_double_char(self):
        """?? 是双字符中缀操作符，不与 ? 冲突"""
        # 在 Nexa 语法中: expr ?? TrueAgent : FalseAgent  → DAG 条件分支
        # 两者语法位置不同：? 是后缀，?? 是中缀
        # 此测试确认 ? 和 ?? 可以共存于同一 flow 中
        result_ok = NexaResult.ok("success")
        result_err = NexaResult.err("error")
        
        # ? 操作符行为
        assert propagate_or_else(result_ok) == "success"
        with pytest.raises(ErrorPropagation):
            propagate_or_else(result_err)
        
        # ?? DAG 分支行为（由 dag_branch 函数处理，不在此测试）


# ============================================================
# 10. 向后兼容测试
# ============================================================

class TestBackwardCompatibility:
    """向后兼容测试 — 字符串结果自动包装"""
    
    def test_string_result_auto_wraps(self):
        """Agent.run() 返回字符串时自动包装为 NexaResult.ok"""
        result = wrap_agent_result("agent string output")
        assert result.is_ok
        assert result.value == "agent string output"
    
    def test_plain_string_propagates_as_ok(self):
        """propagate_or_else 对普通字符串视为成功"""
        value = propagate_or_else("plain string")
        assert value == "plain string"
    
    def test_plain_int_propagates_as_ok(self):
        """propagate_or_else 对普通数字视为成功"""
        value = propagate_or_else(42)
        assert value == 42
    
    def test_nexa_result_unwrap_does_not_change_string(self):
        """NexaResult.ok 包装字符串 → unwrap 返回原始字符串"""
        original = "hello world"
        result = NexaResult.ok(original)
        assert result.unwrap() == original
    
    def test_existing_try_catch_still_works(self):
        """现有 try/catch 语法仍然正常工作"""
        # ErrorPropagation 是 Exception 子类，可以被 try/catch 捕获
        try:
            NexaResult.err("test error").unwrap()
        except Exception as e:
            assert isinstance(e, ErrorPropagation)
            assert e.error == "test error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])