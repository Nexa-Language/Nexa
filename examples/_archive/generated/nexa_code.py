#!/usr/bin/env python3
"""
Nexa Code — Interactive AI Programming Assistant CLI

A Claude Code-like interactive CLI built on Nexa v2.0 Harness Runtime.
Features:
  - Interactive REPL with multi-turn conversation
  - File read/write/search tools
  - Shell command execution
  - ReAct autoloop (Reason→Act→Observe→Reflect)
  - Context management with importance-weighted paging
  - Lifecycle hooks (before_step/after_step)
  - Reflection injection for self-correction
  - State snapshot/restore for error recovery
  - Output verification
  - Multi-agent orchestration (CodeAssistant + CodeReviewer)

Usage:
  python nexa_code.py              # Start interactive session
  python nexa_code.py "task"       # One-shot mode
  python nexa_code.py --model X    # Override model
"""

import os
import sys
import json
import time
import subprocess
import readline  # GNU readline for history/editing
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Nexa runtime imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.runtime.secrets import nexa_secrets
from src.runtime.harness_kernel import (
    HarnessKernel, HarnessRuntimeMode, AutoLoopConfig, StepResult, get_kernel, reset_kernel
)
from src.runtime.execution_engine import ExecutionEngine
from src.runtime.context_manager import ContextManager, estimate_tokens
from src.runtime.tool_registry import ToolRegistry, ToolSchema, get_tool_registry
from src.runtime.lifecycle_hooks import LifecycleHookManager
from src.runtime.state_store import StateStore
from src.runtime.trace_system import TraceSystem
from src.runtime.evaluation_interface import EvaluationInterface, VerifyResult
from src.runtime.llm_router import LLMRouter, ModelRequirement

# ═══════════════════════════════════════════════════════════════════════
#  ANSI Colors & Formatting
# ═══════════════════════════════════════════════════════════════════════

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"

    @staticmethod
    def enabled() -> bool:
        """Check if terminal supports colors."""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


def cprint(text: str, color: str = Colors.RESET, bold: bool = False) -> None:
    """Print with color support."""
    if not Colors.enabled():
        print(text)
        return
    prefix = color
    if bold:
        prefix = Colors.BOLD + color
    print(f"{prefix}{text}{Colors.RESET}")


def print_banner() -> None:
    """Print Nexa Code startup banner."""
    cprint("", Colors.CYAN)
    cprint("  ╔════════════════════════════════════════════════╗", Colors.CYAN, bold=True)
    cprint("  ║          Nexa Code v2.0.0                     ║", Colors.CYAN, bold=True)
    cprint("  ║   The First Harness Native AI Coding Agent    ║", Colors.CYAN, bold=True)
    cprint("  ╚════════════════════════════════════════════════╝", Colors.CYAN, bold=True)
    cprint("", Colors.CYAN)
    cprint("  Harness Dimensions: E(autoloop) T(@tool) C(context) S(snapshot) L(hooks) V(verify)", Colors.DIM)
    cprint("", Colors.CYAN)
    cprint("  Type your request, or use /help for commands.", Colors.GREEN)
    cprint("  Use Ctrl+C to interrupt, /exit to quit.", Colors.GREEN)
    cprint("", Colors.CYAN)


# ═══════════════════════════════════════════════════════════════════════
#  Tool Implementations (T-dimension)
# ═══════════════════════════════════════════════════════════════════════

class NexaCodeTools:
    """Built-in tools for Nexa Code CLI — file ops, search, shell exec."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = Path(working_dir).resolve()

    def read_file(self, path: str) -> str:
        """Read a file and return its contents."""
        target = self._resolve_path(path)
        if not target.exists():
            return f"Error: File '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a file."
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            # Show line numbers for code files
            numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines[:200]))
            if len(lines) > 200:
                numbered += f"\n... ({len(lines) - 200} more lines)"
            return f"File: {path} ({len(lines)} lines)\n{numbered}"
        except Exception as e:
            return f"Error reading '{path}': {e}"

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        target = self._resolve_path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            lines = content.splitlines()
            return f"✅ Written {len(lines)} lines to {path}"
        except Exception as e:
            return f"Error writing '{path}': {e}"

    def search_files(self, pattern: str, directory: str = ".") -> str:
        """Search for a pattern in files using grep."""
        target_dir = self._resolve_path(directory)
        if not target_dir.exists():
            return f"Error: Directory '{directory}' does not exist."
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "--include=*.rs", "--include=*.nx",
                 "--include=*.md", "--include=*.toml", "--include=*.json", pattern],
                cwd=str(target_dir), capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0 and not result.stdout:
                return f"No matches found for '{pattern}' in {directory}"
            lines = result.stdout.splitlines()[:30]
            output = "\n".join(lines)
            if len(result.stdout.splitlines()) > 30:
                output += f"\n... ({len(result.stdout.splitlines()) - 30} more matches)"
            return output
        except subprocess.TimeoutExpired:
            return f"Search timed out for '{pattern}'"
        except Exception as e:
            return f"Error searching: {e}"

    def list_directory(self, path: str = ".") -> str:
        """List files in a directory."""
        target = self._resolve_path(path)
        if not target.exists():
            return f"Error: Directory '{path}' does not exist."
        try:
            entries = sorted(target.iterdir())
            output = []
            for entry in entries:
                if entry.is_dir():
                    output.append(f"  📁 {entry.name}/")
                else:
                    size = entry.stat().st_size
                    output.append(f"  📄 {entry.name} ({size} bytes)")
            return f"Directory: {path}\n" + "\n".join(output[:50])
        except Exception as e:
            return f"Error listing '{path}': {e}"

    def shell_exec(self, command: str) -> str:
        """Execute a shell command safely."""
        import shlex
        # Safety: block destructive commands
        dangerous = ["rm -rf", "drop database", "chmod 777", "dd", "mkfs", ":(){ :|:& };:"]
        for d in dangerous:
            if d in command.lower():
                return f"⛔ Blocked dangerous command: '{command}'"
        if any(ch in command for ch in "|&;<>$`\n"):
            return "⛔ Blocked command: shell metacharacters are not allowed"

        try:
            result = subprocess.run(
                shlex.split(command), shell=False, cwd=str(self.working_dir),
                capture_output=True, text=True, timeout=30
            )
            output = ""
            if result.stdout:
                output += result.stdout[:2000]
            if result.stderr:
                output += f"\nstderr:\n{result.stderr[:500]}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            return output if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Command timed out: '{command}'"
        except Exception as e:
            return f"Error executing: {e}"

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to working directory."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.working_dir / p


# ═══════════════════════════════════════════════════════════════════════
#  LLM Interface — OpenAI-compatible API
# ═══════════════════════════════════════════════════════════════════════

class NexaCodeLLM:
    """LLM interface for Nexa Code — uses OpenAI-compatible API."""

    def __init__(self, model: str = None):
        self.api_key, self.base_url = nexa_secrets.get_provider_config("default")
        if not self.api_key:
            self.api_key = nexa_secrets.get("API_KEY") or nexa_secrets.get("OPENAI_API_KEY")
        if not self.base_url:
            self.base_url = nexa_secrets.get("BASE_URL") or "https://api.openai.com/v1"
        self.model = model or nexa_secrets.get("MODEL_NAME") or "minimax-m2.5"
        # Handle model name dict
        if isinstance(self.model, dict):
            self.model = self.model.get("strong", "minimax-m2.5")

    def chat(self, messages: List[Dict], tools: List[Dict] = None, max_tokens: int = 4096) -> str:
        """Send a chat completion request."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = client.chat.completions.create(**kwargs)

            choice = response.choices[0]

            # Handle tool calls
            if hasattr(choice, 'message') and choice.message.tool_calls:
                return self._handle_tool_calls(choice.message)

            return choice.message.content or "(empty response)"
        except Exception as e:
            return f"LLM Error: {e}"

    def _handle_tool_calls(self, message) -> str:
        """Process tool calls from LLM response."""
        results = []
        for tc in message.tool_calls:
            func_name = tc.function.name
            func_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            results.append(f"Tool call: {func_name}({json.dumps(func_args, indent=2)})")
        return "\n".join(results)


# ═══════════════════════════════════════════════════════════════════════
#  Nexa Code — Main Interactive Agent
# ═══════════════════════════════════════════════════════════════════════

class NexaCode:
    """
    Interactive AI Programming Assistant — the main agent loop.

    Implements full Harness H=(E,T,C,S,L,V):
      E: autoloop — ReAct cycle with max_steps and exit conditions
      T: @tool — file read/write/search/exec tools registered in ToolRegistry
      C: with_context — conversation history with importance-weighted paging
      S: snapshot/restore — state snapshots for error recovery
      L: lifecycle hooks — before_step/after_step + reflect injection
      V: verify — output quality verification
    """

    SYSTEM_PROMPT = """You are Nexa Code, an expert AI programming assistant built on the Nexa v2.0 Harness Runtime.

You help users write, debug, refactor, and understand code. You have access to these tools:

1. read_file(path) — Read a file and show its contents with line numbers
2. write_file(path, content) — Write content to a file (creates directories if needed)
3. search_files(pattern, directory) — Search for a text pattern in code files
4. list_directory(path) — List files and directories
5. shell_exec(command) — Execute a shell command (dangerous commands are blocked)

When asked to modify code:
  - First read the relevant files to understand the current state
  - Then propose changes with clear explanations
  - Then write the changes using write_file
  - Verify the result by reading the file again or running tests

When asked to debug:
  - Read the error message and relevant code
  - Search for related patterns
  - Identify the root cause
  - Propose and implement the fix

Always be concise, technical, and precise. Show code changes with context.
Format your responses with markdown when appropriate.
"""

    def __init__(self, model: str = None, working_dir: str = "."):
        self.llm = NexaCodeLLM(model=model)
        self.tools = NexaCodeTools(working_dir=working_dir)
        self.conversation: List[Dict] = []
        self.step_count = 0
        self.max_steps = 20
        self.working_dir = working_dir

        # ─── Harness Subsystems ───
        # E-dimension: ExecutionEngine via HarnessKernel
        self.kernel = get_kernel()

        # T-dimension: ToolRegistry
        self.tool_registry = get_tool_registry()
        self._register_tools()

        # C-dimension: ContextManager (requires kernel)
        self.context_mgr = ContextManager(kernel=self.kernel)

        # S-dimension: StateStore
        self.state_store = StateStore()

        # L-dimension: LifecycleHookManager
        self.hooks = LifecycleHookManager()
        self.hooks.register("before_step", self._before_step)
        self.hooks.register("after_step", self._after_step)

        # V-dimension: EvaluationInterface
        self.evaluator = EvaluationInterface()

        # Initialize conversation
        self.conversation.append({"role": "system", "content": self.SYSTEM_PROMPT})

    def _register_tools(self) -> None:
        """Register all tools in ToolRegistry (T-dimension)."""
        # ToolRegistry.register(name, fn, schema) requires a callable
        noop_fn = lambda **kwargs: None  # Placeholder — actual execution via _execute_tool
        schemas = [
            ToolSchema(name="read_file", description="Read a file and return its contents with line numbers",
                       parameters={"path": {"type": "string", "description": "File path to read"}}),
            ToolSchema(name="write_file", description="Write content to a file",
                       parameters={"path": {"type": "string", "description": "File path to write"},
                                   "content": {"type": "string", "description": "Content to write"}}),
            ToolSchema(name="search_files", description="Search for a pattern in code files",
                       parameters={"pattern": {"type": "string", "description": "Search pattern"},
                                   "directory": {"type": "string", "description": "Directory to search in", "default": "."}}),
            ToolSchema(name="list_directory", description="List files in a directory",
                       parameters={"path": {"type": "string", "description": "Directory path", "default": "."}}),
            ToolSchema(name="shell_exec", description="Execute a shell command safely",
                       parameters={"command": {"type": "string", "description": "Shell command to execute"}}),
        ]
        for schema in schemas:
            self.tool_registry.register(schema.name, noop_fn, schema)

    def _before_step(self, **kwargs) -> None:
        """L-dimension: before_step hook."""
        self.step_count += 1
        cprint(f"  ⚡ Step {self.step_count}", Colors.DIM)

    def _after_step(self, **kwargs) -> None:
        """L-dimension: after_step hook."""
        cprint(f"  ✅ Step {self.step_count} completed", Colors.DIM)

    def _execute_tool(self, tool_name: str, args: Dict) -> str:
        """Execute a tool call by name."""
        tool_map = {
            "read_file": lambda a: self.tools.read_file(a.get("path", "")),
            "write_file": lambda a: self.tools.write_file(a.get("path", ""), a.get("content", "")),
            "search_files": lambda a: self.tools.search_files(a.get("pattern", ""), a.get("directory", ".")),
            "list_directory": lambda a: self.tools.list_directory(a.get("path", ".")),
            "shell_exec": lambda a: self.tools.shell_exec(a.get("command", "")),
        }
        handler = tool_map.get(tool_name)
        if handler:
            return handler(args)
        return f"Unknown tool: {tool_name}"

    def _build_tool_schemas_for_api(self) -> List[Dict]:
        """Build OpenAI-compatible tool schemas for API calls."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file and return its contents with line numbers",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "File path"}},
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "content": {"type": "string", "description": "Content to write"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for a pattern in code files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Search pattern"},
                            "directory": {"type": "string", "description": "Directory", "default": "."}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files in a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "Directory path", "default": "."}},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "shell_exec",
                    "description": "Execute a shell command safely (dangerous commands blocked)",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string", "description": "Shell command"}},
                        "required": ["command"]
                    }
                }
            },
        ]

    def process_request(self, user_input: str) -> str:
        """
        Process a user request through the full Harness pipeline.

        E-dimension: autoloop with tool-use ReAct cycle
        C-dimension: context management (add to conversation)
        S-dimension: snapshot before execution
        L-dimension: hooks + reflect
        V-dimension: verify output quality
        """
        # ─── C-dimension: Add to context ───
        self.conversation.append({"role": "user", "content": user_input})
        self.context_mgr.add_message("user", user_input)

        # ─── S-dimension: Snapshot ───
        snap_id = self.state_store.snapshot({
            "conversation": self.conversation.copy(),
            "step_count": self.step_count,
        })

        # ─── L-dimension: before_step hook ───
        self.hooks.fire("before_step", step=self.step_count + 1)

        # ─── E-dimension: autoloop ReAct cycle ───
        max_tool_rounds = 5  # Max tool-use rounds per request
        final_response = ""

        for round_idx in range(max_tool_rounds):
            # Call LLM with tools
            tool_schemas = self._build_tool_schemas_for_api()
            response = self.llm.chat(self.conversation, tools=tool_schemas)

            # Check if LLM wants to call tools
            # Parse tool calls from response format: "Tool call: func_name({...})"
            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                # No tool calls — this is the final response
                final_response = response
                break

            # Execute tool calls and feed results back
            cprint(f"  🔧 Tool calls: {len(tool_calls)}", Colors.YELLOW)
            tool_results = []
            for func_name, func_args in tool_calls:
                cprint(f"  → {func_name}({json.dumps(func_args)[:80]})", Colors.BLUE)
                result = self._execute_tool(func_name, func_args)
                cprint(f"  ← {result[:100]}...", Colors.DIM)
                tool_results.append(f"Tool {func_name} result:\n{result}")

            # Add tool results to conversation
            self.conversation.append({"role": "assistant", "content": response})
            tool_summary = "\n\n".join(tool_results)
            self.conversation.append({"role": "user", "content": f"Tool results:\n{tool_summary}\n\nBased on these results, continue your task or provide your final answer."})

            # ─── L-dimension: reflect injection ───
            if round_idx >= 3:
                reflect_msg = "Reflect: Are you making progress? Consider if a simpler approach might work better."
                self.conversation.append({"role": "system", "content": reflect_msg})

        if not final_response:
            final_response = response

        # ─── C-dimension: Add response to context ───
        self.conversation.append({"role": "assistant", "content": final_response})
        self.context_mgr.add_message("assistant", final_response)

        # ─── L-dimension: after_step hook ───
        self.hooks.fire("after_step", step=self.step_count)

        # ─── V-dimension: verify ───
        # Simple verification: check response is non-empty and relevant
        if final_response and len(final_response) > 10:
            verify_result = self.evaluator.verify_satisfies(final_response, "string")
            cprint(f"  ✓ Verify: passed={verify_result.passed}", Colors.GREEN)
        else:
            verify_result = self.evaluator.verify_satisfies(final_response or "", "string")
            cprint(f"  ✗ Verify: passed={verify_result.passed}", Colors.RED)
            # ─── S-dimension: restore on verification failure ───
            self.state_store.restore(snap_id)

        return final_response

    def _parse_tool_calls(self, response: str) -> List[Tuple[str, Dict]]:
        """Parse tool calls from LLM response text.

        Handles format: "Tool call: func_name({json_args})"
        Also handles inline tool requests like "I'll use read_file to check..."
        """
        tool_calls = []

        # Format 1: Explicit "Tool call: func_name({...})"
        import re
        pattern = r'Tool call:\s+(\w+)\((\{[^}]*\})\)'
        matches = re.findall(pattern, response)
        for func_name, args_json in matches:
            try:
                args = json.loads(args_json)
                tool_calls.append((func_name, args))
            except json.JSONDecodeError:
                tool_calls.append((func_name, {"raw_args": args_json}))

        # Format 2: LLM says "Let me use X to..." — detect intent
        intent_patterns = [
            (r"I'll (?:read|check|look at|examine|view)\s+(\S+)", "read_file", lambda m: {"path": m.group(1).strip('"').strip("'").strip("`")}),
            (r"Let me (?:read|check|look at|examine|view)\s+(\S+)", "read_file", lambda m: {"path": m.group(1).strip('"').strip("'").strip("`")}),
            (r'I need to (?:search|find|grep)\s+for\s+"([^"]+)"', "search_files", lambda m: {"pattern": m.group(1)}),
            (r'Let me (?:search|find|grep)\s+for\s+"([^"]+)"', "search_files", lambda m: {"pattern": m.group(1)}),
            (r"I'll (?:run|execute)\s+`([^`]+)`", "shell_exec", lambda m: {"command": m.group(1)}),
            (r"Let me (?:run|execute)\s+`([^`]+)`", "shell_exec", lambda m: {"command": m.group(1)}),
        ]
        for pat, func_name, arg_builder in intent_patterns:
            match = re.search(pat, response)
            if match and not any(t[0] == func_name for t in tool_calls):
                tool_calls.append((func_name, arg_builder(match)))

        return tool_calls

    def handle_slash_command(self, cmd: str) -> Optional[str]:
        """Handle special /commands in the REPL."""
        parts = cmd.strip().split()
        command = parts[0].lower()

        if command == "/help":
            return (
                "\nNexa Code Commands:\n"
                "  /help        — Show this help\n"
                "  /exit        — Exit Nexa Code\n"
                "  /clear       — Clear conversation history\n"
                "  /model NAME  — Switch LLM model\n"
                "  /stats       — Show Harness statistics\n"
                "  /snap        — Take a state snapshot\n"
                "  /restore ID  — Restore a state snapshot\n"
                "  /tools       — List registered tools\n"
                "  /context     — Show context manager stats\n"
                "  /trace       — Show execution trace\n"
                "  /cd PATH     — Change working directory\n"
                "  /read PATH   — Read a file directly\n"
                "  /write PATH  — Write to file (enter content, end with /end)\n"
                "  /search PAT  — Search for pattern\n"
                "  /run CMD     — Run shell command\n"
            )
        elif command == "/exit":
            cprint("Goodbye! 👋", Colors.GREEN)
            sys.exit(0)
        elif command == "/clear":
            self.conversation = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            self.step_count = 0
            return "Conversation cleared."
        elif command == "/model":
            if len(parts) > 1:
                self.llm.model = parts[1]
                return f"Model switched to: {parts[1]}"
            return f"Current model: {self.llm.model}"
        elif command == "/stats":
            stats = self.kernel.stats()
            return json.dumps(stats, indent=2)
        elif command == "/snap":
            snap_id = self.state_store.snapshot({
                "conversation": self.conversation.copy(),
                "step_count": self.step_count,
            })
            return f"Snapshot saved: {snap_id}"
        elif command == "/restore":
            if len(parts) > 1:
                state = self.state_store.restore(parts[1])
                if state:
                    self.conversation = state.get("conversation", self.conversation)
                    self.step_count = state.get("step_count", self.step_count)
                    return f"Restored snapshot: {parts[1]}"
                return f"Snapshot not found: {parts[1]}"
            return "Usage: /restore SNAP_ID"
        elif command == "/tools":
            tools = self.tool_registry.list_tools()
            return "\n".join(f"  {t.name}: {t.description}" for t in tools)
        elif command == "/context":
            stats = self.context_mgr.get_stats()
            return json.dumps(stats, indent=2)
        elif command == "/trace":
            traces = self.kernel.get_trace()
            return json.dumps(traces, indent=2) if traces else "No traces recorded."
        elif command == "/cd":
            if len(parts) > 1:
                new_dir = parts[1]
                if os.path.isdir(new_dir):
                    self.tools.working_dir = Path(new_dir).resolve()
                    self.working_dir = new_dir
                    os.chdir(new_dir)
                    return f"Working directory: {new_dir}"
                return f"Directory not found: {new_dir}"
            return f"Current directory: {self.tools.working_dir}"
        elif command == "/read":
            if len(parts) > 1:
                return self.tools.read_file(parts[1])
            return "Usage: /read PATH"
        elif command == "/search":
            if len(parts) > 1:
                return self.tools.search_files(parts[1])
            return "Usage: /search PATTERN"
        elif command == "/run":
            if len(parts) > 1:
                cmd_str = " ".join(parts[1:])
                return self.tools.shell_exec(cmd_str)
            return "Usage: /run COMMAND"
        elif command == "/write":
            if len(parts) > 1:
                path = parts[1]
                cprint("Enter content (end with /end):", Colors.YELLOW)
                lines = []
                while True:
                    line = input()
                    if line.strip() == "/end":
                        break
                    lines.append(line)
                content = "\n".join(lines)
                return self.tools.write_file(path, content)
            return "Usage: /write PATH"
        else:
            return f"Unknown command: {command}. Type /help for available commands."

    def run_repl(self) -> None:
        """Run the interactive REPL loop."""
        print_banner()

        while True:
            try:
                # Read user input
                cprint(f"\nnexa-code ({self.tools.working_dir})>", Colors.GREEN, bold=True)
                user_input = input().strip()

                if not user_input:
                    continue

                # Handle slash commands
                if user_input.startswith("/"):
                    result = self.handle_slash_command(user_input)
                    if result:
                        cprint(result, Colors.CYAN)
                    continue

                # Process through Harness pipeline
                cprint("", Colors.RESET)
                response = self.process_request(user_input)

                # Display response
                cprint("\n" + response, Colors.WHITE)

            except KeyboardInterrupt:
                cprint("\n\nInterrupted. Press Ctrl+C again or /exit to quit.", Colors.YELLOW)
                try:
                    input()
                except KeyboardInterrupt:
                    cprint("Goodbye! 👋", Colors.GREEN)
                    sys.exit(0)
            except EOFError:
                cprint("Goodbye! 👋", Colors.GREEN)
                sys.exit(0)

    def run_one_shot(self, task: str) -> str:
        """Run a single task without interactive REPL."""
        cprint(f"Task: {task}", Colors.CYAN)
        response = self.process_request(task)
        cprint(response, Colors.WHITE)
        return response


# ═══════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nexa Code — AI Programming Assistant")
    parser.add_argument("task", nargs="?", help="One-shot task to execute")
    parser.add_argument("--model", help="Override LLM model")
    parser.add_argument("--dir", default=".", help="Working directory")
    parser.add_argument("--max-steps", type=int, default=20, help="Max autoloop steps")
    args = parser.parse_args()

    agent = NexaCode(model=args.model, working_dir=args.dir)
    agent.max_steps = args.max_steps

    if args.task:
        agent.run_one_shot(args.task)
    else:
        agent.run_repl()


if __name__ == "__main__":
    main()
