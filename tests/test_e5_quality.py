# tests/test_e5_quality.py
# E5 扮演质量维度（纯逻辑，不依赖 tkinter）：
#   - perform_action(action, quality) 按主动/被动/背离施加不同权重
#   - digestion_ratio 为所需行为的加权均值
#   - action_weight 可随角色序列化往返
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from sequences import make_sequence
from anchor import Anchor
from gui.state import GUIState


@H.test("e5_quality_weights")
def t():
    """同一行为用不同质量表演，累积权重不同"""
    ch = make_sequence("error", 9)
    ch.perform_action("偷窃", "active")      # +1.0
    ch.perform_action("偷窃", "passive")      # +0.5
    ch.perform_action("偷窃", "divergent")    # -0.5
    w = ch.action_weight["偷窃"]
    H.expect(abs(w - 1.0) < 1e-9, f"偷窃 权重应为 1.0（1+0.5-0.5），实际 {w}")
    H.expect(len(ch.digestion_actions) == 3, "应记录 3 次表演历史")
    # 主动一次即视为该行为完全消化（权重>=1.0）
    ch2 = make_sequence("error", 9)
    ch2.perform_action("潜入", "active")
    H.expect(ch2.action_weight["潜入"] == 1.0, "主动一次权重应为 1.0")


@H.test("e5_digestion_ratio_weighted")
def t():
    """消化度为所需行为的加权均值；全部主动 → 完全消化"""
    ch = make_sequence("error", 9)
    H.expect(ch.digestion_ratio == 0.0, "初始消化度应为 0")
    # 被动表演一个行为 → 仅 0.5 权重
    one = next(iter(ch.required_actions))
    ch.perform_action(one, "passive")
    n = len(ch.required_actions)
    H.expect(abs(ch.digestion_ratio - 0.5 / n) < 1e-9,
             f"单个被动应得 0.5/{n} 消化度，实际 {ch.digestion_ratio}")
    # 补全其余行为（主动）→ 完全消化
    for a in ch.required_actions:
        ch.perform_action(a, "active")
    H.expect(ch.digested, "全部主动表演后应完全消化")


@H.test("e5_quality_serialized")
def t():
    """action_weight 随 to_dict/from_dict 往返，消化度一致"""
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=60, connections=4, name="q")
    ch.perform_action("偷窃", "active")
    ch.perform_action("潜入", "passive")
    d = ch.to_dict()
    H.expect("action_weight" in d, "存档应含 action_weight")

    ch2 = make_sequence("error", 9)
    ch2.anchor = Anchor(humanity=60, connections=4, name="q")
    # 直接走 Sequence.from_dict
    from sequences import Sequence
    ch3 = Sequence.from_dict(d)
    H.expect(abs(ch3.digestion_ratio - ch.digestion_ratio) < 1e-9, "往返后消化度应一致")
    H.expect(ch3.action_weight.get("偷窃") == 1.0, "偷窃 权重应恢复为 1.0")
    H.expect(abs(ch3.action_weight.get("潜入", 0) - 0.5) < 1e-9, "潜入 权重应恢复为 0.5")


if __name__ == "__main__":
    H.run_all()
