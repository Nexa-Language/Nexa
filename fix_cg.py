with open("src/code_generator.py", "r") as f:
    original = f.read()

import_str = "from src.runtime.stdlib import STD_TOOLS_SCHEMA"
new_import_str = "from src.runtime.stdlib import STD_TOOLS_SCHEMA, STD_NAMESPACE_MAP"
if import_str in original and new_import_str not in original:
    original = original.replace(import_str, new_import_str)

old_loop = """            tool_refs_list = []
            for t in uses:
                if t.startswith("std."):
                    tool_refs_list.append(f"STD_TOOLS_SCHEMA['{t.replace('std.', 'std_')}_execute']")
                else:
                    tool_refs_list.append(f"__tool_{t}_schema")
            tool_refs = ", ".join(tool_refs_list)"""

new_loop = """            tool_refs_list = []
            for t in uses:
                if t.startswith("std."):
                    if t in STD_NAMESPACE_MAP:
                        for fn_name in STD_NAMESPACE_MAP[t]:
                            tool_refs_list.append(f"STD_TOOLS_SCHEMA['{fn_name}']")
                    else:
                        print(f"⚠️ Warning: Unknown standard namespace '{t}'")
                else:
                    tool_refs_list.append(f"__tool_{t}_schema")
            tool_refs = ", ".join(tool_refs_list)"""

original = original.replace(old_loop, new_loop)

# I should also make sure code_generator itself imports STD_NAMESPACE_MAP in its own environment
# Wait, it doesn't need to be in BOILERPLATE for the generated code, 
# although it IS in BOILERPLATE currently:
# from src.runtime.stdlib import STD_TOOLS_SCHEMA
# Let's add STD_NAMESPACE_MAP to code_generator's OWN imports at the top.

top_import = "import json"
if "from src.runtime.stdlib import STD_NAMESPACE_MAP" not in original:
    original = original.replace(top_import, "import json\nfrom src.runtime.stdlib import STD_NAMESPACE_MAP")

with open("src/code_generator.py", "w") as f:
    f.write(original)
