"""Quick test: launch one game and report result."""
import os, subprocess, sys, time

main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NathanWinters_CN", "main.py")
cwd = os.path.dirname(main_py)

proc = subprocess.Popen(
    [sys.executable, main_py],
    cwd=cwd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

time.sleep(2.0)
poll = proc.poll()

if poll is None:
    # Still running — success!
    proc.terminate()
    proc.wait(timeout=3)
    print("SUCCESS: Game launched and ran for 2 seconds")
else:
    stderr = proc.stderr.read().decode("utf-8", errors="replace")
    stdout = proc.stdout.read().decode("utf-8", errors="replace")
    print(f"FAILED (exit code {poll})")
    print("STDERR:")
    print(stderr)
    print("STDOUT:")
    print(stdout)
