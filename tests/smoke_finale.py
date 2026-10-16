"""冒烟测试：规划收尾（四面镜激光炮/赏金首图鉴/兴奋剂/博士手记）"""
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import tk_stub  # noqa: E402

tk_stub.install()

from data import ConfigLoader  # noqa: E402
from model import Direction, Enemy, GameState, StoryManager  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_finaletest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── 四面镜配置：4 个赏金首必掉 ──
        assert config.items[21].name == "红镜片" and config.items[24].name == "绿镜片"
        drops = {bid: (config.enemies[config.bounties[bid].enemy_id].drop_item_id,
                       config.enemies[config.bounties[bid].enemy_id].drop_rate)
                 for bid in (5, 8, 9, 10)}  # 神秘人/弗朗/波特/沙漠之舟
        for bid, (did, rate) in drops.items():
            assert did in (21, 22, 23, 24) and rate == 1.0, \
                f"赏金首 {bid} 应必掉镜片: {did}@{rate}"
        laser = config.get_weapon_by_id(14)
        assert laser is not None and laser.attack == 500 and laser.price == 0, \
            "4342 激光炮应存在且不可购买"

        vm = GameViewModel(config)
        vm.command_new_game(1)
        d = vm.data
        from model import Item

        # ── 合成前：集不齐静默 ──
        d.inventory = [Item(config.items[22])]
        vm.command_start_dialog(config.npcs[10])
        assert not any("四面镜" in m for m in d.log_messages), "集不齐不应合成"

        # ── 合成：集齐四片 + 主炮孔有位（吉普车主炮孔 0 → 需要先开孔）──
        v = d.current_vehicle
        assert not v.can_equip(config.get_weapon_by_id(14)), "野驴无主炮孔应装不下"
        d.gold = 99999
        d.state = GameState.GARAGE
        vm.command_mod_action(1)  # 开主炮孔
        assert v.can_equip(config.get_weapon_by_id(14))
        d.inventory = [Item(config.items[i]) for i in (21, 22, 23, 24)]
        d.state = GameState.TOWN
        vm.command_start_dialog(config.npcs[10])
        assert any("4342" in m for m in d.log_messages), "应合成激光炮"
        assert any(w.id == 14 for w in v.main_weapons), "激光炮应装上主炮"
        assert all(it.id not in (21, 22, 23, 24) for it in d.inventory), \
            "镜片应被消耗"
        assert v.attack == 500 + 40, f"战车攻击应为激光炮500+15机关炮40: {v.attack}"

        # ── 兴奋剂战斗实装 ──
        vm.command_new_game(1)
        d = vm.data
        d.state = GameState.BATTLE
        d.current_enemy = Enemy(config.enemies[18])  # 千血敌人
        d.inventory = [Item(config.items[3])]  # 兴奋剂 +20%
        atk_before = d.player.attack
        vm.command_use_item(0)
        assert abs(d.player.attack - atk_before * 1.2) <= 1, \
            f"兴奋剂应 +20% 攻击: {d.player.attack} vs {atk_before}"

        # ── 博士手记：章节解锁 ──
        d.story_chapter = 2
        note = StoryManager.handnote_text(2)
        assert "大破坏" in note and "造梦者" in note, "3 篇应解锁"
        assert "红狼》" not in note, "第 5 篇未解锁"
        d.story_chapter = 6
        note = StoryManager.handnote_text(6)
        assert "红狼" in note, "通关应全解锁"

        # ── 赏金首档案图鉴 ──
        d.bounty_claimed.add(1)
        codex = vm._render_codex()
        assert "赏金首档案" in codex and "水怪" in codex and "在逃" in codex

        print("SMOKE OK: 规划收尾（四面镜/兴奋剂/手记/档案）全部通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
