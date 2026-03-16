import re

with open('src/runtime/stdlib.py', 'r') as f:
    content = f.read()

# Add std_ask_human
hitl_schema = """    "std_ask_human": {
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
"""

content = content.replace('"std_time_now": {', hitl_schema + '    "std_time_now": {')

content = content.replace('"std.time": ["std_time_now"]', '"std.time": ["std_time_now"],\n    "std.hitl": ["std_ask_human"],\n    "std.ask_human": ["std_ask_human"]')

with open('src/runtime/stdlib.py', 'w') as f:
    f.write(content)
