# tests/test_e7_factions.py
# E7 阵营 / 塔罗会社交（纯逻辑，不依赖 tkinter）：
#   - 事件结算可提升阵营声望（faction 效果字段）
#   - FactionSystem.do_action 消耗声望换取材料 / 理智 / 锚
#   - 声望不足时安全拒绝
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from sequences import make_sequence
from pollution import PollutionSource
from anchor import Anchor
from inventory import Inventory
from gui.state import GUIState
from events import resolve_choice
from factions import FactionSystem, FACTIONS, ACTIONS


@H.test("e7_reputation_earned_from_event")
def t():
    """事件结算的 faction 字段应提升对应阵营声望"""
    st = GUIState()
    st.character = make_sequence("error", 9)
    st.factions = {}
    ev = {"title": "x", "narrative": "x",
          "choices": [{"text": "A", "effects": {"faction": {"tarot": 8}}}]}
    resolve_choice(st, ev, 0)
    H.expect(st.factions.get("tarot", 0) == 8, "tarot 声望应 +8")
    H.expect("tarot" in FACTIONS, "FACTIONS 应含 tarot")


@H.test("e7_faction_action_tarot_exchange")
def t():
    """塔罗会换取材料：声望 -10，获得一份缺失材料"""
    st = GUIState()
    st.character = make_sequence("error", 9)
    st.inventory = Inventory()
    st.factions = {"tarot": 10}
    fs = FactionSystem(st.factions)
    logs = fs.do_action(st, "tarot_exchange")
    st.factions = fs.to_dict()
    H.expect(st.factions["tarot"] == 0, "塔罗会声望应清零")
    H.expect(st.inventory.total() == 1, "应获得 1 份材料")
    H.expect(any("塔罗会馈赠" in l for l in logs), "日志应标注塔罗会馈赠")


@H.test("e7_faction_action_church_purify")
def t():
    """教会净化：声望 -10，理智 +30（封顶）"""
    ch = make_sequence("error", 9)
    ch.pollution.accumulate(PollutionSource("acting", 2.0))   # SAN 60
    st = GUIState()
    st.character = ch
    st.factions = {"church": 10}
    fs = FactionSystem(st.factions)
    logs = fs.do_action(st, "church_purify")
    st.factions = fs.to_dict()
    H.expect(abs(ch.pollution.san - 90.0) < 1e-9, f"安抚后 SAN 应 90，实际 {ch.pollution.san}")
    H.expect(st.factions["church"] == 0, "教会声望应清零")


@H.test("e7_faction_action_secret_anchor")
def t():
    """隐秘组织加持：声望 -10，人性之锚 +15"""
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=50, connections=5, name="x")
    st = GUIState()
    st.character = ch
    st.factions = {"secret": 10}
    fs = FactionSystem(st.factions)
    logs = fs.do_action(st, "secret_anchor")
    st.factions = fs.to_dict()
    H.expect(abs(ch.anchor.humanity - 65.0) < 1e-9, f"人性应 +15 到 65，实际 {ch.anchor.humanity}")
    H.expect(st.factions["secret"] == 0, "隐秘组织声望应清零")


@H.test("e7_faction_action_insufficient")
def t():
    """声望不足应安全拒绝而非崩溃"""
    st = GUIState()
    st.character = make_sequence("error", 9)
    st.factions = {}   # tarot 声望 0 < 10
    fs = FactionSystem(st.factions)
    logs = fs.do_action(st, "tarot_exchange")
    st.factions = fs.to_dict()
    H.expect(st.factions.get("tarot", 0) == 0, "拒绝后声望不应变化")
    H.expect(any("声望不足" in l for l in logs), "应记录声望不足提示")


@H.test("e7_actions_well_formed")
def t():
    """ACTIONS 每个动作必须指向已知阵营且带合法 cost"""
    for key, a in ACTIONS.items():
        H.expect(a["faction"] in FACTIONS, f"{key} 的 faction 应在 FACTIONS 中")
        H.expect(isinstance(a.get("cost"), int) and a["cost"] > 0, f"{key} 应有正整数 cost")


if __name__ == "__main__":
    H.run_all()
