from src.nexa_parser import parse
from src.ast_transformer import NexaTransformer

code = """
protocol ReviewResult {
    score: "int",
    summary: "string"
}

@limit(max_tokens=500)
agent Coder implements ReviewResult {
    prompt: "Test"
}
"""
tree = parse(code)
transformer = NexaTransformer()
ast = transformer.transform(tree)

import json
print(json.dumps(ast, indent=2))
