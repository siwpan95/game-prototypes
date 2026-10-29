"""
Progress Quest Multiverse - PQ 架构版主题引擎

集成原版 ProgressQuest 的核心架构（队列系统、Tick 引擎、确定随机数），
同时保留多主题系统（JSON 数据）。
"""

import sys
import os
import threading
import time

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))  # 当前在 src/core/
src_path = os.path.dirname(src_path)                   # 上一级即为 src/
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# 导入原有类
from core.game_engine_v2 import GameEngine, Character, Item, Monster, Quest, GameState
from themes.theme_loader import get_theme, list_theme_ids, list_theme_names, discover_themes

# 导入新的 PQ 核心架构
from core.queue_system import QueueSystem, QueueItem
from core.deterministic_rng import DeterministicRNG
from core.monster_task_generator import MonsterTaskGenerator
from core.equipment_generator import EquipmentGenerator
from core.tick_engine import TickEngine


class PQThemedGameEngine(GameEngine):
    """PQ 架构版主题化游戏引擎
    
    结合原版 ProgressQuest 的核心架构和多主题系统：
    1. 使用队列系统管理行动 (QueueSystem)
    2. 使用 Tick 引擎驱动游戏循环 (TickEngine)
    3. 使用确定随机数确保可重复性 (DeterministicRNG)
    4. 保留主题系统 (JSON 数据)
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
    
    def __init__(self, theme_name="diablo", seed: int = None):
        """初始化
        
        Args:
            theme_name: 主题名称
            seed: 随机种子 (用于确定随机数)
        """
        super().__init__()
        self.theme_name = theme_name
        
        # 父类 _init_game_data 加载的默认数据在主题模式下完全冗余，清空
        self.monsters = []
        self.shop_items = []
        
        # 通过加载器从 JSON 加载主题
        self.theme = self.load_theme(theme_name)
        if not self.theme:
            raise ValueError(f"无法加载主题: {theme_name}")
        
        # 将主题商店物品转换为引擎 Item
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
        
        # ========== PQ 核心架构初始化 ==========
        
        # 1. 确定随机数生成器
        self.rng = DeterministicRNG(seed=seed)
        self.log(f"🎲 随机数种子: {self.rng.get_seed()}")
        
        # 2. 队列系统
        self.queue_system = QueueSystem()
        
        # 3. 怪物任务生成器
        theme_data = self._load_theme_data()
        self.monster_task_generator = MonsterTaskGenerator(theme_data, self.rng)
        
        # 4. 装备生成器
        self.equipment_generator = EquipmentGenerator(theme_data, self.rng)
        
        # 5. Tick 引擎
        self.tick_engine = TickEngine(
            queue_system=self.queue_system,
            character=None,  # 将在 create_character 后设置
            rng=self.rng,
            ui_callback=self._on_tick_update
        )
        # 注入生成器到 TickEngine
        self.tick_engine.monster_task_generator = self.monster_task_generator
        self.tick_engine.equipment_generator = self.equipment_generator
        
        # 游戏状态
        self.is_running = False
        self.on_log = None
        self.on_update = None
        
        self.log(f"✅ PQ 架构初始化完成")
    
    def _load_theme_data(self) -> dict:
        """加载主题数据 (供生成器使用)
        
        从 themes/data/ 读取 JSON 文件，转换为生成器需要的格式。
        """
        import json
        
        theme_data = {}
        theme_dir = os.path.join(os.path.dirname(__file__), 'themes', 'data', self.theme_name)
        
        # 读取怪物数据
        monsters_file = os.path.join(theme_dir, 'monsters.json')
        if os.path.exists(monsters_file):
            with open(monsters_file, 'r', encoding='utf-8') as f:
                theme_data['monsters'] = json.load(f)
        
        # 读取装备数据
        equipment_file = os.path.join(theme_dir, 'equipment.json')
        if os.path.exists(equipment_file):
            with open(equipment_file, 'r', encoding='utf-8') as f:
                theme_data['equipment'] = json.load(f)
        
        # 读取修饰符数据 (如果有)
        prefixes_file = os.path.join(theme_dir, 'prefixes.json')
        if os.path.exists(prefixes_file):
            with open(prefixes_file, 'r', encoding='utf-8') as f:
                theme_data['prefixes'] = json.load(f)
        
        return theme_data
    
    @classmethod
    def load_theme(cls, theme_name: str):
        """加载主题数据（不创建引擎实例，供开始界面使用）"""
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
        
        # 将 character 设置到 TickEngine
        self.tick_engine.character = self.character
        
        # 解锁第一章（序章已默认解锁）
        if len(self.plot_chapters) > 1:
            self.plot_chapters[1].unlocked = True
            self._current_chapter_index = 1
        
        # 初始化活跃任务列表（使用主题任务目标池）
        self.active_tasks = []
        self._populate_active_tasks()
        
        # ========== PQ 架构：初始化第一个行动 ==========
        
        # 生成第一个怪物任务
        first_task = self.monster_task_generator.generate(
            char_level=self.character.level,
            char_name=self.character.name
        )
        self.queue_system.enqueue(first_task)
        self.queue_system.dequeue()
        
        # 初始化当前行动文本
        self.current_action_text = first_task.label
        self.action_target_count = 1
        self.action_current_count = 0
        
        self.log(f"⚔️ 开始冒险！第一个任务: {first_task.label}")
    
    def start_game(self):
        """启动游戏 (PQ 架构：启动 TickEngine)"""
        if not self.character:
            raise ValueError("请先创建角色")
        
        self.is_running = True
        self.tick_engine.start()
        self.log(f"▶️ 游戏启动 (Tick 间隔: {self.tick_engine.TICK_INTERVAL_MS}ms)")
    
    def stop_game(self):
        """停止游戏"""
        self.is_running = False
        self.tick_engine.stop()
        self.log(f"⏸️ 游戏停止")
    
    def pause_game(self):
        """暂停游戏（不清除状态）"""
        if self.is_running:
            self.tick_engine.stop()
            self.log(f"⏸️ 游戏已暂停")
    
    def resume_game(self):
        """恢复游戏"""
        if self.is_running and not self.tick_engine.is_running:
            self.tick_engine.start()
            self.log(f"▶️ 游戏已恢复")
    
    def _on_tick_update(self, status: dict):
        """Tick 更新回调 (供 UI 更新)"""
        # 更新当前行动文本
        self.current_action_text = status['current_action']
        
        # 调用外部回调
        if self.on_update:
            self.on_update(status)
    
    def _game_tick(self):
        """游戏主循环 (PQ 架构：由 TickEngine 调用)
        
        这个方法保留用于兼容原有代码，但主要逻辑已移到 TickEngine。
        """
        # 这个方法现在由 TickEngine 自动调用，不需要手动调用
        pass
    
    def get_available_races(self) -> list:
        """获取可用种族"""
        return self.theme.races
    
    def get_available_classes(self) -> list:
        """获取可用职业"""
        return self.theme.classes
    
    def get_theme_info(self) -> str:
        """获取主题信息"""
        return self.theme.get_theme_description()
    
    # ========== PQ 架构：游戏逻辑包装方法 ==========
    
    def _process_completed_action(self):
        """处理完成的行动 (包装 TickEngine 方法)"""
        if self.tick_engine:
            self.tick_engine._process_completed_action()
    
    def _select_next_action(self):
        """选择下一个行动 (包装 TickEngine 方法)"""
        if self.tick_engine:
            self.tick_engine._select_next_action()
    
    def _check_level_up(self):
        """检查升级 (包装 TickEngine 方法)"""
        if self.tick_engine:
            self.tick_engine._check_level_up()
    
    def get_pq_status(self) -> dict:
        """获取 PQ 架构状态"""
        if self.tick_engine:
            return self.tick_engine.get_status()
        
        # 回退：返回默认状态
        char_data = {}
        if self.character:
            char_data = {
                'name': getattr(self.character, 'name', 'Unknown'),
                'level': getattr(self.character, 'level', 1),
                'exp': getattr(self.character, 'exp', 0),
                'gold': getattr(self.character, 'gold', 0),
            }
        
        return {
            'is_running': False,
            'tick_count': 0,
            'current_action': 'Idle',
            'progress': 0.0,
            'queue_length': 0,
            'character': char_data,
        }
    
    def _game_tick_manual(self):
        """手动推进一个 tick (用于测试)
        
        这个方法模拟 TickEngine 的一个 tick，用于测试。
        """
        if not self.character:
            return
        
        # 1. 推进当前行动
        action_completed = self.queue_system.advance(50)
        
        if action_completed:
            # 处理完成的行动
            self._process_completed_action()
            # 选择下一个行动
            self._select_next_action()
        
        # 2. 获得经验
        if self.queue_system.current_action:
            exp_gain = 1.0  # 每次 tick 获得 1 经验
            self.character.exp = getattr(self.character, 'exp', 0) + exp_gain
        
        # 3. 检查升级
        self._check_level_up()
        
        # 4. 返回当前状态
        return self.get_pq_status()
    
    def save_game(self, filepath: str = None):
        """便捷保存方法（默认保存到项目根目录 saves/ 下）"""
        if filepath is None:
            save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'saves')
            filepath = os.path.join(save_dir, f"{self.theme_name}_{self.character.name}.json")
        self.save(filepath)
    
    def load_game(self, filepath: str = None):
        """便捷加载方法（默认加载最近存档）"""
        if filepath is None:
            save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'saves')
            if not os.path.exists(save_dir):
                raise FileNotFoundError("没有存档文件")
            files = [f for f in os.listdir(save_dir) if f.startswith(self.theme_name) and f.endswith('.json')]
            if not files:
                raise FileNotFoundError("没有存档文件")
            filepath = os.path.join(save_dir, sorted(files, key=lambda x: os.path.getmtime(os.path.join(save_dir, x)), reverse=True)[0])
        self.load(filepath)


# ========== 测试代码 ==========

if __name__ == "__main__":
    print("=== Progress Quest Multiverse - PQ 架构版测试 ===\n")
    
    # 列出所有可用主题
    print("可用主题:", ", ".join(PQThemedGameEngine.list_themes()))
    print()
    
    # 创建 PQ 架构版游戏引擎
    engine = PQThemedGameEngine("diablo", seed=12345)
    
    # 显示可用种族和职业
    print("可用种族:", ", ".join(engine.get_available_races()[:6]) + "...")
    print("可用职业:", ", ".join(engine.get_available_classes()))
    print()
    
    # 创建角色
    engine.create_character("黑暗流浪者", "人类", "死灵法师")
    
    # 设置日志回调
    def on_log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    
    engine.on_log = on_log
    
    # 设置更新回调
    def on_update(status):
        print(f"📊 当前行动: {status['current_action']}")
        print(f"   进度: {status['progress']:.1%}")
    
    engine.on_update = on_update
    
    # 启动游戏
    print("\n=== 启动游戏 (5 秒) ===\n")
    engine.start_game()
    
    # 运行 5 秒
    time.sleep(5)
    
    # 停止游戏
    engine.stop_game()
    
    # 显示最终状态
    print("\n=== 最终状态 ===")
    pq_status = engine.get_pq_status()
    print(f"队列长度: {pq_status['queue_length']}")
    print(f"当前行动: {pq_status['current_action']}")
    print(f"进度: {pq_status['progress']:.1%}")
    print(f"Tick 计数: {pq_status['tick_count']}")
    print(f"随机种子: {pq_status['seed']}")
    
    print("\n✅ PQ 架构集成测试完成！")
