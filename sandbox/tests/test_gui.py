"""gui.py 图形界面冒烟测试。

无显示环境（无法初始化 Tk）会自动跳过，不影响 CI/无头回归。
"""
from __future__ import annotations

import unittest

try:
    import tkinter as tk
    _TK_OK = True
except Exception:  # pragma: no cover - 无 tkinter 时整体跳过
    _TK_OK = False

import entities
import progression
from game import Game


@unittest.skipUnless(_TK_OK, "tkinter 不可用（无显示环境）")
class TestGUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gui
        cls.gui = gui
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:  # 无显示环境：跳过整个类
            raise unittest.SkipTest(f"无法初始化 Tk: {exc}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "root"):
            cls.root.destroy()

    def _app(self, seed: int = 7, floors: int = 8):
        return self.gui.DungeonGUI(self.root, seed=seed, floors=floors)

    def test_construct_and_refresh(self):
        """GUI 能构造并渲染首层（地图/背包/小地图）。"""
        app = self._app()
        app.refresh_all()
        self.assertEqual(app.game.status, "playing")
        self.assertTrue(len(app.minimap_text.get("1.0", "end").strip()) > 0)

    def test_character_panel(self):
        """C 键角色面板可打开并关闭，不抛异常。"""
        app = self._app()
        app.open_character()
        for w in self.root.winfo_children():
            if isinstance(w, tk.Toplevel):
                w.destroy()

    def test_level_up_applies_perk(self):
        """升级三选一：点击「选择」应套用一个 perk 并清空待处理队列。"""
        app = self._app()
        app.game.pending_levels = [3]

        def click_choice(widget):
            for c in widget.winfo_children():
                if isinstance(c, tk.Button) and c.cget("text") == "选择":
                    c.invoke()
                    return True
                if click_choice(c):
                    return True
            return False

        self.root.after(50, lambda: click_choice(self.root))
        app.open_level_up()
        self.assertTrue(app.game.progression.perks)
        self.assertEqual(len(app.game.pending_levels), 0)

    def test_deep_floor_renders_ranged_and_traps(self):
        """第 4 层混入远程怪与主题陷阱，GUI 渲染不崩且小地图有内容。"""
        app = self._app()
        g = Game(seed=7, floors=8)
        g._build_floor(4)
        app.game = g
        app._boss_art_shown = False
        app.refresh_all()
        mm = app.minimap_text.get("1.0", "end").strip()
        self.assertTrue(len(mm) > 0)
        ranged = [m for m in g.monsters
                  if m.get(entities.MobBrain).attack_range > 1]
        self.assertGreaterEqual(len(ranged), 1)  # floor>=3 应含远程怪
        self.assertGreaterEqual(len(g.floor.get("trap_types", {})), 1)


if __name__ == "__main__":
    unittest.main()
