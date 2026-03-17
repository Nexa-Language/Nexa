from src.nexa_parser import get_parser
parser = get_parser()
tree = parser.parse('agent Test uses mcp:"http://test" { }\n')
print(tree.pretty())
