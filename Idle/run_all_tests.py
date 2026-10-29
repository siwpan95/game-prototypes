"""
离线测试运行器（无需 pytest / 网络）。
收集 tests/ 下所有 test_*.py 的 test_* 方法并运行，输出汇总。
运行：python run_all_tests.py
"""
import sys
import os
import types
import tempfile

# pytest 占位（test_upgrade.py 仅 import，不使用）
sys.modules.setdefault("pytest", types.ModuleType("pytest"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 切换到临时目录，避免加载/写入本地 idle_save.json
os.chdir(tempfile.mkdtemp())

TEST_FILES = [
    "tests.test_fmt",
    "tests.test_upgrade",
    "tests.test_state",
    "tests.test_engine_calc",
    "tests.test_p0",
    "tests.test_p1",
    "tests.test_p2",
    "tests.test_balance",
]


def run():
    total = 0
    failed = 0
    failures = []
    for modname in TEST_FILES:
        try:
            mod = __import__(modname, fromlist=["*"])
        except Exception as ex:  # noqa
            print(f"[IMPORT FAIL] {modname}: {ex}")
            failed += 1
            continue
        for clsname in dir(mod):
            cls = getattr(mod, clsname)
            if not isinstance(cls, type) or not clsname.startswith("Test"):
                continue
            if cls is type or cls.__module__ != modname:
                continue
            inst = cls()
            for mname in dir(inst):
                if not mname.startswith("test_"):
                    continue
                total += 1
                try:
                    getattr(inst, mname)()
                except Exception as ex:  # noqa
                    failed += 1
                    failures.append(f"{modname}.{clsname}.{mname}: {ex}")
    print("=" * 50)
    print(f"总测试: {total}  通过: {total - failed}  失败: {failed}")
    if failures:
        print("-" * 50)
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("✅ 全部通过")
        sys.exit(0)


if __name__ == "__main__":
    run()
