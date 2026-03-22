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


# ==================== 标准库注册 ====================

def get_stdlib_tools() -> Dict[str, StdTool]:
    """获取所有标准库工具"""
    return {
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
    }


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
    "std.fs": ["file_read", "file_write", "file_exists", "file_list"],
    "std.http": ["http_get", "http_post"],
    "std.time": ["time_now", "time_diff"],
    "std.text": ["text_split", "text_replace", "text_upper", "text_lower"],
    "std.json": ["json_parse", "json_get"],
    "std.hash": ["hash_md5", "hash_sha256", "base64_encode", "base64_decode"],
    "std.math": ["math_calc", "math_random"],
    "std.regex": ["regex_match", "regex_replace"],
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
]
