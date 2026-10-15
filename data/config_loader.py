"""Excel配置加载器
用于从Excel文件中加载游戏配置数据
"""
import math

import pandas as pd
import os
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


def _col(row, key: str, default):
    """安全读取行字段：列不存在或值为 NaN 时返回默认值"""
    if key not in row:
        return default
    value = row[key]
    if isinstance(value, float) and math.isnan(value):
        return default
    if value is None:
        return default
    return value


def _to_bool(value, default: bool = False) -> bool:
    """把 Excel 单元格转成布尔：是/真/true/1/yes → True"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("是", "真", "true", "1", "yes", "y", "t")
    return default

@dataclass
class EnemyData:
    id: int
    name: str
    hp: int
    attack: int
    defense: int
    speed: int
    exp_reward: int
    gold_reward: int
    encounter_rate: float
    description: str
    region_id: int = 1  # 出现区域（对应 Maps 表 ID，1=荒野）

@dataclass
class ItemData:
    id: int
    name: str
    type: str
    effect_value: int
    price: int
    description: str
    usable_in_battle: bool

@dataclass
class VehicleData:
    id: int
    name: str
    hp: int
    attack: int
    defense: int
    speed: int
    fuel_capacity: int
    fuel_consumption: float
    repair_cost: int
    description: str

@dataclass
class MapData:
    id: int
    name: str
    width: int
    height: int
    terrain_types: str
    encounter_rate: float
    music: str
    infinite: bool = True      # 无限地图（荒野） vs 有限地图（城镇/遗迹）
    is_town: bool = False      # 是否城镇地图
    entrance_x: int = -1       # 荒野入口坐标（-1 = 无）
    entrance_y: int = -1

@dataclass
class NPCData:
    id: int
    name: str
    role: str
    dialog: str
    location_x: int
    location_y: int
    map_id: int

@dataclass
class SkillData:
    id: int
    name: str
    type: str
    cost: int
    effect: str
    description: str
    unlock_level: int = 1  # 解锁等级（玩家达到该等级才学会）

@dataclass
class ShopData:
    id: int
    name: str
    type: str
    map_id: int
    items: List[int]
    price_multiplier: float

@dataclass
class QuestData:
    id: int
    name: str
    type: str
    description: str
    target_id: int
    reward_exp: int
    reward_gold: int
    reward_item_id: int
    target_count: int = 1  # 目标数量（击杀数/收集数/到访次数）

class ConfigLoader:
    def __init__(self, excel_path: str = "config.xlsx"):
        self.excel_path = excel_path
        self.enemies: Dict[int, EnemyData] = {}
        self.items: Dict[int, ItemData] = {}
        self.vehicles: Dict[int, VehicleData] = {}
        self.maps: Dict[int, MapData] = {}
        self.npcs: Dict[int, NPCData] = {}
        self.skills: Dict[int, SkillData] = {}
        self.shops: Dict[int, ShopData] = {}
        self.quests: Dict[int, QuestData] = {}
        
    def load_all(self) -> bool:
        """加载所有配置数据"""
        try:
            if not os.path.exists(self.excel_path):
                print(f"配置文件不存在: {self.excel_path}")
                return False
            
            # 加载各个工作表
            self._load_enemies()
            self._load_items()
            self._load_vehicles()
            self._load_maps()
            self._load_npcs()
            self._load_skills()
            self._load_shops()
            self._load_quests()
            
            print("配置加载完成!")
            return True
        except Exception as e:
            print(f"加载配置时出错: {e}")
            return False
    
    def _load_enemies(self):
        """加载敌人配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Enemies')
            for _, row in df.iterrows():
                enemy = EnemyData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    hp=int(row['HP']),
                    attack=int(row['攻击']),
                    defense=int(row['防御']),
                    speed=int(row['速度']),
                    exp_reward=int(row['经验值']),
                    gold_reward=int(row['金币']),
                    encounter_rate=float(row['遭遇率']),
                    description=str(row['描述']),
                    region_id=int(_col(row, '区域ID', 1)),
                )
                self.enemies[enemy.id] = enemy
            print(f"加载了 {len(self.enemies)} 个敌人配置")
        except Exception as e:
            print(f"加载敌人配置失败: {e}")
    
    def _load_items(self):
        """加载物品配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Items')
            for _, row in df.iterrows():
                item = ItemData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    type=str(row['类型']),
                    effect_value=int(row['效果值']),
                    price=int(row['价格']),
                    description=str(row['描述']),
                    usable_in_battle=bool(row['战斗中可用'])
                )
                self.items[item.id] = item
            print(f"加载了 {len(self.items)} 个物品配置")
        except Exception as e:
            print(f"加载物品配置失败: {e}")
    
    def _load_vehicles(self):
        """加载战车配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Vehicles')
            for _, row in df.iterrows():
                vehicle = VehicleData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    hp=int(row['HP']),
                    attack=int(row['攻击']),
                    defense=int(row['防御']),
                    speed=int(row['速度']),
                    fuel_capacity=int(row['燃料容量']),
                    fuel_consumption=float(row['燃料消耗']),
                    repair_cost=int(row['修理费用']),
                    description=str(row['描述'])
                )
                self.vehicles[vehicle.id] = vehicle
            print(f"加载了 {len(self.vehicles)} 个战车配置")
        except Exception as e:
            print(f"加载战车配置失败: {e}")
    
    def _load_maps(self):
        """加载地图配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Maps')
            for _, row in df.iterrows():
                map_data = MapData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    width=int(row['宽度']),
                    height=int(row['高度']),
                    terrain_types=str(row['地形类型']),
                    encounter_rate=float(row['遭遇率']),
                    music=str(row['音乐']),
                    infinite=_to_bool(_col(row, '无限地图', True), True),
                    is_town=_to_bool(_col(row, '是否城镇', False), False),
                    entrance_x=int(_col(row, '入口X', -1)),
                    entrance_y=int(_col(row, '入口Y', -1)),
                )
                self.maps[map_data.id] = map_data
            print(f"加载了 {len(self.maps)} 个地图配置")
        except Exception as e:
            print(f"加载地图配置失败: {e}")
    
    def _load_npcs(self):
        """加载NPC配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='NPCs')
            for _, row in df.iterrows():
                npc = NPCData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    role=str(row['角色']),
                    dialog=str(row['对话']),
                    location_x=int(row['X坐标']),
                    location_y=int(row['Y坐标']),
                    map_id=int(row['地图ID'])
                )
                self.npcs[npc.id] = npc
            print(f"加载了 {len(self.npcs)} 个NPC配置")
        except Exception as e:
            print(f"加载NPC配置失败: {e}")
    
    def _load_skills(self):
        """加载技能配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Skills')
            for _, row in df.iterrows():
                skill = SkillData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    type=str(row['类型']),
                    cost=int(row['消耗']),
                    effect=str(row['效果']),
                    description=str(row['描述']),
                    unlock_level=max(1, int(_col(row, '解锁等级', 1))),
                )
                self.skills[skill.id] = skill
            print(f"加载了 {len(self.skills)} 个技能配置")
        except Exception as e:
            print(f"加载技能配置失败: {e}")
    
    def _load_shops(self):
        """加载商店配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Shops')
            for _, row in df.iterrows():
                # 解析商品列表字符串为整数列表
                items_str = str(row['商品列表']).strip()
                if items_str:
                    items_list = [int(x.strip()) for x in items_str.split(',') if x.strip()]
                else:
                    items_list = []
                
                shop = ShopData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    type=str(row['类型']),
                    map_id=int(row['地图ID']),
                    items=items_list,
                    price_multiplier=float(row['价格倍数'])
                )
                self.shops[shop.id] = shop
            print(f"加载了 {len(self.shops)} 个商店配置")
        except Exception as e:
            print(f"加载商店配置失败: {e}")
    
    def _load_quests(self):
        """加载任务配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Quests')
            for _, row in df.iterrows():
                quest = QuestData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    type=str(row['类型']),
                    description=str(row['描述']),
                    target_id=int(row['目标ID']),
                    reward_exp=int(row['奖励经验']),
                    reward_gold=int(row['奖励金币']),
                    reward_item_id=int(row['奖励物品']),
                    target_count=max(1, int(_col(row, '目标数量', 1))),
                )
                self.quests[quest.id] = quest
            print(f"加载了 {len(self.quests)} 个任务配置")
        except Exception as e:
            print(f"加载任务配置失败: {e}")
    
    def get_enemy_by_id(self, enemy_id: int) -> Optional[EnemyData]:
        """根据ID获取敌人数据"""
        return self.enemies.get(enemy_id)
    
    def get_item_by_id(self, item_id: int) -> Optional[ItemData]:
        """根据ID获取物品数据"""
        return self.items.get(item_id)
    
    def get_vehicle_by_id(self, vehicle_id: int) -> Optional[VehicleData]:
        """根据ID获取战车数据"""
        return self.vehicles.get(vehicle_id)
    
    def get_map_by_id(self, map_id: int) -> Optional[MapData]:
        """根据ID获取地图数据"""
        return self.maps.get(map_id)
    
    def get_npc_by_id(self, npc_id: int) -> Optional[NPCData]:
        """根据ID获取NPC数据"""
        return self.npcs.get(npc_id)
    
    def get_skill_by_id(self, skill_id: int) -> Optional[SkillData]:
        """根据ID获取技能数据"""
        return self.skills.get(skill_id)
    
    def get_shop_by_id(self, shop_id: int) -> Optional[ShopData]:
        """根据ID获取商店数据"""
        return self.shops.get(shop_id)
    
    def get_quest_by_id(self, quest_id: int) -> Optional[QuestData]:
        """根据ID获取任务数据"""
        return self.quests.get(quest_id)
    
    def get_random_enemy(self, map_id: int = 1) -> Optional[EnemyData]:
        """按地图ID抽取敌人：只在该区域敌人中按遭遇率加权随机

        该区域没有配置敌人时，回退为区域 1（荒野通用怪），避免空图。
        """
        if not self.enemies:
            return None

        enemies = [e for e in self.enemies.values() if e.region_id == map_id]
        if not enemies:
            enemies = [e for e in self.enemies.values() if e.region_id == 1]
        if not enemies:
            enemies = list(self.enemies.values())

        weights = [e.encounter_rate for e in enemies]

        # 加权随机选择
        total = sum(weights)
        if total <= 0:
            return random.choice(enemies)

        roll = random.uniform(0, total)
        acc = 0.0
        for enemy in enemies:
            acc += enemy.encounter_rate
            if roll <= acc:
                return enemy

        return enemies[-1]
    
    def get_starting_items(self) -> List[ItemData]:
        """获取初始物品"""
        starting_items = []
        for item in self.items.values():
            if item.id <= 3:  # 假设ID 1-3是初始物品
                starting_items.append(item)
        return starting_items
    
    def get_items_by_type(self, item_type: str) -> List[ItemData]:
        """根据类型获取物品列表"""
        return [item for item in self.items.values() if item.type == item_type]

# 测试函数
def test_loader():
    """测试配置加载器"""
    loader = ConfigLoader()
    if loader.load_all():
        print("\n=== 配置数据预览 ===")
        print(f"敌人数量: {len(loader.enemies)}")
        print(f"物品数量: {len(loader.items)}")
        print(f"战车数量: {len(loader.vehicles)}")
        print(f"地图数量: {len(loader.maps)}")
        print(f"NPC数量: {len(loader.npcs)}")
        print(f"技能数量: {len(loader.skills)}")
        print(f"商店数量: {len(loader.shops)}")
        print(f"任务数量: {len(loader.quests)}")
        
        # 显示第一个敌人
        if loader.enemies:
            first_enemy = next(iter(loader.enemies.values()))
            print(f"\n示例敌人: {first_enemy.name}")
            print(f"  HP: {first_enemy.hp}, 攻击: {first_enemy.attack}")
            print(f"  描述: {first_enemy.description}")

if __name__ == "__main__":
    test_loader()