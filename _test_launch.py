#!/usr/bin/env python3
"""
逐个测试所有中文游戏项目是否能正常初始化并打开窗口。
对每个项目使用独立子进程，避免模块缓存污染。
"""
import os
import sys
import subprocess
import time

BASE = r"C:\Users\13122\Desktop\stay\hell below\ch"

PROJECTS = sorted([
    d for d in os.listdir(BASE)
    if os.path.isdir(os.path.join(BASE, d)) and not d.startswith(".")
])

PYTHON = sys.executable


def test_project_subprocess(proj_dir: str) -> dict:
    """Run a project's main.py as a subprocess and check if it starts."""
    result = {"ok": False, "error": ""}
    main_py = os.path.join(proj_dir, "main.py")

    if not os.path.exists(main_py):
        result["error"] = "no main.py"
        return result

    try:
        proc = subprocess.Popen(
            [PYTHON, main_py],
            cwd=proj_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        # Wait a short time for startup
        time.sleep(2.0)

        # Check if still running
        poll = proc.poll()
        if poll is None:
            # Still running — good sign, terminate it
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            result["ok"] = True
            result["error"] = "启动成功，正常运行"
        else:
            # Exited with error
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            stdout = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""

            error_msg = (stderr + stdout).strip()
            if error_msg:
                lines = [l for l in error_msg.split("\n") if "Error" in l or "error" in l or "Traceback" in l]
                if lines:
                    error_msg = "\n".join(lines[-5:])
                else:
                    error_msg = error_msg[-500:]

            result["error"] = f"启动后崩溃 (exit code {poll}): {error_msg[:500]}"

    except Exception as e:
        result["error"] = f"启动异常: {e}"

    return result


# ── 输出报告 ──
print("=" * 60)
print(f"  游戏启动测试报告  ({len(PROJECTS)} 个项目)")
print("=" * 60)

ok_count = 0
results = []

for proj in PROJECTS:
    proj_dir = os.path.join(BASE, proj)
    r = test_project_subprocess(proj_dir)
    results.append((proj, r))
    icon = "✅" if r["ok"] else "❌"
    print(f"  {icon} {proj}")
    if r["error"]:
        print(f"       → {r['error'][:120]}")
    if r["ok"]:
        ok_count += 1

print()
print(f"结果：{ok_count}/{len(PROJECTS)} 个项目可以正常启动")
if ok_count < len(PROJECTS):
    print("❌ 有项目无法正常启动，请查看上方错误信息")
else:
    print("✅ 所有项目均可正常启动！")
print("=" * 60)
