import sys
import os
import subprocess

cli_cmd = ["python3", "-m", "src.cli", "run", "examples/09_cognitive_architecture.nx"]
process = subprocess.Popen(
    cli_cmd,
    env=dict(os.environ, PYTHONPATH=os.getcwd()),
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

for line in iter(process.stdout.readline, ''):
    sys.stdout.write(line)
    if "Human input required:" in line:
        print("[Driver] Detected HITL. Simulating input: 'LGTM! Commit the code.'")
        process.stdin.write("LGTM! Commit the code.\n")
        process.stdin.flush()

process.wait()
sys.exit(process.returncode)
