# tests/test_e6_abilities.py
# E6 能力效果化（纯逻辑，不依赖 tkinter）：
#   - 具效果的能力在事件结算中施加 SAN 安抚 / 额外材料 / 线索
#   - 未注册的能力不产生任何结算效果（不影响既有事件断言）
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from sequences import make_sequence
from pollution import PollutionSource
from gui.state import GUIState
from inventory import Inventory
from events import resolve_choice
from abilities import apply_ability_effects, ABILITY_EFFECTS


def _ch_with(*names, san=80):
    ch = make_sequence("error", 9)
    for n in names:
        ch.abilities.append(n)
    ch.pollution.accumulate(PollutionSource("acting", (100 - san) / 20.0))
    return ch


def _neutral_state(ch):
    st = GUIState()
    st.character = ch
    st.inventory = Inventory()
    return st


@H.test("e6_ability_san_relief")
def t():
    """占卜 应安抚理智（SAN +10 封顶）并标注日志"""
    ch = _ch_with("占卜", san=80)
    st = _neutral_state(ch)
    assert ch.pollution.san == 80.0
    ev = {"title": "t", "narrative": "x", "choices": [{"text": "A", "effects": {}}]}
    logs = resolve_choice(st, ev, 0)
    H.expect(abs(ch.pollution.san - 90.0) < 1e-9, f"占卜应 +10 SAN，实际 {ch.pollution.san}")
    H.expect(any("占卜" in l for l in logs), "日志应标注占卜能力")


@H.test("e6_ability_bonus_material")
def t():
    """观众 应获得额外材料『情绪标本』"""
    ch = _ch_with("观众")
    st = _neutral_state(ch)
    ev = {"title": "t", "narrative": "x", "choices": [{"text": "A", "effects": {}}]}
    logs = resolve_choice(st, ev, 0)
    H.expect(st.inventory.count("情绪标本") == 1, "观众应获得『情绪标本』")
    H.expect(any("情绪标本" in l for l in logs), "日志应标注额外材料")


@H.test("e6_ability_clue")
def t():
    """阅读者 应揭示一条隐秘线索"""
    ch = _ch_with("阅读者")
    st = _neutral_state(ch)
    ev = {"title": "t", "narrative": "x", "choices": [{"text": "A", "effects": {}}]}
    logs = resolve_choice(st, ev, 0)
    H.expect(any("隐秘线索" in l for l in logs), "阅读者应揭示隐秘线索")


@H.test("e6_unregistered_ability_no_effect")
def t():
    """未注册的能力不应改变事件结算（错误途径原生能力无效果）"""
    ch = make_sequence("error", 9)   # 夜视/格斗精通 等，均不在注册表
    st = _neutral_state(ch)
    base_san = ch.pollution.san
    ev = {"title": "t", "narrative": "x", "choices": [{"text": "A", "effects": {}}]}
    logs = resolve_choice(st, ev, 0)
    H.expect(abs(ch.pollution.san - base_san) < 1e-9, "无效果能力不应改变 SAN")
    H.expect(not any("能力〔" in l for l in logs), "不应出现任何能力结算日志")


@H.test("e6_registry_well_formed")
def t():
    """注册表条目必须用合法字段描述"""
    valid = {"san_relief", "bonus_material", "clue", "desc"}
    for name, e in ABILITY_EFFECTS.items():
        H.expect(e.get("desc"), f"{name} 应有 desc 描述")
        extra = set(e.keys()) - valid
        H.expect(not extra, f"{name} 含未知字段 {extra}")


if __name__ == "__main__":
    H.run_all()
