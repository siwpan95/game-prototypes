"""
Progress Quest Multiverse - 核心游戏引擎 V2
基于官网机制完善：击杀怪物 → 战利品 → 负重 → 出售 → 购买 → 任务 → 升级
"""

import time
import threading
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class GameState(Enum):
    """游戏状态"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class TaskType(Enum):
    """任务类型"""
    KILL_MONSTER = "kill_monster"      # 击杀怪物
    SELL_LOOT = "sell_loot"           # 出售战利品
    BUY_EQUIPMENT = "buy_equipment"   # 购买装备
    COMPLETE_QUEST = "complete_quest"  # 完成任务
    LEVEL_UP = "level_up"             # 升级


@dataclass
class Item:
    """物品/装备（原版PQ：负重按堆数计算，每堆算1）"""
    name: str
    value: int = 0         # 价值（金币）
    item_type: str = "misc"  # weapon, armor, potion, misc
    stat_bonus: Dict[str, int] = field(default_factory=dict)  # 属性加成
    count: int = 1          # 堆数（原版PQ核心：每堆算1负重）
    level: int = 1          # 物品等级（用于装备品质）
    
    def __str__(self):
        prefix = ""
        if self.stat_bonus:
            bonuses = [f"+{v}{k[:3]}" for k, v in self.stat_bonus.items() if v > 0]
            if bonuses:
                prefix = " ".join(bonuses) + " "
        return f"{prefix}{self.name} x{self.count}"


@dataclass
class Monster:
    """怪物"""
    name: str
    level: int
    hp: int
    exp_reward: int
    loot_table: List[Tuple[Item, float]]  # (物品, 掉落概率)
    
    def __str__(self):
        return f"Lv.{self.level} {self.name} (EXP:{self.exp_reward})"


@dataclass
class Quest:
    """任务"""
    name: str
    description: str
    target_monster: Optional[str] = None  # 需要击杀的怪物
    target_count: int = 1
    current_count: int = 0
    reward_exp: int = 100
    reward_gold: int = 50
    reward_item: Optional[Item] = None
    
    def is_complete(self) -> bool:
        return self.current_count >= self.target_count
    
    def __str__(self):
        if self.target_monster:
            return f"{self.name}: 击杀 {self.target_monster} ({self.current_count}/{self.target_count})"
        return self.name


@dataclass
class Spell:
    """法术"""
    name: str
    level: int  # 罗马数字等级

    def __str__(self):
        roman = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX',
                 'XXI', 'XXII', 'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX', 'XXX']
        lvl = roman[min(self.level - 1, len(roman) - 1)] if self.level > 0 else '?'
        return f"{self.name}"


@dataclass
class PlotChapter:
    """剧情章节（原版PQ：逐步解锁，用任务数作为过渡）"""
    name: str
    completed: bool = False
    unlocked: bool = False       # 是否已解锁（可见）
    description: str = ""        # 章节描述（序章用）
    is_prologue: bool = False    # 是否为序章（纯文字，无复选框）
    tasks_required: int = 0      # 解锁下一章需完成的任务数


@dataclass
class ActiveTask:
    """活跃任务"""
    task_type: str       # 获取 / 消灭 / 安抚 / 寻找 / 交付
    description: str     # 目标描述（如 "一些巨眼怪"）
    completed: bool = False


@dataclass
class Character:
    """角色"""
    name: str
    race: str
    char_class: str
    level: int = 1
    exp: int = 0
    exp_to_next_level: int = 1200
    gold: int = 0
    
    # 7项基础属性
    strength: int = 10      # 力
    constitution: int = 10   # 体
    dexterity: int = 10      # 敏
    intelligence: int = 10   # 智
    charm: int = 10          # 魅(威知)
    wisdom: int = 10         # 慧(感知)
    
    # HP / MP
    hp_max: int = 10
    mp_max: int = 5
    
    # 11个装备槽（与原版PQ一致）
    # 注意：装备显示属性加成，但除武器外不影响实际游戏速度（原版精神）
    equipment: Dict[str, Optional[Item]] = field(default_factory=lambda: {
        'weapon': None,     # 武器
        'shoulder': None,   # 肩牌
        'helm': None,       # 头盔
        'chest': None,      # 胸甲
        'arms': None,        # 臂甲
        'gloves': None,     # 手套
        'underarmor': None, # 内甲
        'pants': None,      # 裤甲
        'legs': None,       # 腿甲
        'shins': None,      # 胫甲
        'boots': None,      # 战靴
    })
    
    # 法术书
    spellbook: List[Spell] = field(default_factory=list)
    
    # 主题化法术池（由外部主题注入，为空则使用默认池）
    spell_pool: List[str] = field(default_factory=list)
    
    # 背包（原版PQ：负重 = 物品堆数，上限 = 10 + STR）
    inventory: List[Item] = field(default_factory=list)
    encumbrance: int = 0  # 当前负重（物品堆数）
    
    def __post_init__(self):
        """根据STR计算最大负重（原版PQ核心机制）"""
        self.max_encumbrance = 10 + self.strength  # 上限 = 10 + 力量
    
    def get_encumbrance_percent(self) -> float:
        """获取负重百分比（原版PQ机制）"""
        if self.max_encumbrance == 0:
            return 0.0
        return min(100.0, (self.encumbrance / self.max_encumbrance) * 100.0)
    
    def add_item(self, item: Item) -> bool:
        """添加物品到背包（原版PQ：每堆算1负重）"""
        if self.encumbrance + 1 > self.max_encumbrance:
            return False
        # 检查是否已存在同类物品（合并堆数）
        for inv_item in self.inventory:
            if inv_item.name == item.name:
                inv_item.count += 1
                self.encumbrance += 1
                return True
        # 新物品
        self.inventory.append(item)
        self.encumbrance += 1
        return True
    
    def remove_item(self, item_name: str) -> bool:
        """从背包移除物品（减少1堆）"""
        for i, inv_item in enumerate(self.inventory):
            if inv_item.name == item_name:
                inv_item.count -= 1
                self.encumbrance -= 1
                if inv_item.count <= 0:
                    self.inventory.pop(i)
                return True
        return False
    
    def sell_all_loot(self) -> int:
        """出售所有战利品，返回获得的金币"""
        total_value = sum(item.value * item.count for item in self.inventory)
        self.gold += total_value
        self.inventory.clear()
        self.encumbrance = 0
        return total_value
    
    def get_total_stat(self, stat_name: str) -> int:
        """获取包括装备加成的属性值"""
        base_stat = getattr(self, stat_name, 0)
        bonus = sum(eq.stat_bonus.get(stat_name, 0) for eq in self.equipment.values() if eq)
        return base_stat + bonus
    
    def level_up(self):
        """升级（原版PQ机制：随机提升属性 + 有概率学会新法术）"""
        self.level += 1
        self.exp -= self.exp_to_next_level
        self.exp_to_next_level = int(self.exp_to_next_level * 1.15)
        
        # 随机提升1~2项属性
        stats = ['strength', 'constitution', 'dexterity', 'intelligence', 'charm', 'wisdom']
        for _ in range(random.randint(1, 2)):
            stat = random.choice(stats)
            setattr(self, stat, getattr(self, stat) + random.randint(1, 3))
        
        # 提升HP/MP
        self.hp_max += random.randint(2, 5)
        self.mp_max += random.randint(1, 3)
        
        # ✅ 关键：STR提升后更新最大负重（原版PQ核心机制）
        self.max_encumbrance = 10 + self.strength
        
        # 有概率学会新法术
        if random.random() < 0.4:
            self._learn_spell()
    
    def _learn_spell(self):
        """学习新法术（优先使用主题法术池）"""
        # 默认法术池（主题未提供时回退）
        default_spells = [
            "火焰之箭", "冰霜之触", "闪电链", "治疗术", "护盾",
            "隐形术", "传送门", "魔法飞弹", "催眠术", "召唤狼",
            "毒雾", "岩石装甲", "疾风步", "圣光", "暗影箭"
        ]
        spell_names = self.spell_pool if self.spell_pool else default_spells
        if not spell_names:
            return

        # 根据等级选择法术
        available = spell_names[:min(len(spell_names), max(1, self.level))]
        name = random.choice(available)
        level = min(self.level, 30)
        
        # 检查是否已学会
        existing_names = [s.name for s in self.spellbook]
        if name not in existing_names:
            self.spellbook.append(Spell(name=name, level=level))
    
    def __str__(self):
        eq_str = ", ".join(f"{k}:{v.name if v else '无'}" for k, v in self.equipment.items())
        return (f"{self.name} Lv.{self.level} | {self.race} {self.char_class}\n"
                f"力:{self.strength} 体:{self.constitution} 敏:{self.dexterity} "
                f"智:{self.intelligence} 魅:{self.charm} 慧:{self.wisdom}\n"
                f"HP:{self.hp_max} MP:{self.mp_max}\n"
                f"装备: {eq_str}\n金币: {self.gold} | 负重: {self.encumbrance}/{self.max_encumbrance}")


class ProgressBar:
    """进度条"""
    def __init__(self, name: str, max_value: float = 100.0):
        self.name = name
        self.current = 0.0
        self.max_value = max_value
    
    def increment(self, amount: float):
        """增加进度"""
        self.current = min(self.max_value, self.current + amount)
    
    def decrement(self, amount: float):
        """减少进度"""
        self.current = max(0.0, self.current - amount)
    
    def reset(self):
        """重置进度"""
        self.current = 0.0
    
    def set_to_max(self):
        """设置为满"""
        self.current = self.max_value
    
    def is_complete(self) -> bool:
        """是否完成"""
        return self.current >= self.max_value
    
    def get_percent(self) -> float:
        """获取完成百分比"""
        if self.max_value == 0:
            return 0.0
        return (self.current / self.max_value) * 100.0
    
    def __str__(self):
        percent = self.get_percent()
        bar_length = 20
        filled = int(bar_length * percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        return f"{self.name}: |{bar}| {percent:.1f}%"


class GameEngine:
    """游戏引擎 - V2版本，完善核心机制"""
    
    # 装备槽位名称（中文，与原版PQ一致）
    SLOT_NAMES = {
        'weapon': '武器', 'shoulder': '肩牌', 'helm': '头盔', 'chest': '胸甲',
        'arms': '臂甲', 'gloves': '手套', 'underarmor': '内甲',
        'pants': '裤甲', 'legs': '腿甲', 'shins': '胫甲', 'boots': '足甲'
    }
    
    # 任务类型前缀
    TASK_TYPES = ['获取', '消灭', '安抚', '寻找', '交付']
    
    def __init__(self):
        self.state = GameState.STOPPED
        self.character: Optional[Character] = None
        
        # 进度条系统（核心！）
        self.exp_bar = ProgressBar("经验", 1200)
        self.plot_bar = ProgressBar("剧情", 100)
        self.quest_bar = ProgressBar("任务", 100)
        self.encum_bar = ProgressBar("负重", 100)
        self.action_bar = ProgressBar("行动", 100)  # 底部当前行动进度条
        
        # 游戏数据
        self.current_task: Optional[str] = None
        self.current_monster: Optional[Monster] = None
        self.current_quest: Optional[Quest] = None
        
        # 多任务系统（活跃任务列表，最多8个）
        self.active_tasks: List[ActiveTask] = []

        # 剧情章节（原版PQ：逐步解锁，序章=纯文字介绍）
        self.plot_chapters: List[PlotChapter] = [
            PlotChapter("序章", completed=True, unlocked=True,
                        description="在这个世界中，一个无名冒险者踏上了旅程...",
                        is_prologue=True, tasks_required=0),
            PlotChapter("章 I",  unlocked=False, tasks_required=3),
            PlotChapter("章 II", unlocked=False, tasks_required=5),
            PlotChapter("章 III", unlocked=False, tasks_required=8),
            PlotChapter("章 IV", unlocked=False, tasks_required=12),
            PlotChapter("章 V", unlocked=False, tasks_required=16),
            PlotChapter("章 VI", unlocked=False, tasks_required=20),
            PlotChapter("章 VII", unlocked=False, tasks_required=25),
            PlotChapter("章 VIII", unlocked=False, tasks_required=30),
        ]

        # 剧情进度追踪
        self._quests_completed_total: int = 0  # 累计完成任务数
        self._current_chapter_index: int = 0   # 当前章节索引（0=序章）
        
        # 当前行动描述（底部大进度条的文字）
        self.current_action_text: str = ""
        self.action_target_count: int = 0
        self.action_current_count: int = 0
        
        # 游戏循环
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        
        # 回调
        self.on_task_complete: Optional[callable] = None
        self.on_level_up: Optional[callable] = None
        self.on_quest_complete: Optional[callable] = None
        self.on_encumbrance_full: Optional[callable] = None
        self.on_log: Optional[callable] = None
        
        # 游戏速度（秒/tick）
        self.tick_speed = 1.0
        
        # 主题
        self.theme: Optional['GameTheme'] = None  # 主题引擎设置
        
        # 初始化游戏数据
        self._init_game_data()
    
    def _init_game_data(self):
        """初始化游戏数据（怪物、物品等）"""
        # 怪物数据
        self.monsters = [
            Monster("史莱姆", 1, 10, 50, [
                (Item("史莱姆凝胶", 5, "misc"), 0.8),
                (Item("史莱姆核心", 10, "misc"), 0.3)
            ]),
            Monster("哥布林", 2, 20, 100, [
                (Item("哥布林耳朵", 8, "misc"), 0.9),
                (Item("短剑", 50, "weapon", {"strength": 2}), 0.1)
            ]),
            Monster("骷髅", 3, 30, 150, [
                (Item("骨头", 3, "misc"), 0.7),
                (Item("破旧的盔甲", 80, "armor", {"constitution": 1}), 0.05)
            ]),
            Monster("巨魔", 5, 50, 300, [
                (Item("巨魔皮", 15, "misc"), 0.6),
                (Item("巨魔棒", 120, "weapon", {"strength": 5}), 0.08)
            ])
        ]
        
        # 装备商店
        self.shop_items = [
            Item("铁剑", 100, "weapon", {"strength": 3}),
            Item("铁盔甲", 150, "armor", {"constitution": 2}),
            Item("皮靴", 50, "boots", {"dexterity": 1}),
            Item("铁头盔", 80, "helmet", {"constitution": 1})
        ]
    
    def create_character(self, name: str, race: str, char_class: str):
        """创建角色"""
        self.character = Character(name, race, char_class)

        # 解锁第一章（序章已默认解锁）
        if len(self.plot_chapters) > 1:
            self.plot_chapters[1].unlocked = True
            self._current_chapter_index = 1

        # 初始化活跃任务列表
        self.active_tasks = []
        self._populate_active_tasks()
        
        # 初始化第一个任务和怪物
        self._start_new_quest()
        self._start_new_monster()
        
        # 初始化当前行动
        self.current_action_text = f"正在准备 {self.character.name} 的冒险..."
        self.action_target_count = 1
        self.action_current_count = 0
        
        self.log(f"🎮 创建了新角色: {name} ({race} {char_class})")
    
    def _populate_active_tasks(self):
        """生成活跃任务列表（最多8个，使用主题数据）"""
        if not self.character:
            return
        self.active_tasks = []
        
        # 优先使用主题任务目标池
        if self.theme and self.theme.task_targets:
            target_pool = self.theme.task_targets
        else:
            # 默认任务目标池（旧版回退）
            target_pool = [
                ("获取", "一棺材"), ("消灭", "一些巨眼怪"), ("安抚", "一些洞穴人"),
                ("寻找", "一些闪亮的亮晶晶的小东西"), ("交付", "针"),
                ("安抚", "一些钢铁农夫"), ("消灭", "一鸡盅"),
                ("获取", "一些双重的花彩"), ("寻找", "一些精细的羊毛"),
                ("交付", "一饼干"), ("安抚", "一杆"), ("寻找", "一些里倪倪斯"),
                ("安抚", "一些王冠"), ("寻找", "一些塔根元素"), ("寻找", "一些十字的月桂树"),
            ]
        
        num_tasks = min(8, 3 + self.character.level // 5)  # 等级越高任务越多
        selected = random.sample(target_pool, min(num_tasks, len(target_pool)))
        
        for task_type, desc in selected:
            completed = random.random() < 0.15  # 15%概率已完成
            self.active_tasks.append(ActiveTask(task_type=task_type, description=desc, completed=completed))
    
    def _start_new_monster(self):
        """开始狩猎新怪物"""
        # 根据角色等级选择怪物
        available = [m for m in self.monsters if m.level <= self.character.level + 2]
        self.current_monster = random.choice(available)
        self.log(f"⚔️ 遭遇了 {self.current_monster.name}！")
    
    def _start_new_quest(self):
        """开始新任务"""
        target_monster = random.choice([m.name for m in self.monsters])
        target_count = random.randint(3, 8)
        self.current_quest = Quest(
            name=f"狩猎任务 {random.randint(1, 100)}",
            description=f"击杀 {target_count} 只 {target_monster}",
            target_monster=target_monster,
            target_count=target_count,
            reward_exp=target_count * 50,
            reward_gold=target_count * 10
        )
        self.quest_bar.reset()
        self.log(f"📜 新任务: {self.current_quest.name}")
    
    def start(self):
        """开始游戏"""
        if not self.character:
            raise ValueError("请先创建角色！")
        
        self.state = GameState.RUNNING
        self._running = True
        
        def game_loop():
            last_time = time.time()
            
            while self._running:
                current_time = time.time()
                elapsed = current_time - last_time
                
                if not self._paused and elapsed >= self.tick_speed:
                    self._game_tick()
                    last_time = current_time
                
                time.sleep(0.1)
        
        self._thread = threading.Thread(target=game_loop, daemon=True)
        self._thread.start()
        self.log("▶️ 游戏开始！")
    
    def _game_tick(self):
        """游戏主循环 - 完善的核心机制"""
        with self._lock:
            if not self.character:
                return

            # 0. 原版 PQ 核心：经验随时间自动获得（每 tick MaxProgress/1000）
            exp_gain = self.exp_bar.max_value / 1000.0
            self.character.exp += exp_gain
            self.exp_bar.current = self.character.exp

            # 1. 检查负重 - 如果满了，先回城出售
            if self._check_and_handle_encumbrance():
                return

            # 2. 战斗：击杀怪物
            self._prepare_combat_action()
            self._kill_monster()

            # 3. 检查任务完成
            if self.current_quest and self.current_quest.is_complete():
                self._complete_quest()
                return

            # 4. 检查升级
            if self.exp_bar.is_complete():
                self._level_up()
                return

            # 5. 更新进度条
            self._update_bars()

    def _check_and_handle_encumbrance(self) -> bool:
        """检查负重是否已满，满了则回城出售；返回 True 表示已处理"""
        if self.character.get_encumbrance_percent() >= 100:
            self.current_action_text = "正在回城出售战利品..."
            self.action_bar.reset()
            self._sell_loot()
            return True
        return False

    def _prepare_combat_action(self):
        """准备当前战斗行动描述与目标计数"""
        if self.current_monster:
            monster = self.current_monster
            self.current_action_text = f"正在对战 {self.action_current_count + 1} 年轻的 {monster.name}..."
            self.action_target_count = max(1, int(monster.hp / (self.character.get_total_stat('strength') + 3)))
    
    def _kill_monster(self):
        """击杀怪物"""
        if not self.current_monster:
            self._start_new_monster()
            return

        # 模拟战斗
        damage = self.character.get_total_stat("strength") + random.randint(1, 6)
        self.current_monster.hp -= damage
        self.action_current_count += 1
        self.action_bar.increment(100.0 / max(1, self.action_target_count))

        if self.current_monster.hp <= 0:
            self._on_monster_kill(damage)
        else:
            self.log(f"⚔️ 攻击 {self.current_monster.name}！(HP: {self.current_monster.hp}/{self.current_monster.hp + damage})")

    def _on_monster_kill(self, last_damage: int):
        """怪物被击杀后的处理"""
        self.log(f"✅ 击杀了 {self.current_monster.name}！")

        # 掉落战利品
        self._process_loot_drops()

        # 更新任务进度
        self._update_quest_progress_on_kill()

        # 重置行动计数器
        self.action_current_count = 0
        self.action_bar.reset()

        # 随机完成一个活跃任务
        self._maybe_complete_random_active_task()

        # 选择新怪物
        self._start_new_monster()

    def _process_loot_drops(self):
        """处理怪物掉落战利品"""
        for item, drop_chance in self.current_monster.loot_table:
            if random.random() < drop_chance:
                cloned_item = Item(item.name, item.value, item.item_type, dict(item.stat_bonus))
                if self.character.add_item(cloned_item):
                    self.log(f"🎁 获得了 {item.name}！")
                    self._update_encumbrance_bar()
                else:
                    self.log(f"⚠️ 背包已满，无法拾取 {item.name}")

    def _update_quest_progress_on_kill(self):
        """击杀后更新当前任务进度"""
        if self.current_quest and self.current_quest.target_monster == self.current_monster.name:
            self.current_quest.current_count += 1
            quest_progress = (self.current_quest.current_count / self.current_quest.target_count) * 100
            self.quest_bar.current = quest_progress

    def _maybe_complete_random_active_task(self):
        """随机完成一个未完成的活跃任务"""
        if random.random() < 0.05 and self.active_tasks:
            incomplete = [t for t in self.active_tasks if not t.completed]
            if incomplete:
                task = random.choice(incomplete)
                task.completed = True
                self.log(f"📋 完成活跃任务: {task.task_type} {task.description}")
    
    def _sell_loot(self):
        """出售战利品（回城）"""
        gold_earned = self.character.sell_all_loot()
        self.log(f"🏪 回城出售战利品，获得 {gold_earned} 金币（总金币: {self.character.gold}）")
        
        # 重置负重条
        self.encum_bar.reset()
        
        # 检查是否可以购买更好的装备
        self._buy_equipment()
    
    # 装备类型 -> 可装备槽位映射（支持全部11个槽位）
    _SLOT_MAP = {
        'weapon': ['weapon'],
        'armor': ['chest', 'arms', 'legs', 'pants', 'underarmor'],
        'helmet': ['helm'],
        'boots': ['boots', 'shins'],
        'shoulder': ['shoulder'],
        'gloves': ['gloves'],
    }

    def _buy_equipment(self):
        """购买装备"""
        for item in self.shop_items:
            if self.character.gold >= item.value * 2:  # 价格是价值的2倍
                self.character.gold -= item.value * 2
                self._equip_item(item)
                self.log(f"🛒 购买了 {item.name} 并装备！")
                break

    def _equip_item(self, item: Item):
        """将物品装备到合适的槽位"""
        possible_slots = self._get_possible_slots(item)
        for slot in possible_slots:
            if slot in self.character.equipment:
                self.character.equipment[slot] = Item(
                    name=item.name,
                    value=item.value,
                    item_type=item.item_type,
                    stat_bonus=dict(item.stat_bonus)
                )
                break

    def _get_possible_slots(self, item: Item) -> List[str]:
        """获取物品可以装备的所有槽位"""
        return self._SLOT_MAP.get(item.item_type, [item.item_type])
    
    def _trigger_plot_event(self):
        """触发剧情推进（基于完成任务数解锁章节）"""
        self._quests_completed_total += 1

        # 找到当前未完成的最前章节
        for i, chapter in enumerate(self.plot_chapters):
            if chapter.is_prologue:
                continue
            if not chapter.completed:
                # 检查是否应该解锁下一章
                next_idx = i + 1
                if next_idx < len(self.plot_chapters):
                    next_chapter = self.plot_chapters[next_idx]
                    if (self._quests_completed_total >= next_chapter.tasks_required
                            and not next_chapter.unlocked):
                        # 当前章完成，解锁下一章
                        chapter.completed = True
                        next_chapter.unlocked = True
                        self._current_chapter_index = next_idx
                        self.log(f"📖 {chapter.name} 完成！解锁: {next_chapter.name}")
                break

    def _complete_quest(self):
        """完成任务（原版PQ机制：五种奖励随机）"""
        if not self.current_quest:
            return

        reward_type = random.choice(['exp_gold', 'special_item', 'equipment', 'stat_boost', 'new_spell'])
        self._apply_quest_reward(reward_type)

        if self.on_quest_complete:
            self.on_quest_complete(self.current_quest)

        # 推进剧情（基于任务数，不再随机）
        self._trigger_plot_event()

        # 开始新任务
        self._start_new_quest()

    def _apply_quest_reward(self, reward_type: str):
        """根据奖励类型分发到对应处理器"""
        handlers = {
            'exp_gold': self._reward_exp_gold,
            'special_item': self._reward_special_item,
            'equipment': self._reward_equipment,
            'stat_boost': self._reward_stat_boost,
            'new_spell': self._reward_new_spell,
        }
        handler = handlers.get(reward_type)
        if handler:
            handler()
        else:
            self._reward_exp_gold()

    def _reward_exp_gold(self):
        """任务奖励：经验 + 金币"""
        self.character.exp += self.current_quest.reward_exp
        self.character.gold += self.current_quest.reward_gold
        self.log(f"🎉 完成任务: {self.current_quest.name}！")
        self.log(f"   获得经验: {self.current_quest.reward_exp}，金币: {self.current_quest.reward_gold}")

    def _reward_special_item(self):
        """任务奖励：特殊物品（背包满时折算金币）"""
        special = Item(f"★{self.current_quest.name}的纪念品", value=200, item_type='misc')
        if self.character.add_item(special):
            self.log(f"🎉 完成任务: {self.current_quest.name}！")
            self.log(f"   ✨ 获得特殊宝物: {special.name}！")
        else:
            self.character.gold += 100
            self.log(f"🎉 完成任务: {self.current_quest.name}！（背包满，兑换为100金币）")

    def _reward_equipment(self):
        """任务奖励：种族精制武器"""
        better_weapon = Item(f"{self.character.race}精制剑", value=150,
                                item_type='weapon', stat_bonus={'strength': self.character.level})
        self.character.equipment['weapon'] = better_weapon
        self.log(f"🎉 完成任务: {self.current_quest.name}！")
        self.log(f"   🗡️ 获得新装备: {better_weapon.name}（力+{self.character.level}）")

    def _reward_stat_boost(self):
        """任务奖励：随机属性提升"""
        stat = random.choice(['strength', 'constitution', 'dexterity', 'intelligence', 'charm', 'wisdom'])
        old_val = getattr(self.character, stat)
        setattr(self.character, stat, old_val + random.randint(1, 2))
        stat_cn = {'strength':'力','constitution':'体','dexterity':'敏',
                   'intelligence':'智','charm':'魅','wisdom':'慧'}.get(stat, stat)
        self.log(f"🎉 完成任务: {self.current_quest.name}！")
        self.log(f"   📈 属性提升: {stat_cn}+{getattr(self.character, stat) - old_val}")
        if stat == 'strength':
            self.character.max_encumbrance = 10 + self.character.strength

    def _reward_new_spell(self):
        """任务奖励：学习新法术"""
        self.character._learn_spell()
        if self.character.spellbook:
            latest = self.character.spellbook[-1]
            roman = ['I','II','III','IV','V','VI','VII','VIII','IX','X',
                     'XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX'][min(latest.level-1, 19)]
            self.log(f"🎉 完成任务: {self.current_quest.name}！")
            self.log(f"   ✨ 学会新法术: {latest.name} {roman}！")
    
    def _level_up(self):
        """升级"""
        self.character.level_up()
        self.exp_bar.current = self.character.exp
        self.exp_bar.max_value = self.character.exp_to_next_level
        
        self.log(f"🎊 升级！当前等级: {self.character.level}")
        self.log(f"   经验条上限: {self.character.exp_to_next_level}")
        
        if self.on_level_up:
            self.on_level_up(self.character)
    
    def _update_bars(self):
        """更新所有进度条"""
        # 经验条
        self.exp_bar.current = self.character.exp
        
        # 负重条
        self._update_encumbrance_bar()
        
        # 剧情条：基于已完成的章节数
        completed_chapters = sum(1 for c in self.plot_chapters if c.completed)
        total_chapters = len(self.plot_chapters)
        if total_chapters > 0:
            self.plot_bar.current = (completed_chapters / total_chapters) * 100
    
    def get_ui_data(self) -> dict:
        """获取UI需要的全部数据（一次性返回，避免频繁调用）"""
        if not self.character:
            return {}

        char = self.character

        return {
            'char': self._build_character_data(char),
            'equipment': self._build_equipment_display(char),
            'spellbook': [(s.name, s.level) for s in char.spellbook],
            'inventory': self._build_inventory_counts(char),
            'encum_percent': char.get_encumbrance_percent(),
            'plot_chapters': [(c.name, c.completed, c.unlocked, c.is_prologue, c.description) for c in self.plot_chapters],
            'active_tasks': [(t.task_type, t.description, t.completed) for t in self.active_tasks],
            'bars': self.get_bars(),
            'action_text': self.current_action_text,
            'action_percent': self.action_bar.get_percent(),
            'quest': (f"{self.current_quest.name}: {self.current_quest.description}"
                      f" ({self.current_quest.current_count}/{self.current_quest.target_count})"
                      if self.current_quest else "无"),
            'monster': self.current_monster.name if self.current_monster else "无",
        }

    def _build_inventory_counts(self, char: Character) -> List[Tuple[str, int]]:
        """统计背包物品（按名称合并计数）"""
        inv_counts: Dict[str, int] = {}
        for item in char.inventory:
            inv_counts[item.name] = inv_counts.get(item.name, 0) + 1
        return list(inv_counts.items())

    def _build_equipment_display(self, char: Character) -> List[Tuple[str, str]]:
        """构建装备列表（带属性前缀）"""
        equipment_display = []
        for slot_id, item in char.equipment.items():
            slot_name = self.SLOT_NAMES.get(slot_id, slot_id)
            if item:
                prefix = self._format_item_prefix(item)
                display_name = f"{prefix}{item.name}" if prefix else item.name
                equipment_display.append((slot_name, display_name))
            else:
                equipment_display.append((slot_name, ""))
        return equipment_display

    def _format_item_prefix(self, item: Item) -> str:
        """生成装备属性前缀（如 '+3力的'）"""
        if not item.stat_bonus:
            return ""
        prefix = ""
        for stat, val in item.stat_bonus.items():
            stat_cn = {'strength': '力', 'constitution': '体', 'dexterity': '敏',
                       'intelligence': '智', 'charm': '魅', 'wisdom': '慧'}.get(stat, stat)
            prefix += f"+{val}{stat_cn}的"
        return prefix

    def _build_character_data(self, char: Character) -> dict:
        """构建角色基础数据"""
        return {
            'name': char.name, 'race': char.race, 'class': char.char_class,
            'level': char.level, 'gold': char.gold,
            'stats': {'力': char.strength, '体': char.constitution, '敏': char.dexterity,
                      '智': char.intelligence, '魅': char.charm, '慧': char.wisdom},
            'hp_max': char.hp_max, 'mp_max': char.mp_max,
        }
    
    def _update_encumbrance_bar(self):
        """更新负重条"""
        encum_percent = self.character.get_encumbrance_percent()
        self.encum_bar.current = encum_percent
        
        # 检查是否满了
        if encum_percent >= 100 and self.on_encumbrance_full:
            self.on_encumbrance_full()
    
    def stop(self):
        """停止游戏"""
        self._running = False
        self.state = GameState.STOPPED
        if self._thread:
            self._thread.join(timeout=2)
        self.log("⏹️ 游戏停止")
    
    def pause(self):
        """暂停游戏"""
        self._paused = True
        self.state = GameState.PAUSED
        self.log("⏸️ 游戏暂停")
    
    def resume(self):
        """继续游戏"""
        self._paused = False
        self.state = GameState.RUNNING
        self.log("▶️ 游戏继续")
    
    @staticmethod
    def _item_to_dict(item: Item) -> dict:
        """将 Item 序列化为字典"""
        if not item:
            return None
        return {
            'name': item.name,
            'value': item.value,
            'item_type': item.item_type,
            'stat_bonus': dict(item.stat_bonus),
            'count': item.count,
            'level': item.level
        }
    
    @staticmethod
    def _dict_to_item(data: dict) -> Item:
        """从字典反序列化为 Item"""
        if not data:
            return None
        # 兼容旧存档
        if 'weight' in data:
            del data['weight']
        return Item(**data)
    
    @classmethod
    def _monster_to_dict(cls, monster: Monster) -> dict:
        """将 Monster 序列化为字典"""
        if not monster:
            return None
        return {
            'name': monster.name,
            'level': monster.level,
            'hp': monster.hp,
            'exp_reward': monster.exp_reward,
            'loot_table': [[cls._item_to_dict(item), chance] for item, chance in monster.loot_table]
        }
    
    @classmethod
    def _dict_to_monster(cls, data: dict) -> Monster:
        """从字典反序列化为 Monster"""
        if not data:
            return None
        loot_table = []
        for item_data, chance in data.get('loot_table', []):
            loot_table.append((cls._dict_to_item(item_data), chance))
        return Monster(
            name=data['name'],
            level=data['level'],
            hp=data['hp'],
            exp_reward=data['exp_reward'],
            loot_table=loot_table
        )
    
    @classmethod
    def _quest_to_dict(cls, quest: Quest) -> dict:
        """将 Quest 序列化为字典"""
        if not quest:
            return None
        data = dict(quest.__dict__)
        data['reward_item'] = cls._item_to_dict(quest.reward_item)
        return data
    
    @classmethod
    def _dict_to_quest(cls, data: dict) -> Quest:
        """从字典反序列化为 Quest"""
        if not data:
            return None
        data = dict(data)
        data['reward_item'] = cls._dict_to_item(data.get('reward_item'))
        return Quest(**data)
    
    def save(self, filepath: str):
        """保存游戏"""
        if not self.character:
            raise ValueError("没有角色可以保存！")

        char = self.character
        data = {
            'character': {
                'name': char.name,
                'race': char.race,
                'char_class': char.char_class,
                'level': char.level,
                'exp': char.exp,
                'exp_to_next_level': char.exp_to_next_level,
                'gold': char.gold,
                'strength': char.strength,
                'dexterity': char.dexterity,
                'constitution': char.constitution,
                'intelligence': char.intelligence,
                'charm': char.charm,
                'wisdom': char.wisdom,
                'hp_max': char.hp_max,
                'mp_max': char.mp_max,
                'equipment': {k: v.__dict__ if v else None for k, v in char.equipment.items()},
                'inventory': [item.__dict__ for item in char.inventory],
                'spellbook': [{'name': s.name, 'level': s.level} for s in char.spellbook],
                'encumbrance': char.encumbrance,
                'max_encumbrance': char.max_encumbrance
            },
            'exp_bar': {'current': self.exp_bar.current, 'max_value': self.exp_bar.max_value},
            'plot_bar': {'current': self.plot_bar.current, 'max_value': self.plot_bar.max_value},
            'quest_bar': {'current': self.quest_bar.current, 'max_value': self.quest_bar.max_value},
            'encum_bar': {'current': self.encum_bar.current, 'max_value': self.encum_bar.max_value},
            'action_bar': {'current': self.action_bar.current, 'max_value': self.action_bar.max_value},
            'quest': self._quest_to_dict(self.current_quest) if self.current_quest else None,
            'monster': self._monster_to_dict(self.current_monster) if self.current_monster else None,
            'plot_chapters': [{'name': c.name, 'completed': c.completed, 'unlocked': c.unlocked,
                               'description': c.description, 'is_prologue': c.is_prologue,
                               'tasks_required': c.tasks_required} for c in self.plot_chapters],
            'active_tasks': [{'task_type': t.task_type, 'description': t.description,
                              'completed': t.completed} for t in self.active_tasks],
            'progress': {
                'quests_completed_total': self._quests_completed_total,
                'current_chapter_index': self._current_chapter_index,
                'current_action_text': self.current_action_text,
                'action_target_count': self.action_target_count,
                'action_current_count': self.action_current_count
            }
        }

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.log(f"💾 游戏已保存: {filepath}")

    def load(self, filepath: str):
        """加载游戏"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加载角色
        char_data = data['character']
        self.character = Character(
            name=char_data['name'],
            race=char_data['race'],
            char_class=char_data['char_class'],
            level=char_data['level'],
            exp=char_data['exp'],
            exp_to_next_level=char_data['exp_to_next_level'],
            gold=char_data['gold']
        )
        self.character.strength = char_data['strength']
        self.character.dexterity = char_data['dexterity']
        self.character.constitution = char_data['constitution']
        self.character.intelligence = char_data['intelligence']
        self.character.charm = char_data.get('charm', 10)
        self.character.wisdom = char_data.get('wisdom', 10)
        self.character.hp_max = char_data.get('hp_max', 10)
        self.character.mp_max = char_data.get('mp_max', 5)
        
        # 加载负重数据（兼容旧存档）
        if 'max_encumbrance' in char_data:
            self.character.max_encumbrance = char_data['max_encumbrance']
            self.character.encumbrance = char_data.get('encumbrance', 0)
        else:
            # 旧存档：根据STR计算
            self.character.max_encumbrance = 10 + self.character.strength
            self.character.encumbrance = 0
        
        # 加载装备
        for k, v in char_data['equipment'].items():
            if v:
                # 移除可能的weight字段（兼容旧存档）
                if 'weight' in v:
                    del v['weight']
                self.character.equipment[k] = Item(**v)
        
        # 加载背包
        for item_data in char_data['inventory']:
            # 移除可能的weight字段（兼容旧存档）
            if 'weight' in item_data:
                del item_data['weight']
            self.character.add_item(Item(**item_data))
        
        # 加载法术书
        self.character.spellbook = []
        for spell_data in char_data.get('spellbook', []):
            self.character.spellbook.append(Spell(**spell_data))
        
        # 加载进度条
        self.exp_bar.current = data['exp_bar']['current']
        self.exp_bar.max_value = data['exp_bar']['max_value']
        self.plot_bar.current = data['plot_bar']['current']
        self.plot_bar.max_value = data['plot_bar']['max_value']
        self.quest_bar.current = data['quest_bar']['current']
        self.quest_bar.max_value = data['quest_bar']['max_value']
        self.encum_bar.current = data['encum_bar']['current']
        self.encum_bar.max_value = data['encum_bar']['max_value']
        self.action_bar.current = data.get('action_bar', {}).get('current', 0)
        self.action_bar.max_value = data.get('action_bar', {}).get('max_value', 100)
        
        # 加载任务
        self.current_quest = self._dict_to_quest(data.get('quest'))
        
        # 加载怪物
        self.current_monster = self._dict_to_monster(data.get('monster'))
        
        # 加载剧情章节
        self.plot_chapters = []
        for chapter_data in data.get('plot_chapters', []):
            self.plot_chapters.append(PlotChapter(**chapter_data))
        
        # 加载活跃任务
        self.active_tasks = []
        for task_data in data.get('active_tasks', []):
            self.active_tasks.append(ActiveTask(**task_data))
        
        # 加载进度追踪
        progress_data = data.get('progress', {})
        self._quests_completed_total = progress_data.get('quests_completed_total', 0)
        self._current_chapter_index = progress_data.get('current_chapter_index', 0)
        self.current_action_text = progress_data.get('current_action_text', '')
        self.action_target_count = progress_data.get('action_target_count', 1)
        self.action_current_count = progress_data.get('action_current_count', 0)
        
        self.log(f"📂 游戏已加载: {filepath}")
    
    def log(self, message: str):
        """日志记录"""
        if self.on_log:
            self.on_log(message)
        else:
            print(message)
    
    def get_status(self) -> str:
        """获取游戏状态"""
        if not self.character:
            return "未创建角色"
        
        status = f"""
{'='*50}
{str(self.character)}
{'='*50}
进度条:
{self.exp_bar}
{self.plot_bar}
{self.quest_bar}
{self.encum_bar}

当前任务: {self.current_quest if self.current_quest else '无'}
当前怪物: {self.current_monster.name if self.current_monster else '无'}
游戏状态: {self.state.value}
{'='*50}
"""
        return status
    
    def get_bars(self) -> dict:
        """获取所有进度条的百分比"""
        return {
            'exp': self.exp_bar.get_percent(),
            'plot': self.plot_bar.get_percent(),
            'quest': self.quest_bar.get_percent(),
            'encum': self.encum_bar.get_percent()
        }
    
    def get_recent_logs(self, count: int = 5) -> list:
        """获取最近的日志（简化版，实际应该存储日志）"""
        # 这里简化为返回空列表，实际实现需要存储日志
        return []


# 测试代码
if __name__ == "__main__":
    # 创建游戏引擎
    engine = GameEngine()
    
    # 创建角色
    engine.create_character("勇者", "人类", "战士")
    
    # 设置日志回调
    def on_log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    
    engine.on_log = on_log
    
    # 开始游戏
    try:
        engine.start()
        
        # 运行一段时间
        print("游戏运行中...按 Ctrl+C 停止")
        while True:
            print(engine.get_status())
            time.sleep(5)
    
    except KeyboardInterrupt:
        engine.stop()
        print("\n游戏已停止")
