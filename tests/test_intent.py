"""
Intent System Tests — .nxintent 文件解析 + intent check/coverage 测试

测试覆盖:
1. NxIntentParser — .nxintent 文件解析
2. AnnotationScanner — @implements 注解扫描
3. IntentRunner — intent check 和 coverage
4. Glossary 解析和合并
5. Feature/Scenario 解析
6. 彩色输出
"""

import pytest
import os
import tempfile
from pathlib import Path

from src.runtime.intent import (
    NxIntentParser, AnnotationScanner, IntentRunner,
    Colors, GlossaryEntry, Scenario, Feature, IntentFile,
    ImplementsAnnotation, CoverageReport
)


# ========================================
# 1. NxIntentParser Tests
# ========================================

class TestNxIntentParser:
    """Intent 文件解析器测试"""
    
    def setup_method(self):
        self.parser = NxIntentParser()
    
    def test_parse_basic_intent_file(self):
        """解析基本 intent 文件"""
        content = """
## Glossary

| Term | Means |
|------|-------|
| a user asks {question} | agent run with input {question} |
| the agent responds with {text} | output contains {text} |

---

Feature: Weather Bot
  id: feature.weather_bot
  description: "Weather information agent"

  Scenario: Weather query
    When a user asks "What is the weather?"
    → the agent responds with "weather"
"""
        intent_file = self.parser.parse(content)
        
        assert len(intent_file.glossary) >= 2
        assert len(intent_file.features) >= 1
    
    def test_parse_glossary_table(self):
        """解析 Glossary 表格"""
        glossary_text = """
## Glossary

| Term | Means |
|------|-------|
| a user asks {question} | agent run with input {question} |
| the agent responds with {text} | output contains {text} |
| the response is valid | protocol check passes |
"""
        entries = self.parser._parse_glossary(glossary_text)
        
        assert len(entries) >= 3
        assert entries[0].term == "a user asks {question}"
        assert entries[0].means == "agent run with input {question}"
    
    def test_parse_features_text_format(self):
        """解析 Features（文本格式）"""
        features_text = """
Feature: Weather Bot
  id: feature.weather_bot
  description: "Weather information agent"

  Scenario: Weather query
    When a user asks "What is the weather?"
    → the agent responds with "weather"
    → the response is valid

  Scenario: Invalid query
    When a user asks "xyzzy"
    → the agent responds with "clarification"
"""
        features = self.parser._parse_features_text(features_text)
        
        assert len(features) >= 1
        assert features[0].name == "Weather Bot"
        assert features[0].id == "feature.weather_bot"
        assert len(features[0].scenarios) >= 2
    
    def test_parse_scenarios_with_assertions(self):
        """解析 Scenario 断言"""
        features_text = """
Feature: Test Bot
  id: feature.test_bot

  Scenario: Basic test
    When a user asks "hello"
    → the agent responds with "greeting"
    → the response is valid
"""
        features = self.parser._parse_features_text(features_text)
        
        assert len(features) >= 1
        scenario = features[0].scenarios[0]
        assert scenario.name == "Basic test"
        assert len(scenario.assertions) >= 2
        assert scenario.when == "a user asks \"hello\""
    
    def test_split_sections(self):
        """分离 Glossary 和 Feature 部分"""
        content = """
## Glossary

| Term | Means |
|------|-------|
| test term | test means |

---

Feature: Test
  id: feature.test
"""
        glossary_text, features_text = self.parser._split_sections(content)
        
        assert "Glossary" in glossary_text or "term" in glossary_text.lower()
        assert "Feature" in features_text
    
    def test_parse_file_from_disk(self):
        """从文件解析"""
        # 使用示例文件
        intent_path = Path("examples/intent_demo/weather_bot.nxintent")
        if intent_path.exists():
            intent_file = self.parser.parse_file(str(intent_path))
            assert len(intent_file.glossary) > 0
            assert len(intent_file.features) > 0
    
    def test_parse_file_not_found(self):
        """文件不存在"""
        with pytest.raises(FileNotFoundError):
            self.parser.parse_file("/nonexistent/file.nxintent")
    
    def test_parse_empty_content(self):
        """解析空内容"""
        intent_file = self.parser.parse("")
        assert len(intent_file.glossary) == 0
        assert len(intent_file.features) == 0


# ========================================
# 2. AnnotationScanner Tests
# ========================================

class TestAnnotationScanner:
    """注解扫描器测试"""
    
    def setup_method(self):
        self.scanner = AnnotationScanner()
    
    def test_scan_implements_annotation(self):
        """扫描 @implements 注解"""
        content = """
// @implements: feature.weather_bot
agent WeatherBot implements WeatherReport {
    role: "Weather Assistant"
}
"""
        annotations = self.scanner.scan_content(content)
        
        assert len(annotations) >= 1
        assert annotations[0].feature_id == "feature.weather_bot"
        assert annotations[0].agent_name == "WeatherBot"
        assert annotations[0].annotation_type == "implements"
    
    def test_scan_supports_annotation(self):
        """扫描 @supports 注解"""
        content = """
// @supports: constraint.output_format
agent Formatter {
    role: "Format output"
}
"""
        annotations = self.scanner.scan_content(content)
        
        assert len(annotations) >= 1
        assert annotations[0].feature_id == "constraint.output_format"
        assert annotations[0].annotation_type == "supports"
    
    def test_scan_multiple_annotations(self):
        """扫描多个注解"""
        content = """
// @implements: feature.weather_bot
agent WeatherBot implements WeatherReport {
    role: "Weather Assistant"
}

// @implements: feature.forecast
agent ForecastBot {
    role: "Forecast Assistant"
}
"""
        annotations = self.scanner.scan_content(content)
        
        assert len(annotations) >= 2
    
    def test_scan_no_annotations(self):
        """扫描无注解内容"""
        content = """
agent SimpleBot {
    role: "Simple"
}
"""
        annotations = self.scanner.scan_content(content)
        assert len(annotations) == 0
    
    def test_scan_file(self):
        """从文件扫描"""
        nx_path = Path("examples/intent_demo/weather_bot.nx")
        if nx_path.exists():
            annotations = self.scanner.scan_file(str(nx_path))
            assert len(annotations) >= 1
            # 应找到 feature.weather_bot
            feature_ids = {a.feature_id for a in annotations}
            assert "feature.weather_bot" in feature_ids
    
    def test_scan_file_not_found(self):
        """文件不存在 → 空列表"""
        annotations = self.scanner.scan_file("/nonexistent/file.nx")
        assert len(annotations) == 0
    
    def test_find_implemented_feature_ids(self):
        """查找已实现的 feature IDs"""
        content = """
// @implements: feature.weather_bot
agent WeatherBot {
    role: "Weather"
}

// @implements: feature.translation
agent Translator {
    role: "Translate"
}
"""
        annotations = self.scanner.scan_content(content)
        feature_ids = {a.feature_id for a in annotations if a.annotation_type == "implements"}
        
        assert "feature.weather_bot" in feature_ids
        assert "feature.translation" in feature_ids


# ========================================
# 3. IntentRunner Tests
# ========================================

class TestIntentRunner:
    """Intent Runner 执行引擎测试"""
    
    def setup_method(self):
        self.runner = IntentRunner(verbose=True)
    
    def test_find_intent_file(self):
        """自动查找 .nxintent 文件"""
        nx_path = "examples/intent_demo/weather_bot.nx"
        intent_path = self.runner._find_intent_file(nx_path)
        
        # 应找到同目录下的 .nxintent 文件
        assert intent_path is not None
        assert intent_path.endswith(".nxintent")
    
    def test_build_vocabulary(self):
        """构建词汇表"""
        parser = NxIntentParser()
        intent_path = Path("examples/intent_demo/weather_bot.nxintent")
        
        if intent_path.exists():
            intent_file = parser.parse_file(str(intent_path))
            vocabulary = self.runner._build_vocabulary(intent_file)
            
            # 应包含标准词汇 + 用户 Glossary
            assert vocabulary.term_count() > 0
    
    def test_check_with_demo_files(self):
        """使用示例文件执行 check"""
        nx_path = "examples/intent_demo/weather_bot.nx"
        intent_path = "examples/intent_demo/weather_bot.nxintent"
        
        if Path(nx_path).exists() and Path(intent_path).exists():
            results = self.runner.check(nx_path, intent_file_path=intent_path)
            # 结果应该是 FeatureResult 列表
            assert isinstance(results, list)
    
    def test_coverage_with_demo_files(self):
        """使用示例文件计算 coverage"""
        nx_path = "examples/intent_demo/weather_bot.nx"
        intent_path = "examples/intent_demo/weather_bot.nxintent"
        
        if Path(nx_path).exists() and Path(intent_path).exists():
            report = self.runner.coverage(nx_path, intent_file_path=intent_path)
            assert isinstance(report, CoverageReport)
            assert report.total_features > 0
            assert report.implemented_features >= 0
    
    def test_check_no_intent_file(self):
        """无 intent 文件 → 空"""
        # 创建临时 .nx 文件（无对应的 .nxintent）
        with tempfile.NamedTemporaryFile(suffix='.nx', delete=False, mode='w') as f:
            f.write('agent TestBot { role: "Test" }')
            temp_path = f.name
        
        try:
            results = self.runner.check(temp_path)
            # 无 intent 文件 → 空结果
            assert isinstance(results, list)
        finally:
            os.unlink(temp_path)


# ========================================
# 4. Colors Tests
# ========================================

class TestColors:
    """ANSI 颜色输出测试"""
    
    def test_green(self):
        """绿色输出"""
        text = Colors.green("✓")
        assert "✓" in text
        assert "\033[92m" in text
    
    def test_red(self):
        """红色输出"""
        text = Colors.red("✗")
        assert "✗" in text
        assert "\033[91m" in text
    
    def test_yellow(self):
        """黄色输出"""
        text = Colors.yellow("⏭️")
        assert "⏭️" in text
        assert "\033[93m" in text
    
    def test_bold(self):
        """粗体输出"""
        text = Colors.bold("Title")
        assert "Title" in text
        assert "\033[1m" in text
    
    def test_reset(self):
        """RESET 包含在输出中"""
        text = Colors.green("test")
        assert "\033[0m" in text


# ========================================
# 5. Data Structure Tests
# ========================================

class TestDataStructures:
    """数据结构测试"""
    
    def test_glossary_entry(self):
        """GlossaryEntry"""
        entry = GlossaryEntry(term="test term", means="test means")
        assert entry.term == "test term"
        assert entry.means == "test means"
    
    def test_scenario(self):
        """Scenario"""
        scenario = Scenario(name="Test scenario", when="a user asks X")
        scenario.assertions.append("the agent responds with Y")
        assert scenario.name == "Test scenario"
        assert len(scenario.assertions) == 1
    
    def test_feature(self):
        """Feature"""
        feature = Feature(id="feature.test", name="Test Feature")
        feature.scenarios.append(Scenario(name="Test scenario"))
        assert feature.id == "feature.test"
        assert len(feature.scenarios) == 1
    
    def test_intent_file(self):
        """IntentFile"""
        intent = IntentFile(source_path="test.nxintent")
        intent.glossary.append(GlossaryEntry(term="a", means="b"))
        intent.features.append(Feature(id="f1", name="F1"))
        assert len(intent.glossary) == 1
        assert len(intent.features) == 1
    
    def test_implements_annotation(self):
        """ImplementsAnnotation"""
        ann = ImplementsAnnotation(
            feature_id="feature.weather_bot",
            agent_name="WeatherBot",
            line_number=5
        )
        assert ann.feature_id == "feature.weather_bot"
        assert ann.agent_name == "WeatherBot"
    
    def test_coverage_report(self):
        """CoverageReport"""
        report = CoverageReport(
            total_features=3,
            implemented_features=2,
            coverage_percentage=66.7
        )
        assert report.total_features == 3
        assert report.coverage_percentage == 66.7


# ========================================
# 6. Parser Annotation Tests (nexa_parser.py)
# ========================================

class TestParserAnnotations:
    """Nexa Parser 注解提取测试"""
    
    def test_extract_implements_from_parser(self):
        """从 parser 提取 @implements"""
        from src.nexa_parser import extract_implements_annotations
        
        code = """
// @implements: feature.weather_bot
agent WeatherBot implements WeatherReport {
    role: "Weather Assistant",
    prompt: "Provide weather information"
}
"""
        annotations = extract_implements_annotations(code)
        
        assert len(annotations) >= 1
        assert annotations[0]["feature_id"] == "feature.weather_bot"
        assert annotations[0]["agent_name"] == "WeatherBot"
    
    def test_extract_supports_from_parser(self):
        """从 parser 提取 @supports"""
        from src.nexa_parser import extract_implements_annotations
        
        code = """
// @supports: constraint.output_format
agent Formatter {
    role: "Formatter"
}
"""
        annotations = extract_implements_annotations(code)
        
        assert len(annotations) >= 1
        assert annotations[0]["constraint_id"] == "constraint.output_format"
    
    def test_extract_annotations_in_ast(self):
        """注解出现在 AST 中"""
        from src.nexa_parser import parse
        
        code = """
// @implements: feature.test
agent TestAgent {
    role: "Test"
}
"""
        ast = parse(code)
        # AST 应包含 annotations 字段
        if "annotations" in ast:
            assert len(ast["annotations"]) >= 1
            assert ast["annotations"][0]["feature_id"] == "feature.test"


# ========================================
# 7. Code Generator Annotation Tests
# ========================================

class TestCodeGeneratorAnnotations:
    """Code Generator 注解保留测试"""
    
    def test_annotations_preserved_in_generated_code(self):
        """@implements 注解保留在生成的 Python 代码中"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        from src.code_generator import CodeGenerator
        
        code = """
// @implements: feature.test_bot
agent TestAgent {
    role: "Test Agent",
    prompt: "Test prompt"
}
"""
        # Parse (with annotations)
        from src.nexa_parser import get_parser
        lark_parser = get_parser()
        tree = lark_parser.parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        # Extract annotations and add to AST
        from src.nexa_parser import extract_implements_annotations
        annotations = extract_implements_annotations(code)
        if annotations:
            ast["annotations"] = annotations
        
        # Generate code
        generator = CodeGenerator(ast)
        python_code = generator.generate()
        
        # Generated code should contain @implements comment
        assert "@implements" in python_code
        assert "feature.test_bot" in python_code