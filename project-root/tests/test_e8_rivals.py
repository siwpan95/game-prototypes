# tests/test_e8_rivals.py
# AI 对手非凡者系统（E8）纯逻辑单测：推进、权柄争夺、竞争、序列化、可复现性。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from rivals import Rival, RivalSystem
from uniqueness import Uniqueness, SequenceOneCharacteristic
from pathways_data import get_pathway
from sequences import make_sequence
from anchor import Anchor
from pollution import PollutionSource


@H.test("e8_rival_advances_over_time")
def t():
    """对手应随 tick 推进（消化→晋升，序列等级下降）。"""
    rv = Rival("Amon", "error", start_level=9)
    lvl0 = rv.character.LEVEL
    rv.advance_one_tick(rng=__import__("random").Random(1))
    for _ in range(30):
        rv.advance_one_tick(rng=__import__("random").Random(1))
    H.expect(rv.character.LEVEL < lvl0, f"对手应已推进（{lvl0}→{rv.character.LEVEL}）")


@H.test("e8_rival_claims_uniqueness")
def t():
    """抵达序列1 的对手应占住本途径唯一性（与玩家竞争 owner 槽位）。"""
    rv = Rival("Amon", "fool", start_level=1)
    rv.advance_one_tick()
    u = Uniqueness.get_or_create(f"{get_pathway('fool')['name']}唯一性", "fool")
    H.expect(u.owner is rv.character, "对手应已占住 fool 途径唯一性")
    H.expect(rv._claimed, "claimed 应置位")


@H.test("e8_competition_player_can_take")
def t():
    """对手先占住唯一性后，玩家应能「击败并夺取」（复用现有控制器逻辑）。"""
    rv = Rival("Amon", "error", start_level=1)
    rv.advance_one_tick()
    u = Uniqueness.get_or_create(f"{get_pathway('error')['name']}唯一性", "error")
    H.expect(u.owner is rv.character, "对手先占住唯一性")
    player = make_sequence("error", 1)
    player.anchor = Anchor(humanity=100, connections=10, name="玩家")
    # 复用现有「击败并夺取」逻辑：unbind + bind
    u.unbind()
    u.bind(player)
    H.expect(u.owner is player, "玩家应能击败并夺取唯一性")


@H.test("e8_system_tick_deterministic")
def t():
    """相同种子的两个 RivalSystem 在相同 tick 数后应可复现。"""
    a = RivalSystem(seed=99); a.add_rival("fool")
    b = RivalSystem(seed=99); b.add_rival("fool")
    a.tick(25); b.tick(25)
    la = a.status()[0]["level"]; lb = b.status()[0]["level"]
    H.expect(la == lb, f"相同种子应可复现（{la} vs {lb}）")


@H.test("e8_serialization_roundtrip")
def t():
    """Rival / RivalSystem 应可随 GameSession 序列化还原。"""
    # 单个 Rival
    rv = Rival("Amon", "fool", start_level=1)
    rv.advance_one_tick()
    d = rv.to_dict()
    rv2 = Rival.from_dict(d)
    H.expect(rv2.character.LEVEL == rv.character.LEVEL, "Rival 等级应一致")
    H.expect(rv2.name == "Amon", "Rival 名应一致")
    H.expect(rv2._claimed == rv._claimed, "Rival claimed 应一致")
    # RivalSystem
    rs = RivalSystem(seed=5)
    rs.add_rival("fool", start_level=1)
    rs.tick(1)
    rs2 = RivalSystem.from_dict(rs.to_dict())
    H.expect(rs2.count() == 1, "读档后对手数应一致")
    H.expect(rs2.status()[0]["pathway_key"] == "fool", "读档后途径应一致")
    H.expect(rs2.status()[0]["name"] == rs.status()[0]["name"], "读档后名应一致")
