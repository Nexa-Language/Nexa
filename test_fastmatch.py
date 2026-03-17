from src.nexa_parser import get_parser
parser = get_parser()
tree = parser.parse('flow main { semantic_if "Test" against msg { print(msg); } }\n')
print(tree.pretty())
