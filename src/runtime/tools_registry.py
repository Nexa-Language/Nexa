import json
import hashlib
import time
import subprocess
from .stdlib import execute_stdlib_tool, get_stdlib_tools

def calculate_hash(text: str) -> str:
    """Calculates the SHA256 string for any given input string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_current_time(timezone: str = "UTC") -> str:
    """Returns the current time given a timezone."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def std_shell_execute(command: str, timeout: int = 60) -> str:
    """执行系统命令"""
    try:
        result = subprocess.run(
            command,
            shell=True,
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

# Tool dispatcher mapped by function name
LOCAL_TOOLS = {
    "calculate_hash": calculate_hash,
    "get_current_time": get_current_time,
    "std_shell_execute": std_shell_execute,
    "std_fs_read_file": std_fs_read_file,
    "std_fs_write_file": std_fs_write_file,
    "std_http_fetch": std_http_fetch,
    "std_time_now": std_time_now,
    "std_ask_human": std_ask_human
}

def execute_tool(name: str, args_json: str) -> str:
    print(f"    [ToolRegistry] Executing {name} with args {args_json} ...")
    if name not in LOCAL_TOOLS:
        return f"Error: Tool '{name}' not found locally."
    
    try:
        args = json.loads(args_json)
        result = LOCAL_TOOLS[name](**args)
        print(f"    [ToolRegistry] Execution result: {result}")
        return str(result)
    except Exception as e:
        err = f"Error executing tool {name}: {str(e)}"
        print(f"    [ToolRegistry] {err}")
        return err
