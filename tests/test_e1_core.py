# tests/test_e1_core.py
# P0 核心逻辑的无头单测（不依赖 tkinter，任何 Python 均可运行）：
#   E1  get_potion_formula / Inventory
#   E2  PollutionManager 连续 SAN
#   E3  events.pick_event / resolve_choice
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from pathways_data import get_potion_formula, get_all_pathway_keys
from inventory import Inventory
from pollution import PollutionLevel, PollutionManager, PollutionSource
from sequences import make_sequence
from anchor import Anchor
from gui.state import GUIState
from events import pick_event, resolve_choice


@H.test("e1_formula_all_pathways")
def t():
    """22 条途径各序列都能推导配方，且主材料唯一、辅助材料齐全"""
    for pk in get_all_pathway_keys():
        for lvl in (9, 8, 7, 6, 5, 4, 3, 2, 1):
            f = get_potion_formula(pk, lvl)
            H.expect(f["main"].endswith("非凡特性"), f"{pk}/{lvl} 主材料格式错误")
            H.expect(len(f["supplementary"]) >= 1, f"{pk}/{lvl} 应有辅助材料")
            # 辅助材料不应出现重复
            H.expect(len(set(f["supplementary"])) == len(f["supplementary"]),
                     f"{pk}/{lvl} 辅助材料不应重复")


@H.test("e1_inventory_has_consume")
def t():
    """Inventory 的 has / missing / consume 语义正确"""
    inv = Inventory()
    f = {"main": "M", "supplementary": ["A", "B"]}
    H.expect(not inv.has(f), "空库存不应满足配方")
    inv.add("M", 1); inv.add("A", 1)
    H.expect(not inv.has(f), "仅部分材料仍不满足")
    H.expect(set(inv.missing(f)) == {"B"}, "missing 应只报告 B")
    inv.add("B", 1)
    H.expect(inv.has(f), "齐备后应满足")
    ok = inv.consume(f)
    H.expect(ok and not inv.has(f), "consume 后应刚好耗尽并变为不满足")


@H.test("e2_san_continuous")
def t():
    """PollutionManager 的连续 SAN：累积降 SAN，recover 升 SAN"""
    pm = PollutionManager(PollutionLevel.SANE)
    H.expect(pm.san == 100.0 and pm.san_status() == "清醒", "初始 SAN 应为 100 清醒")
    pm.accumulate(PollutionSource("acting", 1.0))   # _points 1 -> SAN 80
    H.expect(abs(pm.san - 80.0) < 1e-6, f"SAN 应降到 80，实际 {pm.san}")
    H.expect(pm.san_status() == "低语", "SAN80 应为低语")
    pm.recover(20.0)                                 # +20 -> SAN 100
    H.expect(abs(pm.san - 100.0) < 1e-6, "recover(20) 后 SAN 应回到 100")
    # 兼容属性
    H.expect(pm.value == pm.level.value, "pm.value 应等于 level.value")
    H.expect(pm.name == pm.level.name, "pm.name 应等于 level.name")
    H.expect(pm.label_cn == pm.level.label_cn, "pm.label_cn 应等于 level.label_cn")


@H.test("e3_pick_and_resolve")
def t():
    """事件抽取 + 选择结算：SAN/锚/材料/消化 正确作用"""
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=50, connections=5, name="t")
    state = GUIState()
    state.character = ch
    state.inventory = Inventory()

    ev = pick_event(ch, state)
    H.expect(ev is not None, "应能抽到事件")

    # 构造确定性事件以验证结算
    scripted = {
        "title": "测试事件", "narrative": "x",
        "choices": [
            {"text": "A", "effects": {"san": 15, "anchor": 5, "needed_materials": 1, "digestion": 1}},
            {"text": "B", "effects": {"san": -20}},
        ],
    }
    # 选择 B：理智 -20
    before = ch.pollution.san
    logs = resolve_choice(state, scripted, 1)
    H.expect(abs(ch.pollution.san - (before - 20)) < 1e-6,
             f"选择 B 后 SAN 应 -20，实际 {ch.pollution.san}")
    H.expect(state.pending_event is None, "resolve 不应改动 pending_event")

    # 选择 A：理智+15（封顶100）、锚+5、获得所需材料、消化+1
    logs = resolve_choice(state, scripted, 0)
    H.expect(ch.anchor.humanity == 55, f"锚人性应 +5 到 55，实际 {ch.anchor.humanity}")
    H.expect(state.inventory.total() >= 1, "选择 A 应获得所需材料")
    H.expect(ch.digestion_ratio > 0, "选择 A 应提升消化进度")

    # 越界索引应安全返回错误日志
    bad = resolve_choice(state, scripted, 9)
    H.expect(any("无此选项" in line for line in bad), "越界选项应返回错误提示")


if __name__ == "__main__":
    H.run_all()
