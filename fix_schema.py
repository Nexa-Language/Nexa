with open("src/runtime/stdlib.py", "r") as f:
    text = f.read()

bad = '''        "function": {
            "name": "std_time_now",
            "description": "Returns the current local system time formatted as YYYY-MM-DD HH:MM:SS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Optional timezone to retrieve the time for"}
                },
                "required": []
            }
        }'''

good = '''        "function": {
            "name": "std_time_now",
            "description": "Returns the current local system time formatted as YYYY-MM-DD HH:MM:SS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone to retrieve the time for, e.g., 'UTC'"}
                },
                "required": ["timezone"]
            }
        }'''

if bad in text:
    text = text.replace(bad, good)
else:
    print("Not found")

with open("src/runtime/stdlib.py", "w") as f:
    f.write(text)
