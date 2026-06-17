"""
Nexa v2.2.1: Context-as-Structure 特性测试

测试范围:
1. Grammar: context { ... } 子块能正确解析
2. AST: context_spec 字段正确提取
3. Runtime: NexaAgent 接受 context_spec 参数，last_context() 返回 AgentContext
4. Validator: C-004 规则检测 context 不兼容
5. Codegen: 生成的 Python 含 context_spec 参数和 nexa_context_pipeline
6. 向后兼容: 不加 context 块的 agent 行为不变
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.nexa_parser import parse
from src.harness_validator import HarnessValidator, HarnessMode
from src.runtime.agent_context import AgentContext, ContextSpec, is_compatible


class TestContextGrammar:
    """v2.2.1 Grammar: context { ... } 子块解析"""

    def test_context_block_parses(self):
        """agent with context block parses successfully"""
        code = '''
agent X {
    model: "m",
    context {
        source: upstream,
        sink: downstream,
        output_schema: Foo,
        max_history_turns: 20,
        inherit: [messages, artifacts]
    }
    prompt: "p"
}
'''
        ast = parse(code)
        agents = [n for n in ast["body"] if n.get("type") == "AgentDeclaration"]
        assert len(agents) == 1
        spec = agents[0].get("context_spec")
        assert spec is not None
        assert spec["source"] == "upstream"
        assert spec["sink"] == "downstream"
        assert spec["output_schema"] == "Foo"
        assert spec["max_history_turns"] == 20
        assert spec["inherit"] == ["messages", "artifacts"]

    def test_agent_without_context_block_backward_compatible(self):
        """agent without context block has context_spec=None (v2.1 behavior)"""
        code = '''
agent X {
    model: "m",
    prompt: "p"
}
'''
        ast = parse(code)
        agents = [n for n in ast["body"] if n.get("type") == "AgentDeclaration"]
        assert len(agents) == 1
        assert agents[0].get("context_spec") is None

    def test_context_block_with_minimal_fields(self):
        """context block works with just source field"""
        code = '''
agent X {
    model: "m",
    context {
        source: upstream
    }
    prompt: "p"
}
'''
        ast = parse(code)
        agents = [n for n in ast["body"] if n.get("type") == "AgentDeclaration"]
        spec = agents[0]["context_spec"]
        assert spec["source"] == "upstream"
        # inherit defaults to [] when omitted
        assert spec["inherit"] == []


class TestContextSpecRuntime:
    """v2.2.1 Runtime: ContextSpec dataclass"""

    def test_context_spec_from_dict(self):
        d = {"source": "upstream", "output_schema": "Foo", "inherit": ["messages"]}
        spec = ContextSpec.from_dict(d)
        assert spec.source == "upstream"
        assert spec.output_schema == "Foo"
        assert spec.inherit == ["messages"]

    def test_context_spec_from_none(self):
        assert ContextSpec.from_dict(None) is None

    def test_context_spec_defaults(self):
        d = {}
        spec = ContextSpec.from_dict(d)
        assert spec.source == "upstream"
        assert spec.sink == "downstream"

    def test_is_compatible_no_spec(self):
        """No context spec = permissive (no error)"""
        assert is_compatible(None, None) is True

    def test_is_compatible_matching_schema(self):
        up = ContextSpec(output_schema="Foo")
        down = ContextSpec(input_schema="Foo")
        assert is_compatible(up, down) is True

    def test_is_compatible_mismatched_schema(self):
        up = ContextSpec(output_schema="Foo")
        down = ContextSpec(input_schema="Bar")
        assert is_compatible(up, down) is False

    def test_is_compatible_missing_one_schema(self):
        """If either side omits schema, we are permissive"""
        up = ContextSpec(output_schema="Foo")
        down = ContextSpec()  # no input_schema
        assert is_compatible(up, down) is True


class TestNexaAgentContextIntegration:
    """v2.2.1 NexaAgent accepts context_spec parameter"""

    def test_agent_accepts_context_spec_dict(self):
        from src.runtime.agent import NexaAgent
        agent = NexaAgent(
            name="Test",
            prompt="hi",
            context_spec={"source": "upstream", "output_schema": "Foo"},
        )
        assert agent.context_spec is not None
        assert agent.context_spec.source == "upstream"
        assert agent.context_spec.output_schema == "Foo"

    def test_agent_without_context_spec(self):
        from src.runtime.agent import NexaAgent
        agent = NexaAgent(name="Test", prompt="hi")
        assert agent.context_spec is None
        assert agent.last_context() is None

    def test_agent_context_to_dict(self):
        spec = ContextSpec(source="shared:mem", output_schema="Bar")
        d = spec.to_dict()
        assert d["source"] == "shared:mem"
        assert d["output_schema"] == "Bar"


class TestValidatorC004:
    """v2.2.1 Validator: C-004 context compatibility check"""

    def test_c004_triggers_on_schema_mismatch(self):
        code = '''
protocol A { x: "string" }
protocol B { y: "string" }
agent X {
    model: "m",
    context { output_schema: A }
    prompt: "p"
}
agent Y {
    model: "m",
    context { input_schema: B }
    prompt: "p"
}
flow main {
    result = "test" >> X >> Y;
}
'''
        ast = parse(code)
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        c004_errors = [e for e in report.errors if e.rule_id == "C-004"]
        assert len(c004_errors) >= 1, "C-004 should trigger on schema mismatch"
        assert "X >> Y" in c004_errors[0].message

    def test_c004_not_triggered_on_matching_schema(self):
        code = '''
protocol A { x: "string" }
agent X {
    model: "m",
    context { output_schema: A }
    prompt: "p"
}
agent Y {
    model: "m",
    context { input_schema: A }
    prompt: "p"
}
flow main {
    result = "test" >> X >> Y;
}
'''
        ast = parse(code)
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        c004_errors = [e for e in report.errors if e.rule_id == "C-004"]
        assert len(c004_errors) == 0, "C-004 should NOT trigger when schemas match"

    def test_c004_not_triggered_without_context_block(self):
        """v2.1 agents without context blocks don't trigger C-004"""
        code = '''
agent X { model: "m", prompt: "p" }
agent Y { model: "m", prompt: "p" }
flow main {
    result = "test" >> X >> Y;
}
'''
        ast = parse(code)
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        c004_errors = [e for e in report.errors if e.rule_id == "C-004"]
        assert len(c004_errors) == 0


class TestCodegen:
    """v2.2.1 Codegen: context_spec parameter and nexa_context_pipeline"""

    def test_codegen_generates_context_spec_param(self):
        from src.code_generator import CodeGenerator
        code = '''
agent X {
    model: "m",
    context { output_schema: Foo, inherit: [messages] }
    prompt: "p"
}
flow main {
    result = "test" >> X;
}
'''
        ast = parse(code)
        gen = CodeGenerator(ast)
        output = gen.generate()
        assert "context_spec=" in output
        assert "output_schema" in output

    def test_codegen_uses_context_pipeline(self):
        from src.code_generator import CodeGenerator
        code = '''
agent X { model: "m", prompt: "p" }
flow main {
    result = "test" >> X;
}
'''
        ast = parse(code)
        gen = CodeGenerator(ast)
        output = gen.generate()
        assert "nexa_context_pipeline" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
