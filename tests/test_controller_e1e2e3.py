# tests/test_controller_e1e2e3.py
# 控制器层无头测试（E1 材料门禁 / E3 事件流转）。
# 用 FakeGUI(ControllersMixin) 替代完整 GUI：只实现 add_log / refresh_all /
# _draw_pathway_list 三个钩子，不实例化 tk.Tk()，因此无需显示环境也能跑
# （但 gui.controllers 顶层 import tkinter，需在带 tkinter 的 Python 下运行）。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from sequences import make_sequence
from anchor import Anchor
from gui.state import GUIState
from gui.controllers import ControllersMixin
from pathways_data import get_potion_formula
from pollution import PollutionSource


class FakeGUI(ControllersMixin):
    """最小控制器宿主：复用 ControllersMixin 的真实晋升/事件逻辑。"""
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


def _digested_seq9(pk="error"):
    ch = make_sequence(pk, 9)
    ch.anchor = Anchor(humanity=85, connections=7, name="t")
    for a in ch.act_catalog():
        ch.perform_action(a)
    return ch


@H.test("ctrl_e1_ascend_requires_materials")
def t():
    """E1：材料不足时晋升被拦截；搜集后晋升成功并消耗材料"""
    gui = FakeGUI()
    gui.character = _digested_seq9()
    H.expect(gui.character.digested, "应已消化")
    # 材料不足 -> 拦截
    gui._do_ascend()
    H.expect(gui.character.LEVEL == 9, "材料不足时晋升应被拦截，等级仍为 9")
    H.expect(any("魔药材料不足" in l for l in gui.logs), "应记录材料不足提示")
    # 搜集材料
    gui._do_gather_materials()
    formula = get_potion_formula("error", 8)
    H.expect(gui.state.inventory.has(formula), "gather 后应满足配方")
    # 再次晋升 -> 成功并消耗
    gui._do_ascend()
    H.expect(gui.character.LEVEL == 8, "材料齐备后应晋升至序列8")
    H.expect(not gui.state.inventory.has(formula), "晋升后应消耗魔药材料")


@H.test("ctrl_e3_event_flow")
def t():
    """E3：触发随机事件设置 pending_event；选择后结算并清除"""
    gui = FakeGUI()
    gui.character = _digested_seq9()
    # 预置一些污染，使 SAN 低于满值：这样无论事件是扣 SAN 还是恢复 SAN，
    # SAN 都会发生变化（满 SAN 时恢复类效果无法再上升，会误判为“无效果”）。
    gui.character.pollution.accumulate(PollutionSource("acting", 1.0))  # SAN 100 -> 80
    gui._do_random_event()
    H.expect(gui.state.pending_event is not None, "触发随机事件应设置 pending_event")
    ev = gui.state.pending_event
    n_choices = len(ev["choices"])
    san_before = gui.character.pollution.san
    # 选择第一个选项
    gui._do_event_choice(0)
    H.expect(gui.state.pending_event is None, "选择后 pending_event 应被清除")
    # SAN 应因事件效果发生变化（除非恰好 +0）
    H.expect(gui.character.pollution.san != san_before or
             ev["choices"][0].get("effects", {}).get("san", 0) == 0,
             "事件结算应改变 SAN（或该选项本就无 SAN 效果）")
    _ = n_choices
