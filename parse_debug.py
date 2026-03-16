from src.nexa_parser import parse
from src.ast_transformer import NexaTransformer

code = """
agent Reviewer implements ReviewResult {
    prompt: "Review the provided code. Give a score from 1 to 10 and a brief summary. Return as JSON.",
    model: "deepseek/deepseek-chat"
}
"""
tree = parse(code)
print(tree.pretty())
