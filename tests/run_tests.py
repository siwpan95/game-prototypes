# -*- coding: utf-8 -*-
"""测试聚合入口（标准库自跑，无第三方依赖）。

    python -m tests.run_tests
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODULES = [
    ('tests.test_dungeon', 'ALL_DUNGEON_TESTS_PASSED', '世界源 / 规则源 / 回退 / 通关'),
]


def main() -> int:
    env = dict(os.environ)
    env['PYTHONPATH'] = ROOT + os.pathsep + env.get('PYTHONPATH', '')
    failed = []
    for mod, marker, desc in MODULES:
        proc = subprocess.run(
            [sys.executable, '-m', mod], cwd=ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace')
        out = proc.stdout or ''
        cases = sum(1 for line in out.splitlines() if line.strip().startswith('ok:'))
        if proc.returncode == 0 and marker in out:
            print(f'  [PASS] {mod}  {cases} 项  ({desc})')
        else:
            failed.append(mod)
            print(f'  [FAIL] {mod}  ({desc})')
            print('\n'.join('        ' + ln for ln in out.splitlines()[-12:]))
    print('=' * 70)
    print(f'[run_tests] 模块 {len(MODULES) - len(failed)}/{len(MODULES)} 通过')
    if failed:
        print('ALL_TESTS_FAILED')
        return 1
    print('ALL_TESTS_PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
