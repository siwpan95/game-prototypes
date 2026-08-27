# tests/test_controller_e5.py
# 控制器层无头测试（E5 扮演质量维度）。
# FakeGUI(ControllersMixin) 只实现 add_log / refresh_all / _draw_pathway_list 三个钩子，
# 不实例化 tk.Tk()。gui.controllers 顶层 import tkinter，须在带 tkinter 的 Python 下运行。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.controllers import ControllersMixin
from gui.state import GUIState
from sequences import make_sequence


class FakeGUI(ControllersMixin):
    @property
    def character(self):
        return self.state.character

    @character.setter
    def character(self, v):
        self.state.character = v

    def __init__(self):
        self.state = GUIState()
        self.state.fonts = H.make_fonts()
        self.logs = []

    def add_log(self, m):
        self.logs.append(m)

    def refresh_all(self):
        pass

    def _draw_pathway_list(self):
        pass


@H.test("ctrl_e5_passive_half_weight")
def t():
    """E5：_do_action(act, 'passive') 应施加 0.5 权重并标注日志"""
    gui = FakeGUI()
    gui.character = make_sequence("error", 9)
    act = next(iter(gui.character.required_actions))
    gui._do_action(act, "passive")
    w = gui.character.action_weight.get(act, 0.0)
    H.expect(abs(w - 0.5) < 1e-9, f"被动应得 0.5 权重，实际 {w}")
    H.expect(any("被动" in l for l in gui.logs), "日志应标注『被动』")


@H.test("ctrl_e5_divergent_penalty")
def t():
    """E5：_do_action(act, 'divergent') 应扣 0.5 权重"""
    gui = FakeGUI()
    gui.character = make_sequence("error", 9)
    act = next(iter(gui.character.required_actions))
    gui._do_action(act, "divergent")
    w = gui.character.action_weight.get(act, 0.0)
    H.expect(abs(w - (-0.5)) < 1e-9, f"背离应扣 0.5 权重，实际 {w}")


if __name__ == "__main__":
    H.run_all()
