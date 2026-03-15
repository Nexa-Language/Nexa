with open("src/code_generator.py", "r") as f:
    text = f.read()

text = text.replace(
    'return f\'"{expr["value"]}"\'        elif ex_type == "SecretCall":\n            return f\'nexa_secrets.get("{expr["key"]}")\'        elif ex_type == "Identifier":',
    'return f\'"{expr["value"]}"\'\n        elif ex_type == "SecretCall":\n            return f\'nexa_secrets.get("{expr["key"]}")\'\n        elif ex_type == "Identifier":'
)

with open("src/code_generator.py", "w") as f:
    f.write(text)
