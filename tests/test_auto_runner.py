"""自动化引擎测试。"""
from __future__ import annotations

import unittest

from yuanbao.config import Config
from yuanbao.core.automaton import CellularAutomaton
from yuanbao.core.detector import CNNDetector
from yuanbao.engine.auto_runner import AutoRunner
from yuanbao.tasks.requirement import TaskRequirement
from yuanbao.tasks.task import Task


def make_setup(size=10, seed=42, density=0.5):
    cfg = Config(GRID_SIZE=size, INIT_DENSITY=density, STEP_INTERVAL=0.0)
    ca = CellularAutomaton(cfg, seed=seed)
    det = CNNDetector(size, cfg)
    return cfg, ca, det


class TestAutoRunner(unittest.TestCase):
    def test_step_increments_counter(self):
        _cfg, ca, det = make_setup()
        runner = AutoRunner(ca, det, [])
        self.assertEqual(runner.step_count, 0)
        runner.step()
        self.assertEqual(runner.step_count, 1)
        runner.step()
        self.assertEqual(runner.step_count, 2)

    def test_step_with_no_tasks_returns_not_done(self):
        _cfg, ca, det = make_setup()
        runner = AutoRunner(ca, det, [])
        all_done, collected = runner.step()
        # 没有任务时 all() 对空列表返回 True
        self.assertTrue(all_done)
        self.assertEqual(collected, [])

    def test_collect_clears_cell(self):
        cfg, ca, det = make_setup(size=5, seed=1, density=0.0)
        ca.set_cell(2, 2, cfg.tag_index('red'))
        ca.set_cell(2, 3, cfg.tag_index('green'))
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {'green': 1}}, 1)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])
        # 直接走 runner 的一步逻辑会先 step() 演化 CA，可能破坏布置；
        # 这里复用 runner 的检测+收集路径（不演化）以验证收集语义。
        grid, tag = ca.get_state()
        matches = det.detect_pattern(grid, tag, req.pattern)
        for pos in matches:
            if pos in runner.collected_positions:
                continue
            if ca.clear_cell(*pos):
                runner.collected_positions.add(pos)
                req.collected += 1
                if req.done:
                    break
        self.assertEqual(req.collected, 1)
        self.assertEqual(ca.grid[2][2], 0)
        self.assertEqual(ca.tag_grid[2][2], 0)
        self.assertIn((2, 2), runner.collected_positions)

    def test_no_duplicate_collection(self):
        cfg, ca, det = make_setup(size=5, seed=2, density=0.0)
        ca.set_cell(2, 2, cfg.tag_index('red'))
        ca.set_cell(2, 3, cfg.tag_index('green'))
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {'green': 1}}, 5)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])
        # 第一次检测收集
        grid, tag = ca.get_state()
        for pos in det.detect_pattern(grid, tag, req.pattern):
            if pos in runner.collected_positions:
                continue
            if ca.clear_cell(*pos):
                runner.collected_positions.add(pos)
                req.collected += 1
        self.assertEqual(req.collected, 1)
        # 同一状态再次检测，中心已被清空，应无匹配
        grid2, tag2 = ca.get_state()
        self.assertEqual(det.detect_pattern(grid2, tag2, req.pattern), [])

    def test_run_completes_when_count_zero(self):
        _cfg, ca, det = make_setup(size=5, seed=3)
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {}}, 0)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])
        done = runner.run(max_steps=5, interval=0.0)
        self.assertTrue(done)
        self.assertTrue(task.completed)

    def test_stop_interrupts_threaded_run(self):
        # 验证 stop() 能中断正在运行的后台线程：on_step 在第 3 步请求停止，
        # 线程应退出且不触发 on_complete(True)（被中断不算完成）。
        _cfg, ca, det = make_setup(size=5, seed=9)
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {}}, 10 ** 9)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])

        def on_step(n: int, r: AutoRunner) -> None:
            if n >= 3:
                r.stop()

        completed = []
        thread = runner.run_threaded(
            max_steps=10 ** 9,
            interval=0.0,
            on_step=on_step,
            on_complete=lambda ok, r: completed.append(ok),
        )
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(runner.is_running)
        self.assertGreaterEqual(runner.step_count, 3)
        self.assertEqual(completed, [])

    def test_reset_clears_stop_flag(self):
        # stop() 设置标志后，reset() 应清除它，使后续运行可正常启动。
        _cfg, ca, det = make_setup(size=5, seed=4)
        runner = AutoRunner(ca, det, [])
        runner.stop()
        runner.reset()
        # reset 后能正常完成一个 count=0 的任务，说明 stop_flag 已清除
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {}}, 0)
        task = Task("t", [req])
        runner.tasks = [task]
        done = runner.run(max_steps=3, interval=0.0)
        self.assertTrue(done)

    def test_run_with_callbacks(self):
        _cfg, ca, det = make_setup(size=5, seed=5)
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {}}, 0)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])
        steps_seen = []
        complete_seen = []

        def on_step(n, r):
            steps_seen.append(n)

        def on_complete(ok, r):
            complete_seen.append(ok)

        runner.run(max_steps=5, interval=0.0, on_step=on_step, on_complete=on_complete)
        self.assertTrue(len(steps_seen) >= 1)
        self.assertEqual(complete_seen, [True])

    def test_run_threaded_completes(self):
        _cfg, ca, det = make_setup(size=5, seed=6)
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {}}, 0)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])
        flag = {"done": False}

        def on_complete(ok, r):
            flag["done"] = True

        thread = runner.run_threaded(max_steps=5, interval=0.0, on_complete=on_complete)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(flag["done"])
        self.assertFalse(runner.is_running)

    def test_reset(self):
        _cfg, ca, det = make_setup(size=5, seed=7)
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {}}, 3)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])
        runner.step()
        runner.step()
        self.assertEqual(runner.step_count, 2)
        runner.reset()
        self.assertEqual(runner.step_count, 0)
        self.assertEqual(len(runner.collected_positions), 0)
        self.assertEqual(req.collected, 0)
        self.assertFalse(task.completed)

    def test_all_done_property(self):
        _cfg, ca, det = make_setup(size=5, seed=8)
        req = TaskRequirement("r", {'center': 'red', 'neighbors': {}}, 0)
        task = Task("t", [req])
        runner = AutoRunner(ca, det, [task])
        self.assertFalse(runner.all_done)
        task.completed = True
        self.assertTrue(runner.all_done)


if __name__ == "__main__":
    unittest.main()
