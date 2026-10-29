"""
Progress Quest Multiverse - 主题系统
高度工具化的主题框架，便于创建和添加新主题
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class ThemeItem:
    """主题物品（原版PQ：负重按堆数计算）"""
    name: str
    value: int = 0
    item_type: str = "misc"
    stat_bonus: Dict[str, int] = field(default_factory=dict)
    count: int = 1
    level: int = 1


@dataclass
class ThemeMonster:
    """主题怪物"""
    name: str
    level: int
    hp: int
    exp_reward: int
    loot_table: List[Tuple[ThemeItem, float]]


@dataclass
class ThemeQuest:
    """主题任务"""
    name: str
    description: str
    target_monster: str
    target_count: int
    reward_exp: int
    reward_gold: int
    reward_item: Optional[ThemeItem] = None


class GameTheme:
    """游戏主题基类"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.monsters = []
        self.shop_items = []
        self.quest_templates = []
        self.races = []
        self.classes = []
        # 主题化数据池：骨架只负责运行逻辑，血肉交给主题
        self.spell_pool: List[str] = []
        self.task_targets: List[Tuple[str, str]] = []
    
    def get_random_monster(self, max_level: int) -> ThemeMonster:
        """获取随机怪物"""
        available = [m for m in self.monsters if m.level <= max_level]
        return random.choice(available) if available else None
    
    def get_random_quest(self) -> ThemeQuest:
        """获取随机任务"""
        if not self.quest_templates:
            return None
        template = random.choice(self.quest_templates)
        # 复制模板并随机化
        quest = ThemeQuest(
            name=f"{template.name} {random.randint(1, 100)}",
            description=template.description,
            target_monster=template.target_monster,
            target_count=random.randint(3, 8),
            reward_exp=template.reward_exp,
            reward_gold=template.reward_gold,
            reward_item=template.reward_item
        )
        return quest
    
    def get_shop_items(self) -> List[ThemeItem]:
        """获取商店物品"""
        return self.shop_items

    def get_theme_description(self) -> str:
        """获取主题描述文案"""
        return self.description

    def get_theme_info(self) -> dict:
        """获取主题完整元数据（供开始界面展示）"""
        return {
            'name': self.name,
            'description': self.description,
            'race_count': len(self.races),
            'class_count': len(self.classes),
            'monster_count': len(self.monsters),
            'quest_count': len(self.quest_templates),
            'shop_count': len(self.shop_items),
        }
