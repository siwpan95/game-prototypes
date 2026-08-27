"""Manual test runner -- runs the critical-path unit tests WITHOUT pytest.

Why this exists:
    The CI installs pytest and runs ``pytest tests/``. On a dev machine where
    pytest (and pygame) are NOT installed, this script provides an equivalent
    green/red check using only the standard library ``assert``.

How it works:
    It loads each ``tests/test_*.py`` module by file path (importlib), discovers
    every top-level function named ``test_*``, and runs them. Any raised
    AssertionError / Exception is recorded as a failure; everything else is a pass.

    For the OFFICIAL run, install pytest and use:
        pytest tests/            # or:  python -m pytest tests/

Usage:
    python tests/run_manual.py
Exit code: 0 if all tests pass, 1 if any fail.
"""
import importlib.util
import inspect
import os
import sys
import traceback

# Make the project root importable so test modules' `from models.xxx` resolve.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
# The 4 critical-path modules delivered for action items #8 / #10.
TEST_MODULES = [
    "test_combat",
    "test_save",
    "test_game_state",
    "test_inventory",
]


def _load_module(name):
    path = os.path.join(TESTS_DIR, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collect_tests(module):
    return [
        (name, obj)
        for name, obj in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("test_") and obj.__module__ == module.__name__
    ]


def main():
    passed = 0
    failed = 0
    failures = []

    print("=" * 64)
    print("Manual test run (no pytest) -- critical-path unit tests")
    print("=" * 64)

    for mod_name in TEST_MODULES:
        try:
            module = _load_module(mod_name)
        except Exception:
            failed += 1
            failures.append((mod_name, "<module load>", traceback.format_exc()))
            print(f"[LOAD FAIL] {mod_name}")
            continue

        tests = _collect_tests(module)
        if not tests:
            print(f"[WARN] {mod_name}: no test_* functions found")
        for test_name, test_fn in tests:
            try:
                test_fn()
                passed += 1
                print(f"  PASS  {mod_name}.{test_name}")
            except Exception:
                failed += 1
                failures.append((mod_name, test_name, traceback.format_exc()))
                print(f"  FAIL  {mod_name}.{test_name}")

    print("=" * 64)
    print(f"TOTAL: {passed + failed}  |  PASSED: {passed}  |  FAILED: {failed}")
    if failures:
        print("\n--- FAILURE DETAILS ---")
        for mod_name, test_name, tb in failures:
            print(f"\n[{mod_name}.{test_name}]\n{tb}")
        print("\nRESULT: RED")
        sys.exit(1)
    print("RESULT: GREEN")
    sys.exit(0)


if __name__ == "__main__":
    main()
