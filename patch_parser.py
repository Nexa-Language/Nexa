import re

with open('src/nexa_parser.py', 'r') as f:
    content = f.read()

content = content.replace("?script_stmt: tool_decl | agent_decl | flow_decl", "?script_stmt: tool_decl | agent_decl | flow_decl | protocol_decl")

protocol_rules = """
protocol_decl: "protocol" IDENTIFIER "{" protocol_body* "}"
protocol_body: IDENTIFIER ":" STRING_LITERAL ","?
"""

content = content.replace('tool_body: "description" ":" STRING_LITERAL "," "parameters" ":" json_object', 'tool_body: "description" ":" STRING_LITERAL "," "parameters" ":" json_object\n' + protocol_rules)

agent_rule_old = 'agent_decl: "agent" IDENTIFIER ["->" return_type] ["uses" use_identifier_list] "{" agent_property* "}"'
agent_rule_newest = 'agent_decl: ["@" "limit" "(" "max_tokens" "=" INT ")"] "agent" IDENTIFIER ["->" return_type] ["uses" use_identifier_list] ["implements" IDENTIFIER] "{" agent_property* "}"'
content = content.replace(agent_rule_old, agent_rule_newest)

if "%import common.INT" not in content:
    content = content.replace("%import common.WS", "%import common.INT\n%import common.WS")

with open('src/nexa_parser.py', 'w') as f:
    f.write(content)
