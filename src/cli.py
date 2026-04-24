# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================
import sys
import os
import argparse
import subprocess
import shutil
import time
from pathlib import Path

# Add src dir to sys.path to allow imports when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Version info — 从单一版本源读取
from src._version import NEXA_VERSION

from nexa_parser import parse
from ast_transformer import NexaTransformer
from code_generator import CodeGenerator
from runtime.inspector import inspect_nexa_file, format_inspect_json, format_inspect_text
from runtime.validator import validate_nexa_file, format_error_json, format_error_human
# P1-4: Built-In HTTP Server
from runtime.http_server import parse_server_block, format_routes_text, format_routes_json

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

def serve_file(nx_file_path: str, port: int = None):
    """
    P1-4: Build and run a .nx file as an HTTP server.
    
    Similar to run_file but explicitly for server mode.
    """
    generated_py_path = build_file(nx_file_path)
    
    if port:
        print(f"🚀 Starting Nexa HTTP Server on port {port} from {nx_file_path}")
    else:
        print(f"🚀 Starting Nexa HTTP Server from {nx_file_path}")
    
    print("="*50)
    
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if port:
            env['NEXA_PORT'] = str(port)
        process = subprocess.Popen(
            [sys.executable, generated_py_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            env=env
        )
        process.communicate()
        sys.exit(process.returncode)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")
        sys.exit(130)

def routes_file(nx_file_path: str, json_output: bool = False):
    """
    P1-4: List all HTTP routes from a .nx file.
    
    Parses the file and extracts ServerDeclaration route info.
    """
    input_path = Path(nx_file_path)
    if not input_path.exists():
        print(f"❌ Error: File '{nx_file_path}' does not exist.")
        sys.exit(1)
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        tree = parse(source_code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        # Find ServerDeclaration nodes
        servers = []
        for node in ast.get("body", []):
            if isinstance(node, dict) and node.get("type") == "ServerDeclaration":
                servers.append(node)
        
        if not servers:
            print("ℹ️ No server declarations found in this file.")
            return
        
        for server in servers:
            port = server.get("port", 8080)
            server_obj = parse_server_block(server)
            
            if json_output:
                print(format_routes_json(server_obj.state))
            else:
                print(f"\n📡 HTTP Server on port {port}:")
                print(format_routes_text(server_obj.state))
                print()
    
    except Exception as e:
        print(f"❌ Error parsing file: {e}")
        sys.exit(1)

def clear_cache():
    """
    Clear the Nexa cache directory.
    """
    cache_dir = Path(".nexa_cache")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("✅ Cache cleared successfully.")
    else:
        print("ℹ️ No cache directory found.")

def show_version():
    """
    Display the Nexa version.
    """
    print(f"Nexa v{NEXA_VERSION}")

def intent_check(nx_file_path: str, intent_file_path: str = None, verbose: bool = False):
    """
    执行 intent check — 验证代码是否符合 intent 定义。
    
    Usage: nexa intent check <file.nx> [--intent <intent_file>] [--verbose]
    """
    from src.runtime.intent import IntentRunner
    
    runner = IntentRunner(verbose=verbose)
    results = runner.check(nx_file_path, intent_file_path=intent_file_path)
    
    # 根据结果设置退出码
    all_passed = all(fr.passed for fr in results)
    if not all_passed:
        sys.exit(1)


def intent_coverage(nx_file_path: str, intent_file_path: str = None):
    """
    显示 intent coverage — 特性覆盖率报告。
    
    Usage: nexa intent coverage <file.nx> [--intent <intent_file>]
    """
    from src.runtime.intent import IntentRunner
    
    runner = IntentRunner()
    report = runner.coverage(nx_file_path, intent_file_path=intent_file_path)
    
    # 输出覆盖率百分比
    if report.coverage_percentage < 100:
        print(f"\n💡 Tip: Add @implements annotations to your .nx file to increase coverage")


def inspect_file(nx_file_path: str, format_type: str = "json"):
    """
    Inspect a .nx file and output its structural description.

    Usage: nexa inspect <file.nx> [--format json|text]
    """
    result = inspect_nexa_file(nx_file_path)

    if format_type == "json":
        print(format_inspect_json(result))
    else:
        print(format_inspect_text(result))

def validate_file(nx_file_path: str, json_output: bool = False, quiet: bool = False):
    """
    Validate a .nx file and output validation results.

    Usage: nexa validate <file.nx> [--json] [--quiet]
    """
    result = validate_nexa_file(nx_file_path)

    if json_output:
        print(format_error_json(result))
    else:
        print(format_error_human(result, quiet=quiet))

    # Exit with error code if validation failed
    if not result.get("valid", False):
        sys.exit(1)

def lint_file(nx_file_path: str, strict: bool = False, warn_untyped: bool = False):
    """
    Run the Nexa type system linter on a .nx file.
    
    v1.1: 渐进式类型系统 — lint 检查
    
    Usage:
        nexa lint app.nx              # default: 只检查有类型标注的代码
        nexa lint app.nx --strict     # strict: 缺失类型标注=lint错误
        nexa lint app.nx --warn-untyped  # warn: 缺失类型标注发出警告
    """
    from src.runtime.type_system import TypeChecker, LintMode, TypeMode, get_type_mode, get_lint_mode
    
    input_path = Path(nx_file_path)
    if not input_path.exists():
        print(f"❌ Error: File '{nx_file_path}' does not exist.")
        sys.exit(1)
    
    # Determine lint mode from CLI flags
    lint_mode_str = None
    if strict:
        lint_mode_str = "strict"
    elif warn_untyped:
        lint_mode_str = "warn"
    
    lint_mode = get_lint_mode(cli_override=lint_mode_str)
    type_mode = get_type_mode()
    
    print(f"🔍 Linting {nx_file_path} (lint_mode={lint_mode.value}, type_mode={type_mode.value}) ...\n" + "="*50)
    
    try:
        # Parse the file
        with open(input_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        tree = parse(source_code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        # Create type checker with specified modes
        checker = TypeChecker(type_mode=type_mode, lint_mode=lint_mode)
        
        # Run lint type check
        lint_result = checker.lint_check_annotations(ast)
        
        # Output results
        if lint_result.passed and not lint_result.warnings:
            print("✅ All type annotations are complete and correct.")
        else:
            if lint_result.warnings:
                for warning in lint_result.warnings:
                    print(f"⚠️ Warning: {warning.message}")
                    if warning.context:
                        for k, v in warning.context.items():
                            print(f"   {k}: {v}")
            
            if lint_result.violations:
                for violation in lint_result.violations:
                    print(f"❌ Error: {violation}")
                    if violation.context:
                        for k, v in violation.context.items():
                            print(f"   {k}: {v}")
        
        print("="*50)
        
        if lint_result.violations:
            # strict 模式下有错误 → 非零退出码
            print(f"\n❌ Lint failed with {len(lint_result.violations)} errors.")
            sys.exit(1)
        elif lint_result.warnings:
            print(f"\n⚠️ Lint passed with {len(lint_result.warnings)} warnings.")
        else:
            print(f"\n✅ Lint passed successfully.")
    
    except Exception as e:
        print(f"❌ Lint failed: {e}")
        sys.exit(1)


def handle_jobs_command(args):
    """P1-3: Handle 'nexa jobs' subcommands"""
    from src.runtime.jobs import JobQueue, format_job_status, format_jobs_table
    
    # Ensure JobQueue is configured (default: memory)
    JobQueue._ensure_configured()
    
    if args.jobs_command == "list":
        status_filter = args.status
        limit = args.limit
        records = JobQueue.list_jobs(status=status_filter, limit=limit)
        print(format_jobs_table(records))
    
    elif args.jobs_command == "status":
        job_id = args.job_id
        record = JobQueue.status(job_id)
        if record:
            print(format_job_status(record))
        else:
            print(f"❌ Job '{job_id}' not found.")
    
    elif args.jobs_command == "cancel":
        job_id = args.job_id
        success = JobQueue.cancel(job_id)
        if success:
            print(f"✅ Job '{job_id}' cancelled successfully.")
        else:
            print(f"❌ Failed to cancel job '{job_id}'. It may not be in a cancellable state.")
    
    elif args.jobs_command == "retry":
        job_id = args.job_id
        success = JobQueue.retry(job_id)
        if success:
            print(f"✅ Job '{job_id}' retried successfully. It has been moved back to the pending queue.")
        else:
            print(f"❌ Failed to retry job '{job_id}'. It may not be in the dead letter queue.")
    
    elif args.jobs_command == "clear":
        count = JobQueue.clear_completed()
        print(f"✅ Cleared {count} completed/expired/cancelled jobs.")
    
    else:
        print("Usage: nexa jobs list|status|cancel|retry|clear")


def handle_workers_command(args):
    """P1-3: Handle 'nexa workers' subcommands"""
    from src.runtime.jobs import JobQueue, JobWorker, format_jobs_table
    
    if args.workers_command == "start":
        # Build the .nx file first to register job specs
        nx_file = args.file
        generated_py_path = build_file(nx_file)
        
        # Import the generated module to register JobSpecs
        import importlib.util
        dir_path = os.path.dirname(os.path.abspath(generated_py_path))
        if dir_path not in sys.path:
            sys.path.insert(0, dir_path)
        
        module_name = os.path.basename(generated_py_path)[:-3]
        spec = importlib.util.spec_from_file_location(module_name, generated_py_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        # Configure JobQueue
        JobQueue._ensure_configured()
        
        # Execute the module to register JobSpecs (but don't run flows)
        try:
            # Only execute registration parts, not the main flow
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"⚠️ Warning: Module execution had errors (JobSpecs should still be registered): {e}")
        
        # Start worker
        worker = JobWorker(
            worker_id=args.worker_id,
            poll_interval=args.poll_interval,
        )
        print(f"🚀 Starting worker '{args.worker_id}' with poll interval {args.poll_interval}s...")
        print(f"📋 Registered jobs: {[s.name for s in JobQueue._backend.__class__ == MemoryBackend and [] or []]}")
        
        # Print registered specs
        from src.runtime.jobs import JobRegistry
        specs = JobRegistry.list_specs()
        print(f"📋 Registered JobSpecs:")
        for s in specs:
            print(f"   - {s.name} on {s.queue} (priority={s.priority.name}, retry={s.retry_count})")
        
        worker.start(daemon=False)
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⚠️ Stopping worker...")
            worker.stop()
            print("✅ Worker stopped.")
    
    elif args.workers_command == "status":
        # Show queue statistics
        JobQueue._ensure_configured()
        stats = JobQueue.stats()
        print("📊 Job Queue Statistics:")
        for status, count in stats.items():
            print(f"   {status}: {count}")
        
        # Show registered specs
        from src.runtime.jobs import JobRegistry
        specs = JobRegistry.list_specs()
        if specs:
            print("\n📋 Registered JobSpecs:")
            for s in specs:
                print(f"   - {s.name} on {s.queue} (priority={s.priority.name}, retry={s.retry_count})")
        else:
            print("\n📋 No JobSpecs registered.")
    
    else:
        print("Usage: nexa workers start <file.nx>|status")


def main():
    parser = argparse.ArgumentParser(description=f"Nexa Language CLI {NEXA_VERSION}")
    parser.add_argument("-v", "--version", action="store_true", help="Show version and exit")
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
    
    # Inspect command (Agent-Native Tooling)
    inspect_parser = subparsers.add_parser("inspect", help="Inspect .nx file structure (Agent-Native Tooling)")
    inspect_parser.add_argument("file", help="Path to the .nx source file")
    inspect_parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format (default: json)")
    
    # Validate command (Agent-Native Tooling)
    validate_parser = subparsers.add_parser("validate", help="Validate .nx file syntax and semantics")
    validate_parser.add_argument("file", help="Path to the .nx source file")
    validate_parser.add_argument("--json", action="store_true", help="Output in machine-readable JSON format")
    validate_parser.add_argument("--quiet", action="store_true", help="Only output errors, no success messages")
    
    # v1.1: Lint command (渐进式类型系统)
    lint_parser = subparsers.add_parser("lint", help="Run type system linter on a .nx file (Gradual Type System)")
    lint_parser.add_argument("file", help="Path to the .nx source file")
    lint_parser.add_argument("--strict", action="store_true", help="Strict lint mode: missing type annotations = error (non-zero exit)")
    lint_parser.add_argument("--warn-untyped", action="store_true", help="Warn lint mode: warn about missing type annotations")
    
    # Intent command (IDD - Intent-Driven Development)
    intent_parser = subparsers.add_parser("intent", help="Intent-Driven Development commands")
    intent_subparsers = intent_parser.add_subparsers(dest="intent_command", help="Intent commands")
    
    # intent check
    intent_check_parser = intent_subparsers.add_parser("check", help="Verify code matches intent definitions")
    intent_check_parser.add_argument("file", help="Path to the .nx source file")
    intent_check_parser.add_argument("--intent", help="Path to .nxintent file (auto-detected if omitted)", default=None)
    intent_check_parser.add_argument("--verbose", "-V", action="store_true", help="Show detailed check results")
    
    # intent coverage
    intent_coverage_parser = intent_subparsers.add_parser("coverage", help="Show feature coverage report")
    intent_coverage_parser.add_argument("file", help="Path to the .nx source file")
    intent_coverage_parser.add_argument("--intent", help="Path to .nxintent file (auto-detected if omitted)", default=None)
    
    # P1-3: Jobs command (后台任务系统)
    jobs_parser = subparsers.add_parser("jobs", help="Background Job System commands")
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", help="Jobs commands")
    
    # jobs list
    jobs_list_parser = jobs_subparsers.add_parser("list", help="List all jobs")
    jobs_list_parser.add_argument("--status", choices=["pending", "running", "completed", "failed", "dead", "cancelled", "expired"], default=None, help="Filter by status")
    jobs_list_parser.add_argument("--limit", type=int, default=50, help="Maximum number of jobs to list")
    
    # jobs status
    jobs_status_parser = jobs_subparsers.add_parser("status", help="Show job status")
    jobs_status_parser.add_argument("job_id", help="Job ID to check")
    
    # jobs cancel
    jobs_cancel_parser = jobs_subparsers.add_parser("cancel", help="Cancel a job")
    jobs_cancel_parser.add_argument("job_id", help="Job ID to cancel")
    
    # jobs retry
    jobs_retry_parser = jobs_subparsers.add_parser("retry", help="Retry a dead letter job")
    jobs_retry_parser.add_argument("job_id", help="Job ID to retry")
    
    # jobs clear
    jobs_clear_parser = jobs_subparsers.add_parser("clear", help="Clear completed/expired/cancelled jobs")
    
    # P1-4: Serve command (Built-In HTTP Server)
    serve_parser = subparsers.add_parser("serve", help="Start an HTTP server from a .nx file")
    serve_parser.add_argument("file", help="Path to the .nx source file with server declarations")
    serve_parser.add_argument("--port", type=int, default=None, help="Override server port")

    # P1-4: Routes command (Built-In HTTP Server)
    routes_parser = subparsers.add_parser("routes", help="List all HTTP routes from a .nx file")
    routes_parser.add_argument("file", help="Path to the .nx source file")
    routes_parser.add_argument("--json", action="store_true", help="Output routes as JSON")

    # P1-3: Workers command
    workers_parser = subparsers.add_parser("workers", help="Job Worker commands")
    workers_subparsers = workers_parser.add_subparsers(dest="workers_command", help="Workers commands")
    
    # workers start
    workers_start_parser = workers_subparsers.add_parser("start", help="Start a job worker")
    workers_start_parser.add_argument("file", help="Path to the .nx source file with job definitions")
    workers_start_parser.add_argument("--worker-id", default="worker-1", help="Worker identifier")
    workers_start_parser.add_argument("--poll-interval", type=float, default=1.0, help="Poll interval in seconds")
    
    # workers status
    workers_status_parser = workers_subparsers.add_parser("status", help="Show worker and queue status")
    
    # Cache command
    cache_parser = subparsers.add_parser("cache", help="Manage cache")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache commands")
    clear_parser = cache_subparsers.add_parser("clear", help="Clear the cache directory")
    
    args = parser.parse_args()
    
    # Handle --version flag
    if args.version:
        show_version()
        return
    
    if args.command == "build":
        build_file(args.file)
    elif args.command == "run":
        run_file(args.file)
    elif args.command == "test":
        test_file(args.file)
    elif args.command == "inspect":
        inspect_file(args.file, format_type=args.format)
    elif args.command == "validate":
        validate_file(args.file, json_output=args.json, quiet=args.quiet)
    elif args.command == "lint":
        lint_file(args.file, strict=args.strict, warn_untyped=args.warn_untyped)
    elif args.command == "intent":
        if args.intent_command == "check":
            intent_check(args.file, intent_file_path=args.intent, verbose=args.verbose)
        elif args.intent_command == "coverage":
            intent_coverage(args.file, intent_file_path=args.intent)
        else:
            intent_parser.print_help()
    elif args.command == "serve":
        serve_file(args.file, port=args.port)
    elif args.command == "routes":
        routes_file(args.file, json_output=args.json)
    elif args.command == "jobs":
        handle_jobs_command(args)
    elif args.command == "workers":
        handle_workers_command(args)
    elif args.command == "cache":
        if args.cache_command == "clear":
            clear_cache()
        else:
            print("Usage: nexa cache clear")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
