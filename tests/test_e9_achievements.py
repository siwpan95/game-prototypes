# tests/test_e9_achievements.py
# 成就 / 图鉴 / 多结局（E9）纯逻辑单测。
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from sequences import make_sequence
from pollution import PollutionSource
from rivals import RivalSystem
from achievements import (AchievementSystem, CodexSystem, ACHIEVEMENTS,
                          evaluate_achievements, record_codex, evaluate_ending)


def _state(**kw):
    st = types.SimpleNamespace()
    st.character = kw.get("character")
    st.old_one_info = kw.get("old_one_info")
    st.factions = kw.get("factions", {})
    st.seen_events = kw.get("seen_events", set())
    st.event_log = kw.get("event_log", [])
    st.achievements = AchievementSystem()
    st.codex = CodexSystem()
    st.rival_system = kw.get("rival_system")
    return st


@H.test("e9_first_step_achievement")
def t():
    """执行过扮演行为应解锁「第一步」。"""
    ch = make_sequence("error", 9)
    ch.perform_action("偷窃")
    st = _state(character=ch)
    new = evaluate_achievements(st)
    H.expect("第一步" in new, "应解锁第一步")
    H.expect(st.achievements.is_unlocked("first_step"), "first_step 应已记录")


@H.test("e9_true_god_achievement")
def t():
    """成为序列0 应解锁「真神登临」。"""
    ch = make_sequence("error", 0)
    st = _state(character=ch)
    new = evaluate_achievements(st)
    H.expect("真神登临" in new, "应解锁真神登临")


@H.test("e9_first_loss_achievement")
def t():
    """污染达到失控应解锁「第一次失控」。"""
    ch = make_sequence("error", 9)
    ch.pollution.accumulate(PollutionSource("acting", 5.0))
    st = _state(character=ch)
    new = evaluate_achievements(st)
    H.expect("第一次失控" in new, "应解锁第一次失控")


@H.test("e9_codex_records")
def t():
    """图鉴应记录已见序列 / 能力 / 事件。"""
    ch = make_sequence("error", 9)
    st = _state(character=ch, seen_events={"测试事件"})
    record_codex(st)
    n_seq, _ = st.codex.sequence_progress()
    H.expect(n_seq >= 1, "应记录已见序列")
    H.expect("测试事件" in st.codex.events, "应记录已见事件")
    H.expect(len(st.codex.abilities) > 0, "应记录已见能力")


@H.test("e9_ending_evaluation")
def t():
    """多结局应随状态正确判定。"""
    ch = make_sequence("error", 0)
    st = _state(character=ch)
    H.expect(evaluate_ending(st)[0] == "true_god", "序列0 → 真神登临")
    ch2 = make_sequence("error", 9)
    ch2.pollution.accumulate(PollutionSource("acting", 5.0))
    st2 = _state(character=ch2)
    H.expect(evaluate_ending(st2)[0] == "loss", "失控 → 失控沉沦")


@H.test("e9_serialization")
def t():
    """成就 / 图鉴应可序列化还原。"""
    ch = make_sequence("error", 9)
    ch.perform_action("偷窃")
    st = _state(character=ch, seen_events={"测试事件"})
    evaluate_achievements(st)
    record_codex(st)
    a2 = AchievementSystem.from_dict(st.achievements.to_dict())
    H.expect(a2.is_unlocked("first_step"), "成就应可还原")
    c2 = CodexSystem.from_dict(st.codex.to_dict())
    H.expect(len(c2.sequences) == len(st.codex.sequences), "图鉴序列应可还原")
    H.expect(c2.events == st.codex.events, "图鉴事件应可还原")
