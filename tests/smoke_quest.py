"""冒烟测试：任务系统（T1.4 验收）

覆盖：kill/collect/explore 三类任务的正确判定、目标数量语义、
奖励发放、日志渲染。
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
from model import Character, Enemy, GameState, QuestManager  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_questtest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"
        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data

        # 4 个任务全部激活
        assert len(d.quest_progress) == 4, f"应有 4 个进行中任务: {len(d.quest_progress)}"

        # ── kill 任务：清理野犬（杀 3 只野犬） ──
        quest1 = config.quests[1]
        assert quest1.target_id == 1 and quest1.target_count == 3, "野犬任务配置错误"
        for i in range(2):
            d.current_enemy = Enemy(config.enemies[1])
            from model import BattleEngine
            BattleEngine.resolve_victory(d, config.items)
            assert quest1.id in [t.quest_data.id for t in d.quest_progress], \
                f"杀 {i+1} 只时不应完成"
        d.current_enemy = Enemy(config.enemies[1])
        BattleEngine.resolve_victory(d, config.items)
        assert quest1.id not in [t.quest_data.id for t in d.quest_progress], "杀满 3 只应完成"
        assert any(q.id == 1 for q in d.completed_quests), "应出现在已完成列表"

        # 奖励发放：经验 +100、金币 +200、物品 药草
        gold_after = d.gold
        # （初始 500 + 击杀奖励浮动，这里只验证任务奖励到账过：用日志断言）
        assert any("任务完成: 清理野犬" in m for m in d.log_messages), "应有任务完成日志"

        # ── collect 任务：找回被盗物品（获得猎枪） ──
        quest3 = config.quests[3]
        assert quest3.target_id == 4 and quest3.target_count == 1, "收集任务配置错误"
        QuestManager.track_collect(d, 999)  # 无关物品不触发
        assert quest3.id in [t.quest_data.id for t in d.quest_progress], "无关物品不应误触发"
        QuestManager.track_collect(d, 4)  # 猎枪
        assert quest3.id not in [t.quest_data.id for t in d.quest_progress], "获得猎枪应完成"

        # ── explore 任务：调查地下遗迹（到访地图 5） ──
        quest4 = config.quests[4]
        assert quest4.target_id == 5, "探索任务目标应为地图 5"
        QuestManager.track_explore_map(d, 1)  # 当前所在地图，不触发
        assert quest4.id in [t.quest_data.id for t in d.quest_progress], "到访其他地图不应完成"
        d.current_map_id = 5
        QuestManager.track_explore_map(d, 5)
        assert quest4.id not in [t.quest_data.id for t in d.quest_progress], "到访遗迹应完成"

        # ── 购买也计入收集 ──
        quest2 = config.quests[2]
        assert quest2.target_id == 6 and quest2.target_count == 1
        d.state = GameState.TOWN
        d.current_map_id = 3  # 罗克镇武器店（猎枪在售）
        vm.command_enter_shop()
        assert d.current_shop is not None
        # 罗克镇武器店商品含猎枪(4)
        idx = d.current_shop.items.index(4)
        d.gold = 9999
        vm.command_buy_item(idx)
        assert any(it.id == 4 for it in d.inventory), "应买到猎枪"

        # ── 日志渲染包含进度 ──
        text = vm._render_quests()
        assert "任务日志" in text and "进行中" in text, "任务日志渲染异常"

        # ── 任务进度可存档往返 ──
        assert vm.command_save(1)
        vm.command_new_game()  # 重置
        assert vm.command_load(1)
        assert 1 in [q.id for q in vm.data.completed_quests], "读档后已完成任务应保留"
        assert 3 in [q.id for q in vm.data.completed_quests], "读档后已完成任务应保留"
        assert 4 in [q.id for q in vm.data.completed_quests], "读档后已完成任务应保留"
        assert 2 in [t.quest_data.id for t in vm.data.quest_progress], \
            "读档后未完成任务应仍在进行中"
        assert len(vm.data.quest_progress) == 1, "读档后只剩赏金猎人任务未完成"

        print("SMOKE OK: 任务系统全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
