"""
Nexa Terminal UI Library — rich-based rendering for beautiful agent output.

Provides markdown rendering, syntax-highlighted code blocks, spinner
animations, styled panels, and status messages. Used by the std.ui
standard library DSL so users can call ui.markdown(), ui.code(), etc.
directly from .nx files.

Usage from generated Python:
    from src.runtime.ui import (
        print_markdown, print_code, print_panel,
        thinking_spinner, print_agent_reply, print_user_input,
        print_success, print_error, print_warning, print_banner,
        print_tool_call, print_tool_result,
    )
"""

from __future__ import annotations

import sys
import time
from typing import Optional

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.spinner import Spinner
    from rich.live import Live
    from rich.text import Text
    from rich.theme import Theme
    from rich.padding import Padding
    from rich.align import Align
    from rich import box
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


# ─── Theme ───
NEXA_THEME = Theme({
    "nexa.agent": "bold cyan",
    "nexa.user": "green",
    "nexa.tool": "yellow",
    "nexa.error": "bold red",
    "nexa.success": "bold green",
    "nexa.warn": "bold yellow",
    "nexa.info": "blue",
    "nexa.thinking": "dim italic",
    "nexa.banner": "bold magenta",
})

if _RICH_AVAILABLE:
    _console = Console(theme=NEXA_THEME, force_terminal=sys.stdout.isatty())
else:
    _console = None


def _fallback_print(text: str) -> None:
    """Fallback when rich is not installed."""
    print(text)


def _render(text: str, renderable=None) -> None:
    """Render via rich console, or fallback to plain print."""
    if _console and _RICH_AVAILABLE:
        if renderable is not None:
            _console.print(renderable)
        else:
            _console.print(text)
    else:
        _fallback_print(text)


# ─── Public API ───

def print_banner(title: str, subtitle: str = "") -> None:
    """Print a Claude Code-style startup banner."""
    if _RICH_AVAILABLE and _console:
        content = f"[nexa.banner]{title}[/nexa.banner]"
        if subtitle:
            content += f"\n[dim]{subtitle}[/dim]"
        _console.print(Panel(
            Align.center(Text.from_markup(content)),
            border_style="cyan",
            box=box.DOUBLE,
            padding=(1, 2),
        ))
    else:
        print(f"\n{'='*50}")
        print(f"  {title}")
        if subtitle:
            print(f"  {subtitle}")
        print(f"{'='*50}\n")


def print_markdown(text: str) -> None:
    """Render text as markdown (headings, lists, code blocks, bold/italic)."""
    if _RICH_AVAILABLE and _console:
        _console.print(Markdown(text), style="default")
    else:
        _fallback_print(text)


def print_code(code: str, language: str = "python") -> None:
    """Render code with syntax highlighting."""
    if _RICH_AVAILABLE and _console:
        syntax = Syntax(code, language, theme="monokai", line_numbers=False, word_wrap=True)
        _console.print(Panel(syntax, border_style="blue", box=box.ROUNDED, padding=(0, 1)))
    else:
        print(f"```{language}\n{code}\n```")


def print_panel(text: str, title: str = "", style: str = "cyan") -> None:
    """Render text inside a styled panel."""
    if _RICH_AVAILABLE and _console:
        _console.print(Panel(text, title=title, border_style=style, box=box.ROUNDED, padding=(0, 1)))
    else:
        print(f"[{title}] {text}" if title else text)


def thinking_spinner(message: str = "Thinking", duration: float = 1.0) -> None:
    """Show a spinner animation for a short duration."""
    if _RICH_AVAILABLE and _console:
        spinner = Spinner("dots", text=f"[nexa.thinking]{message}...[/nexa.thinking]")
        with _console.status(f"[nexa.thinking]{message}...[/nexa.thinking]", spinner="dots"):
            time.sleep(duration)
    else:
        print(f"{message}...")
        time.sleep(duration)


def print_agent_reply(agent_name: str, reply: str) -> None:
    """Render an agent's reply with agent label and markdown."""
    if _RICH_AVAILABLE and _console:
        _console.print(f"\n[nexa.agent]🤖 {agent_name}[/nexa.agent]")
        # Try markdown rendering; fallback to plain if it fails
        try:
            _console.print(Panel(Markdown(reply), border_style="cyan", box=box.ROUNDED, padding=(0, 1)))
        except Exception:
            _console.print(Panel(reply, border_style="cyan", box=box.ROUNDED, padding=(0, 1)))
    else:
        print(f"\n🤖 {agent_name}")
        print(reply)


def print_user_input(text: str) -> None:
    """Render user input in green."""
    if _RICH_AVAILABLE and _console:
        _console.print(f"[nexa.user]❯ {text}[/nexa.user]")
    else:
        print(f"❯ {text}")


def print_success(msg: str) -> None:
    """Render a success message."""
    _render(f"✅ {msg}", Text(f"✅ {msg}", style="nexa.success") if _RICH_AVAILABLE else None)


def print_error(msg: str) -> None:
    """Render an error message."""
    _render(f"❌ {msg}", Text(f"❌ {msg}", style="nexa.error") if _RICH_AVAILABLE else None)


def print_warning(msg: str) -> None:
    """Render a warning message."""
    _render(f"⚠️  {msg}", Text(f"⚠️  {msg}", style="nexa.warn") if _RICH_AVAILABLE else None)


def print_info(msg: str) -> None:
    """Render an info message."""
    _render(f"ℹ️  {msg}", Text(f"ℹ️  {msg}", style="nexa.info") if _RICH_AVAILABLE else None)


def print_tool_call(tool_name: str, args: str = "") -> None:
    """Render a tool call notification."""
    if _RICH_AVAILABLE and _console:
        _console.print(f"[nexa.tool]🔧 {tool_name}[/nexa.tool]" + (f" [dim]{args}[/dim]" if args else ""))
    else:
        print(f"🔧 {tool_name} {args}")


def print_tool_result(result: str) -> None:
    """Render a tool execution result."""
    if _RICH_AVAILABLE and _console:
        _console.print(f"[dim]  └─ {result[:200]}{'...' if len(result) > 200 else ''}[/dim]")
    else:
        print(f"  └─ {result[:200]}")


def input_prompt(prompt: str = "nexa> ") -> str:
    """Styled input prompt with CJK wide-character support.

    Uses prompt_toolkit when available (correct backspace handling for
    multi-byte CJK characters). Falls back to rich Prompt, then to
    built-in input().
    """
    # Try prompt_toolkit first — it handles CJK width correctly
    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.formatted_text import HTML
        return pt_prompt(HTML(f'<style fg="ansigreen">{prompt}</style>'))
    except ImportError:
        pass
    except (EOFError, KeyboardInterrupt):
        return ""

    # Fallback: rich Prompt
    try:
        if _RICH_AVAILABLE and _console:
            from rich.prompt import Prompt
            return Prompt.ask(prompt, console=_console, show_default=False)
    except Exception:
        pass

    # Last resort: built-in input (may have CJK backspace issues)
    try:
        return input(prompt)
    except EOFError:
        return ""


def is_available() -> bool:
    """Check if rich is available."""
    return _RICH_AVAILABLE
