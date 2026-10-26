"""
Progress Quest Multiverse - 主题化游戏引擎

主题数据由 theme_loader 从 JSON 文件自动加载，
新增主题只需在 themes/data/ 放入 JSON 文件，无需修改代码。
"""

import sys
import os
import threading
import time
import random

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))  # 当前在 src/core/
src_path = os.path.dirname(src_path)                   # 上一级即为 src/
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from core.game_engine_v2 import GameEngine, Character, Item, Monster, Quest, GameState
from themes.theme_loader import get_theme, list_theme_ids, list_theme_names, discover_themes


class ThemedGameEngine(GameEngine):
    """主题化游戏引擎

    主题数据来自 JSON 文件（themes/data/*.json），
    通过 theme_loader 自动发现和加载，类似 mod 管理器。
    """

    @classmethod
    def list_themes(cls):
        """列出所有可用主题 ID"""
        return list_theme_ids()

    @classmethod
    def get_theme_display_name(cls, theme_name):
        """获取主题显示名称"""
        names = list_theme_names()
        return names.get(theme_name, theme_name)

    @classmethod
    def get_theme_labels(cls, theme_name):
        """获取主题的自定义标签（race_label 等）"""
        info = discover_themes().get(theme_name, {})
        return {
            'race_label': info.get('race_label', '种族'),
            'class_label': info.get('class_label', '职业'),
            'monster_label': info.get('monster_label', '怪物'),
        }

    def __init__(self, theme_name="warcraft"):
        super().__init__()
        self.theme_name = theme_name

        # 父类 _init_game_data 加载的默认数据在主题模式下完全冗余，清空
        self.monsters = []
        self.shop_items = []

        # 通过加载器从 JSON 加载主题
        self.theme = self.load_theme(theme_name)
        if not self.theme:
            raise ValueError(f"无法加载主题: {theme_name}")

        # 将主题商店物品转换为引擎 Item，交给父类 _buy_equipment 统一处理
        self.shop_items = [
            Item(
                name=item_data.name,
                value=item_data.value,
                item_type=item_data.item_type,
                stat_bonus=dict(item_data.stat_bonus),
                count=item_data.count,
                level=item_data.level
            )
            for item_data in self.theme.get_shop_items()
        ]

        self.log(f"🎮 已加载主题: {self.theme.name}")
        self.log(self.theme.get_theme_description())

    @classmethod
    def load_theme(cls, theme_name: str):
        """加载主题数据（不创建引擎实例，供开始界面使用）

        通过 theme_loader 从 JSON 文件加载，带缓存。
        """
        return get_theme(theme_name)
    
    def create_character(self, name: str, race: str, char_class: str):
        """创建角色（使用主题数据）"""
        # 验证种族和职业
        if race not in self.theme.races:
            raise ValueError(f"无效种族: {race}，可选: {', '.join(self.theme.races)}")
        
        if char_class not in self.theme.classes:
            raise ValueError(f"无效职业: {char_class}，可选: {', '.join(self.theme.classes)}")
        
        # 创建角色
        self.character = Character(name, race, char_class)
        self.character.spell_pool = self.theme.spell_pool  # 注入主题法术池
        self.log(f"🎮 创建了新角色: {name} ({race} {char_class})")
        
        # 解锁第一章（序章已默认解锁）
        if len(self.plot_chapters) > 1:
            self.plot_chapters[1].unlocked = True
            self._current_chapter_index = 1
        
        # 初始化活跃任务列表（使用主题任务目标池）
        self.active_tasks = []
        self._populate_active_tasks()
        
        # 初始化第一个任务和怪物
        self._start_new_quest()
        self._start_new_monster()
        
        # 初始化当前行动
        self.current_action_text = f"正在准备 {self.character.name} 的冒险..."
        self.action_target_count = 1
        self.action_current_count = 0
    
    def _start_new_monster(self):
        """开始狩猎新怪物（使用主题数据）"""
        # 根据角色等级选择怪物
        monster_data = self.theme.get_random_monster(self.character.level + 2)
        if not monster_data:
            self.log("⚠️ 没有可用的怪物数据")
            return
        
        # 转换为游戏引擎的Monster对象
        loot_table = []
        for item_data, drop_chance in monster_data.loot_table:
            item = Item(
                name=item_data.name,
                value=item_data.value,
                item_type=item_data.item_type,
                stat_bonus=dict(item_data.stat_bonus),
                count=item_data.count
            )
            loot_table.append((item, drop_chance))
        
        self.current_monster = Monster(
            name=monster_data.name,
            level=monster_data.level,
            hp=monster_data.hp,
            exp_reward=monster_data.exp_reward,
            loot_table=loot_table
        )
        
        self.log(f"⚔️ 遭遇了 {self.current_monster.name}！")
    
    def _start_new_quest(self):
        """开始新任务（使用主题数据）"""
        quest_data = self.theme.get_random_quest()
        if not quest_data:
            self.log("⚠️ 没有可用的任务数据")
            return
        
        # 转换为游戏引擎的Quest对象
        reward_item = None
        if quest_data.reward_item:
            reward_item = Item(
                name=quest_data.reward_item.name,
                value=quest_data.reward_item.value,
                item_type=quest_data.reward_item.item_type,
                stat_bonus=dict(quest_data.reward_item.stat_bonus),
                count=quest_data.reward_item.count
            )
        
        self.current_quest = Quest(
            name=quest_data.name,
            description=quest_data.description,
            target_monster=quest_data.target_monster,
            target_count=quest_data.target_count,
            reward_exp=quest_data.reward_exp,
            reward_gold=quest_data.reward_gold,
            reward_item=reward_item
        )
        
        self.quest_bar.reset()
        self.log(f"📜 新任务: {self.current_quest.name}")

    def get_available_races(self) -> list:
        """获取可用种族"""
        return self.theme.races
    
    def get_available_classes(self) -> list:
        """获取可用职业"""
        return self.theme.classes
    
    def get_theme_info(self) -> str:
        """获取主题信息"""
        return self.theme.get_theme_description()

    def save_game(self, filepath: str = None):
        """便捷保存方法（默认保存到项目根目录 saves/ 下）"""
        if filepath is None:
            save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'saves')
            filepath = os.path.join(save_dir, f"{self.theme_name}_{self.character.name}.json")
        self.save(filepath)

    def load_game(self, filepath: str = None):
        """便捷加载方法（默认加载最近存档）"""
        if filepath is None:
            save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'saves')
            if not os.path.exists(save_dir):
                raise FileNotFoundError("没有存档文件")
            files = [f for f in os.listdir(save_dir) if f.startswith(self.theme_name) and f.endswith('.json')]
            if not files:
                raise FileNotFoundError("没有存档文件")
            filepath = os.path.join(save_dir, sorted(files, key=lambda x: os.path.getmtime(os.path.join(save_dir, x)), reverse=True)[0])
        self.load(filepath)


# 测试代码
if __name__ == "__main__":
    print("=== Progress Quest Multiverse - 主题引擎测试 ===\n")

    # 列出所有可用主题
    print("可用主题:", ", ".join(ThemedGameEngine.list_themes()))
    print()

    # 创建主题化游戏引擎
    engine = ThemedGameEngine("warcraft")

    # 显示可用种族和职业
    print("可用种族:", ", ".join(engine.get_available_races()[:6]) + "...")
    print("可用职业:", ", ".join(engine.get_available_classes()))
    print()

    # 创建角色
    engine.create_character("萨尔", "兽人", "死亡骑士")

    # 设置日志回调
    def on_log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    engine.on_log = on_log

    # 模拟运行10秒
    print("\n=== 开始模拟游戏 (10秒) ===\n")
    start_time = time.time()
    last_update = start_time
    tick_count = 0

    while time.time() - start_time < 10:
        current_time = time.time()
        dt = current_time - last_update
        last_update = current_time

        # 手动调用游戏tick
        engine._game_tick()
        tick_count += 1

        # 每2秒显示一次状态
        if int(current_time - start_time) % 2 == 0 and tick_count % 10 == 0:
            bars = engine.get_bars()
            print(f"\n时间: {int(current_time - start_time)}秒")
            print(f"经验条: {bars['exp']:.1f}% | 任务条: {bars['quest']:.1f}%")
            print(f"负重条: {bars['encum']:.1f}% | 剧情条: {bars['plot']:.1f}%")

        time.sleep(0.5)

    print("\n=== 模拟结束 ===")
    print(engine.get_status())
