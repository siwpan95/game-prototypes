"""命令行入口与默认任务定义。

入口行为
--------
* ``python -m yuanbao``           -> 启动 GUI（默认）
* ``python -m yuanbao --cli``     -> 命令行模式
* ``python main.py``              -> 启动 GUI
* ``python yuanbao.py``（旧入口）-> 同 ``python -m yuanbao``
"""
from __future__ import annotations

import argparse
from typing import List, Optional

from yuanbao.config import Config
from yuanbao.core.automaton import CellularAutomaton
from yuanbao.core.detector import CNNDetector
from yuanbao.tasks.requirement import TaskRequirement
from yuanbao.tasks.task import Task
from yuanbao.engine.auto_runner import AutoRunner


def build_default_tasks() -> List[Task]:
    """构造示例任务集合。可被 CLI 与 GUI 共用。"""
    req1 = TaskRequirement(
        description="红细胞且周围恰有1个绿邻居",
        pattern={"center": "red", "neighbors": {"green": 1}},
        count=3,
    )
    req2 = TaskRequirement(
        description="蓝细胞且周围恰有2个黄邻居",
        pattern={"center": "blue", "neighbors": {"yellow": 2}},
        count=2,
    )
    return [Task("生态收集", [req1, req2])]


def run_cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yuanbao",
        description="细胞工厂 - 元胞自动机 × CNN 标签任务系统",
    )
    parser.add_argument("--cli", action="store_true", help="使用命令行模式（默认启动 GUI）")
    parser.add_argument("--grid", type=int, default=Config.GRID_SIZE, help="网格大小")
    parser.add_argument("--steps", type=int, default=200, help="CLI 模式最大步数")
    parser.add_argument("--interval", type=float, default=Config.STEP_INTERVAL, help="步间隔（秒）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（便于复现）")
    ns = parser.parse_args(argv)

    if not ns.cli:
        # 默认 GUI
        from yuanbao.gui.app import launch_gui
        launch_gui()
        return 0

    cfg = Config(GRID_SIZE=ns.grid, STEP_INTERVAL=ns.interval)
    ca = CellularAutomaton(cfg, seed=ns.seed)
    detector = CNNDetector(cfg.GRID_SIZE, cfg)
    tasks = build_default_tasks()
    runner = AutoRunner(ca, detector, tasks)

    print("🧬 细胞工厂 - 元胞自动机 × CNN 标签任务系统")
    print("=== 自动化挂机开始 ===")

    def on_step(n: int, r: AutoRunner) -> None:
        print(f"\n第 {n} 代:")
        r.ca.display()
        for t in r.tasks:
            print(t.status())

    def on_complete(ok: bool, r: AutoRunner) -> None:
        if ok:
            print("\n🎉 所有任务完成！")

    done = runner.run(max_steps=ns.steps, interval=ns.interval, on_step=on_step, on_complete=on_complete)
    if not done:
        print("\n⚠️ 达到最大步数，任务未全部完成。")
    return 0 if done else 1
