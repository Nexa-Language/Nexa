
import subprocess
import json
import os
import datetime
import urllib.request
import urllib.error
import re

def std_shell_execute(command: str) -> str:
    """Executes a shell command on the local operating system and returns the output."""
    print(f"\n\033[93m⚠️ [Nexa Sandbox] Agent requested to run: {command}\033[0m\n")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]:\n{result.stderr}"
        return output if output.strip() else "[Command executed successfully with no output]"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def std_fs_read_file(filepath: str) -> str:
    print(f"\n\033[94m🔍 [Nexa FS] Reading file: {filepath}\033[0m\n")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {filepath}: {str(e)}"

def std_fs_write_file(filepath: str, content: str) -> str:
    print(f"\n\033[94m💾 [Nexa FS] Writing file: {filepath}\033[0m\n")
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {filepath}"
    except Exception as e:
        return f"Error writing to file {filepath}: {str(e)}"

def std_http_fetch(url: str) -> str:
    print(f"\n\033[96m🌐 [Nexa HTTP] Fetching: {url}\033[0m\n")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Nexa/0.7'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
            # Very basic HTML tag stripping to keep text
            text = re.sub(r'<style.*?>.*?</style>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(r'<script.*?>.*?</script>', ' ', text, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()[:20000] # Limit size to prevent context overflow
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"

def std_time_now(**kwargs) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n\033[95m🕒 [Nexa Time] Time requested, returned: {now}\033[0m\n")
    return now

STD_TOOLS_SCHEMA = {
    "std_shell_execute": {
        "name": "std_shell_execute",
            "description": "Executes a shell command on the local operating system and returns the output (stdout/stderr).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["command"]
        }
    },
    "std_fs_read_file": {
        "name": "std_fs_read_file",
            "description": "Reads the content of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The absolute or relative path to the file"}
                },
                "required": ["filepath"]
        }
    },
    "std_fs_write_file": {
        "name": "std_fs_write_file",
            "description": "Writes text content to a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The absolute or relative path to the file"},
                    "content": {"type": "string", "description": "The text content to write"}
                },
                "required": ["filepath", "content"]
        }
    },
    "std_http_fetch": {
        "name": "std_http_fetch",
             "description": "Fetches and returns the plain text content of a given URL.",
             "parameters": {
                 "type": "object",
                 "properties": {
                     "url": {"type": "string", "description": "The URL to fetch, including http:// or https://"}
                 },
                 "required": ["url"]
        }
    },
        "std_ask_human": {
        "name": "std_ask_human",
        "description": "Asks the human user a question and waits for their input.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The question or prompt to show to the human user"}
            },
            "required": ["prompt"]
        }
    },
    "std_time_now": {
        "name": "std_time_now",
            "description": "Returns the current local system time formatted as YYYY-MM-DD HH:MM:SS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone to retrieve the time for, e.g., 'UTC'"}
                },
                "required": ["timezone"]
        }
    }
}

STD_NAMESPACE_MAP = {
    "std.shell": ["std_shell_execute"],
    "std.fs": ["std_fs_read_file", "std_fs_write_file"],
    "std.http": ["std_http_fetch"],
    "std.time": ["std_time_now"],
    "std.hitl": ["std_ask_human"],
    "std.ask_human": ["std_ask_human"]
}

def std_ask_human(prompt: str) -> str:
    print(f"\n\033[1;35m[Nexa HITL] Human input required: {prompt}\033[0m", flush=True)
    import sys
    try:
        return sys.stdin.readline().strip()
    except Exception as e:
        return f"Error reading user input: {str(e)}"
