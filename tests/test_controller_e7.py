# tests/test_controller_e7.py
# 控制器层无头测试（E7 阵营 / 塔罗会社交）。
# FakeGUI(ControllersMixin) 只实现 add_log / refresh_all / _draw_pathway_list 三个钩子，
# 不实例化 tk.Tk()。gui.controllers 顶层 import tkinter，须在带 tkinter 的 Python 下运行。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.controllers import ControllersMixin
from gui.state import GUIState
from sequences import make_sequence
from pollution import PollutionSource
from anchor import Anchor
from factions import FactionSystem


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


@H.test("ctrl_e7_faction_action_exchanges")
def t():
    """E7：_do_faction_action(tarot, tarot_exchange) 扣声望并发材料"""
    gui = FakeGUI()
    gui.character = make_sequence("error", 9)
    gui.state.factions = {"tarot": 10}
    gui._do_faction_action("tarot", "tarot_exchange")
    H.expect(gui.state.factions["tarot"] == 0, "塔罗会声望应清零")
    H.expect(gui.state.inventory.total() == 1, "应获得 1 份材料")
    H.expect(any("塔罗会馈赠" in l for l in gui.logs), "日志应标注塔罗会馈赠")


@H.test("ctrl_e7_faction_action_insufficient_safe")
def t():
    """E7：声望不足时 _do_faction_action 应安全拒绝"""
    gui = FakeGUI()
    gui.character = make_sequence("error", 9)
    gui.state.factions = {}
    gui._do_faction_action("tarot", "tarot_exchange")
    H.expect(any("声望不足" in l for l in gui.logs), "应记录声望不足提示")
    H.expect(gui.state.inventory.total() == 0, "未执行则不应获得材料")


if __name__ == "__main__":
    H.run_all()
