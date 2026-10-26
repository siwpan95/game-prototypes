"""Headless self-check for the Smile skinner-box logic.

Only the logic layer is exercised: reward probability/pity, milestones,
result -> expression mapping, and the persisted check-in state.  ``app.py`` /
``ui`` are never imported, and pygame is only imported transitively by the
``core`` package (no display or mixer initialisation, so no window/audio).

Run from the project root::

    python selfcheck.py
"""
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.achievements import all_milestones, check_new_milestones
from core.expression_map import result_to_expression
from core.qiandao import (
    QiandaoState, pity_adjusted_prob, reinforcement_prob,
)


def check_probability_curve():
    p_empty = reinforcement_prob(0, 0)
    if not 0.02 <= p_empty <= 0.05:
        raise AssertionError("empty-state probability is out of range")
    if not (reinforcement_prob(10, 10) > reinforcement_prob(5, 5) > p_empty):
        raise AssertionError("probability does not rise with n and c")
    if reinforcement_prob(20, 5) <= reinforcement_prob(5, 5):
        raise AssertionError("probability does not rise with total pulls")
    if reinforcement_prob(5, 20) <= reinforcement_prob(5, 5):
        raise AssertionError("probability does not rise with streak")

    base, soft, hard = pity_adjusted_prob(0.10, 0)
    if (base, soft, hard) != (0.10, False, False):
        raise AssertionError("no-pity probability should equal the base")
    boosted, in_soft, hard = pity_adjusted_prob(0.10, 3)
    if not in_soft or hard or boosted <= 0.10:
        raise AssertionError("soft pity did not boost the probability")
    final, in_soft, hard = pity_adjusted_prob(0.10, 6)
    if final != 1.0 or not hard or not in_soft:
        raise AssertionError("hard pity must be 100%")


def check_milestones():
    unlocked = set()
    first = check_new_milestones(3, 3, unlocked)
    if [m["id"] for m in first] != ["streak_3"]:
        raise AssertionError("streak_3 milestone did not fire alone")
    if check_new_milestones(3, 3, unlocked):
        raise AssertionError("milestones fired twice")
    second = check_new_milestones(10, 7, unlocked)
    if [m["id"] for m in second] != ["streak_7", "total_10"]:
        raise AssertionError("milestone set at n=10,c=7 is %s" % second)
    if len(all_milestones()) != 10:
        raise AssertionError("unexpected milestone catalogue size")


def check_expression_mapping():
    reward = {"reinforced": True, "reward": {"rarity": "传说"}}
    if result_to_expression(reward) != "surprised":
        raise AssertionError("legendary rarity did not map to surprised")
    unknown = {"reinforced": True, "reward": {"rarity": "???"}}
    if result_to_expression(unknown) != "happy":
        raise AssertionError("unknown rarity should fall back to happy")

    expected = {1: "bored", 2: "disappointed", 3: "sad",
                4: "sad", 5: "worried", 8: "annoyed", 12: "angry"}
    for streak, expr in expected.items():
        got = result_to_expression({"reinforced": False, "no_reward_streak": streak})
        if got != expr:
            raise AssertionError("no-reward streak %d mapped to %s" % (streak, got))


def check_pity_sign_and_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        st = QiandaoState(tmp)
        if st.n != 0 or st.c != 0 or st.freezes != 1:
            raise AssertionError("fresh check-in state is wrong")
        if not st.can_sign_today():
            raise AssertionError("a new player should be able to sign today")

        st.no_reward_streak = 6  # hard pity is guaranteed on the next sign
        result = st.sign()
        if not result["reinforced"] or not result["pity_triggered"]:
            raise AssertionError("hard pity did not force a reward")
        if result["prob"] != 1.0:
            raise AssertionError("hard-pity probability was not 1.0")
        if st.n != 1 or st.c != 1 or st.no_reward_streak != 0:
            raise AssertionError("sign did not advance n/c or reset the streak")
        if result["reward"]["name"] != "神秘奖励":
            raise AssertionError("empty reward pool should use the fallback reward")
        if not st.history or not st.history[-1]["reinforced"]:
            raise AssertionError("sign result was not written to history")
        if st.can_sign_today():
            raise AssertionError("today's sign should be recorded in last_sign_date")
        stats = st.get_stats()
        if stats["reward_count"] != 1 or stats["reward_rate"] != 1.0:
            raise AssertionError("stats do not reflect the single successful sign")

        reloaded = QiandaoState(tmp)
        if (reloaded.n, reloaded.c, reloaded.best_c) != (1, 1, 1):
            raise AssertionError("check-in counters were not persisted")
        if len(reloaded.history) != 1:
            raise AssertionError("check-in history was not persisted")


def check_streak_freeze():
    with tempfile.TemporaryDirectory() as tmp:
        st = QiandaoState(tmp)
        st.c = 5
        st.freezes = 1
        st.last_sign_date = (date.today() - timedelta(days=2)).isoformat()
        result = st.sign()
        if not result["freeze_used"]:
            raise AssertionError("missing one day did not consume a freeze")
        if st.freezes != 0 or st.c != 6:
            raise AssertionError("freeze did not preserve the streak")
        if st.best_c < 6:
            raise AssertionError("best streak was not raised")

        st.freezes = 0
        st.c = 10
        st.last_sign_date = (date.today() - timedelta(days=3)).isoformat()
        result = st.sign()
        if result["freeze_used"]:
            raise AssertionError("freeze was used with no cards left")
        if st.c != 1:
            raise AssertionError("a >1-day gap must reset the streak to 1")


def main():
    try:
        check_probability_curve()
        check_milestones()
        check_expression_mapping()
        check_pity_sign_and_persistence()
        check_streak_freeze()
    except Exception as exc:  # noqa: BLE001 - report, never traceback-crash
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        return 1
    print("selfcheck ok: reward probability curve + soft/hard pity, milestones, "
          "result->expression map, check-in persistence, streak freeze/reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
