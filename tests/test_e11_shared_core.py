# tests/test_e11_shared_core.py
# CLI↔GUI 共享核心（E11）单测：GameSession 承载 P2 系统（对手/成就/图鉴）的
# 序列化 roundtrip，以及 main.run_journey_demo 用同一引擎跑通完整养成循环。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.state import GUIState
from sequences import make_sequence
from rivals import RivalSystem
from achievements import record_codex, evaluate_achievements
from save_load import GameSession


@H.test("e11_gamesession_roundtrip_with_p2")
def t():
    """GameSession 应完整序列化还原 对手/成就/图鉴。"""
    st = GUIState()
    st.character = make_sequence("error", 9)
    st.character.perform_action("偷窃")
    st.rival_system = RivalSystem(seed=3)
    st.rival_system.add_rival("fool", start_level=1)
    st.rival_system.tick(2)
    record_codex(st)
    evaluate_achievements(st)

    sess = GameSession.from_state(st)
    sess2 = GameSession.from_dict(sess.to_dict())
    st2 = GUIState()
    sess2.apply_to_state(st2)

    H.expect(st2.character.LEVEL == st.character.LEVEL, "角色等级应一致")
    H.expect(st2.rival_system.count() == st.rival_system.count(), "对手数应一致")
    H.expect(st2.achievements.progress() == st.achievements.progress(), "成就进度应一致")
    H.expect(st2.codex.sequence_progress() == st.codex.sequence_progress(), "图鉴进度应一致")


@H.test("e11_journey_demo_runs")
def t():
    """main.run_journey_demo 应跑通完整养成循环并返回合理汇总。"""
    import main
    summary = main.run_journey_demo()
    H.expect(summary["level"] <= 8, "旅程应完成至少一次晋升")
    H.expect(summary["rival_count"] >= 1, "应至少有一名 AI 对手")
    H.expect(summary["achievements"][0] >= 1, "应至少解锁 1 项成就")
    H.expect(summary["codex_sequences"][0] >= 1, "图鉴应记录已见序列")
