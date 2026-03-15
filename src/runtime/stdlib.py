import subprocess
import json

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
    }
}
