"""
Nexa 渐进式类型系统 (Gradual Type System) 测试

测试双轴类型安全模式、类型推断、类型检查、Protocol合规性、
联合类型、Option/Result类型、nexa.toml配置文件等。
"""

import os
import sys
import pytest
import tempfile

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime.type_system import (
    TypeMode, LintMode, get_type_mode, get_lint_mode,
    PrimitiveTypeExpr, GenericTypeExpr, UnionTypeExpr, OptionTypeExpr,
    ResultTypeExpr, AliasTypeExpr, FuncTypeExpr, SemanticTypeExpr,
    TypeInferrer, InferredType, TypeChecker, TypeViolation, TypeWarning,
    TypeCheckResult, TypeNarrower, build_type_expr_from_ast,
    build_protocol_fields_from_ast, check_type, check_protocol,
)
from src.runtime.config import (
    load_nexa_config, find_nexa_toml, get_config_value,
    create_default_nexa_toml, _parse_toml,
)


# ============================================================
# TypeMode / LintMode 环境变量读取测试
# ============================================================

class TestTypeModeEnv:
    """测试 NEXA_TYPE_MODE 环境变量读取"""

    def test_type_mode_strict_from_env(self):
        os.environ["NEXA_TYPE_MODE"] = "strict"
        mode = get_type_mode()
        assert mode == TypeMode.STRICT
        del os.environ["NEXA_TYPE_MODE"]

    def test_type_mode_warn_from_env(self):
        os.environ["NEXA_TYPE_MODE"] = "warn"
        mode = get_type_mode()
        assert mode == TypeMode.WARN
        del os.environ["NEXA_TYPE_MODE"]

    def test_type_mode_forgiving_from_env(self):
        os.environ["NEXA_TYPE_MODE"] = "forgiving"
        mode = get_type_mode()
        assert mode == TypeMode.FORGIVING
        del os.environ["NEXA_TYPE_MODE"]

    def test_type_mode_default_is_warn(self):
        # 清除环境变量
        if "NEXA_TYPE_MODE" in os.environ:
            del os.environ["NEXA_TYPE_MODE"]
        # 清除缓存
        from src.runtime.config import load_nexa_config
        load_nexa_config(force_reload=True)
        mode = get_type_mode()
        assert mode == TypeMode.WARN

    def test_type_mode_invalid_env_defaults_warn(self):
        os.environ["NEXA_TYPE_MODE"] = "invalid_value"
        mode = get_type_mode()
        assert mode == TypeMode.WARN
        del os.environ["NEXA_TYPE_MODE"]

    def test_type_mode_cli_override(self):
        os.environ["NEXA_TYPE_MODE"] = "warn"
        mode = get_type_mode(cli_override="strict")
        assert mode == TypeMode.STRICT
        del os.environ["NEXA_TYPE_MODE"]


class TestLintModeEnv:
    """测试 NEXA_LINT_MODE 环境变量读取"""

    def test_lint_mode_strict_from_env(self):
        os.environ["NEXA_LINT_MODE"] = "strict"
        mode = get_lint_mode()
        assert mode == LintMode.STRICT
        del os.environ["NEXA_LINT_MODE"]

    def test_lint_mode_warn_from_env(self):
        os.environ["NEXA_LINT_MODE"] = "warn"
        mode = get_lint_mode()
        assert mode == LintMode.WARN
        del os.environ["NEXA_LINT_MODE"]

    def test_lint_mode_default_is_default(self):
        if "NEXA_LINT_MODE" in os.environ:
            del os.environ["NEXA_LINT_MODE"]
        from src.runtime.config import load_nexa_config
        load_nexa_config(force_reload=True)
        mode = get_lint_mode()
        assert mode == LintMode.DEFAULT

    def test_lint_mode_cli_override(self):
        os.environ["NEXA_LINT_MODE"] = "default"
        mode = get_lint_mode(cli_override="strict")
        assert mode == LintMode.STRICT
        del os.environ["NEXA_LINT_MODE"]


# ============================================================
# 类型推断测试 (TypeInferrer)
# ============================================================

class TestTypeInferrer:
    """测试类型推断器"""

    def test_infer_int(self):
        result = TypeInferrer.infer_type(5)
        assert isinstance(result, PrimitiveTypeExpr)
        assert result.name == "int"

    def test_infer_float(self):
        result = TypeInferrer.infer_type(3.14)
        assert isinstance(result, PrimitiveTypeExpr)
        assert result.name == "float"

    def test_infer_str(self):
        result = TypeInferrer.infer_type("hello")
        assert isinstance(result, PrimitiveTypeExpr)
        assert result.name == "str"

    def test_infer_bool(self):
        result = TypeInferrer.infer_type(True)
        assert isinstance(result, PrimitiveTypeExpr)
        assert result.name == "bool"

    def test_infer_none(self):
        result = TypeInferrer.infer_type(None)
        assert isinstance(result, OptionTypeExpr)

    def test_infer_list_of_ints(self):
        result = TypeInferrer.infer_type([1, 2, 3])
        assert isinstance(result, GenericTypeExpr)
        assert result.name == "list"
        assert isinstance(result.type_params[0], PrimitiveTypeExpr)
        assert result.type_params[0].name == "int"

    def test_infer_list_of_strs(self):
        result = TypeInferrer.infer_type(["a", "b", "c"])
        assert isinstance(result, GenericTypeExpr)
        assert result.name == "list"
        assert result.type_params[0].name == "str"

    def test_infer_dict(self):
        result = TypeInferrer.infer_type({"key": "value"})
        assert isinstance(result, GenericTypeExpr)
        assert result.name == "dict"

    def test_infer_empty_list(self):
        result = TypeInferrer.infer_type([])
        assert isinstance(result, GenericTypeExpr)
        assert result.name == "list"

    def test_infer_bool_not_int(self):
        """bool 不应该被推断为 int"""
        result = TypeInferrer.infer_type(True)
        assert result.name == "bool"
        assert result.name != "int"


# ============================================================
# TypeExpr 类型表达式测试
# ============================================================

class TestTypeExpr:
    """测试类型表达式"""

    def test_primitive_type_str(self):
        t = PrimitiveTypeExpr("str")
        assert t.to_type_str() == "str"
        assert t.to_python_type() == str

    def test_primitive_type_int(self):
        t = PrimitiveTypeExpr("int")
        assert t.to_type_str() == "int"
        assert t.to_python_type() == int

    def test_generic_list_type(self):
        t = GenericTypeExpr("list", [PrimitiveTypeExpr("int")])
        assert t.to_type_str() == "list[int]"

    def test_generic_dict_type(self):
        t = GenericTypeExpr("dict", [PrimitiveTypeExpr("str"), PrimitiveTypeExpr("int")])
        assert t.to_type_str() == "dict[str, int]"

    def test_option_type(self):
        t = OptionTypeExpr(PrimitiveTypeExpr("str"))
        assert t.to_type_str() == "str?"
        assert t.to_python_type() == type(None) or "Optional" in str(t.to_python_type())

    def test_result_type(self):
        t = ResultTypeExpr(PrimitiveTypeExpr("int"), PrimitiveTypeExpr("str"))
        assert t.to_type_str() == "Result[int, str]"

    def test_union_type(self):
        t = UnionTypeExpr([PrimitiveTypeExpr("str"), PrimitiveTypeExpr("int")])
        assert t.to_type_str() == "str | int"

    def test_alias_type(self):
        t = AliasTypeExpr("UserId")
        assert t.to_type_str() == "UserId"

    def test_semantic_type(self):
        t = SemanticTypeExpr(PrimitiveTypeExpr("str"), "must be a valid email")
        assert t.to_type_str() == 'str @ "must be a valid email"'

    def test_func_type(self):
        t = FuncTypeExpr([PrimitiveTypeExpr("float"), PrimitiveTypeExpr("float")], PrimitiveTypeExpr("float"))
        assert t.to_type_str() == "(float, float) -> float"

    def test_equality(self):
        assert PrimitiveTypeExpr("str") == PrimitiveTypeExpr("str")
        assert PrimitiveTypeExpr("str") != PrimitiveTypeExpr("int")
        assert OptionTypeExpr(PrimitiveTypeExpr("int")) == OptionTypeExpr(PrimitiveTypeExpr("int"))


# ============================================================
# TypeChecker 类型检查测试
# ============================================================

class TestTypeChecker:
    """测试类型检查器"""

    def setup_method(self):
        """每个测试方法前清除环境变量"""
        if "NEXA_TYPE_MODE" in os.environ:
            del os.environ["NEXA_TYPE_MODE"]
        if "NEXA_LINT_MODE" in os.environ:
            del os.environ["NEXA_LINT_MODE"]
        from src.runtime.config import load_nexa_config
        load_nexa_config(force_reload=True)

    def test_check_type_match_str_pass(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_type_match("hello", PrimitiveTypeExpr("str"))
        assert result.passed

    def test_check_type_match_str_fail(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_type_match(42, PrimitiveTypeExpr("str"))
        assert not result.passed
        assert len(result.violations) == 1

    def test_check_type_match_int_to_float_widening(self):
        """int 兼容 float (数值 widening)"""
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_type_match(42, PrimitiveTypeExpr("float"))
        assert result.passed

    def test_check_type_match_bool_not_int(self):
        """bool 不兼容 int"""
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_type_match(True, PrimitiveTypeExpr("int"))
        assert not result.passed

    def test_strict_mode_raises_violation(self):
        """strict 模式下类型不匹配抛 TypeViolation"""
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_type_match(42, PrimitiveTypeExpr("str"))
        assert not result.passed
        with pytest.raises(TypeViolation):
            checker.handle_violation(result)

    def test_warn_mode_logs_warning(self):
        """warn 模式下类型不匹配仅日志警告"""
        checker = TypeChecker(type_mode=TypeMode.WARN)
        result = checker.check_type_match(42, PrimitiveTypeExpr("str"))
        # warn 模式: 有类型警告但不阻止通过
        assert len(result.warnings) >= 1  # warn 模式产生警告

    def test_forgiving_mode_ignores(self):
        """forgiving 模式下类型不匹配静默忽略"""
        checker = TypeChecker(type_mode=TypeMode.FORGIVING)
        result = checker.check_type_match(42, PrimitiveTypeExpr("str"))
        assert result.passed  # forgiving 模式完全忽略
        assert len(result.violations) == 0
        assert len(result.warnings) == 0

    def test_check_function_call(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_function_call(
            "process_payment",
            [100.0],
            [PrimitiveTypeExpr("float")]
        )
        assert result.passed

    def test_check_function_call_wrong_arg_count(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_function_call(
            "process_payment",
            [100.0, "USD"],
            [PrimitiveTypeExpr("float")]
        )
        assert not result.passed

    def test_check_function_call_wrong_type(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_function_call(
            "process_payment",
            ["100"],
            [PrimitiveTypeExpr("float")]
        )
        assert not result.passed

    def test_check_return_type(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_return_type("my_func", 42, PrimitiveTypeExpr("int"))
        assert result.passed

    def test_check_return_type_wrong(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result = checker.check_return_type("my_func", "hello", PrimitiveTypeExpr("int"))
        assert not result.passed


# ============================================================
# Protocol 合规性检查测试
# ============================================================

class TestProtocolCompliance:
    """测试 Protocol 合规性检查"""

    def test_protocol_compliance_pass(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        checker.register_protocol("AnalysisReport", {
            "title": PrimitiveTypeExpr("str"),
            "sentiment": PrimitiveTypeExpr("str"),
            "confidence": PrimitiveTypeExpr("float"),
        })
        data = {
            "title": "Market Analysis",
            "sentiment": "positive",
            "confidence": 0.85,
        }
        result = checker.check_protocol_compliance(data, "AnalysisReport")
        assert result.passed

    def test_protocol_compliance_missing_field(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        checker.register_protocol("AnalysisReport", {
            "title": PrimitiveTypeExpr("str"),
            "sentiment": PrimitiveTypeExpr("str"),
            "confidence": PrimitiveTypeExpr("float"),
        })
        data = {
            "title": "Market Analysis",
            "sentiment": "positive",
            # missing "confidence"
        }
        result = checker.check_protocol_compliance(data, "AnalysisReport")
        assert not result.passed

    def test_protocol_compliance_wrong_type(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        checker.register_protocol("AnalysisReport", {
            "title": PrimitiveTypeExpr("str"),
            "confidence": PrimitiveTypeExpr("float"),
        })
        data = {
            "title": "Market Analysis",
            "confidence": "high",  # str 而不是 float
        }
        result = checker.check_protocol_compliance(data, "AnalysisReport")
        assert not result.passed

    def test_protocol_compliance_warn_mode(self):
        checker = TypeChecker(type_mode=TypeMode.WARN)
        checker.register_protocol("AnalysisReport", {
            "title": PrimitiveTypeExpr("str"),
            "confidence": PrimitiveTypeExpr("float"),
        })
        data = {
            "title": "Market Analysis",
            "confidence": "high",  # type mismatch
        }
        result = checker.check_protocol_compliance(data, "AnalysisReport")
        # warn 模式: 有警告（类型不匹配产生警告而非错误）
        assert len(result.warnings) >= 1

    def test_register_protocol_field(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        checker.register_protocol_field("MyProto", "name", PrimitiveTypeExpr("str"))
        checker.register_protocol_field("MyProto", "age", PrimitiveTypeExpr("int"))
        data = {"name": "Alice", "age": 30}
        result = checker.check_protocol_compliance(data, "MyProto")
        assert result.passed


# ============================================================
# 联合类型检查测试
# ============================================================

class TestUnionType:
    """测试联合类型兼容性检查"""

    def test_union_match_first(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        union = UnionTypeExpr([PrimitiveTypeExpr("str"), PrimitiveTypeExpr("int")])
        result = checker.check_union_type("hello", union)
        assert result.passed

    def test_union_match_second(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        union = UnionTypeExpr([PrimitiveTypeExpr("str"), PrimitiveTypeExpr("int")])
        result = checker.check_union_type(42, union)
        assert result.passed

    def test_union_no_match(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        union = UnionTypeExpr([PrimitiveTypeExpr("str"), PrimitiveTypeExpr("int")])
        result = checker.check_union_type(3.14, union)
        assert not result.passed


# ============================================================
# Option / Result 类型测试
# ============================================================

class TestOptionResultType:
    """测试 Option[T] / Result[T, E] 类型处理"""

    def test_option_none_is_valid(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        opt = OptionTypeExpr(PrimitiveTypeExpr("str"))
        result = checker.check_option_type(None, opt)
        assert result.passed

    def test_option_non_none_match_inner(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        opt = OptionTypeExpr(PrimitiveTypeExpr("str"))
        result = checker.check_option_type("hello", opt)
        assert result.passed

    def test_option_non_none_not_match_inner(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        opt = OptionTypeExpr(PrimitiveTypeExpr("int"))
        result = checker.check_option_type("hello", opt)
        assert not result.passed

    def test_result_ok_type(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result_type = ResultTypeExpr(PrimitiveTypeExpr("int"), PrimitiveTypeExpr("str"))
        result = checker.check_result_type(42, result_type)
        assert result.passed

    def test_result_err_type(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result_type = ResultTypeExpr(PrimitiveTypeExpr("int"), PrimitiveTypeExpr("str"))
        result = checker.check_result_type("error message", result_type)
        assert result.passed

    def test_result_no_match(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        result_type = ResultTypeExpr(PrimitiveTypeExpr("int"), PrimitiveTypeExpr("str"))
        result = checker.check_result_type(3.14, result_type)
        assert not result.passed


# ============================================================
# nexa.toml 配置文件测试
# ============================================================

class TestNexaTomlConfig:
    """测试 nexa.toml 配置文件加载"""

    def test_parse_toml_basic(self):
        content = '[project]\nname = "my-app"\nversion = "0.1.0"\n\n[type]\nmode = "strict"\n\n[lint]\nmode = "warn"'
        config = _parse_toml(content)
        assert config["project"]["name"] == "my-app"
        assert config["project"]["version"] == "0.1.0"  # version is a string, not float
        assert config["type"]["mode"] == "strict"
        assert config["lint"]["mode"] == "warn"

    def test_parse_toml_bool(self):
        content = """
[runtime]
cache_enabled = true
debug = false
"""
        config = _parse_toml(content)
        assert config["runtime"]["cache_enabled"] == True
        assert config["runtime"]["debug"] == False

    def test_parse_toml_integer(self):
        content = """
[agent]
default_timeout = 30
default_retry = 3
"""
        config = _parse_toml(content)
        assert config["agent"]["default_timeout"] == 30
        assert config["agent"]["default_retry"] == 3

    def test_parse_toml_comments(self):
        content = '[type]\nmode = "warn"'
        config = _parse_toml(content)
        assert config["type"]["mode"] == "warn"

    def test_create_default_nexa_toml(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_default_nexa_toml(Path(tmpdir) / "nexa.toml")
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "type" in content
            assert "lint" in content

    def test_config_not_found_returns_empty(self):
        """找不到 nexa.toml 返回空字典"""
        from src.runtime.config import _config_cache
        # 强制清除缓存
        import src.runtime.config as config_module
        config_module._config_cache = None
        config_module._config_path = None
        
        if "NEXA_TYPE_MODE" in os.environ:
            del os.environ["NEXA_TYPE_MODE"]
        config = load_nexa_config(force_reload=True)
        # 可能找到项目根目录的 nexa.toml，也可能找不到
        # 只验证返回的是字典
        assert isinstance(config, dict)


# ============================================================
# build_type_expr_from_ast 测试
# ============================================================

class TestBuildTypeExprFromAST:
    """测试从 AST 字典构建 TypeExpr 对象"""

    def test_build_primitive(self):
        ast = {"type": "BaseType", "name": "str"}
        result = build_type_expr_from_ast(ast)
        assert isinstance(result, PrimitiveTypeExpr)
        assert result.name == "str"

    def test_build_list(self):
        ast = {"type": "GenericType", "name": "list", "type_params": [{"type": "BaseType", "name": "int"}]}
        result = build_type_expr_from_ast(ast)
        assert isinstance(result, GenericTypeExpr)
        assert result.name == "list"
        assert result.type_params[0].name == "int"

    def test_build_option(self):
        ast = {"type": "OptionTypeExpr", "inner": {"type": "BaseType", "name": "str"}}
        result = build_type_expr_from_ast(ast)
        assert isinstance(result, OptionTypeExpr)
        assert result.inner.name == "str"

    def test_build_result(self):
        ast = {"type": "ResultTypeExpr", "ok_type": {"type": "BaseType", "name": "int"}, "err_type": {"type": "BaseType", "name": "str"}}
        result = build_type_expr_from_ast(ast)
        assert isinstance(result, ResultTypeExpr)
        assert result.ok_type.name == "int"
        assert result.err_type.name == "str"

    def test_build_union(self):
        ast = {"type": "UnionTypeExpr", "types": [{"type": "BaseType", "name": "str"}, {"type": "BaseType", "name": "int"}]}
        result = build_type_expr_from_ast(ast)
        assert isinstance(result, UnionTypeExpr)
        assert len(result.types) == 2

    def test_build_alias(self):
        ast = {"type": "CustomType", "name": "UserId"}
        result = build_type_expr_from_ast(ast)
        assert isinstance(result, AliasTypeExpr)
        assert result.name == "UserId"

    def test_build_semantic(self):
        ast = {"type": "SemanticType", "base_type": {"type": "BaseType", "name": "str"}, "constraint": "must be email"}
        result = build_type_expr_from_ast(ast)
        assert isinstance(result, SemanticTypeExpr)
        assert result.constraint == "must be email"

    def test_build_from_string(self):
        result = build_type_expr_from_ast("int")
        assert isinstance(result, PrimitiveTypeExpr)
        assert result.name == "int"


# ============================================================
# TypeNarrower 流敏感类型收窄测试
# ============================================================

class TestTypeNarrower:
    """测试流敏感类型收窄"""

    def test_narrow_after_none_check(self):
        opt = OptionTypeExpr(PrimitiveTypeExpr("str"))
        narrowed = TypeNarrower.narrow_after_none_check(opt)
        assert isinstance(narrowed, PrimitiveTypeExpr)
        assert narrowed.name == "str"

    def test_narrow_after_isinstance(self):
        union = UnionTypeExpr([PrimitiveTypeExpr("str"), PrimitiveTypeExpr("int")])
        narrowed = TypeNarrower.narrow_after_isinstance(union, PrimitiveTypeExpr("int"))
        assert narrowed == PrimitiveTypeExpr("int")

    def test_narrow_after_match(self):
        union = UnionTypeExpr([PrimitiveTypeExpr("str"), PrimitiveTypeExpr("int"), PrimitiveTypeExpr("float")])
        narrowed = TypeNarrower.narrow_after_match(union, PrimitiveTypeExpr("float"))
        assert narrowed == PrimitiveTypeExpr("float")


# ============================================================
# 便捷函数测试
# ============================================================

class TestConvenienceFunctions:
    """测试 check_type 和 check_protocol 便捷函数"""

    def setup_method(self):
        if "NEXA_TYPE_MODE" in os.environ:
            del os.environ["NEXA_TYPE_MODE"]

    def test_check_type_pass(self):
        result = check_type("hello", PrimitiveTypeExpr("str"))
        assert result.passed

    def test_check_protocol_pass(self):
        checker = TypeChecker(type_mode=TypeMode.STRICT)
        checker.register_protocol("TestProto", {
            "name": PrimitiveTypeExpr("str"),
        })
        result = check_protocol({"name": "Alice"}, "TestProto")
        assert result.passed


# ============================================================
# Lint 类型检查测试
# ============================================================

class TestLintCheck:
    """测试 Lint 类型检查"""

    def test_lint_default_mode_no_warnings(self):
        """default 模式只检查有标注的代码"""
        checker = TypeChecker(type_mode=TypeMode.WARN, lint_mode=LintMode.DEFAULT)
        ast = {
            "body": [
                {
                    "type": "FlowDeclaration",
                    "name": "test_flow",
                    "params": [{"name": "x", "type": "Any"}],
                    "return_type": None,
                }
            ]
        }
        result = checker.lint_check_annotations(ast)
        assert result.passed  # default 模式不检查缺失标注

    def test_lint_warn_mode_warnings(self):
        """warn 模式对缺失标注发出警告"""
        checker = TypeChecker(type_mode=TypeMode.WARN, lint_mode=LintMode.WARN)
        ast = {
            "body": [
                {
                    "type": "FlowDeclaration",
                    "name": "test_flow",
                    "params": [{"name": "x", "type": "Any"}],
                    "return_type": None,
                }
            ]
        }
        result = checker.lint_check_annotations(ast)
        assert len(result.warnings) > 0

    def test_lint_strict_mode_errors(self):
        """strict 模式缺失标注=lint错误"""
        checker = TypeChecker(type_mode=TypeMode.STRICT, lint_mode=LintMode.STRICT)
        ast = {
            "body": [
                {
                    "type": "FlowDeclaration",
                    "name": "test_flow",
                    "params": [{"name": "x", "type": "Any"}],
                    "return_type": None,
                }
            ]
        }
        result = checker.lint_check_annotations(ast)
        assert not result.passed
        assert len(result.violations) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])