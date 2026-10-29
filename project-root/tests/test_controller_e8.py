# tests/test_controller_e8.py
# 控制器层无头测试（E8 AI 对手）。FakeGUI 只实现 add_log / refresh_all / _draw_pathway_list。
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


@H.test("ctrl_e8_rival_tick_creates_and_advances")
def t():
    """_do_rival_tick 应创建对手系统并随多次推进使对手等级下降。"""
    gui = FakeGUI()
    gui.character = make_sequence("error", 9)
    gui._do_rival_tick()
    H.expect(gui.state.rival_system is not None, "应已创建对手系统")
    H.expect(gui.state.rival_system.count() >= 1, "应至少有一名对手")
    for _ in range(50):
        gui._do_rival_tick()
    levels = [s["level"] for s in gui.state.rival_system.status()]
    H.expect(min(levels) < 9, f"对手应随时间推进（最低等级 {min(levels)}）")


@H.test("ctrl_e8_add_rival")
def t():
    """_do_add_rival 应添加指定途径的对手。"""
    gui = FakeGUI()
    gui.character = make_sequence("error", 9)
    gui._do_add_rival("fool")
    H.expect(gui.state.rival_system.count() == 1, "应添加 1 名对手")
    H.expect(gui.state.rival_system.status()[0]["pathway_key"] == "fool", "对手途径应为 fool")
