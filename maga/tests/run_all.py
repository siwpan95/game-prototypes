"""一键运行全部冒烟测试

用法（仓库根目录）：
    python tests/run_all.py

按文件名顺序执行 tests/smoke_*.py，任一失败即退出码 1。
本机托管 Python 无 tkinter（环境限制），各测试通过 tests/tk_stub.py
注入桩后驱动 ViewModel；在有 tkinter 的环境可直接 python main.py 验 GUI。
"""
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)


def main():
    test_files = sorted(
        f for f in os.listdir(TESTS_DIR)
        if f.startswith("smoke_") and f.endswith(".py")
    )
    if not test_files:
        print("没有找到冒烟测试文件")
        return 1

    failed = []
    for name in test_files:
        print(f"\n{'=' * 60}\n>>> {name}\n{'=' * 60}")
        result = subprocess.run(
            [sys.executable, os.path.join(TESTS_DIR, name)],
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            failed.append(name)

    print(f"\n{'=' * 60}")
    if failed:
        print(f"失败 {len(failed)}/{len(test_files)}: {', '.join(failed)}")
        return 1
    print(f"全部通过（{len(test_files)}/{len(test_files)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
