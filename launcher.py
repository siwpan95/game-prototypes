# -*- coding: utf-8 -*-
"""
launcher — MCclone 统一启动器（MC1 文字冒险 + MC2 2D 复刻，均基于 allin_engine）

功能：
  1. 启动 MC1 —— 我的世界文字冒险（Tkinter GUI）
  2. 启动 MC2 —— 我的世界 2D 侧视复刻（pygame GUI）
  3. 运行探针测试 —— 用 allin_engine.test.Probe 验证两游戏可运行、可玩
  4. 退出

说明：
  - MC1 / MC2 在启动时会自行把引擎父目录（本目录 <仓库根>）注入 sys.path，
    因此只要 allin_engine 在本目录下，即可正常导入。
  - GUI 程序以独立子进程启动（不阻塞本菜单）；探针测试在本进程内运行并可查看明细。
  - 命令行用法：python launcher.py --probes   直接运行全部探针并返回退出码。

依赖：Python 3.10+ ；MC1 需 tkinter ；MC2 需 pygame（无显示设备时 GUI 无法启动，
但探针测试可 headless 运行）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MC1_GUI = ROOT / "MC1" / "main.py"
MC2_GUI = ROOT / "MC2" / "mcclone" / "main_gui.py"
MC1_PROBES = ROOT / "tests" / "integration" / "test_mc1_probes.py"
MC2_PROBES = ROOT / "tests" / "integration" / "test_mc2_probes.py"
UNIFIED_PROBES = ROOT / "tests" / "integration" / "test_unified_probes.py"

PY = sys.executable


def _launch_gui(label: str, script: Path) -> None:
    if not script.exists():
        print(f"  ❌ 找不到 {label} 入口：{script}")
        return
    try:
        # 独立子进程启动 GUI，避免阻塞菜单；重定向到 DEVNULL 防止污染菜单输出
        subprocess.Popen(
            [PY, str(script)],
            cwd=str(script.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"  🚀 已启动 {label}（独立窗口）。若未见窗口，请确认显示环境与依赖。")
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ 启动 {label} 失败：{type(e).__name__}: {e}")


def _run_probes() -> int:
    """运行 MC1 + MC2 探针测试，返回合并退出码（0 = 全部通过）。"""
    failures = 0
    for name, script in (("MC1", MC1_PROBES), ("MC2", MC2_PROBES),
                         ("统一产品", UNIFIED_PROBES)):
        if not script.exists():
            print(f"  ❌ 缺少探针脚本：{script}")
            failures += 1
            continue
        print(f"\n{'=' * 60}\n  {name} 探针测试\n{'=' * 60}")
        rc = subprocess.run([PY, str(script)], cwd=str(ROOT)).returncode
        if rc != 0:
            failures += 1
            print(f"  ⚠️  {name} 探针存在失败（退出码 {rc}）")
        else:
            print(f"  ✅ {name} 探针全部通过")
    print(f"\n{'=' * 60}")
    if failures == 0:
        print("  🎉 全部探针通过：MC1 与 MC2 均可正常运行并游玩。")
    else:
        print(f"  ⚠️  有 {failures} 项探针套件未全部通过，请检查上方日志。")
    print("=" * 60)
    return failures


def _menu() -> None:
    while True:
        print("\n" + "=" * 56)
        print("  MCclone 统一启动器  ·  基于 allin_engine 引擎")
        print("=" * 56)
        print("  [1] 启动 MC1 —— 我的世界文字冒险（Tkinter GUI）")
        print("  [2] 启动 MC2 —— 我的世界 2D 侧视复刻（pygame GUI）")
        print("  [3] 运行探针测试 —— 验证两游戏可运行 / 可玩")
        print("  [4] 退出")
        print("-" * 56)
        try:
            choice = input("请选择 [1-4]：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if choice == "1":
            _launch_gui("MC1 文字冒险", MC1_GUI)
        elif choice == "2":
            _launch_gui("MC2 2D 复刻", MC2_GUI)
        elif choice == "3":
            _run_probes()
        elif choice == "4":
            print("再见！")
            break
        else:
            print("  ❓ 无效选项，请输入 1-4。")


def main() -> int:
    parser = argparse.ArgumentParser(description="MCclone 统一启动器")
    parser.add_argument(
        "--probes", action="store_true",
        help="直接运行 MC1 + MC2 探针测试并退出（适合 CI / 自动化）",
    )
    args = parser.parse_args()
    if args.probes:
        return _run_probes()
    _menu()
    return 0


if __name__ == "__main__":
    sys.exit(main())
