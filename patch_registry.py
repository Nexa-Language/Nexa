with open('src/runtime/tools_registry.py', 'r') as f:
    c = f.read()

c = c.replace('"std_time_now, std_ask_human": std_time_now', '"std_time_now": std_time_now,\n    "std_ask_human": std_ask_human')

if "std_ask_human" not in c.split("LOCAL_TOOLS =")[0]:
    c = c.replace("std_time_now", "std_time_now, std_ask_human")

with open('src/runtime/tools_registry.py', 'w') as f:
    f.write(c)

