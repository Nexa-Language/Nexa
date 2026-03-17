import sys
import os
import argparse
import subprocess
from pathlib import Path

# Add src dir to sys.path to allow imports when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nexa_parser import parse
from ast_transformer import NexaTransformer
from code_generator import CodeGenerator

def build_file(nx_file_path: str) -> str:
    """
    Build a .nx file and return the path to the generated .py file.
    """
    input_path = Path(nx_file_path)
    if not input_path.exists():
        print(f"❌ Error: File '{nx_file_path}' does not exist.")
        sys.exit(1)
        
    if input_path.suffix != '.nx':
        print(f"⚠️ Warning: File '{nx_file_path}' does not have a .nx extension.")

    output_path = input_path.with_suffix('.py')
    
    print(f"🔨 Compiling {input_path} ...")
    try:
        # Read source
        with open(input_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Parse and Transform
        tree = parse(source_code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)

        # Handle nxlib includes
        if "includes" in ast:
            for include_stmt in ast["includes"]:
                inc_rel_path = include_stmt["path"]
                inc_full_path = input_path.parent / inc_rel_path
                if not inc_full_path.exists():
                    print(f"❌ Error: Included file '{inc_rel_path}' does not exist at '{inc_full_path}'.")
                    sys.exit(1)
                
                with open(inc_full_path, 'r', encoding='utf-8') as inc_f:
                    inc_code = inc_f.read()
                
                inc_tree = parse(inc_code)
                inc_ast = transformer.transform(inc_tree)
                
                # Merge included bodies to the top of AST
                ast["body"] = inc_ast["body"] + ast["body"]

        # Generate Code
        generator = CodeGenerator(ast)
        python_code = generator.generate()

        # Write output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(python_code)
            
        print(f"✨ Success! Built target: {output_path}")
        return str(output_path)
        
    except Exception as e:
        print(f"❌ Compilation failed: {e}")
        sys.exit(1)

def run_file(nx_file_path: str):
    """
    Build and execute a .nx file.
    """
    generated_py_path = build_file(nx_file_path)
    
    print(f"🚀 Running {generated_py_path} ...\n" + "="*50)
    
    try:
        # Using sys.executable to run with the current python environment
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        process = subprocess.Popen(
            [sys.executable, generated_py_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            env=env
        )
        process.communicate()
        
        print("="*50 + f"\n✅ Execution Finished (Exit code: {process.returncode})")
        sys.exit(process.returncode)
    except KeyboardInterrupt:
        print("\n⚠️ Execution interrupted by user.")
        sys.exit(130)

def test_file(nx_file_path: str):
    """
    Build a .nx file and execute all its test functions.
    """
    generated_py_path = build_file(nx_file_path)
    
    print(f"🧪 Testing {nx_file_path} ...\n" + "="*50)
    
    import importlib.util
    import sys
    
    # Needs to be able to import from the generated file root
    dir_path = os.path.dirname(os.path.abspath(generated_py_path))
    if dir_path not in sys.path:
        sys.path.insert(0, dir_path)
        
    module_name = os.path.basename(generated_py_path)[:-3]
    
    # Load module dynamically
    spec = importlib.util.spec_from_file_location(module_name, generated_py_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"❌ Failed to load module for testing: {e}")
        sys.exit(1)
        
    # Find test functions
    test_functions = [name for name in dir(module) if name.startswith('test_') and callable(getattr(module, name))]
    
    if not test_functions:
        print("⚠️ No test functions found.")
        return
        
    passed = 0
    failed = 0
    
    for test_name in test_functions:
        test_fn = getattr(module, test_name)
        try:
            test_fn()
            print(f"\033[92m[PASS]\033[0m {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"\033[91m[FAIL]\033[0m {test_name}")
            print(f"      AssertionError: {e}")
            failed += 1
        except Exception as e:
            print(f"\033[91m[ERROR]\033[0m {test_name}")
            print(f"      {type(e).__name__}: {e}")
            failed += 1
            
    print("="*50)
    if failed == 0:
        print(f"\033[92m🎉 All {passed} tests passed!\033[0m")
        sys.exit(0)
    else:
        print(f"\033[91m💥 {failed} failed, {passed} passed.\033[0m")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Nexa Language CLI v0.9")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Compile a .nx file to .py")
    build_parser.add_argument("file", help="Path to the .nx source file")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Compile and execute a .nx file")
    run_parser.add_argument("file", help="Path to the .nx source file")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Compile and run tests in a .nx file")
    test_parser.add_argument("file", help="Path to the .nx source file")
    
    args = parser.parse_args()
    
    if args.command == "build":
        build_file(args.file)
    elif args.command == "run":
        run_file(args.file)
    elif args.command == "test":
        test_file(args.file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
