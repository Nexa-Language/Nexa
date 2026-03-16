with open('src/code_generator.py', 'r') as f:
    content = f.read()

content = content.replace(
'''        for node in self.ast.get("body", []):
            if node["type"] == "ToolDeclaration":
                self.tools.append(node)''',
'''        for node in self.ast.get("body", []):
            if node["type"] == "ProtocolDeclaration":
                self.protocols.append(node)
            elif node["type"] == "ToolDeclaration":
                self.tools.append(node)'''
)

with open('src/code_generator.py', 'w') as f:
    f.write(content)
