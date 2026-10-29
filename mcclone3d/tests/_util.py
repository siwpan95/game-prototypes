# -*- coding: utf-8 -*-
"""单测公共夹具：路径自举 + 迷你 runner（各测试模块共用，避免七份重复样板）。

⚠ 本文件**不是**测试模块（不打印 `ALL_*_PASSED`），所以不登记进 `run_all.MODULES`。
"""
from __future__ import annotations

import os
import sys
import traceback

# stdio 编码兜底：必须在任何测试逻辑之前执行。
# 理由（实测踩过）：断言消息里含 `⇒`/`⚠` 等 GBK 编不出的字符时，runner 打印失败信息
# 本身会抛 UnicodeEncodeError ⇒ **失败信息丢了、还多出一条假异常**。
# 与 3dworld 侧 `scripts/_console.py` 同一套做法（宁可显示成 ?，也不丢结论）。
for _stream in (sys.stdout, sys.stderr):
    _rec = getattr(_stream, 'reconfigure', None)
    if _rec is not None:
        try:
            _rec(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

# 把仓根塞进 sys.path（支持 `python -m tests.xxx` 与直接跑两种形态）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def make_suite(marker: str, title: str, stream=None):
    """建一个迷你 runner；返回 `(test 装饰器, main 函数)`。

    用法::

        test, main = make_suite('ALL_BLOCKS_TESTS_PASSED', '方块表')
        @test('规则：邻居不透明就挡死')
        def t_x(): ...
        if __name__ == '__main__':
            sys.exit(main())
    """
    tests = []

    def test(name):
        def deco(fn):
            tests.append((name, fn))
            return fn
        return deco

    def main(argv=None) -> int:
        out = stream or sys.stdout
        failed = []
        for name, fn in tests:
            try:
                fn()
            except AssertionError as exc:
                failed.append((name, str(exc)))
                print(f'  FAIL: {name} :: {exc}', file=out)
            except Exception as exc:                       # noqa: BLE001
                failed.append((name, f'{type(exc).__name__}: {exc}'))
                print(f'  ERROR: {name} :: {type(exc).__name__}: {exc}', file=out)
                traceback.print_exc(file=out)
            else:
                print(f'  ok: {name}', file=out)
        print('=' * 60, file=out)
        if failed:
            print(f'[{title}] {len(tests) - len(failed)}/{len(tests)} 通过', file=out)
            for name, why in failed:
                print(f'  - {name}: {why}', file=out)
            print(f'{marker.replace("PASSED", "FAILED")}', file=out)
            return 1
        print(f'[{title}] {len(tests)}/{len(tests)} 通过', file=out)
        print(marker, file=out)
        return 0

    return test, main
