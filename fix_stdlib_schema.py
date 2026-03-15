import json

with open("src/runtime/stdlib.py", "r") as f:
    text = f.read()

# Replace the wrapper wrapper for all standard tools.
text = text.replace('''"std_shell_execute": {
        "type": "function",
        "function": {
            "name": "std_shell_execute",''', '''"std_shell_execute": {
        "name": "std_shell_execute",''')

text = text.replace('''"std_fs_read_file": {
        "type": "function",
        "function": {
            "name": "std_fs_read_file",''', '''"std_fs_read_file": {
        "name": "std_fs_read_file",''')

text = text.replace('''"std_fs_write_file": {
        "type": "function",
        "function": {
            "name": "std_fs_write_file",''', '''"std_fs_write_file": {
        "name": "std_fs_write_file",''')

text = text.replace('''"std_http_fetch": {
        "type": "function",
        "function": {
             "name": "std_http_fetch",''', '''"std_http_fetch": {
        "name": "std_http_fetch",''')

text = text.replace('''"std_time_now": {
        "type": "function",
        "function": {
            "name": "std_time_now",''', '''"std_time_now": {
        "name": "std_time_now",''')

text = text.replace('''"required": ["command"]
            }
        }
    },''', '''"required": ["command"]
        }
    },''')

text = text.replace('''"required": ["filepath"]
            }
        }
    },''', '''"required": ["filepath"]
        }
    },''')

text = text.replace('''"required": ["filepath", "content"]
            }
        }
    },''', '''"required": ["filepath", "content"]
        }
    },''')

text = text.replace('''"required": ["url"]
             }
        }
    },''', '''"required": ["url"]
        }
    },''')

text = text.replace('''"required": ["timezone"]
            }
        }
    }
}''', '''"required": ["timezone"]
        }
    }
}''')

with open("src/runtime/stdlib.py", "w") as f:
    f.write(text)
