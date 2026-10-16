"""冒烟测试：P2 剧情与内容（T3.1-T3.6 验收）

覆盖：12 张地图与简介、NPC 对话树条件分支、章节状态机推进
（1-6 章全链路）、怪物图鉴击破数、新支线任务目标配置、
剧情与车库/击破数存档往返。
"""
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
from model import (  # noqa: E402
    Direction, GameState, Enemy, StoryManager, MapManager,
)
from viewmodel import GameViewModel  # noqa: E402


def walk_onto_bounty(vm, x, y):
    d = vm.data
    d.player_x, d.player_y = x, y - 1
    vm.command_move(Direction.DOWN)


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_p2test_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── T3.1 十二张地图 ──
        assert len(config.maps) == 12, f"应有 12 张地图: {len(config.maps)}"
        assert len(config.npcs) == 14, f"应有 14 个NPC: {len(config.npcs)}"
        assert len(config.shops) == 5 and len(config.quests) == 8
        assert config.maps[12].name == "神殿废墟"
        assert "诺亚" in config.maps[12].intro, "神殿废墟应有简介文案"
        # 城镇首访简介
        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data
        d.state = GameState.TOWN
        d.current_map_id = 2
        vm.command_leave_town()
        vm.command_interact()  # 走到伊尔镇入口
        vm.command_interact()
        # 直接进镇验证 intro（用一个没去过的镇）
        from model import MapManager
        vm._enter_map(7)  # 帕特港
        assert any("帕特港" in m and "干船坞" in m for m in d.log_messages), \
            "首访应显示城镇简介"
        assert f"visited_map_7" in d.story_flags

        # ── T3.4 对话树条件分支 ──
        npc_graem = config.npcs[1]  # 村长
        assert len(npc_graem.dialogs) == 3, "村长应有 3 段对话"
        d.story_chapter = 0
        assert vm._pick_npc_dialog(npc_graem).startswith("欢迎来到伊尔镇"), \
            "0 章应显示默认段"
        d.story_chapter = 1
        assert "红狼夺走了你的副炮" in vm._pick_npc_dialog(npc_graem), \
            "1 章后应显示红狼段"
        d.story_chapter = 3
        assert "戈麦斯" in vm._pick_npc_dialog(npc_graem), "3 章后应显示英雄段"

        # ── T3.2/T3.3 章节状态机全链路 ──
        vm.command_new_game(1)
        d = vm.data
        assert d.story_chapter == 0

        # 第 1 章：首次遭遇赏金首
        walk_onto_bounty(vm, 0, 25)
        assert d.story_chapter == 1, "首次遭遇应推进到第 1 章"
        assert any("红狼" in m for m in d.log_messages), "应有红狼夺炮文案"
        # 击杀水怪（未接取 → defeated 待领）
        d.current_enemy.hp = 1
        vm.command_attack()
        assert d.state != GameState.BATTLE

        # 第 2 章：首次领取悬赏（水怪悬赏补领）
        d.state = GameState.TOWN
        vm.command_bounty_interact(0)
        assert d.story_chapter == 2, "首次领赏应推进到第 2 章"
        vm.command_handle_escape()
        vm.command_leave_town()

        # 第 3 章：击败戈麦斯
        walk_onto_bounty(vm, 8, 28)
        assert d.current_enemy.name == "戈麦斯"
        d.current_enemy.hp = 1
        vm.command_attack()
        assert d.story_chapter == 3, "击败戈麦斯应推进到第 3 章"
        assert 6 in d.owned_vehicle_ids, "应继承红狼战车"
        assert any("继承" in m or "红狼的意志" in m for m in d.log_messages)
        assert any("红狼之死" in m or "没人给他钱" in m for m in d.log_messages), \
            "应有红狼之死文案"

        # 第 4 章：与文徇对话
        d.current_map_id = 11
        npc_scholar = None
        for n in config.npcs.values():
            if n.id == 10:
                npc_scholar = n
        vm.command_start_dialog(npc_scholar)
        assert d.story_chapter == 4, "与文徇对话应推进到第 4 章"
        vm.command_handle_escape()

        # 第 5 章：红狼战车 + 等级达标（战斗结束检测）
        d.player.level = StoryManager.LEVEL_GATE
        vm.command_leave_town()  # 从霍卢夫镇回荒野
        walk_onto_bounty(vm, 42, 6)  # 沙漠之舟（随便一场战斗结束）
        d.current_enemy.hp = 1
        vm.command_attack()
        assert d.story_chapter == 5, "红狼战车+等级应推进到第 5 章"

        # 第 6 章：击杀诺亚碎片
        d.state = GameState.BATTLE
        d.current_enemy = Enemy(config.enemies[8])  # 诺亚碎片
        d.current_enemy.hp = 1
        vm.command_attack()
        assert d.story_chapter == 6, "击杀诺亚碎片应推进到第 6 章"
        assert any("履带印" in m for m in d.log_messages), "应有终章文案"

        # ── T3.6 图鉴 ──
        assert d.enemy_kills.get(9, 0) >= 1, "击破数应记录水怪"
        assert d.enemy_kills.get(15, 0) >= 1, "击破数应记录戈麦斯"
        codex = vm._render_codex()
        assert "水怪" in codex and "戈麦斯" in codex and "？？？" in codex, \
            "图鉴应有击破记录与未遭遇占位"

        # ── 剧情与车库/击破数存档往返 ──
        d.state = GameState.WORLD
        assert vm.command_save(1)
        vm.command_new_game()
        vm.command_load(1)
        assert vm.data.story_chapter == 6, "读档后章节应保留"
        assert 6 in vm.data.owned_vehicle_ids, "读档后车库应保留"
        assert vm.data.enemy_kills.get(9, 0) >= 1, "读档后击破数应保留"

        # ── T3.5 新支线目标配置 ──
        q5 = config.quests[5]
        assert q5.name == "迷之项圈" and q5.target_id == 20 and q5.type == "collect"
        q6 = config.quests[6]
        assert q6.name == "诺亚的碎片" and q6.target_id == 7 and q6.type == "kill"
        q8 = config.quests[8]
        assert q8.name == "军医的托付" and q8.target_id == 15 and q8.type == "collect"
        assert config.items[20].name == "宠物项圈"
        assert config.enemies[3].drop_item_id == 20, "装甲虫应掉落宠物项圈"

        print("SMOKE OK: P2 剧情与内容全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def BountyManager_status(data, bounty_id):
    from model import BountyManager
    return BountyManager.status(data, bounty_id)


if __name__ == "__main__":
    main()
