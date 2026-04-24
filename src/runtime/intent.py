# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================

"""
Nexa Intent Runtime — Intent-Driven Development (IDD) 系统

让需求文档变成可执行测试，形成"需求→实现→验证"的闭环。

核心功能:
1. .nxintent 文件解析（YAML格式 + Markdown Glossary）
2. Feature/Scenario 结构解析
3. @implements 注解扫描（从 .nx 文件中提取）
4. intent check 执行流程（解析 → 重写 → 执行 → 输出）
5. intent coverage 计算（特性覆盖率百分比）
6. 彩色输出（绿色✓ / 红色✗ / 黄色⏭️）

使用方式:
    from src.runtime.intent import IntentRunner
    
    runner = IntentRunner()
    result = runner.check("weather_bot.nx")
    coverage = runner.coverage("weather_bot.nx")
"""

import re
import os
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from src.ial import (
    Vocabulary, TermEntry, Check, CheckOp, AgentAssertion, ProtocolCheck,
    PipelineCheck, SemanticCheck, CheckResult, ScenarioResult, FeatureResult,
    Primitive, resolve, resolve_scenario_assertions, execute_primitive, 
    execute_primitives, create_standard_vocabulary
)


# ========================================
# ANSI 颜色输出
# ========================================

class Colors:
    """ANSI 颜色常量"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    
    @staticmethod
    def green(text: str) -> str:
        return f"{Colors.GREEN}{text}{Colors.RESET}"
    
    @staticmethod
    def red(text: str) -> str:
        return f"{Colors.RED}{text}{Colors.RESET}"
    
    @staticmethod
    def yellow(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.RESET}"
    
    @staticmethod
    def blue(text: str) -> str:
        return f"{Colors.BLUE}{text}{Colors.RESET}"
    
    @staticmethod
    def cyan(text: str) -> str:
        return f"{Colors.CYAN}{text}{Colors.RESET}"
    
    @staticmethod
    def bold(text: str) -> str:
        return f"{Colors.BOLD}{text}{Colors.RESET}"
    
    @staticmethod
    def dim(text: str) -> str:
        return f"{Colors.DIM}{text}{Colors.RESET}"


# ========================================
# 数据结构
# ========================================

@dataclass
class GlossaryEntry:
    """Glossary 术语条目（从 .nxintent 文件解析）"""
    term: str          # 术语模式
    means: str         # 展开目标
    description: str = ""


@dataclass
class Scenario:
    """Intent Scenario"""
    name: str
    when: str = ""          # "When a user asks X"
    assertions: List[str] = field(default_factory=list)  # 断言列表
    context: Dict[str, Any] = field(default_factory=dict)  # 执行上下文


@dataclass 
class Feature:
    """Intent Feature"""
    id: str
    name: str
    description: str = ""
    scenarios: List[Scenario] = field(default_factory=list)


@dataclass
class IntentFile:
    """解析后的 .nxintent 文件"""
    glossary: List[GlossaryEntry] = field(default_factory=list)
    features: List[Feature] = field(default_factory=list)
    source_path: str = ""


@dataclass
class ImplementsAnnotation:
    """代码中的 @implements 注解"""
    feature_id: str
    agent_name: str
    line_number: int = 0
    source: str = ""  # 注解来源文件
    annotation_type: str = "implements"  # "implements" or "supports"


@dataclass
class CoverageReport:
    """Intent Coverage 报告"""
    total_features: int = 0
    implemented_features: int = 0
    tested_features: int = 0
    passed_features: int = 0
    coverage_percentage: float = 0.0
    feature_details: Dict[str, Dict] = field(default_factory=dict)


# ========================================
# .nxintent 文件解析器
# ========================================

class NxIntentParser:
    """
    .nxintent 文件解析器
    
    支持 YAML 格式，包含:
    - Glossary 表（Markdown 表格格式）
    - Feature / Scenario 结构
    
    文件格式示例:
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
            When a user asks "What is the weather in Beijing?"
            → the agent responds with "weather"
            → the response is valid
    """
    
    def parse(self, content: str, source_path: str = "") -> IntentFile:
        """
        解析 .nxintent 文件内容
        
        Args:
            content: 文件内容字符串
            source_path: 源文件路径（用于追踪）
        
        Returns:
            IntentFile 解析结果
        """
        intent_file = IntentFile(source_path=source_path)
        
        # 分离 Glossary 和 Feature 部分
        glossary_text, features_text = self._split_sections(content)
        
        # 解析 Glossary
        if glossary_text:
            intent_file.glossary = self._parse_glossary(glossary_text)
        
        # 解析 Features (YAML)
        if features_text:
            intent_file.features = self._parse_features(features_text)
        
        return intent_file
    
    def parse_file(self, file_path: str) -> IntentFile:
        """
        从文件路径解析 .nxintent
        
        Args:
            file_path: .nxintent 文件路径
        
        Returns:
            IntentFile 解析结果
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Intent file not found: {file_path}")
        
        content = path.read_text(encoding='utf-8')
        return self.parse(content, source_path=str(path))
    
    def _split_sections(self, content: str) -> Tuple[str, str]:
        """
        分离 Glossary 和 Feature 部分
        
        Glossary 在 "---" 分隔线之前，Features 在之后
        """
        # 查找分隔线
        separator_match = re.search(r'^---\s*$', content, re.MULTILINE)
        
        if separator_match:
            glossary_text = content[:separator_match.start()]
            features_text = content[separator_match.end():]
            return (glossary_text.strip(), features_text.strip())
        
        # 无分隔线 → 整个文件作为 Features（YAML格式）
        # 但先检查是否包含 Glossary 标记
        glossary_match = re.search(r'^##\s+Glossary\s*$', content, re.MULTILINE)
        if glossary_match:
            # 有 Glossary 标记但没有分隔线 → 尝试按 Feature 标记分离
            feature_match = re.search(r'^Feature:', content, re.MULTILINE)
            if feature_match:
                glossary_text = content[:feature_match.start()]
                features_text = content[feature_match.start():]
                return (glossary_text.strip(), features_text.strip())
        
        return ("", content.strip())
    
    def _parse_glossary(self, text: str) -> List[GlossaryEntry]:
        """
        解析 Glossary 表格
        
        支持 Markdown 表格格式:
        | Term | Means |
        |------|-------|
        | a user asks {question} | agent run with input {question} |
        """
        entries = []
        
        # 去掉 Glossary 标题
        text = re.sub(r'^##\s+Glossary\s*', '', text).strip()
        
        # 解析 Markdown 表格行
        lines = text.split('\n')
        table_rows = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('|') and not re.match(r'^\|[\s\-:|]+\|$', line):
                # 不是分隔行 → 数据行
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if len(cells) >= 2:
                    table_rows.append(cells)
        
        # 跳过标题行（如果存在）
        if table_rows and table_rows[0][0].lower() == 'term':
            table_rows = table_rows[1:]
        
        # 转换为 GlossaryEntry
        for row in table_rows:
            term = row[0].strip()
            means = row[1].strip() if len(row) > 1 else ""
            desc = row[2].strip() if len(row) > 2 else ""
            entries.append(GlossaryEntry(term=term, means=means, description=desc))
        
        # 也支持 YAML 格式的 Glossary
        # 尝试解析为 YAML
        try:
            yaml_data = yaml.safe_load(text)
            if isinstance(yaml_data, dict) and 'glossary' in yaml_data:
                for item in yaml_data['glossary']:
                    if isinstance(item, dict):
                        entries.append(GlossaryEntry(
                            term=item.get('term', ''),
                            means=item.get('means', ''),
                            description=item.get('description', '')
                        ))
        except yaml.YAMLError:
            pass
        
        return entries
    
    def _parse_features(self, text: str) -> List[Feature]:
        """
        解析 Features (YAML 格式)
        
        支持格式:
        1. 纯 YAML 格式（自动转换缩进结构）
        2. Nexa 自定义格式（Feature: ... Scenario: ... → 断言）
        """
        features = []
        
        # 预处理：将 Nexa 格式转换为合法 YAML
        yaml_text = self._preprocess_to_yaml(text)
        
        try:
            data = yaml.safe_load(yaml_text)
            if data is None:
                return []
            
            # 处理不同 YAML 结构
            if isinstance(data, dict):
                # 可能是单个 Feature 或多个 Feature
                if 'Feature' in data:
                    feature = self._yaml_to_feature(data)
                    if feature:
                        features.append(feature)
                elif 'features' in data:
                    for item in data['features']:
                        feature = self._yaml_to_feature(item)
                        if feature:
                            features.append(feature)
                else:
                    # 尝试查找 Feature 键（可能带后缀如 "Feature: Weather Bot"）
                    for key in data:
                        if key.startswith('Feature'):
                            feature_data = {key: data[key]}
                            # 合入其他键作为 feature 属性
                            if 'id' in data:
                                feature_data['id'] = data['id']
                            if 'description' in data:
                                feature_data['description'] = data['description']
                            feature = self._yaml_to_feature(feature_data)
                            if feature:
                                features.append(feature)
                            break
            
            elif isinstance(data, list):
                for item in data:
                    feature = self._yaml_to_feature(item)
                    if feature:
                        features.append(feature)
            
        except yaml.YAMLError as e:
            # YAML 解析失败 → 尝试文本解析
            features = self._parse_features_text(text)
        
        # 如果 YAML 解析结果为空 → 尝试文本解析
        if not features:
            features = self._parse_features_text(text)
        
        return features
    
    def _preprocess_to_yaml(self, text: str) -> str:
        """
        预处理 Nexa intent 格式为合法 YAML
        
        转换规则:
        - "Feature: Name" → 键名（需要引号包裹含冒号的键）
        - "→ assertion" → 作为列表项
        - "When ..." → 作为 when 属性
        - "id: feature.xxx" → 作为 id 属性
        """
        result_lines = []
        
        for line in text.split('\n'):
            stripped = line.strip()
            
            # 处理 → 断言行 → 转为 YAML 列表项
            if stripped.startswith('→'):
                indent = len(line) - len(stripped)
                assertion_text = stripped[1:].strip()
                # 去掉引号包裹
                result_lines.append(f"{' ' * indent}- \"{assertion_text}\"")
                continue
            
            # 处理 Feature 行 → 转为 YAML 键
            if re.match(r'^Feature\s*:', stripped):
                indent = len(line) - len(stripped)
                feature_name = stripped.split(':', 1)[1].strip()
                result_lines.append(f"{' ' * indent}\"Feature: {feature_name}\":")
                continue
            
            # 处理 Scenario 行
            if re.match(r'^Scenario\s*:', stripped):
                indent = len(line) - len(stripped)
                scenario_name = stripped.split(':', 1)[1].strip()
                result_lines.append(f"{' ' * indent}\"Scenario: {scenario_name}\":")
                continue
            
            # 处理 When 行
            if re.match(r'^When\s+', stripped):
                indent = len(line) - len(stripped)
                when_text = stripped[4:].strip()
                result_lines.append(f"{' ' * indent}when: \"{when_text}\"")
                continue
            
            # 其他行保持不变
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _yaml_to_feature(self, data: Any) -> Optional[Feature]:
        """
        从 YAML 数据结构构造 Feature
        """
        if not isinstance(data, dict):
            return None
        
        # 提取 feature 名称
        feature_name = ""
        for key in data:
            if key.startswith('Feature'):
                feature_name = key.split(':', 1)[1].strip() if ':' in key else str(data[key])
                break
        if not feature_name:
            feature_name = data.get('name', 'Unknown')
        
        # 提取 feature ID
        feature_id = data.get('id', f"feature.{feature_name.lower().replace(' ', '_')}")
        description = data.get('description', '')
        
        # 提取 scenarios
        scenarios = []
        
        # 查找 Scenario 键
        for key in data:
            if key.startswith('Scenario'):
                scenario_data = data[key]
                scenario_name = key.split(':', 1)[1].strip() if ':' in key else str(data[key])
                
                scenario = Scenario(name=scenario_name)
                
                if isinstance(scenario_data, dict):
                    scenario.when = scenario_data.get('when', '')
                    assertions = scenario_data.get('assertions', scenario_data.get('→', []))
                    if isinstance(assertions, list):
                        scenario.assertions = [str(a).strip('"') for a in assertions]
                    scenario.context = scenario_data.get('context', {})
                elif isinstance(scenario_data, list):
                    # 简单列表 → 全部是断言
                    scenario.assertions = [str(a).strip('"') for a in scenario_data]
                
                scenarios.append(scenario)
        
        # 也查找 scenarios 列表
        if 'scenarios' in data:
            for item in data['scenarios']:
                if isinstance(item, dict):
                    scenario_name = item.get('name', 'Unknown')
                    scenario = Scenario(
                        name=scenario_name,
                        when=item.get('when', ''),
                        assertions=[str(a).strip('"') for a in item.get('assertions', [])],
                        context=item.get('context', {})
                    )
                    scenarios.append(scenario)
        
        feature = Feature(
            id=feature_id,
            name=feature_name,
            description=description,
            scenarios=scenarios
        )
        
        return feature
    
    def _parse_features_text(self, text: str) -> List[Feature]:
        """
        纯文本解析 Features（fallback，当 YAML 解析失败时）
        
        解析 Nexa 自定义格式:
            Feature: Weather Bot
              id: feature.weather_bot
              description: "Weather information agent"
            
              Scenario: Weather query
                When a user asks "What is the weather?"
                → the agent responds with "weather"
                → the response is valid
        """
        features = []
        current_feature = None
        current_scenario = None
        
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            
            # Feature 行
            feature_match = re.match(r'^Feature\s*:\s*(.+)$', stripped)
            if feature_match:
                feature_name = feature_match.group(1).strip()
                current_feature = Feature(
                    id=f"feature.{feature_name.lower().replace(' ', '_')}",
                    name=feature_name
                )
                features.append(current_feature)
                current_scenario = None
                continue
            
            # id 行
            id_match = re.match(r'^id\s*:\s*(.+)$', stripped)
            if id_match and current_feature:
                current_feature.id = id_match.group(1).strip()
                continue
            
            # description 行
            desc_match = re.match(r'^description\s*:\s*(.+)$', stripped)
            if desc_match and current_feature:
                current_feature.description = desc_match.group(1).strip().strip('"')
                continue
            
            # Scenario 行
            scenario_match = re.match(r'^Scenario\s*:\s*(.+)$', stripped)
            if scenario_match and current_feature:
                scenario_name = scenario_match.group(1).strip()
                current_scenario = Scenario(name=scenario_name)
                current_feature.scenarios.append(current_scenario)
                continue
            
            # When 行
            when_match = re.match(r'^When\s+(.+)$', stripped)
            if when_match and current_scenario:
                current_scenario.when = when_match.group(1).strip()
                continue
            
            # → 断言行
            arrow_match = re.match(r'^→\s*(.+)$', stripped)
            if arrow_match and current_scenario:
                assertion_text = arrow_match.group(1).strip()
                current_scenario.assertions.append(assertion_text)
                continue
        
        return features


# ========================================
# @implements 注解扫描器
# ========================================

class AnnotationScanner:
    """
    从 Nexa 源代码中扫描 @implements 和 @supports 注解
    
    支持格式:
        // @implements: feature.weather_bot
        // @supports: constraint.output_format
        agent WeatherBot implements WeatherReport { ... }
    """
    
    def scan_file(self, file_path: str) -> List[ImplementsAnnotation]:
        """
        扫描 .nx 文件中的注解
        
        Args:
            file_path: .nx 文件路径
        
        Returns:
            注解列表
        """
        path = Path(file_path)
        if not path.exists():
            return []
        
        content = path.read_text(encoding='utf-8')
        return self.scan_content(content, source_path=str(path))
    
    def scan_content(self, content: str, source_path: str = "") -> List[ImplementsAnnotation]:
        """
        扫描源代码内容中的注解
        
        Args:
            content: 源代码内容
            source_path: 源文件路径
        
        Returns:
            注解列表
        """
        annotations = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # 匹配 @implements 注解
            impl_match = re.search(r'@implements\s*:\s*([\w.]+)', line)
            if impl_match:
                feature_id = impl_match.group(1)
                # 查找对应的 agent 名称（通常在下一行或同一行）
                agent_name = self._find_agent_name(lines, i)
                annotations.append(ImplementsAnnotation(
                    feature_id=feature_id,
                    agent_name=agent_name,
                    line_number=i + 1,
                    source=source_path,
                    annotation_type="implements"
                ))
            
            # 匹配 @supports 注解
            support_match = re.search(r'@supports\s*:\s*([\w.]+)', line)
            if support_match:
                constraint_id = support_match.group(1)
                agent_name = self._find_agent_name(lines, i)
                # @supports 也创建一个注解，但类型不同
                annotations.append(ImplementsAnnotation(
                    feature_id=constraint_id,
                    agent_name=agent_name,
                    line_number=i + 1,
                    source=source_path,
                    annotation_type="supports"
                ))
        
        return annotations
    
    def _find_agent_name(self, lines: List[str], annotation_line: int) -> str:
        """
        从注解行附近查找 agent 名称
        
        通常 @implements 注解在 agent 声明行之前或同一行。
        """
        # 查找当前行和后续几行中的 agent 关键字
        for j in range(annotation_line, min(annotation_line + 3, len(lines))):
            agent_match = re.search(r'agent\s+(\w+)', lines[j])
            if agent_match:
                return agent_match.group(1)
        
        # 查找前一行
        if annotation_line > 0:
            agent_match = re.search(r'agent\s+(\w+)', lines[annotation_line - 1])
            if agent_match:
                return agent_match.group(1)
        
        return "unknown"
    
    def find_implemented_feature_ids(self, file_path: str) -> Set[str]:
        """
        找出文件中所有 @implements 引用的 feature IDs
        
        Args:
            file_path: .nx 文件路径
        
        Returns:
            feature ID 集合
        """
        annotations = self.scan_file(file_path)
        return {a.feature_id for a in annotations}


# ========================================
# Intent Runner — 核心执行引擎
# ========================================

class IntentRunner:
    """
    Intent-Driven Development 执行引擎
    
    核心功能:
    1. intent check — 验证代码是否符合 intent
    2. intent coverage — 显示特性覆盖率
    3. 彩色输出（✓/✗/⏭️）
    """
    
    def __init__(self, verbose: bool = False):
        self.parser = NxIntentParser()
        self.scanner = AnnotationScanner()
        self.verbose = verbose
    
    def check(self, nx_file_path: str, intent_file_path: str = None) -> List[FeatureResult]:
        """
        执行 intent check — 验证代码是否符合 intent
        
        流程:
        1. 查找对应的 .nxintent 文件
        2. 解析 intent 文件 → Features/Scenarios/Glossary
        3. 扫描 .nx 文件中的 @implements 注解
        4. 构建 Vocabulary（标准 + 用户 Glossary）
        5. 对每个 Scenario 的断言执行: resolve → execute → 输出 ✓/✗/⏭️
        
        Args:
            nx_file_path: .nx 源文件路径
            intent_file_path: .nxintent 文件路径（可选，默认自动查找）
        
        Returns:
            FeatureResult 列表
        """
        # 1. 查找 .nxintent 文件
        if intent_file_path is None:
            intent_file_path = self._find_intent_file(nx_file_path)
        
        if not intent_file_path or not Path(intent_file_path).exists():
            print(Colors.yellow("⏭️  No .nxintent file found for " + nx_file_path))
            return []
        
        # 2. 解析 intent 文件
        intent_file = self.parser.parse_file(intent_file_path)
        
        # 3. 扫描 @implements 注解
        annotations = self.scanner.scan_file(nx_file_path)
        implemented_ids = {a.feature_id for a in annotations}
        
        # 4. 构建 Vocabulary
        vocabulary = self._build_vocabulary(intent_file)
        
        # 5. 尝试构建和加载 runtime
        runtime_context = self._build_runtime_context(nx_file_path, annotations)
        
        # 6. 执行检查并输出结果
        print(Colors.bold("\n🔍 Intent Check: " + nx_file_path))
        print(Colors.dim("   Intent file: " + intent_file_path))
        print()
        
        feature_results = []
        
        for feature in intent_file.features:
            feature_result = FeatureResult(
                feature_id=feature.id,
                feature_name=feature.name
            )
            
            # 检查 feature 是否有 @implements
            is_implemented = feature.id in implemented_ids
            
            if not is_implemented:
                print(Colors.yellow(f"⏭️  Feature '{feature.name}' ({feature.id}) — not implemented"))
                feature_result.passed = True  # 未实现视为 skipped
                continue
            
            print(Colors.blue(f"📋 Feature: {feature.name} ({feature.id})"))
            
            for scenario in feature.scenarios:
                scenario_result = ScenarioResult(
                    scenario_name=scenario.name,
                    feature_id=feature.id
                )
                
                # 构建场景上下文
                scenario_context = {**runtime_context, **scenario.context}
                if scenario.when:
                    scenario_context["when_input"] = scenario.when
                
                # 解析断言 → 原语
                primitives = resolve_scenario_assertions(
                    scenario.assertions, vocabulary, context=scenario_context
                )
                
                print(f"  🎯 Scenario: {scenario.name}")
                
                # 执行原语
                check_results = execute_primitives(primitives, scenario_context)
                
                for result in check_results:
                    scenario_result.results.append(result)
                    self._print_check_result(result)
                
                scenario_result.passed = all(r.passed for r in scenario_result.results)
                feature_result.scenario_results.append(scenario_result)
                
                # 场景结果摘要
                passed_count = sum(1 for r in scenario_result.results if r.passed)
                total_count = len(scenario_result.results)
                symbol = Colors.green("✓") if scenario_result.passed else Colors.red("✗")
                print(f"    {symbol} {scenario.name}: {passed_count}/{total_count} checks passed")
                print()
            
            feature_result.passed = all(sr.passed for sr in feature_result.scenario_results)
            feature_results.append(feature_result)
        
        # 总结果摘要
        self._print_summary(feature_results)
        
        return feature_results
    
    def coverage(self, nx_file_path: str, intent_file_path: str = None) -> CoverageReport:
        """
        计算 intent coverage — 特性覆盖率
        
        流程:
        1. 查找 .nxintent 文件
        2. 解析 Features
        3. 扫描 @implements 注解
        4. 计算覆盖率
        
        Args:
            nx_file_path: .nx 源文件路径
            intent_file_path: .nxintent 文件路径（可选）
        
        Returns:
            CoverageReport
        """
        # 查找 .nxintent 文件
        if intent_file_path is None:
            intent_file_path = self._find_intent_file(nx_file_path)
        
        if not intent_file_path or not Path(intent_file_path).exists():
            print(Colors.yellow("⏭️  No .nxintent file found"))
            report = CoverageReport()
            return report
        
        # 解析 intent 文件
        intent_file = self.parser.parse_file(intent_file_path)
        
        # 扫描注解
        annotations = self.scanner.scan_file(nx_file_path)
        implemented_ids = {a.feature_id for a in annotations}
        
        # 计算 coverage
        total_features = len(intent_file.features)
        implemented_features = 0
        tested_features = 0
        feature_details = {}
        
        for feature in intent_file.features:
            is_implemented = feature.id in implemented_ids
            has_scenarios = len(feature.scenarios) > 0
            
            if is_implemented:
                implemented_features += 1
            if has_scenarios:
                tested_features += 1
            
            feature_details[feature.id] = {
                "name": feature.name,
                "implemented": is_implemented,
                "has_scenarios": has_scenarios,
                "scenario_count": len(feature.scenarios),
                "annotations": [a for a in annotations if a.feature_id == feature.id]
            }
        
        # 覆盖率百分比
        if total_features > 0:
            coverage_percentage = (implemented_features / total_features) * 100
        else:
            coverage_percentage = 0.0
        
        report = CoverageReport(
            total_features=total_features,
            implemented_features=implemented_features,
            tested_features=tested_features,
            passed_features=0,  # 需要 check 才能确定
            coverage_percentage=coverage_percentage,
            feature_details=feature_details
        )
        
        # 输出覆盖率报告
        self._print_coverage_report(report)
        
        return report
    
    def _find_intent_file(self, nx_file_path: str) -> Optional[str]:
        """
        自动查找与 .nx 文件对应的 .nxintent 文件
        
        查找策略:
        1. 同名 .nxintent（如 weather_bot.nx → weather_bot.nxintent）
        2. 同目录下的任何 .nxintent 文件
        3. 父目录中的 .nxintent 文件
        """
        nx_path = Path(nx_file_path)
        
        # 策略 1: 同名 .nxintent
        intent_path = nx_path.with_suffix('.nxintent')
        if intent_path.exists():
            return str(intent_path)
        
        # 策略 2: 同目录下的 .nxintent 文件
        for f in nx_path.parent.glob('*.nxintent'):
            return str(f)
        
        # 策略 3: 父目录中的 .nxintent 文件
        for f in nx_path.parent.parent.glob('*.nxintent'):
            return str(f)
        
        return None
    
    def _build_vocabulary(self, intent_file: IntentFile) -> Vocabulary:
        """
        构建 Vocabulary — 合并标准词汇和用户 Glossary
        
        用户 Glossary 覆盖标准词汇中的同名术语。
        """
        vocabulary = create_standard_vocabulary()
        
        # 合入用户 Glossary
        for entry in intent_file.glossary:
            # 判断 entry_type
            means = entry.means
            
            # 检查是否是展开模式（包含 → 或列表）
            if '→' in means or means.startswith('['):
                # 展开: "term1 → term2" 或 "[term1, term2]"
                if means.startswith('['):
                    # 列表格式
                    try:
                        expanded = yaml.safe_load(means)
                        if isinstance(expanded, list):
                            vocabulary.register(
                                term=entry.term,
                                means=expanded,
                                entry_type="expansion",
                                description=entry.description
                            )
                    except yaml.YAMLError:
                        vocabulary.register(
                            term=entry.term,
                            means=means,
                            entry_type="expansion",
                            description=entry.description
                        )
                else:
                    # → 格式: "term → expansion"
                    parts = means.split('→')
                    expanded = [p.strip() for p in parts if p.strip()]
                    vocabulary.register(
                        term=entry.term,
                        means=expanded,
                        entry_type="expansion",
                        description=entry.description
                    )
            else:
                # 原语映射: "output contains X" → 单个展开字符串
                vocabulary.register(
                    term=entry.term,
                    means=means,
                    entry_type="expansion",
                    description=entry.description
                )
        
        return vocabulary
    
    def _build_runtime_context(self, nx_file_path: str,
                               annotations: List[ImplementsAnnotation]) -> Dict[str, Any]:
        """
        构建 runtime 上下文
        
        尝试编译 .nx 文件并加载为 Python 模块，供 Agent 断言使用。
        """
        context = {
            "nx_file_path": nx_file_path,
            "annotations": annotations,
        }
        
        # 尝试构建 .nx → .py
        try:
            from src.cli import build_file
            generated_py_path = build_file(nx_file_path)
            context["generated_py_path"] = generated_py_path
            
            # 尝试动态加载
            import importlib.util
            dir_path = os.path.dirname(os.path.abspath(generated_py_path))
            if dir_path not in sys.path:
                sys.path.insert(0, dir_path)
            
            module_name = os.path.basename(generated_py_path)[:-3]
            spec = importlib.util.spec_from_file_location(module_name, generated_py_path)
            if spec:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                try:
                    spec.loader.exec_module(module)
                    context["runtime_module"] = module
                except Exception:
                    pass
        except Exception:
            pass
        
        # 从注解中提取 agent_name 和 protocol_name
        for annotation in annotations:
            if annotation.feature_id.startswith("feature."):
                context["agent_name"] = annotation.agent_name
        
        # 从 .nx 文件内容中提取 protocol 信息
        try:
            content = Path(nx_file_path).read_text(encoding='utf-8')
            protocol_match = re.search(r'implements\s+(\w+)', content)
            if protocol_match:
                context["protocol_name"] = protocol_match.group(1)
        except Exception:
            pass
        
        return context
    
    def _print_check_result(self, result: CheckResult):
        """
        打印单个检查结果（彩色）
        """
        if result.passed:
            if "skipped" in result.message.lower():
                symbol = Colors.yellow("⏭️")
            else:
                symbol = Colors.green("✓")
        else:
            symbol = Colors.red("✗")
        
        primitive_desc = str(result.primitive)
        if len(primitive_desc) > 80:
            primitive_desc = primitive_desc[:80] + "..."
        
        message = result.message
        if len(message) > 100:
            message = message[:100] + "..."
        
        print(f"    {symbol} {Colors.dim(primitive_desc)}")
        if self.verbose and message:
            print(f"       {Colors.dim(message)}")
    
    def _print_summary(self, feature_results: List[FeatureResult]):
        """
        打印总结果摘要
        """
        total_scenarios = sum(len(fr.scenario_results) for fr in feature_results)
        passed_scenarios = sum(
            1 for fr in feature_results 
            for sr in fr.scenario_results if sr.passed
        )
        total_checks = sum(
            len(sr.results) for fr in feature_results for sr in fr.scenario_results
        )
        passed_checks = sum(
            1 for fr in feature_results 
            for sr in fr.scenario_results 
            for r in sr.results if r.passed
        )
        skipped_checks = sum(
            1 for fr in feature_results 
            for sr in fr.scenario_results 
            for r in sr.results if r.passed and "skipped" in r.message.lower()
        )
        
        all_passed = all(fr.passed for fr in feature_results)
        
        print(Colors.bold("=" * 50))
        if all_passed:
            print(Colors.green(Colors.bold(f"✅ All features passed!")))
        else:
            print(Colors.red(Colors.bold(f"❌ Some features failed!")))
        
        print(f"  Features:  {len(feature_results)}")
        print(f"  Scenarios: {passed_scenarios}/{total_scenarios} passed")
        print(f"  Checks:    {passed_checks}/{total_checks} passed ({skipped_checks} skipped)")
        print(Colors.bold("=" * 50))
    
    def _print_coverage_report(self, report: CoverageReport):
        """
        打印覆盖率报告（彩色）
        """
        print(Colors.bold("\n📊 Intent Coverage Report"))
        print(Colors.bold("=" * 50))
        
        for feature_id, details in report.feature_details.items():
            name = details["name"]
            implemented = details["implemented"]
            has_scenarios = details["has_scenarios"]
            scenario_count = details["scenario_count"]
            
            impl_symbol = Colors.green("✓") if implemented else Colors.red("✗")
            test_symbol = Colors.green("✓") if has_scenarios else Colors.yellow("⏭️")
            
            print(f"  {impl_symbol} {Colors.bold(name)} ({feature_id})")
            print(f"    Implemented: {impl_symbol}  Scenarios: {test_symbol} ({scenario_count})")
        
        print(Colors.bold("=" * 50))
        
        # 覆盖率百分比
        pct = report.coverage_percentage
        if pct >= 80:
            pct_color = Colors.green
        elif pct >= 50:
            pct_color = Colors.yellow
        else:
            pct_color = Colors.red
        
        print(f"  Coverage: {pct_color(f'{pct:.1f}%')} "
              f"({report.implemented_features}/{report.total_features} features implemented)")
        print(Colors.bold("=" * 50))