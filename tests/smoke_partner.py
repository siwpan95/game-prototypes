"""冒烟测试：T6 伙伴系统 / 秘密商人基地 / 战斗音效"""
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
    tmp_dir = tempfile.mkdtemp(prefix="maga_t6test_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── 伙伴配置 ──
        assert len(config.partners) == 2
        p1, p2 = config.partners[1], config.partners[2]
        assert p1.effect_type == "repair" and p1.recruit_npc == 8
        assert p2.effect_type == "foot_atk" and p2.recruit_npc == 15
        assert config.get_partner_by_npc(15) is p2
        assert len(config.maps) == 13, f"应有 13 张地图: {len(config.maps)}"
        assert config.maps[13].name == "秘密基地" and config.maps[13].is_town
        assert len(config.shops) == 6, "秘密商店应存在"
        secret = [s for s in config.shops.values() if s.map_id == 13][0]
        assert 26 in secret.items and 27 in secret.items, "独占商品应上架"
        assert config.items[26].name == "火箭筒Ⅱ" and config.items[26].effect_value == 65

        vm = GameViewModel(config)
        vm.command_new_game(1)
        d = vm.data

        # ── 招募条件：章节不够不招 ──
        d.current_map_id = 9
        vm.command_start_dialog(config.npcs[8])  # 克里夫（卡拉镇）
        assert 1 not in d.partners, "章节不足不应招募"
        vm.command_handle_escape()

        # ── 招募机械师（chapter 2）──
        d.story_chapter = 2
        vm.command_start_dialog(config.npcs[8])
        assert 1 in d.partners, "应招募机械师"
        vm.command_handle_escape()

        # ── 机械师战后小修 ──
        v = d.current_vehicle
        v.armor_plates = 10
        v.hp = int(v.max_hp * 0.5)
        hp_before = v.hp
        d.state = GameState.BATTLE
        d.current_enemy = Enemy(config.enemies[9])
        d.current_enemy.hp = 1
        vm.command_attack()  # 击杀 → _end_battle → 修车
        assert v.armor_plates == 15, f"战后应+5装甲片: {v.armor_plates}"
        assert v.hp > hp_before, "战后应恢复 10% HP"

        # ── 招募格斗家 + 步行攻击加成 ──
        d.current_map_id = 10
        vm.command_start_dialog(config.npcs[15])  # 退伍老兵·陈
        assert 2 in d.partners, "应招募格斗家"
        assert d.player.foot_atk_mult == 1.25, "步行攻击加成应同步"
        # 步行伤害验证（固定 seed 保证同 roll 对比）
        d.state = GameState.BATTLE
        d.player.combat_on_foot = True
        d.player.vehicle = None
        d.current_enemy = Enemy(config.enemies[1])  # 野犬 30HP
        import random
        import model.battle as bm
        base = d.player.attack
        random.seed(7)
        dmg = bm.BattleEngine.calculate_damage(d.player, d.current_enemy)
        d.player.foot_atk_mult = 1.0
        random.seed(7)
        dmg_nof = bm.BattleEngine.calculate_damage(d.player, d.current_enemy)
        assert dmg > dmg_nof, f"加成应提升伤害: {dmg} vs {dmg_nof}"

        # ── 存档往返：伙伴持久化 ──
        d.state = GameState.WORLD
        d.player.combat_on_foot = False
        d.player.vehicle = v
        assert vm.command_save(1)
        vm.command_new_game()
        vm.command_load(1)
        d = vm.data  # command_load 会替换 data 对象，必须重新取引用
        assert vm.data.partners == {1, 2}, f"读档后伙伴应保留: {vm.data.partners}"
        assert vm.data.player.foot_atk_mult == 1.25, "读档后加成应重算"

        # ── 秘密基地：远坐标入口可达 ──
        d.current_map_id = 1  # 回荒野（存档时在迪斯顿有限地图内）
        d.player_x, d.player_y = 60, 59
        vm.command_move(Direction.DOWN)
        vm.command_interact()
        assert d.current_map_id == 13, "应进入秘密基地"
        d.state = GameState.TOWN
        vm.command_enter_shop()
        assert d.current_shop is not None and d.current_shop.map_id == 13, \
            "秘密商人应可交易"

        # ── 手记全解锁（通关）──
        note = StoryManager.handnote_text(6)
        assert "红狼" in note and "已解密 5/5" in note

        # ── 音效文件 ──
        for name in ("encounter", "victory", "defeat", "levelup", "hit"):
            p = os.path.join(REPO_ROOT, "assets", "sfx", f"{name}.wav")
            assert os.path.exists(p) and os.path.getsize(p) > 1000, \
                f"音效缺失: {name}"

        print("SMOKE OK: 伙伴/秘密基地/音效/手记 全部通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
