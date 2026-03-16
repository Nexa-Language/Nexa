import re

with open('src/code_generator.py', 'r') as f:
    content = f.read()

# Add pydantic import
if "import pydantic" not in content:
    content = content.replace("import json", "import json\nimport pydantic")

# Add protocols list
content = content.replace("self.tools = []", "self.protocols = []\n        self.tools = []")
content = content.replace('elif node["type"] == "ToolDeclaration":', 'elif node["type"] == "ProtocolDeclaration":\n                self.protocols.append(node)\n            elif node["type"] == "ToolDeclaration":')

# Add _generate_protocols
generate_protocols = """    def _generate_protocols(self):
        for proto in self.protocols:
            name = proto["name"]
            self.code.append(f'class {name}(pydantic.BaseModel):')
            for f_name, f_type in proto["fields"].items():
                py_type = "str"
                if f_type == "int": py_type = "int"
                if f_type == "float": py_type = "float"
                if f_type == "bool": py_type = "bool"
                self.code.append(f'    {f_name}: {py_type}')
            self.code.append('')
"""
content = "".join([content.split("    def _generate_tools(self):")[0], generate_protocols, "\n    def _generate_tools(self):", content.split("    def _generate_tools(self):")[1]])

content = content.replace("self._generate_tools()", "self._generate_protocols()\n        self._generate_tools()")

# Adjust _generate_agents
agent_gen_old = """            self.code.append(f'{name} = NexaAgent(')
            self.code.append(f'    name="{name}",')
            self.code.append(f'    prompt="{prompt}",')
            self.code.append(f'    model="{model}",')
            self.code.append(f'    role="{role}",')
            self.code.append(f'    memory_scope="{memory_scope}",')
            self.code.append(f'    tools=[{tool_refs}]')
            self.code.append(f')\\n')"""

agent_gen_new = """            implements = agent.get("implements")
            max_tokens = agent.get("max_tokens")
            
            self.code.append(f'{name} = NexaAgent(')
            self.code.append(f'    name="{name}",')
            self.code.append(f'    prompt="{prompt}",')
            self.code.append(f'    model="{model}",')
            self.code.append(f'    role="{role}",')
            self.code.append(f'    memory_scope="{memory_scope}",')
            if implements:
                self.code.append(f'    protocol={implements},')
            if max_tokens:
                self.code.append(f'    max_tokens={max_tokens},')
            self.code.append(f'    tools=[{tool_refs}]')
            self.code.append(f')\\n')"""
content = content.replace(agent_gen_old, agent_gen_new)

with open('src/code_generator.py', 'w') as f:
    f.write(content)
