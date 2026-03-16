with open('src/runtime/stdlib.py', 'r') as f:
    content = f.read()

content = content.replace(
    'print(f"\\n\\033[1;35m[Nexa HITL] Human input required: {prompt}\\033[0m")',
    'print(f"\\n\\033[1;35m[Nexa HITL] Human input required: {prompt}\\033[0m", flush=True)'
)

with open('src/runtime/stdlib.py', 'w') as f:
    f.write(content)
