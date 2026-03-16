from src.nexa_parser import parse

code = """
@limit(max_tokens=600)
agent Coder {
    prompt: "Write a short Python implementation of quicksort.",
    model: "minimax/minimax-m2.5"
}
"""
tree = parse(code)
print(tree.pretty())
