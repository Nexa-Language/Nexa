import json
import hashlib
import time
from .stdlib import std_shell_execute, std_fs_read_file, std_fs_write_file, std_http_fetch, std_time_now, std_ask_human

def calculate_hash(text: str) -> str:
    """Calculates the SHA256 string for any given input string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_current_time(timezone: str = "UTC") -> str:
    """Returns the current time given a timezone."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

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
