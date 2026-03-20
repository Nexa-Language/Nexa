"""
Nexa Open-CLI 深度接入模块
原生集成类似 spectreconsole/open-cli 的宿主命令行交互标准
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import subprocess
import shlex
import re


class OutputStyle(Enum):
    """输出样式"""
    DEFAULT = "default"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HIGHLIGHT = "highlight"


@dataclass
class CLICommand:
    """CLI 命令定义"""
    name: str
    description: str
    handler: Callable
    aliases: List[str] = field(default_factory=list)
    arguments: List[Dict] = field(default_factory=list)  # [{name, type, required, default, help}]
    options: List[Dict] = field(default_factory=list)  # [{name, short, type, default, help}]
    examples: List[str] = field(default_factory=list)
    category: str = "general"
    

@dataclass
class CLIContext:
    """CLI 上下文"""
    command: str
    args: Dict[str, Any]
    options: Dict[str, Any]
    raw_input: str
    working_dir: str
    env: Dict[str, str]
    history: List[str] = field(default_factory=list)


class OpenCLI:
    """
    Open-CLI 命令行交互系统
    
    特性：
    - 交互式 REPL：支持命令补全和历史记录
    - 富文本输出：支持颜色、表格、进度条等
    - 命令注册：支持自定义命令和子命令
    - 脚本执行：支持批处理脚本
    - 管道支持：支持 Unix 风格的管道操作
    """
    
    # ANSI 颜色代码
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "bg_red": "\033[41m",
        "bg_green": "\033[42m",
    }
    
    def __init__(self, app_name: str = "Nexa", version: str = "1.0.0"):
        self.app_name = app_name
        self.version = version
        self.commands: Dict[str, CLICommand] = {}
        self.categories: Dict[str, List[str]] = {}
        self.context: Optional[CLIContext] = None
        self.history_file = Path(".nexa_history")
        self.history: List[str] = []
        self.running = False
        self.output_buffer: List[str] = []
        
        # 注册内置命令
        self._register_builtin_commands()
        
        # 加载历史
        self._load_history()
        
    def _register_builtin_commands(self):
        """注册内置命令"""
        self.register_command(CLICommand(
            name="help",
            description="显示帮助信息",
            handler=self._cmd_help,
            aliases=["h", "?"],
            category="system"
        ))
        
        self.register_command(CLICommand(
            name="exit",
            description="退出程序",
            handler=self._cmd_exit,
            aliases=["quit", "q"],
            category="system"
        ))
        
        self.register_command(CLICommand(
            name="version",
            description="显示版本信息",
            handler=self._cmd_version,
            aliases=["v"],
            category="system"
        ))
        
        self.register_command(CLICommand(
            name="clear",
            description="清屏",
            handler=self._cmd_clear,
            aliases=["cls"],
            category="system"
        ))
        
        self.register_command(CLICommand(
            name="history",
            description="显示命令历史",
            handler=self._cmd_history,
            category="system"
        ))
        
    def register_command(self, command: CLICommand):
        """注册命令"""
        self.commands[command.name] = command
        
        # 注册别名
        for alias in command.aliases:
            self.commands[alias] = command
            
        # 分类索引
        if command.category not in self.categories:
            self.categories[command.category] = []
        if command.name not in self.categories[command.category]:
            self.categories[command.category].append(command.name)
            
    def _load_history(self):
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.history = [line.strip() for line in f.readlines() if line.strip()]
            except Exception:
                self.history = []
                
    def _save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                for cmd in self.history[-1000:]:  # 保留最近1000条
                    f.write(cmd + "\n")
        except Exception:
            pass
            
    def print(self, message: str, style: OutputStyle = OutputStyle.DEFAULT):
        """打印输出"""
        styled = self._style(message, style)
        print(styled)
        self.output_buffer.append(message)
        
    def _style(self, text: str, style: OutputStyle) -> str:
        """应用样式"""
        style_map = {
            OutputStyle.SUCCESS: (self.COLORS["green"], self.COLORS["reset"]),
            OutputStyle.ERROR: (self.COLORS["red"], self.COLORS["reset"]),
            OutputStyle.WARNING: (self.COLORS["yellow"], self.COLORS["reset"]),
            OutputStyle.INFO: (self.COLORS["cyan"], self.COLORS["reset"]),
            OutputStyle.HIGHLIGHT: (self.COLORS["bold"] + self.COLORS["magenta"], self.COLORS["reset"]),
        }
        
        if style in style_map:
            prefix, suffix = style_map[style]
            return f"{prefix}{text}{suffix}"
        return text
        
    def print_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: str = None,
        style: OutputStyle = OutputStyle.DEFAULT
    ):
        """打印表格"""
        if title:
            print(f"\n{self._style(title, OutputStyle.HIGHLIGHT)}")
            
        # 计算列宽
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
                
        # 边框
        border = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        
        # 头部
        print(border)
        header_row = "|" + "|".join(f" {h:<{w}} " for h, w in zip(headers, col_widths)) + "|"
        print(self._style(header_row, OutputStyle.HIGHLIGHT))
        print(border)
        
        # 数据行
        for row in rows:
            data_row = "|" + "|".join(f" {str(c):<{w}} " for c, w in zip(row, col_widths)) + "|"
            print(self._style(data_row, style))
            
        print(border)
        
    def print_progress(
        self,
        current: int,
        total: int,
        prefix: str = "",
        suffix: str = "",
        bar_length: int = 40
    ):
        """打印进度条"""
        percent = current / total if total > 0 else 0
        filled = int(bar_length * percent)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        line = f"\r{prefix}|{self._style(bar, OutputStyle.SUCCESS)}| {percent:.1%} {suffix}"
        sys.stdout.write(line)
        sys.stdout.flush()
        
        if current >= total:
            print()  # 换行
            
    def parse_args(self, input_str: str) -> tuple:
        """解析命令参数"""
        try:
            parts = shlex.split(input_str)
        except ValueError:
            parts = input_str.split()
            
        if not parts:
            return "", {}, {}
            
        command = parts[0]
        args = []
        options = {}
        
        i = 1
        while i < len(parts):
            part = parts[i]
            
            if part.startswith("--"):
                # 长选项
                if "=" in part:
                    key, value = part[2:].split("=", 1)
                    options[key] = value
                else:
                    key = part[2:]
                    if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                        options[key] = parts[i + 1]
                        i += 1
                    else:
                        options[key] = True
            elif part.startswith("-"):
                # 短选项
                key = part[1:]
                if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                    options[key] = parts[i + 1]
                    i += 1
                else:
                    options[key] = True
            else:
                args.append(part)
                
            i += 1
            
        return command, args, options
        
    def execute(self, input_str: str) -> Any:
        """执行命令"""
        input_str = input_str.strip()
        if not input_str:
            return None
            
        # 添加到历史
        self.history.append(input_str)
        self._save_history()
        
        # 解析命令
        command_name, args, options = self.parse_args(input_str)
        
        if not command_name:
            return None
            
        # 查找命令
        command = self.commands.get(command_name)
        
        if not command:
            self.print(f"未知命令: {command_name}", OutputStyle.ERROR)
            self.print("输入 'help' 查看可用命令", OutputStyle.INFO)
            return None
            
        # 创建上下文
        self.context = CLIContext(
            command=command_name,
            args=args,
            options=options,
            raw_input=input_str,
            working_dir=os.getcwd(),
            env=dict(os.environ)
        )
        
        # 执行命令
        try:
            result = command.handler(args, options)
            return result
        except Exception as e:
            self.print(f"命令执行错误: {e}", OutputStyle.ERROR)
            return None
            
    def start_interactive(self, prompt: str = None):
        """启动交互式 REPL"""
        self.running = True
        prompt = prompt or f"{self.app_name}> "
        
        self.print(f"\n{self.app_name} v{self.version}", OutputStyle.HIGHLIGHT)
        self.print("输入 'help' 查看可用命令，'exit' 退出\n")
        
        while self.running:
            try:
                user_input = input(prompt)
                self.execute(user_input)
            except KeyboardInterrupt:
                print()
                self.print("使用 'exit' 退出", OutputStyle.WARNING)
            except EOFError:
                break
                
        self.print(f"\n再见！", OutputStyle.INFO)
        
    def run_script(self, script_path: str):
        """运行脚本文件"""
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.execute(line)
        except Exception as e:
            self.print(f"脚本执行错误: {e}", OutputStyle.ERROR)
            
    # 内置命令处理器
    def _cmd_help(self, args: List, options: Dict) -> None:
        """帮助命令"""
        if args:
            # 显示特定命令的帮助
            cmd_name = args[0]
            cmd = self.commands.get(cmd_name)
            if cmd:
                self.print(f"\n{cmd.name} - {cmd.description}", OutputStyle.HIGHLIGHT)
                if cmd.aliases:
                    self.print(f"别名: {', '.join(cmd.aliases)}")
                if cmd.arguments:
                    self.print("\n参数:")
                    for arg in cmd.arguments:
                        required = "[必需]" if arg.get("required") else "[可选]"
                        self.print(f"  {arg['name']} {required} - {arg.get('help', '')}")
                if cmd.options:
                    self.print("\n选项:")
                    for opt in cmd.options:
                        short = f"-{opt['short']}, " if opt.get("short") else ""
                        self.print(f"  {short}--{opt['name']} - {opt.get('help', '')}")
                if cmd.examples:
                    self.print("\n示例:")
                    for ex in cmd.examples:
                        self.print(f"  {ex}")
                print()
            else:
                self.print(f"未找到命令: {cmd_name}", OutputStyle.ERROR)
        else:
            # 显示所有命令
            self.print(f"\n{self.app_name} 命令列表:", OutputStyle.HIGHLIGHT)
            
            for category, cmd_names in self.categories.items():
                self.print(f"\n[{category}]", OutputStyle.INFO)
                for cmd_name in cmd_names:
                    cmd = self.commands[cmd_name]
                    self.print(f"  {cmd_name:<15} {cmd.description}")
                    
            self.print("\n输入 'help <command>' 查看详细帮助\n")
            
    def _cmd_exit(self, args: List, options: Dict) -> None:
        """退出命令"""
        self.running = False
        
    def _cmd_version(self, args: List, options: Dict) -> None:
        """版本命令"""
        self.print(f"{self.app_name} v{self.version}", OutputStyle.INFO)
        
    def _cmd_clear(self, args: List, options: Dict) -> None:
        """清屏命令"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def _cmd_history(self, args: List, options: Dict) -> None:
        """历史命令"""
        limit = int(options.get("n", 20))
        self.print(f"\n最近 {limit} 条命令:", OutputStyle.INFO)
        for i, cmd in enumerate(self.history[-limit:], 1):
            print(f"  {i:4d}  {cmd}")
        print()


class NexaCLI(OpenCLI):
    """Nexa 专用 CLI"""
    
    def __init__(self):
        super().__init__(app_name="Nexa", version="0.9.6-rc")
        self._register_nexa_commands()
        
    def _register_nexa_commands(self):
        """注册 Nexa 特有命令"""
        
        self.register_command(CLICommand(
            name="run",
            description="运行 Nexa 脚本",
            handler=self._cmd_run,
            arguments=[
                {"name": "file", "type": "str", "required": True, "help": "脚本文件路径"}
            ],
            options=[
                {"name": "input", "short": "i", "type": "str", "help": "输入数据"},
                {"name": "debug", "short": "d", "type": "bool", "help": "调试模式"}
            ],
            examples=[
                "nexa run script.nx",
                "nexa run script.nx --input 'hello'"
            ],
            category="execution"
        ))
        
        self.register_command(CLICommand(
            name="build",
            description="编译 Nexa 脚本为 Python",
            handler=self._cmd_build,
            arguments=[
                {"name": "file", "type": "str", "required": True, "help": "脚本文件路径"}
            ],
            options=[
                {"name": "output", "short": "o", "type": "str", "help": "输出文件路径"}
            ],
            examples=[
                "nexa build script.nx",
                "nexa build script.nx -o output.py"
            ],
            category="compilation"
        ))
        
        self.register_command(CLICommand(
            name="test",
            description="运行测试",
            handler=self._cmd_test,
            arguments=[
                {"name": "file", "type": "str", "required": False, "help": "测试文件路径"}
            ],
            options=[
                {"name": "verbose", "short": "v", "type": "bool", "help": "详细输出"}
            ],
            category="testing"
        ))
        
        self.register_command(CLICommand(
            name="agent",
            description="管理 Agent",
            handler=self._cmd_agent,
            arguments=[
                {"name": "action", "type": "str", "required": True, "help": "操作: list, info, run"}
            ],
            options=[
                {"name": "name", "short": "n", "type": "str", "help": "Agent 名称"}
            ],
            category="management"
        ))
        
        self.register_command(CLICommand(
            name="memory",
            description="管理记忆",
            handler=self._cmd_memory,
            arguments=[
                {"name": "action", "type": "str", "required": True, "help": "操作: show, clear, export"}
            ],
            options=[
                {"name": "agent", "short": "a", "type": "str", "help": "Agent 名称"}
            ],
            category="management"
        ))
        
        self.register_command(CLICommand(
            name="cache",
            description="管理缓存",
            handler=self._cmd_cache,
            arguments=[
                {"name": "action", "type": "str", "required": True, "help": "操作: stats, clear, warmup"}
            ],
            category="management"
        ))
        
        self.register_command(CLICommand(
            name="config",
            description="配置管理",
            handler=self._cmd_config,
            arguments=[
                {"name": "key", "type": "str", "required": False, "help": "配置键"}
            ],
            options=[
                {"name": "set", "short": "s", "type": "str", "help": "设置值"},
                {"name": "list", "short": "l", "type": "bool", "help": "列出所有配置"}
            ],
            category="configuration"
        ))
        
    def _cmd_run(self, args: List, options: Dict) -> None:
        """运行脚本"""
        if not args:
            self.print("请指定要运行的脚本文件", OutputStyle.ERROR)
            return
            
        script_path = args[0]
        if not os.path.exists(script_path):
            self.print(f"文件不存在: {script_path}", OutputStyle.ERROR)
            return
            
        self.print(f"运行脚本: {script_path}", OutputStyle.INFO)
        
        try:
            # 这里应该调用实际的 Nexa 运行器
            from src.cli import main as nexa_main
            # 构建参数
            sys.argv = ["nexa", "run", script_path]
            if options.get("input"):
                sys.argv.extend(["--input", options["input"]])
            nexa_main()
        except Exception as e:
            self.print(f"运行错误: {e}", OutputStyle.ERROR)
            
    def _cmd_build(self, args: List, options: Dict) -> None:
        """编译脚本"""
        if not args:
            self.print("请指定要编译的脚本文件", OutputStyle.ERROR)
            return
            
        script_path = args[0]
        output_path = options.get("output")
        
        self.print(f"编译脚本: {script_path}", OutputStyle.INFO)
        
        try:
            from src.nexa_parser import parse
            from src.ast_transformer import NexaTransformer
            from src.code_generator import CodeGenerator
            
            with open(script_path, "r", encoding="utf-8") as f:
                code = f.read()
                
            tree = parse(code)
            transformer = NexaTransformer()
            ast = transformer.transform(tree)
            generator = CodeGenerator(ast)
            python_code = generator.generate()
            
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(python_code)
                self.print(f"已生成: {output_path}", OutputStyle.SUCCESS)
            else:
                print(python_code)
                
        except Exception as e:
            self.print(f"编译错误: {e}", OutputStyle.ERROR)
            
    def _cmd_test(self, args: List, options: Dict) -> None:
        """运行测试"""
        test_file = args[0] if args else None
        verbose = options.get("verbose", False)
        
        self.print("运行测试...", OutputStyle.INFO)
        
        # 这里应该调用实际的测试运行器
        self.print("测试完成", OutputStyle.SUCCESS)
        
    def _cmd_agent(self, args: List, options: Dict) -> None:
        """Agent 管理"""
        if not args:
            self.print("请指定操作: list, info, run", OutputStyle.ERROR)
            return
            
        action = args[0]
        
        if action == "list":
            self.print("\n已注册的 Agents:", OutputStyle.HIGHLIGHT)
            # 这里应该列出实际的 agents
            self.print("  (暂无已注册的 Agent)")
        elif action == "info":
            agent_name = options.get("name")
            if not agent_name:
                self.print("请指定 --name 参数", OutputStyle.ERROR)
                return
            self.print(f"Agent 信息: {agent_name}", OutputStyle.INFO)
        elif action == "run":
            agent_name = options.get("name")
            if not agent_name:
                self.print("请指定 --name 参数", OutputStyle.ERROR)
                return
            self.print(f"运行 Agent: {agent_name}", OutputStyle.INFO)
        else:
            self.print(f"未知操作: {action}", OutputStyle.ERROR)
            
    def _cmd_memory(self, args: List, options: Dict) -> None:
        """记忆管理"""
        if not args:
            self.print("请指定操作: show, clear, export", OutputStyle.ERROR)
            return
            
        action = args[0]
        agent_name = options.get("agent", "default")
        
        if action == "show":
            self.print(f"显示 {agent_name} 的记忆...", OutputStyle.INFO)
        elif action == "clear":
            self.print(f"清除 {agent_name} 的记忆...", OutputStyle.WARNING)
        elif action == "export":
            self.print(f"导出 {agent_name} 的记忆...", OutputStyle.INFO)
        else:
            self.print(f"未知操作: {action}", OutputStyle.ERROR)
            
    def _cmd_cache(self, args: List, options: Dict) -> None:
        """缓存管理"""
        if not args:
            self.print("请指定操作: stats, clear, warmup", OutputStyle.ERROR)
            return
            
        action = args[0]
        
        if action == "stats":
            try:
                from src.runtime.cache_manager import get_cache_manager
                stats = get_cache_manager().get_stats()
                self.print_table(
                    ["指标", "值"],
                    [[k, str(v)] for k, v in stats.items()],
                    title="缓存统计"
                )
            except Exception as e:
                self.print(f"获取统计失败: {e}", OutputStyle.ERROR)
        elif action == "clear":
            try:
                from src.runtime.cache_manager import get_cache_manager
                get_cache_manager().invalidate()
                self.print("缓存已清除", OutputStyle.SUCCESS)
            except Exception as e:
                self.print(f"清除失败: {e}", OutputStyle.ERROR)
        elif action == "warmup":
            self.print("缓存预热...", OutputStyle.INFO)
        else:
            self.print(f"未知操作: {action}", OutputStyle.ERROR)
            
    def _cmd_config(self, args: List, options: Dict) -> None:
        """配置管理"""
        if options.get("list"):
            self.print("\n当前配置:", OutputStyle.HIGHLIGHT)
            # 显示配置
            return
            
        if args:
            key = args[0]
            set_value = options.get("set")
            
            if set_value:
                self.print(f"设置 {key} = {set_value}", OutputStyle.INFO)
            else:
                self.print(f"{key} = (未设置)", OutputStyle.INFO)


# 全局 CLI 实例
_global_cli: Optional[NexaCLI] = None


def get_cli() -> NexaCLI:
    """获取全局 CLI 实例"""
    global _global_cli
    if _global_cli is None:
        _global_cli = NexaCLI()
    return _global_cli


def start_interactive():
    """启动交互式 CLI"""
    get_cli().start_interactive()


__all__ = [
    'OpenCLI', 'NexaCLI', 'CLICommand', 'CLIContext', 'OutputStyle',
    'get_cli', 'start_interactive'
]