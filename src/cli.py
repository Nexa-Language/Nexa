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
    
    print(f"🚀 Running {generated_py_path} ...\\n" + "="*50)
    
    try:
        # Using sys.executable to run with the current python environment
        process = subprocess.Popen(
            [sys.executable, generated_py_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True
        )
        process.communicate()
        
        print("="*50 + f"\\n✅ Execution Finished (Exit code: {process.returncode})")
        sys.exit(process.returncode)
    except KeyboardInterrupt:
        print("\\n⚠️ Execution interrupted by user.")
        sys.exit(130)

def main():
    parser = argparse.ArgumentParser(description="Nexa Language CLI v0.1")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Compile a .nx file to .py")
    build_parser.add_argument("file", help="Path to the .nx source file")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Compile and execute a .nx file")
    run_parser.add_argument("file", help="Path to the .nx source file")
    
    args = parser.parse_args()
    
    if args.command == "build":
        build_file(args.file)
    elif args.command == "run":
        run_file(args.file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
