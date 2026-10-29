# tests/test_e4_save_load.py
# E4 存档/读档 的无头单测（纯逻辑，不依赖 tkinter）。
# 覆盖：Sequence/Anchor/PollutionManager to_dict↔from_dict 往返、
#       GameSession 会话序列化、多槽位落盘读写、控制器存档/读档流转。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from save_load import GameSession, slot_path, list_slots
from sequences import make_sequence, Sequence
from anchor import Anchor
from pollution import PollutionLevel, PollutionSource, PollutionManager
from inventory import Inventory
from gui.state import GUIState


def _make_rich_character():
    """构造一个带污染/锚/消化/能力的角色，便于验证往返保真"""
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=70, connections=6, name="克喵之锚")
    ch.anchor.add_believers(120)
    ch.anchor.spread_legacy(15.0)
    ch.pollution.accumulate(PollutionSource("acting", 2.0))   # 点数2 → SAN60 幻觉
    ch.perform_action("偷窃")                                  # active 消化
    ch.perform_action("潜入")                                  # active 消化
    ch.abilities.append("不可名状的低语")                       # 幻觉附加能力
    return ch


@H.test("e4_sequence_roundtrip")
def t():
    """角色 to_dict → from_dict 应保真（途径/等级/性别/污染/锚/消化/能力）"""
    ch = _make_rich_character()
    d = ch.to_dict()
    ch2 = Sequence.from_dict(d)

    H.expect(ch2.PATHWAY_KEY == ch.PATHWAY_KEY, "途径应一致")
    H.expect(ch2.LEVEL == ch.LEVEL, "等级应一致")
    H.expect(ch2.gender == ch.gender, "性别应一致")
    # 污染
    H.expect(abs(ch2.pollution.san - ch.pollution.san) < 1e-6, "SAN 应一致")
    H.expect(ch2.pollution.level == ch.pollution.level, "污染等级应一致")
    H.expect(len(ch2.pollution.sources) == len(ch.pollution.sources), "污染来源数应一致")
    # 锚
    H.expect(ch2.anchor is not None and ch.anchor is not None, "锚应存在")
    H.expect(abs(ch2.anchor.strength - ch.anchor.strength) < 1e-6, "锚强度应一致")
    H.expect(ch2.anchor._believers == 120, "信徒数应一致")
    # 消化
    H.expect(set(ch2.digestion_actions) == set(ch.digestion_actions), "消化行为应一致")
    H.expect(abs(ch2.digestion_ratio - ch.digestion_ratio) < 1e-6, "消化度应一致")
    # 能力（含幻觉附加）
    H.expect(set(ch2.abilities) == set(ch.abilities), "能力集合应一致")


@H.test("e4_pollution_anchor_roundtrip")
def t():
    """PollutionManager / Anchor 各自 to_dict↔from_dict 往返"""
    pm = PollutionManager(PollutionLevel.SANE)
    pm.accumulate(PollutionSource("ritual", 3.5))
    pm2 = PollutionManager.from_dict(pm.to_dict())
    H.expect(abs(pm2.san - pm.san) < 1e-6, "PM SAN 往返一致")
    H.expect(pm2.level == pm.level, "PM 等级往返一致")

    a = Anchor(humanity=55, connections=4, name="x")
    a.add_mind_impressions(300)
    a2 = Anchor.from_dict(a.to_dict())
    H.expect(a2.humanity == 55 and a2.connections == 4, "锚基础字段往返")
    H.expect(a2._mind_impressions == 300, "大众印象往返")


@H.test("e4_gamesession_roundtrip")
def t():
    """GameSession 收集状态 → 还原到新 state，角色/库存/日志/视图一致"""
    state = GUIState()
    state.character = _make_rich_character()
    state.inventory.add("诈骗师非凡特性", 1)
    state.event_log = ["系统启动", "执行扮演：偷窃"]
    state.view_mode = "character"
    state.factions = {"church": 10, "tarot": 5}

    sess = GameSession.from_state(state)
    d = sess.to_dict()
    H.expect(d["character"]["pathway_key"] == "error", "会话含角色")
    H.expect(d["inventory"]["materials"].get("诈骗师非凡特性") == 1, "会话含库存")
    H.expect(d["view_mode"] == "character", "会话含视图")
    H.expect(d["factions"] == {"church": 10, "tarot": 5}, "会话含阵营")

    # 还原到全新 state
    state2 = GUIState()
    sess.apply_to_state(state2)
    H.expect(state2.character.PATHWAY_KEY == "error", "还原后角色途径一致")
    H.expect(state2.inventory.count("诈骗师非凡特性") == 1, "还原后库存一致")
    H.expect(state2.event_log == ["系统启动", "执行扮演：偷窃"], "还原后日志一致")
    H.expect(state2.factions == {"church": 10, "tarot": 5}, "还原后阵营一致")


@H.test("e4_multislot_save_load")
def t():
    """多槽位落盘：不同槽位互不影响，可列目录"""
    # 清理无关槽位，保证断言稳定
    for s in list_slots():
        try:
            os.remove(slot_path(s))
        except Exception:
            pass

    ch = _make_rich_character()
    st_a = GUIState(); st_a.character = ch; st_a.inventory.add("A材料", 1)
    st_b = GUIState(); st_b.character = make_sequence("fool", 9); st_b.inventory.add("B材料", 2)

    GameSession.from_state(st_a).save("slot_a")
    GameSession.from_state(st_b).save("slot_b")

    H.expect("slot_a" in list_slots() and "slot_b" in list_slots(), "两槽位应可见")

    loaded_a = GameSession.load("slot_a")
    st_a2 = GUIState(); loaded_a.apply_to_state(st_a2)
    H.expect(st_a2.character.PATHWAY_KEY == "error", "slot_a 还原 error")
    H.expect(st_a2.inventory.count("A材料") == 1, "slot_a 含 A材料")

    loaded_b = GameSession.load("slot_b")
    st_b2 = GUIState(); loaded_b.apply_to_state(st_b2)
    H.expect(st_b2.character.PATHWAY_KEY == "fool", "slot_b 还原 fool")
    H.expect(st_b2.inventory.count("B材料") == 2, "slot_b 含 B材料")

    # 清理
    for s in ("slot_a", "slot_b"):
        try:
            os.remove(slot_path(s))
        except Exception:
            pass


if __name__ == "__main__":
    H.run_all()
