# -*- coding: utf-8 -*-
"""测试聚合 runner：跑 `tests/` 下全部测试模块（**零 GL**）。

每个模块自带 runner（`python -m tests.<名>`，末尾打印自己的 `ALL_*_PASSED` 标记），
本脚本用**子进程**逐个跑：一个模块崩了不会拖垮其余模块，也不会因为
"import 期就开窗口"而整批失败。

判定 = 退出码 0 **且** 出现该模块专属标记（只看退出码会漏掉"模块级 import 失败
但进程仍正常退出"这种假绿 —— 与引擎侧 `scripts/run_all_tests.py` 同口径）。

用法::

    python -m tests.run_all
    python -m tests.run_all --quiet
    python -m tests.run_all --list
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODULES = [
    ('tests.test_blocks', 'ALL_BLOCKS_TESTS_PASSED', '方块表与面剔除规则'),
    ('tests.test_textures', 'ALL_TEXTURES_TESTS_PASSED', '程序化贴图与图集几何'),
    ('tests.test_world', 'ALL_WORLD_TESTS_PASSED', '世界生成确定性与地层'),
    ('tests.test_mesh', 'ALL_MESH_TESTS_PASSED', '面剔除 / 绕序 / UV 投影'),
    ('tests.test_physics', 'ALL_PHYSICS_TESTS_PASSED', '玩家物理与碰撞'),
    ('tests.test_raycast', 'ALL_RAYCAST_TESTS_PASSED', 'DDA 体素拾取'),
    ('tests.test_kernel', 'ALL_KERNEL_TESTS_PASSED', '内核动作 / 存档 / 自动机'),
    # --- Phase 1 新增（物品/掉落/配方/生存）---
    ('tests.test_items', 'ALL_ITEMS_TESTS_PASSED', '物品表 / 工具 / 挖掘规则'),
    ('tests.test_drops', 'ALL_DROPS_TESTS_PASSED', '掉落规则与确定性'),
    ('tests.test_recipes', 'ALL_RECIPES_TESTS_PASSED', '合成 / 烧炼配方'),
    ('tests.test_survival', 'ALL_SURVIVAL_TESTS_PASSED', '生存循环 / 耐久 / 熔炉'),
    # --- Phase 2-B 新增（生物）---
    ('tests.test_mobs', 'ALL_MOBS_TESTS_PASSED', '生物表与实体'),
    ('tests.test_ai', 'ALL_AI_TESTS_PASSED', '生物 AI / 刷怪 / 攻击'),
    # --- Phase 2-C 新增（洞穴与矿脉分层）---
    ('tests.test_caves', 'ALL_CAVES_TESTS_PASSED', '洞穴生成与护栏'),
    ('tests.test_fluid', 'ALL_FLUID_TESTS_PASSED', '水流灌注与洞内进水'),
    ('tests.test_weather', 'ALL_WEATHER_TESTS_PASSED', '天气状态机与天光影响'),
    ('tests.test_structures', 'ALL_STRUCTURES_TESTS_PASSED', '村庄选址 / 建筑 / 刷怪联动'),
]


def _force_utf8_stdout():
    """stdio 钉 UTF-8：GBK 控制台下 print 含 ⚠/⇒ 的结论会抛异常、把结论一起丢掉。"""
    for stream in (sys.stdout, sys.stderr):
        rec = getattr(stream, 'reconfigure', None)
        if rec is not None:
            try:
                rec(encoding='utf-8', errors='replace')
            except (ValueError, OSError):
                pass


def _count_ok(out: str) -> int:
    return sum(1 for line in out.splitlines() if line.strip().startswith('ok:'))


def run_one(mod: str, marker: str, quiet: bool):
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(
        [_ROOT] + ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    proc = subprocess.run(
        [sys.executable, '-m', mod], cwd=_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace')
    out = proc.stdout or ''
    ok = proc.returncode == 0 and marker in out
    err = ''
    if not ok:
        tail = [l for l in out.splitlines() if l.strip()][-3:]
        err = ' / '.join(tail) if tail else f'exit={proc.returncode}'
    if not quiet:
        print(out, end='' if out.endswith('\n') else '\n')
    return ok, _count_ok(out), err


def main(argv=None) -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser(description='mcclone3d 测试聚合 runner')
    ap.add_argument('--quiet', action='store_true', help='只打印汇总')
    ap.add_argument('--list', action='store_true', help='只列模块')
    args = ap.parse_args(argv)

    if args.list:
        for mod, _m, desc in MODULES:
            print(f'{mod:<24} {desc}')
        return 0

    print(f'[run_all] python = {sys.executable}')
    print(f'[run_all] root   = {_ROOT}')
    print('=' * 62)
    total = passed = 0
    failed = []
    for mod, marker, desc in MODULES:
        ok, n, err = run_one(mod, marker, args.quiet)
        total += n
        if ok:
            passed += 1
            print(f'  [PASS] {mod:<22} {n:>3} 项  ({desc})')
        else:
            failed.append((mod, err))
            print(f'  [FAIL] {mod:<22} {n:>3} 项  ({desc})  {err}')
    print('=' * 62)
    print(f'[run_all] 模块 {passed}/{len(MODULES)} 通过，实际执行用例 {total} 项')
    if failed:
        for mod, err in failed:
            print(f'  - {mod}: {err}')
        print('ALL_TESTS_FAILED')
        return 1
    print('ALL_TESTS_PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
