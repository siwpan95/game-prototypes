"""Test script — check all 11 Chinese games for launchability."""

from __future__ import annotations

import os
import sys
import subprocess
import pathlib
import time

# Add project root to path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.game_registry import GAMES
from src.core.constants import GAMES_BASE_ZH

RESULTS: list[tuple[str, str, str, str]] = []  # (game_id, title, status, detail)


def check_game_quick(game) -> tuple[bool, str]:
    """Quick check: file exists + syntax valid + basic import."""
    main_file = game.main_file_zh

    # 1. File existence
    if not game.exists_zh():
        return False, f"文件不存在: {main_file}"

    # 2. Syntax check (compile)
    try:
        source = main_file.read_text(encoding="utf-8")
        compile(source, str(main_file), "exec")
    except SyntaxError as e:
        return False, f"语法错误: {e}"
    except Exception as e:
        return False, f"读取失败: {e}"

    return True, "语法检查通过"


def launch_and_quick_test(game) -> tuple[bool, str]:
    """Launch game as subprocess and check if it starts without immediate crash."""
    main_file = str(game.main_file_zh)
    game_dir = str(game.game_dir_zh)

    python_exe = sys.executable

    try:
        proc = subprocess.Popen(
            [python_exe, main_file],
            cwd=game_dir,
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
            return True, "启动成功，正常运行"
        else:
            # Exited with error
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            stdout = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""

            # Combine errors
            error_msg = (stderr + stdout).strip()
            if error_msg:
                # Try to extract the most relevant error line
                lines = [l for l in error_msg.split("\n") if "Error" in l or "error" in l or "Traceback" in l]
                if lines:
                    error_msg = "\n".join(lines[-5:])  # Last 5 error lines
                else:
                    error_msg = error_msg[-500:]  # Last 500 chars

            return False, f"启动后崩溃 (exit code {poll}): {error_msg[:500]}"

    except Exception as e:
        return False, f"启动异常: {e}"


def print_separator(char: str = "=", width: int = 70) -> None:
    print(char * width)


def main() -> None:
    print_separator()
    print("  地狱之下 — 中文版游戏启动测试")
    print_separator()

    total = len(GAMES)
    passed_quick = 0
    passed_launch = 0

    # Phase 1: Quick checks (syntax + file existence)
    print("\n[Phase 1] File existence & Syntax check\n")
    quick_results: list[tuple] = []
    for game in GAMES:
        ok, detail = check_game_quick(game)
        status = "[OK]" if ok else "[FAIL]"
        print(f"  Vol.{game.volume:02d}  {game.title_zh:<16}  {status}  {detail}")
        quick_results.append((game, ok, detail))
        if ok:
            passed_quick += 1

    print(f"\n  Passed: {passed_quick}/{total}")

    # Phase 2: Quick launch test (for those that passed syntax check)
    print("\n[Phase 2] Quick launch test (2s each)\n")

    for game, ok, detail in quick_results:
        if not ok:
            print(f"  Vol.{game.volume:02d}  {game.title_zh:<16}  [SKIP] (syntax/file issue)")
            RESULTS.append((game.game_id, game.title_zh, "SKIP", "syntax/file check failed"))
            continue

        print(f"  Vol.{game.volume:02d}  {game.title_zh:<16}  Launching...", end="", flush=True)
        launch_ok, launch_detail = launch_and_quick_test(game)
        status = "[OK]" if launch_ok else "[FAIL]"
        print(f"\r  Vol.{game.volume:02d}  {game.title_zh:<16}  {status}  {launch_detail}")

        if launch_ok:
            passed_launch += 1
        RESULTS.append((game.game_id, game.title_zh, "PASS" if launch_ok else "FAIL", launch_detail))

    # Summary
    print_separator()
    print(f"  测试总结")
    print_separator()
    print(f"  文件/语法通过: {passed_quick}/{total}")
    print(f"  启动测试通过: {passed_launch}/{total}")
    print()

    if passed_launch == total:
        print("  All games start successfully!")
    else:
        print("  Problems found in these games:")
        for gid, title, status, detail in RESULTS:
            if status != "PASS":
                print(f"    - Vol.{gid} {title}: {detail}")


if __name__ == "__main__":
    main()
