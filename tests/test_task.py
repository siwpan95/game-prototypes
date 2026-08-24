"""任务系统测试。"""
from __future__ import annotations

import unittest

from yuanbao.tasks.requirement import TaskRequirement
from yuanbao.tasks.task import Task


class TestRequirement(unittest.TestCase):
    def test_not_done_initially(self):
        r = TaskRequirement("desc", {}, 3)
        self.assertFalse(r.done)

    def test_done_when_collected_reaches_count(self):
        r = TaskRequirement("desc", {}, 3)
        r.collected = 3
        self.assertTrue(r.done)

    def test_done_when_collected_exceeds_count(self):
        r = TaskRequirement("desc", {}, 3)
        r.collected = 5
        self.assertTrue(r.done)

    def test_reset(self):
        r = TaskRequirement("desc", {}, 2)
        r.collected = 2
        r.reset()
        self.assertEqual(r.collected, 0)
        self.assertFalse(r.done)


class TestTask(unittest.TestCase):
    def test_not_completed_initially(self):
        t = Task("t", [TaskRequirement("a", {}, 1)])
        self.assertFalse(t.check_completion())
        self.assertFalse(t.completed)

    def test_completed_when_all_requirements_done(self):
        r1 = TaskRequirement("a", {}, 2)
        r2 = TaskRequirement("b", {}, 1)
        t = Task("t", [r1, r2])
        r1.collected = 2
        self.assertFalse(t.check_completion())
        r2.collected = 1
        self.assertTrue(t.check_completion())
        self.assertTrue(t.completed)

    def test_progress_zero(self):
        t = Task("t", [TaskRequirement("a", {}, 4), TaskRequirement("b", {}, 6)])
        self.assertAlmostEqual(t.progress, 0.0)

    def test_progress_partial(self):
        r1 = TaskRequirement("a", {}, 4)
        r2 = TaskRequirement("b", {}, 6)
        t = Task("t", [r1, r2])
        r1.collected = 2
        r2.collected = 6
        self.assertAlmostEqual(t.progress, 0.8)

    def test_progress_full(self):
        r1 = TaskRequirement("a", {}, 4)
        r2 = TaskRequirement("b", {}, 6)
        t = Task("t", [r1, r2])
        r1.collected = 4
        r2.collected = 6
        self.assertAlmostEqual(t.progress, 1.0)

    def test_progress_capped(self):
        # collected 超过 count 不应让 progress > 1
        r = TaskRequirement("a", {}, 2)
        t = Task("t", [r])
        r.collected = 10
        self.assertAlmostEqual(t.progress, 1.0)

    def test_progress_empty_requirements(self):
        t = Task("t", [])
        self.assertAlmostEqual(t.progress, 1.0)

    def test_progress_zero_count(self):
        t = Task("t", [TaskRequirement("a", {}, 0)])
        self.assertAlmostEqual(t.progress, 1.0)

    def test_reset(self):
        r = TaskRequirement("a", {}, 2)
        t = Task("t", [r])
        r.collected = 2
        t.completed = True
        t.reset()
        self.assertEqual(r.collected, 0)
        self.assertFalse(t.completed)

    def test_status_text(self):
        r = TaskRequirement("a", {}, 2)
        t = Task("t", [r])
        r.collected = 1
        txt = t.status()
        self.assertIn("任务: t", txt)
        self.assertIn("1/2", txt)
        self.assertIn("进行中", txt)


if __name__ == "__main__":
    unittest.main()
