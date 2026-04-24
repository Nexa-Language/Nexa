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
Nexa 标准库 - 内置工具集

提供常用工具的即开即用实现:
- HTTP 请求
- 文件操作
- 数据处理
- 文本处理
- 时间日期

使用示例:
    from src.runtime.stdlib import get_stdlib_tools
    
    tools = get_stdlib_tools()
    # tools 包含所有标准库工具定义
"""

import os
import json
import re
import time
import datetime
import hashlib
import base64
import urllib.parse
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
# P2-4: Template System imports
from .template import (
    NexaTemplateRenderer, FILTER_REGISTRY, render_string, template, compile_template, render,
    agent_template_prompt, agent_template_slot_fill, agent_template_register, agent_template_list,
)


# ==================== 工具定义 ====================

@dataclass
class StdTool:
    """标准工具定义"""
    name: str
    description: str
    parameters: Dict
    handler: Callable
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    def execute(self, **kwargs) -> str:
        """执行工具"""
        try:
            return self.handler(**kwargs)
        except Exception as e:
            return f"Error: {str(e)}"


# ==================== HTTP 工具 ====================

def _http_get(url: str, headers: Dict = None, timeout: int = 30) -> str:
    """HTTP GET 请求"""
    try:
        import urllib.request
        import urllib.error
        
        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        return f"HTTP GET Error: {str(e)}"


def _http_post(url: str, data: str, headers: Dict = None,
               content_type: str = "application/json", timeout: int = 30) -> str:
    """HTTP POST 请求"""
    try:
        import requests
        req_headers = headers or {}
        if content_type:
            req_headers["Content-Type"] = content_type
        resp = requests.post(url, data=data, headers=req_headers, timeout=timeout)
        return json.dumps({"status": resp.status_code, "body": resp.text[:2000]})
    except Exception as e:
        return f"Error: {str(e)}"


def _http_put(url: str, data: str, headers: Dict = None,
              content_type: str = "application/json", timeout: int = 30) -> str:
    """HTTP PUT 请求"""
    try:
        import requests
        req_headers = headers or {}
        if content_type:
            req_headers["Content-Type"] = content_type
        resp = requests.put(url, data=data, headers=req_headers, timeout=timeout)
        return json.dumps({"status": resp.status_code, "body": resp.text[:2000]})
    except Exception as e:
        return f"Error: {str(e)}"


def _http_delete(url: str, headers: Dict = None, timeout: int = 30) -> str:
    """HTTP DELETE 请求"""
    try:
        import requests
        req_headers = headers or {}
        resp = requests.delete(url, headers=req_headers, timeout=timeout)
        return json.dumps({"status": resp.status_code, "body": resp.text[:2000]})
    except Exception as e:
        return f"Error: {str(e)}"
    """HTTP POST 请求"""
    try:
        import urllib.request
        import urllib.error
        
        req = urllib.request.Request(
            url,
            data=data.encode('utf-8'),
            method='POST'
        )
        req.add_header('Content-Type', content_type)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        return f"HTTP POST Error: {str(e)}"


def _url_encode(text: str) -> str:
    """URL 编码"""
    return urllib.parse.quote(text)


def _url_decode(text: str) -> str:
    """URL 解码"""
    return urllib.parse.unquote(text)


# ==================== 文件工具 ====================

def _file_read(path: str, encoding: str = "utf-8") -> str:
    """读取文件"""
    try:
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        return f"File Read Error: {str(e)}"


def _file_write(path: str, content: str, encoding: str = "utf-8") -> str:
    """写入文件"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"File Write Error: {str(e)}"


def _file_append(path: str, content: str, encoding: str = "utf-8") -> str:
    """追加文件"""
    try:
        with open(path, 'a', encoding=encoding) as f:
            f.write(content)
        return f"Successfully appended {len(content)} characters to {path}"
    except Exception as e:
        return f"File Append Error: {str(e)}"


def _file_exists(path: str) -> str:
    """检查文件是否存在"""
    return json.dumps({"exists": os.path.exists(path), "path": path})


def _file_list(directory: str, pattern: str = "*") -> str:
    """列出目录文件"""
    try:
        import glob
        files = glob.glob(os.path.join(directory, pattern))
        return json.dumps({"files": files, "count": len(files)})
    except Exception as e:
        return f"File List Error: {str(e)}"


def _file_delete(path: str) -> str:
    """删除文件"""
    try:
        os.remove(path)
        return f"Successfully deleted {path}"
    except Exception as e:
        return f"File Delete Error: {str(e)}"


# ==================== 数据处理工具 ====================

def _json_parse(text: str) -> str:
    """解析 JSON"""
    try:
        data = json.loads(text)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"JSON Parse Error: {str(e)}"


def _json_stringify(data: str, indent: int = 2) -> str:
    """序列化为 JSON"""
    try:
        parsed = json.loads(data)
        return json.dumps(parsed, indent=indent, ensure_ascii=False)
    except Exception as e:
        return f"JSON Stringify Error: {str(e)}"


def _json_get(text: str, path: str) -> str:
    """获取 JSON 路径值"""
    try:
        data = json.loads(text)
        keys = path.split('.')
        for key in keys:
            if key.isdigit():
                data = data[int(key)]
            else:
                data = data[key]
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return f"JSON Get Error: {str(e)}"


def _regex_match(pattern: str, text: str, flags: str = "") -> str:
    """正则匹配"""
    try:
        re_flags = 0
        if 'i' in flags:
            re_flags |= re.IGNORECASE
        if 'm' in flags:
            re_flags |= re.MULTILINE
        if 's' in flags:
            re_flags |= re.DOTALL
        
        matches = re.findall(pattern, text, re_flags)
        return json.dumps({"matches": matches, "count": len(matches)})
    except Exception as e:
        return f"Regex Match Error: {str(e)}"


def _regex_replace(pattern: str, replacement: str, text: str, flags: str = "") -> str:
    """正则替换"""
    try:
        re_flags = 0
        if 'i' in flags:
            re_flags |= re.IGNORECASE
        
        result = re.sub(pattern, replacement, text, flags=re_flags)
        return result
    except Exception as e:
        return f"Regex Replace Error: {str(e)}"


# ==================== 文本处理工具 ====================

def _text_split(text: str, delimiter: str = "\n", max_splits: int = -1) -> str:
    """分割文本"""
    parts = text.split(delimiter, max_splits if max_splits > 0 else -1)
    return json.dumps({"parts": parts, "count": len(parts)})


def _text_join(parts: str, delimiter: str = "\n") -> str:
    """连接文本"""
    try:
        parts_list = json.loads(parts)
        return delimiter.join(str(p) for p in parts_list)
    except:
        return delimiter.join(parts.split(','))


def _text_upper(text: str) -> str:
    """转大写"""
    return text.upper()


def _text_lower(text: str) -> str:
    """转小写"""
    return text.lower()


def _text_trim(text: str) -> str:
    """去除空白"""
    return text.strip()


def _text_substring(text: str, start: int, length: int = -1) -> str:
    """截取子串"""
    if length < 0:
        return text[start:]
    return text[start:start + length]


def _text_count(text: str, substring: str) -> str:
    """统计子串出现次数"""
    count = text.count(substring)
    return json.dumps({"count": count, "substring": substring})


def _text_replace(text: str, old: str, new: str, count: int = -1) -> str:
    """替换文本"""
    return text.replace(old, new, count if count > 0 else -1)


# ==================== 加密工具 ====================

def _hash_md5(text: str) -> str:
    """MD5 哈希"""
    return hashlib.md5(text.encode()).hexdigest()


def _hash_sha256(text: str) -> str:
    """SHA256 哈希"""
    return hashlib.sha256(text.encode()).hexdigest()


def _base64_encode(text: str) -> str:
    """Base64 编码"""
    return base64.b64encode(text.encode()).decode()


def _base64_decode(text: str) -> str:
    """Base64 解码"""
    return base64.b64decode(text.encode()).decode()


# ==================== 时间工具 ====================

def _time_now(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间"""
    return datetime.datetime.now().strftime(format)


def _time_parse(text: str, format: str = "%Y-%m-%d") -> str:
    """解析时间"""
    try:
        dt = datetime.datetime.strptime(text, format)
        return json.dumps({
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "minute": dt.minute,
            "second": dt.second,
            "weekday": dt.weekday(),
            "iso": dt.isoformat()
        })
    except Exception as e:
        return f"Time Parse Error: {str(e)}"


def _time_sleep(seconds: int) -> str:
    """休眠指定秒数"""
    import time
    time.sleep(seconds)
    return json.dumps({"sleep": seconds})


    

def _time_timestamp() -> str:
    """获取当前时间戳"""
    import time
    return json.dumps({"timestamp": int(time.time())})


def _time_format(iso_string: str, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化时间"""
    try:
        dt = datetime.datetime.fromisoformat(iso_string)
        return dt.strftime(format)
    except Exception as e:
        return f"Time Format Error: {str(e)}"


def _time_diff(start: str, end: str, unit: str = "seconds") -> str:
    """时间差计算"""
    try:
        start_dt = datetime.datetime.fromisoformat(start)
        end_dt = datetime.datetime.fromisoformat(end)
        diff = end_dt - start_dt
        
        if unit == "seconds":
            value = diff.total_seconds()
        elif unit == "minutes":
            value = diff.total_seconds() / 60
        elif unit == "hours":
            value = diff.total_seconds() / 3600
        elif unit == "days":
            value = diff.days
        else:
            value = diff.total_seconds()
        
        return json.dumps({
            "value": value,
            "unit": unit,
            "days": diff.days,
            "seconds": diff.total_seconds()
        })
    except Exception as e:
        return f"Time Diff Error: {str(e)}"


# ==================== 数学工具 ====================

def _math_calc(expression: str) -> str:
    """安全数学计算"""
    try:
        # 只允许安全的数学运算
        allowed = set('0123456789+-*/.() ')
        if not all(c in allowed for c in expression):
            return "Error: Invalid characters in expression"
        
        result = eval(expression)
        return json.dumps({"result": result, "expression": expression})
    except Exception as e:
        return f"Math Calc Error: {str(e)}"


def _math_round(number: float, decimals: int = 0) -> str:
    """四舍五入"""
    return str(round(number, decimals))


def _math_random(min_val: int, max_val: int) -> str:
    """随机数"""
    import random
    return str(random.randint(min_val, max_val))


# ==================== Shell 工具 ====================

def _shell_exec(command: str, timeout: int = 30) -> str:
    """执行 shell 命令"""
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        })
    except subprocess.TimeoutExpired:
        return json.dumps({
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "returncode": -1,
            "success": False
        })
    except Exception as e:
        return json.dumps({
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "success": False
        })


def _shell_which(command: str) -> str:
    """查找命令路径"""
    import shutil
    path = shutil.which(command)
    return json.dumps({
        "command": command,
        "path": path,
        "found": path is not None
    })


# ==================== 交互工具 ====================

def _ask_human(prompt: str, default: str = "") -> str:
    """请求用户输入"""
    try:
        if default:
            result = input(f"{prompt} [{default}]: ")
            return result if result else default
        return input(f"{prompt}: ")
    except EOFError:
        return default or ""


# ==================== P1-5: Database Integration (内置数据库集成) ====================

from .database import (
    NexaDatabase, NexaSQLite, NexaPostgres, DatabaseError,
    query as db_query, query_one as db_query_one, execute as db_execute,
    close as db_close, begin as db_begin, commit as db_commit, rollback as db_rollback,
    python_to_sql, sql_to_python, adapt_sql_params,
    agent_memory_query, agent_memory_store, agent_memory_delete, agent_memory_list,
    contract_violation_to_http_status,
)


def _std_db_sqlite_connect(path: str = ":memory:") -> str:
    """SQLite 连接 — std.db.sqlite.connect"""
    try:
        handle = NexaSQLite.connect(path)
        return json.dumps(handle)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_sqlite_query(handle_json: str, sql: str, params_json: str = "[]") -> str:
    """SQLite 查询所有行 — std.db.sqlite.query"""
    try:
        handle = json.loads(handle_json)
        params = json.loads(params_json) if params_json else []
        results = NexaSQLite.query(handle, sql, params)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_sqlite_query_one(handle_json: str, sql: str, params_json: str = "[]") -> str:
    """SQLite 查询单行 — std.db.sqlite.query_one"""
    try:
        handle = json.loads(handle_json)
        params = json.loads(params_json) if params_json else []
        result = NexaSQLite.query_one(handle, sql, params)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_sqlite_execute(handle_json: str, sql: str, params_json: str = "[]") -> str:
    """SQLite 执行写操作 — std.db.sqlite.execute"""
    try:
        handle = json.loads(handle_json)
        params = json.loads(params_json) if params_json else []
        count = NexaSQLite.execute(handle, sql, params)
        return json.dumps({"affected_rows": count})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_sqlite_close(handle_json: str) -> str:
    """SQLite 关闭连接 — std.db.sqlite.close"""
    try:
        handle = json.loads(handle_json)
        NexaSQLite.close(handle)
        return json.dumps({"closed": True})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_sqlite_begin(handle_json: str) -> str:
    """SQLite 开始事务 — std.db.sqlite.begin"""
    try:
        handle = json.loads(handle_json)
        NexaSQLite.begin(handle)
        return json.dumps({"transaction": "started"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_sqlite_commit(handle_json: str) -> str:
    """SQLite 提交事务 — std.db.sqlite.commit"""
    try:
        handle = json.loads(handle_json)
        NexaSQLite.commit(handle)
        return json.dumps({"transaction": "committed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_sqlite_rollback(handle_json: str) -> str:
    """SQLite 回滚事务 — std.db.sqlite.rollback"""
    try:
        handle = json.loads(handle_json)
        NexaSQLite.rollback(handle)
        return json.dumps({"transaction": "rolled_back"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_connect(url: str) -> str:
    """PostgreSQL 连接 — std.db.postgres.connect"""
    try:
        handle = NexaPostgres.connect(url)
        return json.dumps(handle)
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_query(handle_json: str, sql: str, params_json: str = "[]") -> str:
    """PostgreSQL 查询所有行 — std.db.postgres.query"""
    try:
        handle = json.loads(handle_json)
        params = json.loads(params_json) if params_json else []
        results = NexaPostgres.query(handle, sql, params)
        return json.dumps(results, ensure_ascii=False)
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_query_one(handle_json: str, sql: str, params_json: str = "[]") -> str:
    """PostgreSQL 查询单行 — std.db.postgres.query_one"""
    try:
        handle = json.loads(handle_json)
        params = json.loads(params_json) if params_json else []
        result = NexaPostgres.query_one(handle, sql, params)
        return json.dumps(result, ensure_ascii=False)
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_execute(handle_json: str, sql: str, params_json: str = "[]") -> str:
    """PostgreSQL 执行写操作 — std.db.postgres.execute"""
    try:
        handle = json.loads(handle_json)
        params = json.loads(params_json) if params_json else []
        count = NexaPostgres.execute(handle, sql, params)
        return json.dumps({"affected_rows": count})
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_close(handle_json: str) -> str:
    """PostgreSQL 关闭连接 — std.db.postgres.close"""
    try:
        handle = json.loads(handle_json)
        NexaPostgres.close(handle)
        return json.dumps({"closed": True})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_begin(handle_json: str) -> str:
    """PostgreSQL 开始事务 — std.db.postgres.begin"""
    try:
        handle = json.loads(handle_json)
        NexaPostgres.begin(handle)
        return json.dumps({"transaction": "started"})
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_commit(handle_json: str) -> str:
    """PostgreSQL 提交事务 — std.db.postgres.commit"""
    try:
        handle = json.loads(handle_json)
        NexaPostgres.commit(handle)
        return json.dumps({"transaction": "committed"})
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_postgres_rollback(handle_json: str) -> str:
    """PostgreSQL 回滚事务 — std.db.postgres.rollback"""
    try:
        handle = json.loads(handle_json)
        NexaPostgres.rollback(handle)
        return json.dumps({"transaction": "rolled_back"})
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_memory_query(handle_json: str, agent_name: str, key: str) -> str:
    """Agent 记忆查询 — std.db.memory.query"""
    try:
        handle = json.loads(handle_json)
        result = agent_memory_query(handle, agent_name, key)
        return json.dumps({"value": result})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_memory_store(handle_json: str, agent_name: str, key: str, value: str) -> str:
    """Agent 记忆存储 — std.db.memory.store"""
    try:
        handle = json.loads(handle_json)
        success = agent_memory_store(handle, agent_name, key, value)
        return json.dumps({"stored": success})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_memory_delete(handle_json: str, agent_name: str, key: str) -> str:
    """Agent 记忆删除 — std.db.memory.delete"""
    try:
        handle = json.loads(handle_json)
        success = agent_memory_delete(handle, agent_name, key)
        return json.dumps({"deleted": success})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _std_db_memory_list(handle_json: str, agent_name: str) -> str:
    """Agent 记忆列表 — std.db.memory.list"""
    try:
        handle = json.loads(handle_json)
        result = agent_memory_list(handle, agent_name)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ==================== 标准库注册 ====================

def get_stdlib_tools() -> Dict[str, StdTool]:
    """获取所有标准库工具"""
    _all_tools = {
        # HTTP
        "http_get": StdTool(
            name="http_get",
            description="发送 HTTP GET 请求",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL"},
                    "headers": {"type": "object", "description": "请求头"},
                    "timeout": {"type": "integer", "description": "超时秒数"}
                },
                "required": ["url"]
            },
            handler=_http_get
        ),
        "http_post": StdTool(
            name="http_post",
            description="发送 HTTP POST 请求",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL"},
                    "data": {"type": "string", "description": "请求体"},
                    "headers": {"type": "object", "description": "请求头"},
                    "content_type": {"type": "string", "description": "内容类型"}
                },
                "required": ["url", "data"]
            },
            handler=_http_post
        ),
        "http_put": StdTool(
            name="http_put",
            description="发送 HTTP PUT 请求",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL"},
                    "data": {"type": "string", "description": "请求体"},
                    "headers": {"type": "object", "description": "请求头"}
                },
                "required": ["url", "data"]
            },
            handler=_http_put
        ),
        "http_delete": StdTool(
            name="http_delete",
            description="发送 HTTP DELETE 请求",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL"},
                    "headers": {"type": "object", "description": "请求头"}
                },
                "required": ["url"]
            },
            handler=_http_delete
        ),
        
        # 文件
        "file_read": StdTool(
            name="file_read",
            description="读取文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "encoding": {"type": "string", "description": "编码格式"}
                },
                "required": ["path"]
            },
            handler=_file_read
        ),
        "file_write": StdTool(
            name="file_write",
            description="写入文件",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"}
                },
                "required": ["path", "content"]
            },
            handler=_file_write
        ),
        "file_exists": StdTool(
            name="file_exists",
            description="检查文件是否存在",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"]
            },
            handler=_file_exists
        ),
        "file_append": StdTool(
            name="file_append",
            description="追加文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "追加内容"}
                },
                "required": ["path", "content"]
            },
            handler=_file_append
        ),
        "file_delete": StdTool(
            name="file_delete",
            description="删除文件",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"]
            },
            handler=_file_delete
        ),
        "file_list": StdTool(
            name="file_list",
            description="列出目录文件",
            parameters={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "目录路径"},
                    "pattern": {"type": "string", "description": "文件匹配模式"}
                },
                "required": ["directory"]
            },
            handler=_file_list
        ),
        
        # JSON
        "json_parse": StdTool(
            name="json_parse",
            description="解析 JSON 字符串",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "JSON 字符串"}
                },
                "required": ["text"]
            },
            handler=_json_parse
        ),
        "json_get": StdTool(
            name="json_get",
            description="获取 JSON 路径值",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "JSON 字符串"},
                    "path": {"type": "string", "description": "路径 (如 data.items.0)"}
                },
                "required": ["text", "path"]
            },
            handler=_json_get
        ),
        "json_stringify": StdTool(
            name="json_stringify",
            description="序列化为 JSON",
            parameters={
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "数据对象"},
                    "indent": {"type": "integer", "description": "缩进空格数"}
                },
                "required": ["data"]
            },
            handler=_json_stringify
        ),
        
        # 正则
        "regex_match": StdTool(
            name="regex_match",
            description="正则表达式匹配",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "正则模式"},
                    "text": {"type": "string", "description": "待匹配文本"},
                    "flags": {"type": "string", "description": "标志 (i=忽略大小写, m=多行)"}
                },
                "required": ["pattern", "text"]
            },
            handler=_regex_match
        ),
        "regex_replace": StdTool(
            name="regex_replace",
            description="正则表达式替换",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "正则模式"},
                    "replacement": {"type": "string", "description": "替换内容"},
                    "text": {"type": "string", "description": "待处理文本"}
                },
                "required": ["pattern", "replacement", "text"]
            },
            handler=_regex_replace
        ),
        
        # 文本
        "text_split": StdTool(
            name="text_split",
            description="分割文本",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "待分割文本"},
                    "delimiter": {"type": "string", "description": "分隔符"}
                },
                "required": ["text"]
            },
            handler=_text_split
        ),
        "text_replace": StdTool(
            name="text_replace",
            description="替换文本",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "原文本"},
                    "old": {"type": "string", "description": "被替换内容"},
                    "new": {"type": "string", "description": "替换内容"}
                },
                "required": ["text", "old", "new"]
            },
            handler=_text_replace
        ),
        
        # 加密
        "hash_md5": StdTool(
            name="hash_md5",
            description="计算 MD5 哈希",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "输入文本"}
                },
                "required": ["text"]
            },
            handler=_hash_md5
        ),
        "hash_sha256": StdTool(
            name="hash_sha256",
            description="计算 SHA256 哈希",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "输入文本"}
                },
                "required": ["text"]
            },
            handler=_hash_sha256
        ),
        "base64_encode": StdTool(
            name="base64_encode",
            description="Base64 编码",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "输入文本"}
                },
                "required": ["text"]
            },
            handler=_base64_encode
        ),
        "base64_decode": StdTool(
            name="base64_decode",
            description="Base64 解码",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Base64 文本"}
                },
                "required": ["text"]
            },
            handler=_base64_decode
        ),
        
        # 时间
        "time_now": StdTool(
            name="time_now",
            description="获取当前时间",
            parameters={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "description": "时间格式"}
                },
                "required": []
            },
            handler=_time_now
        ),
        "time_diff": StdTool(
            name="time_diff",
            description="计算时间差",
            parameters={
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "开始时间 (ISO格式)"},
                    "end": {"type": "string", "description": "结束时间 (ISO格式)"},
                    "unit": {"type": "string", "description": "单位 (seconds/minutes/hours/days)"}
                },
                "required": ["start", "end"]
            },
            handler=_time_diff
        ),
        "time_format": StdTool(
            name="time_format",
            description="格式化时间",
            parameters={
                "type": "object",
                "properties": {
                    "iso_string": {"type": "string", "description": "ISO 时间字符串"},
                    "format": {"type": "string", "description": "输出格式"}
                },
                "required": ["iso_string"]
            },
            handler=_time_format
        ),
        "time_sleep": StdTool(
            name="time_sleep",
            description="休眠指定秒数",
            parameters={
                "type": "object",
                "properties": {
                    "seconds": {"type": "integer", "description": "休眠秒数"}
                },
                "required": ["seconds"]
            },
            handler=_time_sleep
        ),
        "time_timestamp": StdTool(
            name="time_timestamp",
            description="获取当前时间戳",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=_time_timestamp
        ),
        
        # 数学
        "math_calc": StdTool(
            name="math_calc",
            description="计算数学表达式",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"]
            },
            handler=_math_calc
        ),
        "math_random": StdTool(
            name="math_random",
            description="生成随机数",
            parameters={
                "type": "object",
                "properties": {
                    "min_val": {"type": "integer", "description": "最小值"},
                    "max_val": {"type": "integer", "description": "最大值"}
                },
                "required": ["min_val", "max_val"]
            },
            handler=_math_random
        ),
        
        # Shell
        "shell_exec": StdTool(
            name="shell_exec",
            description="执行 shell 命令",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时秒数"}
                },
                "required": ["command"]
            },
            handler=_shell_exec
        ),
        "shell_which": StdTool(
            name="shell_which",
            description="查找命令路径",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "命令名称"}
                },
                "required": ["command"]
            },
            handler=_shell_which
        ),
        
        # 交互
        "ask_human": StdTool(
            name="ask_human",
            description="请求用户输入",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "提示信息"},
                    "default": {"type": "string", "description": "默认值"}
                },
                "required": ["prompt"]
            },
            handler=_ask_human
        ),
        
        # P1-5: Database Integration (内置数据库集成)
        "std_db_sqlite_connect": StdTool(
            name="std_db_sqlite_connect",
            description="连接 SQLite 数据库",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "数据库路径 (:memory: 或文件路径)"}
                },
                "required": ["path"]
            },
            handler=_std_db_sqlite_connect
        ),
        "std_db_sqlite_query": StdTool(
            name="std_db_sqlite_query",
            description="SQLite 查询所有行",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"},
                    "sql": {"type": "string", "description": "SQL 查询语句"},
                    "params_json": {"type": "string", "description": "参数 JSON 数组"}
                },
                "required": ["handle_json", "sql"]
            },
            handler=_std_db_sqlite_query
        ),
        "std_db_sqlite_query_one": StdTool(
            name="std_db_sqlite_query_one",
            description="SQLite 查询单行",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"},
                    "sql": {"type": "string", "description": "SQL 查询语句"},
                    "params_json": {"type": "string", "description": "参数 JSON 数组"}
                },
                "required": ["handle_json", "sql"]
            },
            handler=_std_db_sqlite_query_one
        ),
        "std_db_sqlite_execute": StdTool(
            name="std_db_sqlite_execute",
            description="SQLite 执行写操作",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"},
                    "sql": {"type": "string", "description": "SQL 语句"},
                    "params_json": {"type": "string", "description": "参数 JSON 数组"}
                },
                "required": ["handle_json", "sql"]
            },
            handler=_std_db_sqlite_execute
        ),
        "std_db_sqlite_close": StdTool(
            name="std_db_sqlite_close",
            description="SQLite 关闭连接",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_sqlite_close
        ),
        "std_db_sqlite_begin": StdTool(
            name="std_db_sqlite_begin",
            description="SQLite 开始事务",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_sqlite_begin
        ),
        "std_db_sqlite_commit": StdTool(
            name="std_db_sqlite_commit",
            description="SQLite 提交事务",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_sqlite_commit
        ),
        "std_db_sqlite_rollback": StdTool(
            name="std_db_sqlite_rollback",
            description="SQLite 回滚事务",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_sqlite_rollback
        ),
        "std_db_postgres_connect": StdTool(
            name="std_db_postgres_connect",
            description="连接 PostgreSQL 数据库",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "PostgreSQL 连接串"}
                },
                "required": ["url"]
            },
            handler=_std_db_postgres_connect
        ),
        "std_db_postgres_query": StdTool(
            name="std_db_postgres_query",
            description="PostgreSQL 查询所有行",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"},
                    "sql": {"type": "string", "description": "SQL 查询语句"},
                    "params_json": {"type": "string", "description": "参数 JSON 数组"}
                },
                "required": ["handle_json", "sql"]
            },
            handler=_std_db_postgres_query
        ),
        "std_db_postgres_query_one": StdTool(
            name="std_db_postgres_query_one",
            description="PostgreSQL 查询单行",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"},
                    "sql": {"type": "string", "description": "SQL 查询语句"},
                    "params_json": {"type": "string", "description": "参数 JSON 数组"}
                },
                "required": ["handle_json", "sql"]
            },
            handler=_std_db_postgres_query_one
        ),
        "std_db_postgres_execute": StdTool(
            name="std_db_postgres_execute",
            description="PostgreSQL 执行写操作",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"},
                    "sql": {"type": "string", "description": "SQL 语句"},
                    "params_json": {"type": "string", "description": "参数 JSON 数组"}
                },
                "required": ["handle_json", "sql"]
            },
            handler=_std_db_postgres_execute
        ),
        "std_db_postgres_close": StdTool(
            name="std_db_postgres_close",
            description="PostgreSQL 关闭连接",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_postgres_close
        ),
        "std_db_postgres_begin": StdTool(
            name="std_db_postgres_begin",
            description="PostgreSQL 开始事务",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_postgres_begin
        ),
        "std_db_postgres_commit": StdTool(
            name="std_db_postgres_commit",
            description="PostgreSQL 提交事务",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_postgres_commit
        ),
        "std_db_postgres_rollback": StdTool(
            name="std_db_postgres_rollback",
            description="PostgreSQL 回滚事务",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "连接句柄 JSON"}
                },
                "required": ["handle_json"]
            },
            handler=_std_db_postgres_rollback
        ),
        "std_db_memory_query": StdTool(
            name="std_db_memory_query",
            description="Agent 记忆查询",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "数据库连接句柄 JSON"},
                    "agent_name": {"type": "string", "description": "Agent 名称"},
                    "key": {"type": "string", "description": "记忆键名"}
                },
                "required": ["handle_json", "agent_name", "key"]
            },
            handler=_std_db_memory_query
        ),
        "std_db_memory_store": StdTool(
            name="std_db_memory_store",
            description="Agent 记忆存储",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "数据库连接句柄 JSON"},
                    "agent_name": {"type": "string", "description": "Agent 名称"},
                    "key": {"type": "string", "description": "记忆键名"},
                    "value": {"type": "string", "description": "记忆值"}
                },
                "required": ["handle_json", "agent_name", "key", "value"]
            },
            handler=_std_db_memory_store
        ),
        "std_db_memory_delete": StdTool(
            name="std_db_memory_delete",
            description="Agent 记忆删除",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "数据库连接句柄 JSON"},
                    "agent_name": {"type": "string", "description": "Agent 名称"},
                    "key": {"type": "string", "description": "记忆键名"}
                },
                "required": ["handle_json", "agent_name", "key"]
            },
            handler=_std_db_memory_delete
        ),
        "std_db_memory_list": StdTool(
            name="std_db_memory_list",
            description="Agent 记忆列表",
            parameters={
                "type": "object",
                "properties": {
                    "handle_json": {"type": "string", "description": "数据库连接句柄 JSON"},
                    "agent_name": {"type": "string", "description": "Agent 名称"}
                },
                "required": ["handle_json", "agent_name"]
            },
            handler=_std_db_memory_list
        ),
    }


    # ==================== P2-1: Auth & OAuth (std.auth namespace) ====================

    from .auth import (
        oauth as _auth_oauth_fn,
        enable_auth as _auth_enable_auth_fn,
        get_user as _auth_get_user_fn,
        get_session as _auth_get_session_fn,
        session_data as _auth_session_data_fn,
        set_session as _auth_set_session_fn,
        logout_user as _auth_logout_user_fn,
        require_auth as _auth_require_auth_fn,
        jwt_sign as _auth_jwt_sign_fn,
        jwt_verify as _auth_jwt_verify_fn,
        jwt_decode as _auth_jwt_decode_fn,
        csrf_token as _auth_csrf_token_fn,
        csrf_field as _auth_csrf_field_fn,
        verify_csrf as _auth_verify_csrf_fn,
        agent_api_key_generate as _auth_api_key_generate_fn,
        agent_api_key_verify as _auth_api_key_verify_fn,
        agent_auth_context as _auth_auth_context_fn,
    )

    def _std_auth_oauth(**kwargs):
        name = kwargs.get('name', 'google')
        client_id = kwargs.get('client_id', '')
        client_secret = kwargs.get('client_secret', '')
        opts = kwargs.get('opts', None)
        try:
            result = _auth_oauth_fn(name, client_id, client_secret, opts)
            return json.dumps(result.to_dict(), ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_enable_auth(**kwargs):
        providers_json = kwargs.get('providers', '[]')
        options = kwargs.get('options', None)
        try:
            if isinstance(providers_json, str):
                providers_list = json.loads(providers_json)
            else:
                providers_list = providers_json
            provider_configs = []
            for p in providers_list:
                provider_configs.append(_auth_oauth_fn(
                    p.get('name', ''),
                    p.get('client_id', ''),
                    p.get('client_secret', ''),
                    p.get('opts', None)
                ))
            result = _auth_enable_auth_fn(provider_configs, options)
            return json.dumps(result.to_dict(), ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_get_user(**kwargs):
        request_json = kwargs.get('request', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_get_user_fn(req)
            return json.dumps(result, ensure_ascii=False) if result else 'null'
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_get_session(**kwargs):
        request_json = kwargs.get('request', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_get_session_fn(req)
            return json.dumps(result.to_dict(), ensure_ascii=False) if result else 'null'
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_session_data(**kwargs):
        request_json = kwargs.get('request', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_session_data_fn(req)
            return json.dumps(result, ensure_ascii=False) if result else 'null'
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_set_session(**kwargs):
        request_json = kwargs.get('request', '{}')
        data = kwargs.get('data', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            if isinstance(data, str):
                data = json.loads(data)
            result = _auth_set_session_fn(req, data)
            return json.dumps({'success': result})
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_logout_user(**kwargs):
        request_json = kwargs.get('request', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_logout_user_fn(req)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_require_auth(**kwargs):
        request_json = kwargs.get('request', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_require_auth_fn(req)
            if result is None:
                return json.dumps({'authenticated': True})
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_jwt_sign(**kwargs):
        claims_json = kwargs.get('claims', '{}')
        secret = kwargs.get('secret', '')
        options = kwargs.get('options', None)
        try:
            if isinstance(claims_json, str):
                claims = json.loads(claims_json)
            else:
                claims = claims_json
            if isinstance(options, str):
                options = json.loads(options)
            result = _auth_jwt_sign_fn(claims, secret, options)
            return result
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_jwt_verify(**kwargs):
        token = kwargs.get('token', '')
        secret = kwargs.get('secret', '')
        try:
            result = _auth_jwt_verify_fn(token, secret)
            return json.dumps(result, ensure_ascii=False) if result else 'null'
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_jwt_decode(**kwargs):
        token = kwargs.get('token', '')
        try:
            result = _auth_jwt_decode_fn(token)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_csrf_token(**kwargs):
        request_json = kwargs.get('request', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_csrf_token_fn(req)
            return result
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_csrf_field(**kwargs):
        request_json = kwargs.get('request', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_csrf_field_fn(req)
            return result
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_verify_csrf(**kwargs):
        request_json = kwargs.get('request', '{}')
        token = kwargs.get('token', '')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            result = _auth_verify_csrf_fn(req, token)
            return json.dumps({'valid': result})
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_api_key_generate(**kwargs):
        agent_name = kwargs.get('agent_name', '')
        ttl = kwargs.get('ttl', None)
        try:
            if isinstance(ttl, str):
                ttl = int(ttl) if ttl else None
            result = _auth_api_key_generate_fn(agent_name, ttl)
            return result
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_api_key_verify(**kwargs):
        api_key = kwargs.get('api_key', '')
        try:
            result = _auth_api_key_verify_fn(api_key)
            return json.dumps(result, ensure_ascii=False) if result else 'null'
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_auth_auth_context(**kwargs):
        request_json = kwargs.get('request', '{}')
        agent_json = kwargs.get('agent', '{}')
        try:
            from .http_server import NexaRequest
            if isinstance(request_json, str):
                req = NexaRequest.from_raw(method='GET', path='/', headers=json.loads(request_json), body='')
            else:
                req = request_json
            agent = agent_json  # Pass as-is (could be dict or None)
            result = _auth_auth_context_fn(req, agent)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    # P2-1: std.auth namespace — 17 StdTool registrations
    auth_tools = {
        "std_auth_oauth": StdTool(
            name="std_auth_oauth",
            description="创建 OAuth Provider 配置",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Provider 名称 (google/github/custom)"},
                    "client_id": {"type": "string", "description": "OAuth Client ID"},
                    "client_secret": {"type": "string", "description": "OAuth Client Secret"},
                    "opts": {"type": "string", "description": "可选配置 JSON"}
                },
                "required": ["name", "client_id", "client_secret"]
            },
            handler=_std_auth_oauth
        ),
        "std_auth_enable_auth": StdTool(
            name="std_auth_enable_auth",
            description="初始化 Auth 系统",
            parameters={
                "type": "object",
                "properties": {
                    "providers": {"type": "string", "description": "Provider 列表 JSON"},
                    "options": {"type": "string", "description": "可选配置 JSON"}
                },
                "required": ["providers"]
            },
            handler=_std_auth_enable_auth
        ),
        "std_auth_get_user": StdTool(
            name="std_auth_get_user",
            description="获取当前用户信息",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_get_user
        ),
        "std_auth_get_session": StdTool(
            name="std_auth_get_session",
            description="获取用户会话",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_get_session
        ),
        "std_auth_session_data": StdTool(
            name="std_auth_session_data",
            description="获取自定义会话数据",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_session_data
        ),
        "std_auth_set_session": StdTool(
            name="std_auth_set_session",
            description="设置自定义会话数据",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"},
                    "data": {"type": "string", "description": "数据 JSON"}
                },
                "required": ["request", "data"]
            },
            handler=_std_auth_set_session
        ),
        "std_auth_logout_user": StdTool(
            name="std_auth_logout_user",
            description="注销用户",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_logout_user
        ),
        "std_auth_require_auth": StdTool(
            name="std_auth_require_auth",
            description="Auth 中间件路径保护",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_require_auth
        ),
        "std_auth_jwt_sign": StdTool(
            name="std_auth_jwt_sign",
            description="JWT 签名 (HS256)",
            parameters={
                "type": "object",
                "properties": {
                    "claims": {"type": "string", "description": "JWT claims JSON"},
                    "secret": {"type": "string", "description": "签名密钥"},
                    "options": {"type": "string", "description": "可选参数 JSON"}
                },
                "required": ["claims", "secret"]
            },
            handler=_std_auth_jwt_sign
        ),
        "std_auth_jwt_verify": StdTool(
            name="std_auth_jwt_verify",
            description="JWT 验证 (HS256)",
            parameters={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "JWT token"},
                    "secret": {"type": "string", "description": "签名密钥"}
                },
                "required": ["token", "secret"]
            },
            handler=_std_auth_jwt_verify
        ),
        "std_auth_jwt_decode": StdTool(
            name="std_auth_jwt_decode",
            description="JWT 解码 (不验签)",
            parameters={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "JWT token"}
                },
                "required": ["token"]
            },
            handler=_std_auth_jwt_decode
        ),
        "std_auth_csrf_token": StdTool(
            name="std_auth_csrf_token",
            description="生成 CSRF token",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_csrf_token
        ),
        "std_auth_csrf_field": StdTool(
            name="std_auth_csrf_field",
            description="生成 CSRF HTML hidden input",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_csrf_field
        ),
        "std_auth_verify_csrf": StdTool(
            name="std_auth_verify_csrf",
            description="验证 CSRF token",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"},
                    "token": {"type": "string", "description": "待验证 token"}
                },
                "required": ["request", "token"]
            },
            handler=_std_auth_verify_csrf
        ),
        "std_auth_api_key_generate": StdTool(
            name="std_auth_api_key_generate",
            description="生成 Agent API Key",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Agent 名称"},
                    "ttl": {"type": "string", "description": "过期时间(秒), 空为永不过期"}
                },
                "required": ["agent_name"]
            },
            handler=_std_auth_api_key_generate
        ),
        "std_auth_api_key_verify": StdTool(
            name="std_auth_api_key_verify",
            description="验证 Agent API Key",
            parameters={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string", "description": "API Key 字符串"}
                },
                "required": ["api_key"]
            },
            handler=_std_auth_api_key_verify
        ),
        "std_auth_auth_context": StdTool(
            name="std_auth_auth_context",
            description="Agent 认证上下文注入",
            parameters={
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "请求对象 JSON"},
                    "agent": {"type": "string", "description": "Agent 对象 JSON"}
                },
                "required": ["request"]
            },
            handler=_std_auth_auth_context
        ),
    }

    # Merge auth tools into main tools dict
    _all_tools.update(auth_tools)

    # ==================== P2-3: std.kv namespace ====================

    from .kv_store import (
        kv_open, kv_get, kv_get_int, kv_get_str, kv_get_json,
        kv_set, kv_set_nx, kv_del, kv_has, kv_list,
        kv_expire, kv_ttl, kv_flush, kv_incr,
        agent_kv_query, agent_kv_store, agent_kv_context,
    )

    # ==================== P2-2: std.concurrent namespace ====================

    from .concurrent import (
        channel, send, recv, recv_timeout, try_recv, close,
        select, spawn, await_task, try_await, cancel_task,
        parallel, race, after, schedule, cancel_schedule,
        sleep_ms, thread_count, parse_interval,
    )

    def _std_concurrent_channel(**kwargs):
        try:
            handles = channel()
            return json.dumps(handles, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_send(**kwargs):
        tx_json = kwargs.get('tx', '{}')
        value = kwargs.get('value', '')
        try:
            tx = json.loads(tx_json) if isinstance(tx_json, str) else tx_json
            result = send(tx, value)
            return json.dumps({'success': result}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_recv(**kwargs):
        rx_json = kwargs.get('rx', '{}')
        try:
            rx = json.loads(rx_json) if isinstance(rx_json, str) else rx_json
            result = recv(rx)
            return json.dumps({'value': result}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_recv_timeout(**kwargs):
        rx_json = kwargs.get('rx', '{}')
        ms = int(kwargs.get('ms', '1000'))
        try:
            rx = json.loads(rx_json) if isinstance(rx_json, str) else rx_json
            result = recv_timeout(rx, ms)
            return json.dumps({'value': result}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_try_recv(**kwargs):
        rx_json = kwargs.get('rx', '{}')
        try:
            rx = json.loads(rx_json) if isinstance(rx_json, str) else rx_json
            result = try_recv(rx)
            return json.dumps({'value': result}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_close(**kwargs):
        rx_json = kwargs.get('rx', '{}')
        try:
            rx = json.loads(rx_json) if isinstance(rx_json, str) else rx_json
            result = close(rx)
            return json.dumps({'success': result}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_select(**kwargs):
        channels_json = kwargs.get('channels', '[]')
        timeout_ms = kwargs.get('timeout_ms', None)
        try:
            channels_list = json.loads(channels_json) if isinstance(channels_json, str) else channels_json
            tm = int(timeout_ms) if timeout_ms is not None else None
            result = select(channels_list, tm)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_spawn(**kwargs):
        handler_json = kwargs.get('handler', '')
        try:
            # For stdlib tool calls, handler is serialized as string
            # In actual runtime, spawn receives callable or NexaAgent
            handler = json.loads(handler_json) if isinstance(handler_json, str) and handler_json.startswith('{') else handler_json
            task = spawn(handler)
            return json.dumps(task, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_await_task(**kwargs):
        task_json = kwargs.get('task', '{}')
        try:
            task = json.loads(task_json) if isinstance(task_json, str) else task_json
            result = await_task(task)
            return json.dumps({'result': str(result)}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_try_await(**kwargs):
        task_json = kwargs.get('task', '{}')
        try:
            task = json.loads(task_json) if isinstance(task_json, str) else task_json
            result = try_await(task)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_cancel_task(**kwargs):
        task_json = kwargs.get('task', '{}')
        try:
            task = json.loads(task_json) if isinstance(task_json, str) else task_json
            result = cancel_task(task)
            return json.dumps({'success': result}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_parallel(**kwargs):
        handlers_json = kwargs.get('handlers', '[]')
        try:
            handlers_list = json.loads(handlers_json) if isinstance(handlers_json, str) else handlers_json
            results = parallel(handlers_list)
            return json.dumps({'results': [str(r) for r in results]}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_race(**kwargs):
        handlers_json = kwargs.get('handlers', '[]')
        try:
            handlers_list = json.loads(handlers_json) if isinstance(handlers_json, str) else handlers_json
            result = race(handlers_list)
            return json.dumps({'result': str(result)}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_after(**kwargs):
        delay = kwargs.get('delay', '0')
        handler_json = kwargs.get('handler', '')
        try:
            ms = parse_interval(delay) if isinstance(delay, str) else int(delay)
            handler = json.loads(handler_json) if isinstance(handler_json, str) and handler_json.startswith('{') else handler_json
            task = after(ms, handler)
            return json.dumps(task, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_schedule(**kwargs):
        interval = kwargs.get('interval', '1000')
        handler_json = kwargs.get('handler', '')
        try:
            ms = parse_interval(interval) if isinstance(interval, str) else int(interval)
            handler = json.loads(handler_json) if isinstance(handler_json, str) and handler_json.startswith('{') else handler_json
            sched = schedule(ms, handler)
            return json.dumps(sched, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_cancel_schedule(**kwargs):
        schedule_json = kwargs.get('schedule', '{}')
        try:
            sched = json.loads(schedule_json) if isinstance(schedule_json, str) else schedule_json
            result = cancel_schedule(sched)
            return json.dumps({'success': result}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_sleep_ms(**kwargs):
        ms = int(kwargs.get('ms', '100'))
        try:
            sleep_ms(ms)
            return json.dumps({'ok': True}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_concurrent_thread_count(**kwargs):
        try:
            count = thread_count()
            return json.dumps({'count': count}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_open(**kwargs):
        path = kwargs.get('path', ':memory:')
        try:
            handle = kv_open(path)
            return json.dumps(handle.to_dict(), ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_get(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        default = kwargs.get('default', None)
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_get(kv, key, default)
            if result is None:
                return 'null'
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_get_int(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        default = kwargs.get('default', 0)
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_get_int(kv, key, default)
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_get_str(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        default = kwargs.get('default', '')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_get_str(kv, key, default)
            return result
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_get_json(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_get_json(kv, key)
            if result is None:
                return 'null'
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_set(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        value = kwargs.get('value', '')
        opts_json = kwargs.get('opts', None)
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            opts = json.loads(opts_json) if isinstance(opts_json, str) else opts_json
            result = kv_set(kv, key, value, opts)
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_set_nx(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        value = kwargs.get('value', '')
        opts_json = kwargs.get('opts', None)
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            opts = json.loads(opts_json) if isinstance(opts_json, str) else opts_json
            result = kv_set_nx(kv, key, value, opts)
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_del(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_del(kv, key)
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_has(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_has(kv, key)
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_list(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        prefix = kwargs.get('prefix', None)
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_list(kv, prefix)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_expire(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        ttl_seconds = kwargs.get('ttl_seconds', '0')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_expire(kv, key, int(ttl_seconds))
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_ttl(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_ttl(kv, key)
            return str(result) if result is not None else 'null'
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_flush(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_flush(kv)
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_incr(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        amount = kwargs.get('amount', '1')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = kv_incr(kv, key, int(amount))
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_agent_kv_query(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        semantic_query = kwargs.get('semantic_query', '')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            result = agent_kv_query(kv, semantic_query)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_agent_kv_store(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        key = kwargs.get('key', '')
        value = kwargs.get('value', '')
        context_json = kwargs.get('context', None)
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            context = json.loads(context_json) if isinstance(context_json, str) else context_json
            result = agent_kv_store(kv, key, value, context)
            return str(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_kv_agent_kv_context(**kwargs):
        kv_json = kwargs.get('kv', '{}')
        agent_json = kwargs.get('agent', '{}')
        try:
            kv = json.loads(kv_json) if isinstance(kv_json, str) else kv_json
            agent = json.loads(agent_json) if isinstance(agent_json, str) else agent_json
            result = agent_kv_context(kv, agent)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    kv_tools = {
        "std_kv_open": StdTool(
            name="std_kv_open",
            description="打开/创建 KV 存储",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "数据库路径, ':memory:' 创建内存存储"}
                },
                "required": ["path"]
            },
            handler=_std_kv_open
        ),
        "std_kv_get": StdTool(
            name="std_kv_get",
            description="获取 KV 值",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "default": {"type": "string", "description": "默认值"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_get
        ),
        "std_kv_get_int": StdTool(
            name="std_kv_get_int",
            description="类型化获取整数",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "default": {"type": "string", "description": "默认值(0)"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_get_int
        ),
        "std_kv_get_str": StdTool(
            name="std_kv_get_str",
            description="类型化获取字符串",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "default": {"type": "string", "description": "默认值('')"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_get_str
        ),
        "std_kv_get_json": StdTool(
            name="std_kv_get_json",
            description="JSON 解析获取",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_get_json
        ),
        "std_kv_set": StdTool(
            name="std_kv_set",
            description="设置 KV 值",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "value": {"type": "string", "description": "值"},
                    "opts": {"type": "string", "description": "可选参数 JSON (含 ttl)"}
                },
                "required": ["kv", "key", "value"]
            },
            handler=_std_kv_set
        ),
        "std_kv_set_nx": StdTool(
            name="std_kv_set_nx",
            description="仅当不存在时设置 (原子 NX)",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "value": {"type": "string", "description": "值"},
                    "opts": {"type": "string", "description": "可选参数 JSON (含 ttl)"}
                },
                "required": ["kv", "key", "value"]
            },
            handler=_std_kv_set_nx
        ),
        "std_kv_del": StdTool(
            name="std_kv_del",
            description="删除 KV 键",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_del
        ),
        "std_kv_has": StdTool(
            name="std_kv_has",
            description="检查 KV 键是否存在",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_has
        ),
        "std_kv_list": StdTool(
            name="std_kv_list",
            description="列出 KV 键 (前缀过滤)",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "prefix": {"type": "string", "description": "前缀过滤器"}
                },
                "required": ["kv"]
            },
            handler=_std_kv_list
        ),
        "std_kv_expire": StdTool(
            name="std_kv_expire",
            description="设置 KV 键过期时间",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "ttl_seconds": {"type": "string", "description": "TTL 秒数"}
                },
                "required": ["kv", "key", "ttl_seconds"]
            },
            handler=_std_kv_expire
        ),
        "std_kv_ttl": StdTool(
            name="std_kv_ttl",
            description="查看 KV 键剩余 TTL",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_ttl
        ),
        "std_kv_flush": StdTool(
            name="std_kv_flush",
            description="清空所有 KV 键",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"}
                },
                "required": ["kv"]
            },
            handler=_std_kv_flush
        ),
        "std_kv_incr": StdTool(
            name="std_kv_incr",
            description="原子递增 KV 键",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "amount": {"type": "string", "description": "递增量(默认1)"}
                },
                "required": ["kv", "key"]
            },
            handler=_std_kv_incr
        ),
        "std_kv_agent_kv_query": StdTool(
            name="std_kv_agent_kv_query",
            description="语义搜索 KV 数据",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "semantic_query": {"type": "string", "description": "语义查询字符串"}
                },
                "required": ["kv", "semantic_query"]
            },
            handler=_std_kv_agent_kv_query
        ),
        "std_kv_agent_kv_store": StdTool(
            name="std_kv_agent_kv_store",
            description="带上下文存储 KV 值",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "key": {"type": "string", "description": "键名"},
                    "value": {"type": "string", "description": "值"},
                    "context": {"type": "string", "description": "上下文信息 JSON"}
                },
                "required": ["kv", "key", "value"]
            },
            handler=_std_kv_agent_kv_store
        ),
        "std_kv_agent_kv_context": StdTool(
            name="std_kv_agent_kv_context",
            description="KV 数据注入 Agent 上下文",
            parameters={
                "type": "object",
                "properties": {
                    "kv": {"type": "string", "description": "KV Handle JSON"},
                    "agent": {"type": "string", "description": "Agent 对象 JSON"}
                },
                "required": ["kv", "agent"]
            },
            handler=_std_kv_agent_kv_context
        ),
    }

    # Merge KV tools into main tools dict
    _all_tools.update(kv_tools)

    # ==================== P2-2: Concurrent tools dict ====================

    concurrent_tools = {
        "std_concurrent_channel": StdTool(
            name="std_concurrent_channel",
            description='创建通道对 [tx, rx]',
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=_std_concurrent_channel
        ),
        "std_concurrent_send": StdTool(
            name="std_concurrent_send",
            description='通过通道发送值',
            parameters={
                "type": "object",
                "properties": {
                    "tx": {"type": "string", "description": "TX Handle JSON"},
                    "value": {"type": "string", "description": "发送值"}
                },
                "required": ["tx", "value"]
            },
            handler=_std_concurrent_send
        ),
        "std_concurrent_recv": StdTool(
            name="std_concurrent_recv",
            description='阻塞接收通道消息',
            parameters={
                "type": "object",
                "properties": {
                    "rx": {"type": "string", "description": "RX Handle JSON"}
                },
                "required": ["rx"]
            },
            handler=_std_concurrent_recv
        ),
        "std_concurrent_recv_timeout": StdTool(
            name="std_concurrent_recv_timeout",
            description='带超时接收通道消息',
            parameters={
                "type": "object",
                "properties": {
                    "rx": {"type": "string", "description": "RX Handle JSON"},
                    "ms": {"type": "string", "description": "超时毫秒数"}
                },
                "required": ["rx", "ms"]
            },
            handler=_std_concurrent_recv_timeout
        ),
        "std_concurrent_try_recv": StdTool(
            name="std_concurrent_try_recv",
            description='非阻塞 peek 接收',
            parameters={
                "type": "object",
                "properties": {
                    "rx": {"type": "string", "description": "RX Handle JSON"}
                },
                "required": ["rx"]
            },
            handler=_std_concurrent_try_recv
        ),
        "std_concurrent_close": StdTool(
            name="std_concurrent_close",
            description='关闭通道',
            parameters={
                "type": "object",
                "properties": {
                    "rx": {"type": "string", "description": "RX Handle JSON"}
                },
                "required": ["rx"]
            },
            handler=_std_concurrent_close
        ),
        "std_concurrent_select": StdTool(
            name="std_concurrent_select",
            description='多路复用多个通道',
            parameters={
                "type": "object",
                "properties": {
                    "channels": {"type": "string", "description": "RX Handle 列表 JSON"},
                    "timeout_ms": {"type": "string", "description": "超时毫秒数(可选)"}
                },
                "required": ["channels"]
            },
            handler=_std_concurrent_select
        ),
        "std_concurrent_spawn": StdTool(
            name="std_concurrent_spawn",
            description='派生后台任务',
            parameters={
                "type": "object",
                "properties": {
                    "handler": {"type": "string", "description": "Handler JSON"}
                },
                "required": ["handler"]
            },
            handler=_std_concurrent_spawn
        ),
        "std_concurrent_await_task": StdTool(
            name="std_concurrent_await_task",
            description='等待任务完成',
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task Handle JSON"}
                },
                "required": ["task"]
            },
            handler=_std_concurrent_await_task
        ),
        "std_concurrent_try_await": StdTool(
            name="std_concurrent_try_await",
            description='非阻塞 peek 任务状态',
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task Handle JSON"}
                },
                "required": ["task"]
            },
            handler=_std_concurrent_try_await
        ),
        "std_concurrent_cancel_task": StdTool(
            name="std_concurrent_cancel_task",
            description='取消后台任务',
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task Handle JSON"}
                },
                "required": ["task"]
            },
            handler=_std_concurrent_cancel_task
        ),
        "std_concurrent_parallel": StdTool(
            name="std_concurrent_parallel",
            description='并行执行所有 handler',
            parameters={
                "type": "object",
                "properties": {
                    "handlers": {"type": "string", "description": "Handler 列表 JSON"}
                },
                "required": ["handlers"]
            },
            handler=_std_concurrent_parallel
        ),
        "std_concurrent_race": StdTool(
            name="std_concurrent_race",
            description='第一个成功结果, 取消其余',
            parameters={
                "type": "object",
                "properties": {
                    "handlers": {"type": "string", "description": "Handler 列表 JSON"}
                },
                "required": ["handlers"]
            },
            handler=_std_concurrent_race
        ),
        "std_concurrent_after": StdTool(
            name="std_concurrent_after",
            description='延迟执行',
            parameters={
                "type": "object",
                "properties": {
                    "delay": {"type": "string", "description": "延迟(ms或字符串格式)"},
                    "handler": {"type": "string", "description": "Handler JSON"}
                },
                "required": ["delay", "handler"]
            },
            handler=_std_concurrent_after
        ),
        "std_concurrent_schedule": StdTool(
            name="std_concurrent_schedule",
            description='周期执行',
            parameters={
                "type": "object",
                "properties": {
                    "interval": {"type": "string", "description": "间隔(ms或字符串格式)"},
                    "handler": {"type": "string", "description": "Handler JSON"}
                },
                "required": ["interval", "handler"]
            },
            handler=_std_concurrent_schedule
        ),
        "std_concurrent_cancel_schedule": StdTool(
            name="std_concurrent_cancel_schedule",
            description='取消周期调度',
            parameters={
                "type": "object",
                "properties": {
                    "schedule": {"type": "string", "description": "Schedule Handle JSON"}
                },
                "required": ["schedule"]
            },
            handler=_std_concurrent_cancel_schedule
        ),
        "std_concurrent_sleep_ms": StdTool(
            name="std_concurrent_sleep_ms",
            description='取消感知的 sleep',
            parameters={
                "type": "object",
                "properties": {
                    "ms": {"type": "string", "description": "毫秒数"}
                },
                "required": ["ms"]
            },
            handler=_std_concurrent_sleep_ms
        ),
        "std_concurrent_thread_count": StdTool(
            name="std_concurrent_thread_count",
            description='CPU 线程数',
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=_std_concurrent_thread_count
        ),
    }

    # Merge concurrent tools into main tools dict
    _all_tools.update(concurrent_tools)

    # ===== P2-4: Template System (模板系统) =====

    def _std_template_render(**kwargs):
        template_str = kwargs.get('template_str', kwargs.get('template', ''))
        data_json = kwargs.get('data', '{}')
        try:
            data = json.loads(data_json) if isinstance(data_json, str) else data_json
        except (json.JSONDecodeError, TypeError):
            data = {}
        return render_string(template_str, data)

    def _std_template_template(**kwargs):
        path = kwargs.get('path', '')
        data_json = kwargs.get('data', '{}')
        try:
            data = json.loads(data_json) if isinstance(data_json, str) else data_json
        except (json.JSONDecodeError, TypeError):
            data = {}
        return template(path, data)

    def _std_template_compile(**kwargs):
        path = kwargs.get('path', '')
        try:
            result = compile_template(path)
            return json.dumps(result)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_template_render_compiled(**kwargs):
        compiled_json = kwargs.get('compiled', '{}')
        data_json = kwargs.get('data', '{}')
        try:
            compiled = json.loads(compiled_json) if isinstance(compiled_json, str) else compiled_json
            data = json.loads(data_json) if isinstance(data_json, str) else data_json
        except (json.JSONDecodeError, TypeError):
            return f'Error: invalid JSON parameters'
        try:
            return render(compiled, data)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_template_filter_apply(**kwargs):
        value = kwargs.get('value', '')
        filter_name = kwargs.get('filter_name', kwargs.get('filter', ''))
        filter_args_json = kwargs.get('filter_args', '[]')
        try:
            filter_args = json.loads(filter_args_json) if isinstance(filter_args_json, str) else filter_args_json
        except (json.JSONDecodeError, TypeError):
            filter_args = []
        filter_fn = FILTER_REGISTRY.get(filter_name)
        if filter_fn:
            try:
                if filter_args:
                    return filter_fn(value, *filter_args)
                return filter_fn(value)
            except Exception as e:
                return f'Error: {str(e)}'
        return f'Error: unknown filter {filter_name}'

    def _std_template_agent_prompt(**kwargs):
        agent_json = kwargs.get('agent', '{}')
        template_str = kwargs.get('template_str', kwargs.get('template', ''))
        context_json = kwargs.get('context', '{}')
        try:
            agent_data = json.loads(agent_json) if isinstance(agent_json, str) else agent_json
            context_data = json.loads(context_json) if isinstance(context_json, str) else context_json
        except (json.JSONDecodeError, TypeError):
            agent_data = {}
            context_data = {}
        return agent_template_prompt(agent_data, template_str, context_data)

    def _std_template_agent_slot_fill(**kwargs):
        agent_json = kwargs.get('agent', '{}')
        template_str = kwargs.get('template_str', kwargs.get('template', ''))
        slot_sources_json = kwargs.get('slot_sources', '{}')
        try:
            agent_data = json.loads(agent_json) if isinstance(agent_json, str) else agent_json
            slot_sources = json.loads(slot_sources_json) if isinstance(slot_sources_json, str) else slot_sources_json
        except (json.JSONDecodeError, TypeError):
            agent_data = {}
            slot_sources = {}
        return agent_template_slot_fill(agent_data, template_str, slot_sources)

    def _std_template_agent_register(**kwargs):
        agent_json = kwargs.get('agent', '{}')
        name = kwargs.get('name', '')
        template_str = kwargs.get('template_str', kwargs.get('template', ''))
        try:
            agent_data = json.loads(agent_json) if isinstance(agent_json, str) else agent_json
        except (json.JSONDecodeError, TypeError):
            agent_data = {}
        result = agent_template_register(agent_data, name, template_str)
        return json.dumps(result)

    def _std_template_agent_list(**kwargs):
        result = agent_template_list()
        return json.dumps(result)

    def _std_template_filter_upper(**kwargs):
        return FILTER_REGISTRY.get('upper', lambda x: str(x))(kwargs.get('value', ''))

    def _std_template_filter_lower(**kwargs):
        return FILTER_REGISTRY.get('lower', lambda x: str(x))(kwargs.get('value', ''))

    def _std_template_filter_capitalize(**kwargs):
        return FILTER_REGISTRY.get('capitalize', lambda x: str(x))(kwargs.get('value', ''))

    def _std_template_filter_trim(**kwargs):
        return FILTER_REGISTRY.get('trim', lambda x: str(x))(kwargs.get('value', ''))

    def _std_template_filter_default(**kwargs):
        value = kwargs.get('value', '')
        default_val = kwargs.get('default', '')
        return FILTER_REGISTRY.get('default', lambda x, d: str(x))(value, default_val)

    def _std_template_filter_length(**kwargs):
        return FILTER_REGISTRY.get('length', lambda x: '0')(kwargs.get('value', ''))

    def _std_template_filter_json(**kwargs):
        return FILTER_REGISTRY.get('json', lambda x: str(x))(kwargs.get('value', ''))

    def _std_template_filter_escape(**kwargs):
        return FILTER_REGISTRY.get('escape', lambda x: str(x))(kwargs.get('value', ''))

    def _std_template_filter_url_encode(**kwargs):
        return FILTER_REGISTRY.get('url_encode', lambda x: str(x))(kwargs.get('value', ''))

    template_tools = {
        "std_template_render": StdTool(
            name="std_template_render",
            description='P2-4: 渲染模板字符串',
            parameters={
                "type": "object",
                "properties": {
                    "template_str": {"type": "string", "description": "模板字符串内容"},
                    "data": {"type": "string", "description": "数据上下文 JSON"}
                },
                "required": ["template_str"]
            },
            handler=_std_template_render
        ),
        "std_template_template": StdTool(
            name="std_template_template",
            description='P2-4: 加载并渲染外部模板文件',
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "模板文件路径"},
                    "data": {"type": "string", "description": "数据上下文 JSON"}
                },
                "required": ["path"]
            },
            handler=_std_template_template
        ),
        "std_template_compile": StdTool(
            name="std_template_compile",
            description='P2-4: 预编译模板文件',
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "模板文件路径"}
                },
                "required": ["path"]
            },
            handler=_std_template_compile
        ),
        "std_template_render_compiled": StdTool(
            name="std_template_render_compiled",
            description='P2-4: 渲染预编译模板',
            parameters={
                "type": "object",
                "properties": {
                    "compiled": {"type": "string", "description": "编译模板 handle JSON"},
                    "data": {"type": "string", "description": "数据上下文 JSON"}
                },
                "required": ["compiled"]
            },
            handler=_std_template_render_compiled
        ),
        "std_template_filter_apply": StdTool(
            name="std_template_filter_apply",
            description='P2-4: 应用模板过滤器',
            parameters={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "输入值"},
                    "filter_name": {"type": "string", "description": "过滤器名称"},
                    "filter_args": {"type": "string", "description": "过滤器参数 JSON"}
                },
                "required": ["value", "filter_name"]
            },
            handler=_std_template_filter_apply
        ),
        "std_template_agent_prompt": StdTool(
            name="std_template_agent_prompt",
            description='P2-4: Agent Prompt 模板渲染',
            parameters={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "Agent 属性 JSON"},
                    "template_str": {"type": "string", "description": "模板字符串"},
                    "context": {"type": "string", "description": "额外上下文 JSON"}
                },
                "required": ["agent", "template_str"]
            },
            handler=_std_template_agent_prompt
        ),
        "std_template_agent_slot_fill": StdTool(
            name="std_template_agent_slot_fill",
            description='P2-4: Agent 多源 Slot 填充',
            parameters={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "Agent 属性 JSON"},
                    "template_str": {"type": "string", "description": "模板字符串"},
                    "slot_sources": {"type": "string", "description": "Slot 来源 JSON"}
                },
                "required": ["agent", "template_str"]
            },
            handler=_std_template_agent_slot_fill
        ),
        "std_template_agent_register": StdTool(
            name="std_template_agent_register",
            description='P2-4: 注册 Agent 模板',
            parameters={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "Agent 属性 JSON"},
                    "name": {"type": "string", "description": "模板名称"},
                    "template_str": {"type": "string", "description": "模板字符串"}
                },
                "required": ["agent", "name", "template_str"]
            },
            handler=_std_template_agent_register
        ),
        "std_template_agent_list": StdTool(
            name="std_template_agent_list",
            description='P2-4: 列出已注册 Agent 模板',
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=_std_template_agent_list
        ),
        "std_template_filter_upper": StdTool(
            name="std_template_filter_upper",
            description='P2-4: 大写过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_upper
        ),
        "std_template_filter_lower": StdTool(
            name="std_template_filter_lower",
            description='P2-4: 小写过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_lower
        ),
        "std_template_filter_capitalize": StdTool(
            name="std_template_filter_capitalize",
            description='P2-4: 首字母大写过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_capitalize
        ),
        "std_template_filter_trim": StdTool(
            name="std_template_filter_trim",
            description='P2-4: 去空白过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_trim
        ),
        "std_template_filter_default": StdTool(
            name="std_template_filter_default",
            description='P2-4: 默认值过滤器',
            parameters={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "输入值"},
                    "default": {"type": "string", "description": "默认值"}
                },
                "required": ["value"]
            },
            handler=_std_template_filter_default
        ),
        "std_template_filter_length": StdTool(
            name="std_template_filter_length",
            description='P2-4: 长度过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_length
        ),
        "std_template_filter_json": StdTool(
            name="std_template_filter_json",
            description='P2-4: JSON序列化过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_json
        ),
        "std_template_filter_escape": StdTool(
            name="std_template_filter_escape",
            description='P2-4: HTML转义过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_escape
        ),
        "std_template_filter_url_encode": StdTool(
            name="std_template_filter_url_encode",
            description='P2-4: URL编码过滤器',
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string", "description": "输入值"}},
                "required": ["value"]
            },
            handler=_std_template_filter_url_encode
        ),
    }

    _all_tools.update(template_tools)

    # ==================== P3-2/P3-5/P3-6: Pipe, Defer, Null Coalesce ====================

    def _std_pipe_apply(**kwargs):
        'P3-2: Pipe operator — apply value as first arg of function: x |> f => f(x)'
        value = kwargs.get('value', '')
        func_name = kwargs.get('func', '')
        extra_args_json = kwargs.get('extra_args', '[]')
        try:
            extra_args = json.loads(extra_args_json) if isinstance(extra_args_json, str) else extra_args_json
            # In stdlib context, we can't dynamically call arbitrary functions,
            # so this is primarily a documentation/inspection tool
            return json.dumps({'pipe_result': f'{func_name}({value}, {extra_args})', 'desugared': True}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_defer_schedule(**kwargs):
        'P3-5: Defer statement — schedule expression for LIFO execution on scope exit'
        expression = kwargs.get('expression', '')
        try:
            return json.dumps({'deferred': expression, 'note': 'Executes on scope exit in LIFO order'}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_null_coalesce_apply(**kwargs):
        'P3-6: Null coalescing — return fallback if value is None/Option::None/empty dict'
        value_json = kwargs.get('value', 'null')
        fallback = kwargs.get('fallback', '')
        try:
            from . import _nexa_null_coalesce
            value = json.loads(value_json) if isinstance(value_json, str) else value_json
            result = _nexa_null_coalesce(value, fallback)
            if result is None:
                return 'null'
            return json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
        except Exception as e:
            return fallback if fallback else f'Error: {str(e)}'

    def _std_string_interpolate(**kwargs):
        'P3-1: String interpolation — convert #{expr} patterns in strings to interpolated values'
        template = kwargs.get('template', '')
        context_json = kwargs.get('context', '{}')
        try:
            from . import _nexa_interp_str
            context = json.loads(context_json) if isinstance(context_json, str) else context_json
            # Simple replacement of #{expr} patterns using context values
            import re
            def _replace_interp(match):
                expr = match.group(1).strip()
                # Look up in context
                if '.' in expr:
                    parts = expr.split('.')
                    val = context
                    for p in parts:
                        if isinstance(val, dict):
                            val = val.get(p)
                        else:
                            val = None
                        if val is None:
                            break
                    return _nexa_interp_str(val)
                elif '[' in expr:
                    # Bracket access: arr[0] or dict["key"]
                    base_match = re.match(r'^([a-zA-Z_]\w*)\[', expr)
                    if base_match:
                        base_name = base_match.group(1)
                        val = context.get(base_name)
                        # Handle remaining bracket/dot access
                        rest = expr[len(base_name):]
                        while rest:
                            bracket_match = re.match(r'^\[([^\]]+)\]', rest)
                            dot_match = re.match(r'^\.([a-zA-Z_]\w*)', rest)
                            if bracket_match:
                                key = bracket_match.group(1)
                                if key.isdigit():
                                    key = int(key)
                                elif key.startswith('"') or key.startswith("'"):
                                    key = key[1:-1]
                                if isinstance(val, dict):
                                    val = val.get(key)
                                elif isinstance(val, (list, tuple)):
                                    val = val[int(key)] if isinstance(key, int) else None
                                rest = rest[len(bracket_match.group(0)):]
                            elif dot_match:
                                attr = dot_match.group(1)
                                if isinstance(val, dict):
                                    val = val.get(attr)
                                else:
                                    val = None
                                rest = rest[len(dot_match.group(0)):]
                            else:
                                break
                        return _nexa_interp_str(val)
                elif expr in context:
                    return _nexa_interp_str(context.get(expr))
                return ''
            result = re.sub(r'#\{([^}]+)\}', _replace_interp, template)
            # Handle escaped \#{ -> #{ literal
            result = result.replace('\\#{', '#{')
            return result
        except Exception as e:
            return f'Error: {str(e)}'

    # ==================== P3-3: Pattern Matching ====================

    def _std_match_pattern(**kwargs):
        'P3-3: Pattern matching -- match a value against a pattern and return bindings'
        value_json = kwargs.get('value', 'null')
        pattern_json = kwargs.get('pattern', '{}')
        try:
            from .pattern_matching import nexa_match_pattern
            value = json.loads(value_json) if isinstance(value_json, str) else value_json
            pattern = json.loads(pattern_json) if isinstance(pattern_json, str) else pattern_json
            bindings = nexa_match_pattern(pattern, value)
            if bindings is None:
                return json.dumps({'matched': False, 'bindings': {}}, ensure_ascii=False)
            return json.dumps({'matched': True, 'bindings': bindings}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_match_destructure(**kwargs):
        'P3-3: Destructuring -- destructure a value according to a pattern'
        value_json = kwargs.get('value', 'null')
        pattern_json = kwargs.get('pattern', '{}')
        try:
            from .pattern_matching import nexa_destructure
            value = json.loads(value_json) if isinstance(value_json, str) else value_json
            pattern = json.loads(pattern_json) if isinstance(pattern_json, str) else pattern_json
            bindings = nexa_destructure(pattern, value)
            return json.dumps({'bindings': bindings}, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    def _std_match_variant(**kwargs):
        'P3-3: Create enum variant value for pattern matching'
        enum_name = kwargs.get('enum', '')
        variant_name = kwargs.get('variant', '')
        fields_json = kwargs.get('fields', '[]')
        try:
            from .pattern_matching import nexa_make_variant
            fields = json.loads(fields_json) if isinstance(fields_json, str) else fields_json
            result = nexa_make_variant(enum_name, variant_name, *fields)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f'Error: {str(e)}'

    p3_match_tools = {
        "std_match_pattern": StdTool(
            name="std_match_pattern",
            description="P3-3: Match a value against a pattern and return variable bindings",
            parameters={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "JSON value to match"},
                    "pattern": {"type": "string", "description": "JSON pattern definition"}
                },
                "required": ["value", "pattern"]
            },
            handler=_std_match_pattern
        ),
        "std_match_destructure": StdTool(
            name="std_match_destructure",
            description="P3-3: Destructure a value according to a pattern, returning bindings",
            parameters={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "JSON value to destructure"},
                    "pattern": {"type": "string", "description": "JSON pattern definition"}
                },
                "required": ["value", "pattern"]
            },
            handler=_std_match_destructure
        ),
        "std_match_variant": StdTool(
            name="std_match_variant",
            description="P3-3: Create an enum variant value for pattern matching",
            parameters={
                "type": "object",
                "properties": {
                    "enum": {"type": "string", "description": "Enum type name"},
                    "variant": {"type": "string", "description": "Variant name"},
                    "fields": {"type": "string", "description": "JSON array of field values"}
                },
                "required": ["enum", "variant"]
            },
            handler=_std_match_variant
        ),
    }

    _all_tools.update(p3_match_tools)

    p3_tools = {
        "std_pipe_apply": StdTool(
            name="std_pipe_apply",
            description="P3-2: Pipe operator — apply value as first argument of function (x |> f => f(x))",
            parameters={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "Value to pipe (LHS)"},
                    "func": {"type": "string", "description": "Function name (RHS)"},
                    "extra_args": {"type": "string", "description": "Additional arguments JSON array"}
                },
                "required": ["value", "func"]
            },
            handler=_std_pipe_apply
        ),
        "std_defer_schedule": StdTool(
            name="std_defer_schedule",
            description="P3-5: Defer statement — schedule expression for LIFO execution on scope exit",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Expression to defer"}
                },
                "required": ["expression"]
            },
            handler=_std_defer_schedule
        ),
        "std_null_coalesce_apply": StdTool(
            name="std_null_coalesce_apply",
            description="P3-6: Null coalescing — return fallback if value is None/Option::None/empty dict",
            parameters={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "Value to check (may be null-like)"},
                    "fallback": {"type": "string", "description": "Fallback value if null-like"}
                },
                "required": ["value", "fallback"]
            },
            handler=_std_null_coalesce_apply
        ),
        "std_string_interpolate": StdTool(
            name="std_string_interpolate",
            description="P3-1: String interpolation — evaluate #{expr} patterns in strings using a context dictionary",
            parameters={
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "String template with #{expr} patterns"},
                    "context": {"type": "string", "description": "JSON context dictionary for variable lookup"}
                },
                "required": ["template"]
            },
            handler=_std_string_interpolate
        ),
    }

    _all_tools.update(p3_tools)

    # ===== P3-4: ADT — Struct/Enum/Trait/Impl StdTools =====

    from src.runtime.adt import (
        register_struct, make_struct_instance, struct_get_field, struct_set_field,
        is_struct_instance, lookup_struct, get_all_structs,
        register_enum, make_variant, make_unit_variant, is_variant_instance,
        lookup_enum, get_all_enums,
        register_trait, register_impl, call_trait_method,
        lookup_trait, lookup_impl, get_all_traits, get_all_impls,
        adt_reset_registries, adt_get_registry_summary,
    )

    def _std_adt_register_struct(**kwargs):
        'P3-4: Register a struct definition with field names and optional types'
        name = kwargs.get('name', '')
        fields_json = kwargs.get('fields', '[]')
        try:
            fields = json.loads(fields_json) if isinstance(fields_json, str) else fields_json
        except Exception:
            fields = []
        try:
            result = register_struct(name, fields)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_make_struct(**kwargs):
        'P3-4: Create a struct instance with field values'
        name = kwargs.get('name', '')
        fields_json = kwargs.get('fields', '{}')
        try:
            fields = json.loads(fields_json) if isinstance(fields_json, str) else fields_json
        except Exception:
            fields = {}
        try:
            instance = make_struct_instance(name, **fields)
            return json.dumps(instance)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_register_enum(**kwargs):
        'P3-4: Register an enum definition with variant names and optional field types'
        name = kwargs.get('name', '')
        variants_json = kwargs.get('variants', '[]')
        try:
            variants = json.loads(variants_json) if isinstance(variants_json, str) else variants_json
        except Exception:
            variants = []
        try:
            result = register_enum(name, variants)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_make_variant(**kwargs):
        'P3-4: Create an enum variant instance'
        enum_name = kwargs.get('enum', '')
        variant_name = kwargs.get('variant', '')
        fields_json = kwargs.get('fields', '[]')
        try:
            fields = json.loads(fields_json) if isinstance(fields_json, str) else fields_json
        except Exception:
            fields = []
        try:
            result = make_variant(enum_name, variant_name, *fields)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_register_trait(**kwargs):
        'P3-4: Register a trait definition with method signatures'
        name = kwargs.get('name', '')
        methods_json = kwargs.get('methods', '[]')
        try:
            methods = json.loads(methods_json) if isinstance(methods_json, str) else methods_json
        except Exception:
            methods = []
        try:
            result = register_trait(name, methods)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_register_impl(**kwargs):
        'P3-4: Register a trait implementation for a type'
        trait_name = kwargs.get('trait', '')
        type_name = kwargs.get('type', '')
        methods_json = kwargs.get('methods', '{}')
        try:
            methods = json.loads(methods_json) if isinstance(methods_json, str) else methods_json
        except Exception:
            methods = {}
        try:
            result = register_impl(trait_name, type_name, methods)
            return json.dumps({'registered': True, 'trait': trait_name, 'type': type_name})
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_lookup(**kwargs):
        'P3-4: Lookup ADT definitions (struct, enum, trait, impl)'
        kind = kwargs.get('kind', 'struct')
        name = kwargs.get('name', '')
        try:
            if kind == 'struct':
                result = lookup_struct(name)
            elif kind == 'enum':
                result = lookup_enum(name)
            elif kind == 'trait':
                result = lookup_trait(name)
            elif kind == 'impl':
                trait = kwargs.get('trait', '')
                type_n = kwargs.get('type', '')
                result = lookup_impl(trait, type_n)
            else:
                result = None
            return json.dumps(result) if result else json.dumps({'error': f'{kind} {name} not found'})
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_summary(**kwargs):
        'P3-4: Get summary of all registered ADTs'
        try:
            result = adt_get_registry_summary()
            return json.dumps(result)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _std_adt_reset(**kwargs):
        'P3-4: Reset all ADT registries (for testing)'
        try:
            adt_reset_registries()
            return json.dumps({'reset': True})
        except Exception as e:
            return json.dumps({'error': str(e)})

    p4_adt_tools = {
        "std_adt_register_struct": StdTool(
            name="std_adt_register_struct",
            description="P3-4: Register a struct definition with field names and optional types",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Struct name"},
                    "fields": {"type": "string", "description": "JSON array of field definitions"}
                },
                "required": ["name", "fields"]
            },
            handler=_std_adt_register_struct
        ),
        "std_adt_make_struct": StdTool(
            name="std_adt_make_struct",
            description="P3-4: Create a struct instance with field values",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Struct name"},
                    "fields": {"type": "string", "description": "JSON object of field values"}
                },
                "required": ["name"]
            },
            handler=_std_adt_make_struct
        ),
        "std_adt_register_enum": StdTool(
            name="std_adt_register_enum",
            description="P3-4: Register an enum definition with variant names and optional field types",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Enum name"},
                    "variants": {"type": "string", "description": "JSON array of variant definitions"}
                },
                "required": ["name", "variants"]
            },
            handler=_std_adt_register_enum
        ),
        "std_adt_make_variant": StdTool(
            name="std_adt_make_variant",
            description="P3-4: Create an enum variant instance",
            parameters={
                "type": "object",
                "properties": {
                    "enum": {"type": "string", "description": "Enum type name"},
                    "variant": {"type": "string", "description": "Variant name"},
                    "fields": {"type": "string", "description": "JSON array of field values"}
                },
                "required": ["enum", "variant"]
            },
            handler=_std_adt_make_variant
        ),
        "std_adt_register_trait": StdTool(
            name="std_adt_register_trait",
            description="P3-4: Register a trait definition with method signatures",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Trait name"},
                    "methods": {"type": "string", "description": "JSON array of method definitions"}
                },
                "required": ["name", "methods"]
            },
            handler=_std_adt_register_trait
        ),
        "std_adt_register_impl": StdTool(
            name="std_adt_register_impl",
            description="P3-4: Register a trait implementation for a type",
            parameters={
                "type": "object",
                "properties": {
                    "trait": {"type": "string", "description": "Trait name"},
                    "type": {"type": "string", "description": "Type name to implement trait for"},
                    "methods": {"type": "string", "description": "JSON object of method implementations"}
                },
                "required": ["trait", "type"]
            },
            handler=_std_adt_register_impl
        ),
        "std_adt_lookup": StdTool(
            name="std_adt_lookup",
            description="P3-4: Lookup ADT definitions (struct, enum, trait, impl)",
            parameters={
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "ADT kind: struct, enum, trait, impl"},
                    "name": {"type": "string", "description": "Name to look up"}
                },
                "required": ["kind", "name"]
            },
            handler=_std_adt_lookup
        ),
        "std_adt_summary": StdTool(
            name="std_adt_summary",
            description="P3-4: Get summary of all registered ADTs",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=_std_adt_summary
        ),
        "std_adt_reset": StdTool(
            name="std_adt_reset",
            description="P3-4: Reset all ADT registries (for testing)",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=_std_adt_reset
        ),
    }

    _all_tools.update(p4_adt_tools)

    return _all_tools


def get_stdlib_tool(name: str) -> Optional[StdTool]:
    """获取单个标准库工具"""
    tools = get_stdlib_tools()
    return tools.get(name)


def get_stdlib_tool_definitions() -> List[Dict]:
    """获取所有标准库工具定义 (用于 Agent tools 参数)"""
    return [tool.to_dict() for tool in get_stdlib_tools().values()]


def execute_stdlib_tool(name: str, **kwargs) -> str:
    """执行标准库工具"""
    tool = get_stdlib_tool(name)
    if tool:
        return tool.execute(**kwargs)
    return f"Error: Unknown tool '{name}'"


# ==================== 命名空间映射 ====================

STD_NAMESPACE_MAP = {
    "std.fs": ["file_read", "file_write", "file_exists", "file_list", "file_append", "file_delete"],
    "std.http": ["http_get", "http_post", "http_put", "http_delete"],
    "std.time": ["time_now", "time_diff", "time_format", "time_sleep", "time_timestamp"],
    "std.text": ["text_split", "text_replace", "text_upper", "text_lower"],
    "std.json": ["json_parse", "json_get", "json_stringify"],
    "std.hash": ["hash_md5", "hash_sha256", "base64_encode", "base64_decode"],
    "std.math": ["math_calc", "math_random"],
    "std.regex": ["regex_match", "regex_replace"],
    "std.shell": ["shell_exec", "shell_which"],
    "std.ask_human": ["ask_human"],
    # P1-5: Database Integration (内置数据库集成)
    "std.db.sqlite": ["std_db_sqlite_connect", "std_db_sqlite_query", "std_db_sqlite_query_one", "std_db_sqlite_execute", "std_db_sqlite_close", "std_db_sqlite_begin", "std_db_sqlite_commit", "std_db_sqlite_rollback"],
    "std.db.postgres": ["std_db_postgres_connect", "std_db_postgres_query", "std_db_postgres_query_one", "std_db_postgres_execute", "std_db_postgres_close", "std_db_postgres_begin", "std_db_postgres_commit", "std_db_postgres_rollback"],
    "std.db.memory": ["std_db_memory_query", "std_db_memory_store", "std_db_memory_delete", "std_db_memory_list"],
    # P2-1: Auth & OAuth (内置认证与 OAuth)
    "std.auth": ["std_auth_oauth", "std_auth_enable_auth", "std_auth_get_user", "std_auth_get_session", "std_auth_session_data", "std_auth_set_session", "std_auth_logout_user", "std_auth_require_auth", "std_auth_jwt_sign", "std_auth_jwt_verify", "std_auth_jwt_decode", "std_auth_csrf_token", "std_auth_csrf_field", "std_auth_verify_csrf", "std_auth_api_key_generate", "std_auth_api_key_verify", "std_auth_auth_context"],
    # P2-3: KV Store (内置键值存储)
    "std.kv": ["std_kv_open", "std_kv_get", "std_kv_get_int", "std_kv_get_str", "std_kv_get_json", "std_kv_set", "std_kv_set_nx", "std_kv_del", "std_kv_has", "std_kv_list", "std_kv_expire", "std_kv_ttl", "std_kv_flush", "std_kv_incr", "std_kv_agent_kv_query", "std_kv_agent_kv_store", "std_kv_agent_kv_context"],
    # P2-2: Structured Concurrency (结构化并发)
    "std.concurrent": ["std_concurrent_channel", "std_concurrent_send", "std_concurrent_recv", "std_concurrent_recv_timeout", "std_concurrent_try_recv", "std_concurrent_close", "std_concurrent_select", "std_concurrent_spawn", "std_concurrent_await_task", "std_concurrent_try_await", "std_concurrent_cancel_task", "std_concurrent_parallel", "std_concurrent_race", "std_concurrent_after", "std_concurrent_schedule", "std_concurrent_cancel_schedule", "std_concurrent_sleep_ms", "std_concurrent_thread_count"],
    # P2-4: Template System (模板系统)
    "std.template": ["std_template_render", "std_template_template", "std_template_compile", "std_template_render_compiled", "std_template_filter_apply", "std_template_agent_prompt", "std_template_agent_slot_fill", "std_template_agent_register", "std_template_agent_list", "std_template_filter_upper", "std_template_filter_lower", "std_template_filter_capitalize", "std_template_filter_trim", "std_template_filter_default", "std_template_filter_length", "std_template_filter_json", "std_template_filter_escape", "std_template_filter_url_encode"],
    # P3-2/P3-5/P3-6/P3-1: Pipe, Defer, Null Coalesce, String Interpolation
    "std.pipe": ["std_pipe_apply"],
    "std.defer": ["std_defer_schedule"],
    "std.null_coalesce": ["std_null_coalesce_apply"],
    "std.string": ["std_string_interpolate"],
    # P3-3: Pattern Matching (模式匹配)
    "std.match": ["std_match_pattern", "std_match_destructure", "std_match_variant"],
    # P3-4: ADT — Struct/Enum/Trait/Impl (代数数据类型)
    "std.struct": ["std_adt_register_struct", "std_adt_make_struct", "std_adt_lookup"],
    "std.enum": ["std_adt_register_enum", "std_adt_make_variant", "std_adt_lookup"],
    "std.trait": ["std_adt_register_trait", "std_adt_register_impl", "std_adt_lookup", "std_adt_summary", "std_adt_reset"],
}

STD_TOOLS_SCHEMA = {}

def _init_schemas():
    """初始化工具 schema"""
    global STD_TOOLS_SCHEMA
    for name, tool in get_stdlib_tools().items():
        STD_TOOLS_SCHEMA[name] = tool.to_dict()

_init_schemas()

# ==================== 导出 ====================

__all__ = [
    "get_stdlib_tools",
    "get_stdlib_tool",
    "get_stdlib_tool_definitions",
    "execute_stdlib_tool",
    "StdTool",
    "STD_NAMESPACE_MAP",
    "STD_TOOLS_SCHEMA",
    # P1-5: Database stdlib functions
    "_std_db_sqlite_connect", "_std_db_sqlite_query", "_std_db_sqlite_query_one",
    "_std_db_sqlite_execute", "_std_db_sqlite_close", "_std_db_sqlite_begin",
    "_std_db_sqlite_commit", "_std_db_sqlite_rollback",
    "_std_db_postgres_connect", "_std_db_postgres_query", "_std_db_postgres_query_one",
    "_std_db_postgres_execute", "_std_db_postgres_close", "_std_db_postgres_begin",
    "_std_db_postgres_commit", "_std_db_postgres_rollback",
    "_std_db_memory_query", "_std_db_memory_store", "_std_db_memory_delete",
    "_std_db_memory_list",
    # P2-1: Auth stdlib functions
    "_std_auth_oauth", "_std_auth_enable_auth", "_std_auth_get_user",
    "_std_auth_get_session", "_std_auth_session_data", "_std_auth_set_session",
    "_std_auth_logout_user", "_std_auth_require_auth",
    "_std_auth_jwt_sign", "_std_auth_jwt_verify", "_std_auth_jwt_decode",
    "_std_auth_csrf_token", "_std_auth_csrf_field", "_std_auth_verify_csrf",
    "_std_auth_api_key_generate", "_std_auth_api_key_verify", "_std_auth_auth_context",
    # P2-3: KV stdlib functions
    "_std_kv_open", "_std_kv_get", "_std_kv_get_int", "_std_kv_get_str",
    "_std_kv_get_json", "_std_kv_set", "_std_kv_set_nx", "_std_kv_del",
    "_std_kv_has", "_std_kv_list", "_std_kv_expire", "_std_kv_ttl",
    "_std_kv_flush", "_std_kv_incr",
    "_std_kv_agent_kv_query", "_std_kv_agent_kv_store", "_std_kv_agent_kv_context",
    # P2-2: Concurrent stdlib functions
    "_std_concurrent_channel", "_std_concurrent_send", "_std_concurrent_recv",
    "_std_concurrent_recv_timeout", "_std_concurrent_try_recv", "_std_concurrent_close",
    "_std_concurrent_select", "_std_concurrent_spawn", "_std_concurrent_await_task",
    "_std_concurrent_try_await", "_std_concurrent_cancel_task", "_std_concurrent_parallel",
    "_std_concurrent_race", "_std_concurrent_after", "_std_concurrent_schedule",
    "_std_concurrent_cancel_schedule", "_std_concurrent_sleep_ms", "_std_concurrent_thread_count",
    # P2-4: Template stdlib functions
    "_std_template_render", "_std_template_template", "_std_template_compile",
    "_std_template_render_compiled", "_std_template_filter_apply",
    "_std_template_agent_prompt", "_std_template_agent_slot_fill",
    "_std_template_agent_register", "_std_template_agent_list",
    "_std_template_filter_upper", "_std_template_filter_lower",
    "_std_template_filter_capitalize", "_std_template_filter_trim",
    "_std_template_filter_default", "_std_template_filter_length",
    "_std_template_filter_json", "_std_template_filter_escape",
    "_std_template_filter_url_encode",
    # P3-2/P3-5/P3-6/P3-1: Pipe, Defer, Null Coalesce, String Interpolation
    "_std_pipe_apply", "_std_defer_schedule", "_std_null_coalesce_apply", "_std_string_interpolate", "_std_match_pattern", "_std_match_destructure", "_std_match_variant",
    # P3-4: ADT stdlib functions
    "_std_adt_register_struct", "_std_adt_make_struct",
    "_std_adt_register_enum", "_std_adt_make_variant",
    "_std_adt_register_trait", "_std_adt_register_impl",
    "_std_adt_lookup", "_std_adt_summary", "_std_adt_reset",
]
