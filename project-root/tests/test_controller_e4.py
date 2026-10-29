# tests/test_controller_e4.py
# 控制器层无头测试（E4 存档/读档）。
# 用 FakeGUI(ControllersMixin) 替代完整 GUI：只实现 add_log / refresh_all /
# _draw_pathway_list 三个钩子，不实例化 tk.Tk()。gui.controllers 顶层 import
# tkinter，因此须在带 tkinter 的 Python（F:\Python314）下运行。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.controllers import ControllersMixin
from gui.state import GUIState
from sequences import make_sequence
from anchor import Anchor
from save_load import slot_path, GameSession
from inventory import Inventory


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


def _rich():
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=70, connections=6, name="克喵之锚")
    ch.pollution.accumulate(__import__("pollution").PollutionSource("acting", 2.0))
    ch.perform_action("偷窃")
    return ch


@H.test("ctrl_e4_save_then_load_restores")
def t():
    """E4：_do_save 序列化 → 破坏状态 → _do_load 还原会话"""
    gui = FakeGUI()
    gui.character = _rich()
    gui.state.inventory.add("测试材料", 3)
    gui._do_save("quicksave")
    H.expect(any("已存档" in l for l in gui.logs), "应记录存档成功")

    # 破坏当前会话
    gui.character = make_sequence("door", 8)
    gui.state.inventory = Inventory()

    gui._do_load("quicksave")
    H.expect(gui.character.PATHWAY_KEY == "error", "读档后应为 error 途径")
    H.expect(gui.character.LEVEL == 9, "读档后应为序列9")
    H.expect(gui.state.inventory.count("测试材料") == 3, "读档后库存应恢复")
    H.expect(any("已读档" in l for l in gui.logs), "应记录读档成功")

    # 清理
    try:
        os.remove(slot_path("quicksave"))
    except Exception:
        pass


@H.test("ctrl_e4_load_missing_slot_is_safe")
def t():
    """E4：读档不存在的槽位应安全报错，不抛异常"""
    gui = FakeGUI()
    gui.character = _rich()
    # 确保该槽位不存在
    try:
        os.remove(slot_path("no_such_slot_xyz"))
    except Exception:
        pass
    gui._do_load("no_such_slot_xyz")
    H.expect(any("读档失败" in l or "不存在" in l for l in gui.logs),
             "应记录读档失败而非崩溃")


if __name__ == "__main__":
    H.run_all()
