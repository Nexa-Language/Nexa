with open("src/runtime/tools_registry.py", "r") as f:
    original = f.read()

original = original.replace("from .stdlib import std_shell_execute", 
"from .stdlib import std_shell_execute, std_fs_read_file, std_fs_write_file, std_http_fetch, std_time_now")

original = original.replace('"std_shell_execute": std_shell_execute', 
""""std_shell_execute": std_shell_execute,
    "std_fs_read_file": std_fs_read_file,
    "std_fs_write_file": std_fs_write_file,
    "std_http_fetch": std_http_fetch,
    "std_time_now": std_time_now""")

with open("src/runtime/tools_registry.py", "w") as f:
    f.write(original)
