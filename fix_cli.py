with open("src/cli.py", "r") as f:
    content = f.read()

import_os = "import sys\nimport os\n"

old_run = """        # Using sys.executable to run with the current python environment
        process = subprocess.Popen(
            [sys.executable, generated_py_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True
        )"""

new_run = """        # Using sys.executable to run with the current python environment
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        process = subprocess.Popen(
            [sys.executable, generated_py_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            env=env
        )"""

content = content.replace(old_run, new_run)

with open("src/cli.py", "w") as f:
    f.write(content)
