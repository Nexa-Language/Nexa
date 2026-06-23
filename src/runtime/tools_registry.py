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

import json
import hashlib
import time
import subprocess
from .stdlib import (
    execute_stdlib_tool,
    get_stdlib_tools,
    _dangerous_tool_error,
    _dangerous_tools_enabled,
    _is_path_allowed_for_write,
)
from .safe_eval import parse_safe_command

def calculate_hash(text: str) -> str:
    """Calculates the SHA256 string for any given input string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_current_time(timezone: str = "UTC") -> str:
    """Returns the current time given a timezone."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def std_shell_execute(command: str, timeout: int = 60) -> str:
    """执行系统命令"""
    try:
        if not _dangerous_tools_enabled():
            return _dangerous_tool_error("std_shell_execute")
        args = parse_safe_command(command)
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout or result.stderr
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: {str(e)}"

def std_fs_read_file(path: str, encoding: str = "utf-8") -> str:
    """读取文件"""
    try:
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        return f"Error: {str(e)}"

def std_fs_write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """写入文件"""
    try:
        if not _dangerous_tools_enabled():
            return _dangerous_tool_error("std_fs_write_file")
        if not _is_path_allowed_for_write(path):
            return "Error: path is outside NEXA_ALLOWED_WRITE_ROOTS"
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        return "Success"
    except Exception as e:
        return f"Error: {str(e)}"

def std_http_fetch(url: str, headers: dict = None, timeout: int = 30) -> str:
    """HTTP GET 请求"""
    try:
        import urllib.request
        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        return f"Error: {str(e)}"

def std_time_now(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间"""
    return time.strftime(format, time.localtime())

def std_ask_human(prompt: str, default: str = None) -> str:
    """请求用户输入"""
    try:
        if default:
            result = input(f"{prompt} [{default}]: ")
            return result if result else default
        return input(f"{prompt}: ")
    except EOFError:
        return default or ""


def web_search(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo HTML 端点进行免费网络搜索（无需 API key）。

    自动检测 HTTP_PROXY/HTTPS_PROXY 环境变量（如 WSL 的 127.0.0.1:7897）。
    返回 JSON 字符串，包含结果列表（title/snippet/url）。
    优先尝试 Instant Answer API，失败则解析 HTML 搜索结果页。
    """
    import json as _json
    import os
    import re
    import urllib.parse
    import urllib.request

    ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    results = []

    # 自动配置代理（WSL 环境通常用 127.0.0.1:7897）
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or \
                os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""
    if not proxy_url:
        # 尝试常见 WSL 代理端口
        import socket
        for port in ("7897", "7890", "1080"):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(("127.0.0.1", int(port)))
                s.close()
                proxy_url = f"http://127.0.0.1:{port}"
                break
            except Exception:
                continue
    if proxy_url:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()

    # 1) 先试 Instant Answer API（结构化，但覆盖率低）
    api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": ua})
        with opener.open(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        abstract = data.get("AbstractText", "") or data.get("Abstract", "")
        if abstract:
            results.append({
                "title": data.get("Heading", query),
                "snippet": abstract,
                "url": data.get("AbstractURL", ""),
                "source": "DuckDuckGo Instant Answer",
            })
        for topic in (data.get("RelatedTopics") or [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic["Text"][:80],
                    "snippet": topic["Text"],
                    "url": topic.get("FirstURL", ""),
                    "source": "DuckDuckGo Related",
                })
                if len(results) >= max_results:
                    break
    except Exception:
        pass  # fall through to HTML scraping

    # 2) Fallback: HTML 搜索结果页解析
    if len(results) < max_results:
        html_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        try:
            req = urllib.request.Request(html_url, headers={"User-Agent": ua})
            with opener.open(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)</a>', html)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            urls = re.findall(r'class="result__url"[^>]*href="([^"]+)"', html)
            for i in range(min(len(titles), max_results - len(results))):
                snippet = re.sub(r'<[^>]+>', '', snippets[i]) if i < len(snippets) else ""
                results.append({
                    "title": titles[i].strip(),
                    "snippet": snippet.strip()[:300],
                    "url": urls[i] if i < len(urls) else "",
                    "source": "DuckDuckGo HTML",
                })
        except Exception as e:
            if not results:
                return _json.dumps({
                    "error": f"DuckDuckGo request failed: {e}",
                    "query": query,
                    "hint": "Set HTTPS_PROXY=http://127.0.0.1:7897 if behind a proxy",
                }, ensure_ascii=False)

    if not results:
        results.append({
            "title": query,
            "snippet": f"No results found for '{query}'.",
            "source": "DuckDuckGo",
        })

    return _json.dumps({"query": query, "results": results[:max_results]}, ensure_ascii=False)


# Tool dispatcher mapped by function name
LOCAL_TOOLS = {
    "calculate_hash": calculate_hash,
    "get_current_time": get_current_time,
    "std_shell_execute": std_shell_execute,
    "std_fs_read_file": std_fs_read_file,
    "std_fs_write_file": std_fs_write_file,
    "std_http_fetch": std_http_fetch,
    "web_search": web_search,
    "std_time_now": std_time_now,
    "std_ask_human": std_ask_human
}

def execute_tool(name: str, args_json: str) -> str:
    """Execute a tool by name. In NEXA_QUIET mode, shows a spinner instead
    of verbose execution logs. Details are hidden but results still returned."""
    import os as _os

    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError:
        args = {}

    quiet = _os.environ.get("NEXA_QUIET")

    if quiet:
        # v2.3.1: Show compact tool execution status (spinner)
        try:
            from .ui import print_tool_call, print_tool_result
            print_tool_call(name, args_json[:80] if args_json else "")
        except Exception:
            pass
    else:
        print(f"    [ToolRegistry] Executing {name} with args {args_json} ...")

    # First try LOCAL_TOOLS
    if name in LOCAL_TOOLS:
        try:
            result = LOCAL_TOOLS[name](**args)
            if quiet:
                try:
                    from .ui import print_tool_result
                    print_tool_result(str(result))
                except Exception:
                    pass
            else:
                print(f"    [ToolRegistry] Execution result: {result}")
            return str(result)
        except Exception as e:
            err = f"Error executing tool {name}: {str(e)}"
            if not quiet:
                print(f"    [ToolRegistry] {err}")
            return err

    # Then try stdlib tools
    try:
        result = execute_stdlib_tool(name, **args)
        if quiet:
            try:
                from .ui import print_tool_result
                print_tool_result(str(result))
            except Exception:
                pass
        else:
            print(f"    [ToolRegistry] Execution result: {result}")
        return str(result)
    except Exception as e:
        err = f"Error: Tool '{name}' not found locally or in stdlib. {str(e)}"
        if not quiet:
            print(f"    [ToolRegistry] {err}")
        return err
