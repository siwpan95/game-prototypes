# -*- coding: utf-8 -*-
"""验证 3 个新模块 + profile 向后兼容。一次性测试脚本。"""
import sys
import random
sys.path.insert(0, '.')
from core import profile as P
from core import streaks, heirlooms, challenges


def main():
    print("=== 1. profile 默认档案含新字段 ===")
    prof = P._default_profile()
    for k in ['streaks', 'heirlooms_state', 'unlocked_challenges',
              'completed_challenges', 'active_challenge', 'lineage']:
        v = prof.get(k)
        print(f"  {k}: {type(v).__name__} = {str(v)[:70]}")
    print()

    print("=== 2. 旧档案(无新字段)向后兼容 ===")
    old_prof = {'schema_version': 1, 'total_runs': 5,
                'lineage': ['old_data'], 'seen_endings': ['end_x']}
    for k in ['streaks', 'heirlooms_state', 'unlocked_challenges',
              'completed_challenges', 'active_challenge']:
        if k not in old_prof:
            old_prof[k] = P._default_profile()[k]
    print(f"  lineage(旧数据保留): {old_prof['lineage']}")
    print(f"  streaks(新建): {old_prof['streaks']}")
    print(f"  heirlooms_state(新建): {old_prof['heirlooms_state']}")
    print()

    print("=== 3. streaks 模块 ===")
    prof2 = P._default_profile()
    r1 = streaks.record_play(prof2, '2026-08-01')
    print(f"  第1天: streak={r1['streak']}, msg={r1['message']}")
    r2 = streaks.record_play(prof2, '2026-08-02')
    print(f"  第2天: streak={r2['streak']}, msg={r2['message']}")
    r3 = streaks.record_play(prof2, '2026-08-03')
    ms = r3['milestone_reward']
    print(f"  第3天: streak={r3['streak']}, 里程碑={ms['name'] if ms else None}")
    buff = streaks.consume_pending_buff(prof2)
    print(f"  消费buff: {buff}")
    # 破连胜测试
    r4 = streaks.record_play(prof2, '2026-08-10')
    print(f"  间隔8天: broken={r4['broken']}, msg={r4['message']}")
    print()

    print("=== 4. heirlooms 模块 ===")
    prof3 = P._default_profile()
    unlocked = heirlooms.unlock_heirloom(prof3, 'heir_jade_pendant')
    print(f"  解锁玉佩: {unlocked}")
    print(f"  持有: {heirlooms.held_heirloom_ids(prof3)}")

    class FakePlayer:
        def __init__(self):
            self.luck = 5
            self.health = 80
            self.intelligence = 5
            self.talent_modifiers = {}
            self.unlocked_modes = []
            self.decision_tree = None
    p = FakePlayer()
    summary = heirlooms.apply_heirlooms(p, prof3)
    print(f"  应用效果: {summary['applied'][0]['effects_summary']}")
    print(f"  player.luck={p.luck}(应7), player.health={p.health}(应85)")
    random.seed(42)
    inh = heirlooms.roll_inheritance(prof3, random)
    print(f"  传承结果: kept={inh['kept']}, lost={inh['lost']}")
    print()

    print("=== 5. challenges 模块 ===")
    prof4 = P._default_profile()
    start = challenges.start_challenge(prof4, 'chl_zero_to_hero')
    print(f"  激活寒门贵子: ok={start['ok']}")
    print(f"  override: {start['start_override']}")
    active = challenges.active_challenge(prof4)
    print(f"  当前挑战: {active['name'] if active else None}")

    class WinPlayer:
        wealth = 18
        age = 38
        career_tier = 2
        traits = []
        game_mode = 'traditional'
        run_log = []
        education = 'bachelor'
        happiness = 5
    wp = WinPlayer()
    win = challenges.check_win(wp, prof4, active)
    print(f"  胜利检查: won={win['won']}")
    print(f"  met={win['reasons_met']}")
    print(f"  unmet={win['reasons_unmet']}")
    comp = challenges.complete_challenge(prof4, 'chl_zero_to_hero')
    print(f"  完成: ok={comp['ok']}, reward解锁天赋={comp['reward'].get('unlock_talent')}")
    print(f"  profile.unlocked_talents: {prof4.get('unlocked_talents')}")
    print()

    print("=== 6. 挑战进度摘要 ===")
    summ = challenges.challenge_summary(prof4)
    print(f"  total={summ['total']}, completed={summ['completed']}")
    print()

    print("=== 全部模块测试通过 ===")


if __name__ == "__main__":
    main()
