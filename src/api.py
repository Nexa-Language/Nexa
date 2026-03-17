import sys
import os
import io
import contextlib
import importlib.util
from .nexa_parser import parse
from .ast_transformer import NexaTransformer
from .code_generator import CodeGenerator

class NexaRuntime:
    @staticmethod
    def run_script(file_path: str, inputs: dict) -> dict:
        # Load and verify .nx
        with open(file_path, "r", encoding="utf-8") as f:
            src = f.read()
        
        # 1. Parse
        tree = parse(src)
        
        # 2. Transform AST
        transformer = NexaTransformer()
        ast = transformer.transform(tree)

        # 3. Generate Code
        codegen = CodeGenerator(ast)
        codegen.source_path = file_path
        py_code = codegen.generate()
        
        # Create a temporary py file in .nexa_build directory
        build_dir = os.path.join(os.path.dirname(file_path), ".nexa_build")
        os.makedirs(build_dir, exist_ok=True)
        py_path = os.path.join(build_dir, os.path.basename(file_path).replace(".nx", ".py"))
        
        with open(py_path, 'w', encoding='utf-8') as f:
            f.write(py_code)

        # 4. Use importlib to load dynamically
        module_name = "nexa_ephemeral_" + os.path.basename(file_path).replace(".nx", "")
        spec = importlib.util.spec_from_file_location(module_name, py_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        f_out = io.StringIO()
        with contextlib.redirect_stdout(f_out):
            spec.loader.exec_module(module)
            
            # Inject inputs into the module
            for k, v in inputs.items():
                setattr(module, k, v)
                
            result = None
            if hasattr(module, 'flow_main'):
                result = module.flow_main()
                
        output = f_out.getvalue()
        
        return {
            "result": result,
            "stdout": output
        }
