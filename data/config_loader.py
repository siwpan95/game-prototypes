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
    drop_item_id: int = 0  # 掉落物品ID（0=不掉落）
    drop_rate: float = 0.0  # 掉落率（0-1）
    is_bounty: bool = False  # 是否赏金首专用战斗数据（不随机遭遇）
    category: str = "生物"  # 系别：生物/机械/电气（道具克制依据）

@dataclass
class ItemData:
    id: int
    name: str
    type: str
    effect_value: int
    price: int
    description: str
    usable_in_battle: bool
    equip_slot: str = ""  # 装备槽位：""=消耗品；头/身/手/鞋/武器=可装备
    use_scene: str = "人"  # 使用场景：人/车/弹/探索
    effect_type: str = ""  # 效果类型（见 create.py 注释）

    @property
    def is_equipment(self) -> bool:
        return self.equip_slot != ""

@dataclass
class ChassisData:
    """战车底盘"""
    id: int
    name: str
    durability: int      # 耐久（战车 HP 上限）
    defense: int         # 底盘防御
    defense_max: int     # 改造防御上限
    weight: float        # 自重（吨）
    main_slots: int = 1  # 主炮孔
    sub_slots: int = 1   # 副炮孔
    se_slots: int = 0    # S-E 孔
    description: str = ""


@dataclass
class EngineData:
    """战车引擎（决定载重）"""
    id: int
    name: str
    load: float          # 载重（吨）
    defense: int         # 引擎防御
    weight: float        # 自重（吨）
    description: str = ""
    price: int = 0       # 改造店更换价格（0=不出售）


@dataclass
class CUnitData:
    """C 装置（火控，决定命中/回避）"""
    id: int
    name: str
    hit: int
    evade: int
    defense: int
    weight: float
    description: str = ""


@dataclass
class WeaponData:
    """战车武器（主炮/副炮/S-E）"""
    id: int
    name: str
    type: str            # 主炮 / 副炮 / SE
    attack: int
    weight: float
    description: str = ""
    price: int = 0       # 战车店购买价格（0=不出售，专有/掉落）


@dataclass
class VehicleData:
    """战车配置：引用底盘/引擎/C装置/武器部件

    旧版 Vehicles 表（扁平 HP/攻/防/速度 列）加载时会自动合成一套
    部件数据，保证向后兼容。
    """
    id: int
    name: str
    chassis_id: int
    engine_id: int
    cunit_id: int
    main_weapon_ids: list
    sub_weapon_ids: list
    se_weapon_ids: list
    armor_plates: int
    fuel_capacity: int
    fuel_consumption: float
    repair_cost: int
    description: str = ""
    # 获取方式：default=初始拥有；site=荒野坐标发现；bounty=击败赏金首获得
    acquire_type: str = "default"
    acquire_x: int = 0
    acquire_y: int = 0
    acquire_price: int = 0
    acquire_bounty_id: int = 0

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
    effect_type: str = ""  # 效果类型（pierce/double_strike/repair_vehicle/melee_mastery）
    class_id: int = 0       # 职业限定（0=全职业；1=猎人 2=机械师 3=战士）
    cooldown: int = 0       # 使用后冷却回合数


@dataclass
class ClassData:
    """职业：成长率 + 专属特技"""
    id: int
    name: str
    hp_growth: int = 10
    attack_growth: int = 3
    defense_growth: int = 2
    speed_growth: int = 1
    signature_skill: str = ""
    description: str = ""

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


@dataclass
class BountyData:
    """赏金首配置：固定位置的明雷 Boss，悬赏金在悬赏榜结算"""
    id: int
    name: str
    reward: int            # 悬赏金额
    map_id: int            # 所在地图
    x: int                 # 位置坐标
    y: int
    enemy_id: int          # 引用的敌人战斗数据（Enemies 表）
    on_foot: bool = False  # 强制人战（必须下车步行应战）
    description: str = ""

class ConfigLoader:
    def __init__(self, excel_path: str = "config.xlsx"):
        self.excel_path = excel_path
        self.enemies: Dict[int, EnemyData] = {}
        self.items: Dict[int, ItemData] = {}
        self.chassis: Dict[int, ChassisData] = {}
        self.engines: Dict[int, EngineData] = {}
        self.cunits: Dict[int, CUnitData] = {}
        self.weapons: Dict[int, WeaponData] = {}
        self.vehicles: Dict[int, VehicleData] = {}
        self.maps: Dict[int, MapData] = {}
        self.npcs: Dict[int, NPCData] = {}
        self.skills: Dict[int, SkillData] = {}
        self.classes: Dict[int, ClassData] = {}
        self.shops: Dict[int, ShopData] = {}
        self.quests: Dict[int, QuestData] = {}
        self.bounties: Dict[int, BountyData] = {}

    def load_all(self) -> bool:
        """加载所有配置数据"""
        try:
            if not os.path.exists(self.excel_path):
                print(f"配置文件不存在: {self.excel_path}")
                return False

            # 加载各个工作表
            self._load_enemies()
            self._load_items()
            self._load_chassis()
            self._load_engines()
            self._load_cunits()
            self._load_weapons()
            self._load_vehicles()
            self._load_maps()
            self._load_npcs()
            self._load_skills()
            self._load_classes()
            self._load_shops()
            self._load_quests()
            self._load_bounties()

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
                    drop_item_id=int(_col(row, '掉落物品ID', 0)),
                    drop_rate=float(_col(row, '掉落率', 0.0)),
                    is_bounty=_to_bool(_col(row, '是否赏金首', False), False),
                    category=str(_col(row, '系别', '生物') or '生物'),
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
                    usable_in_battle=bool(row['战斗中可用']),
                    equip_slot=str(_col(row, '装备槽位', '') or '').strip(),
                    use_scene=str(_col(row, '使用场景', '人') or '人').strip(),
                    effect_type=str(_col(row, '效果类型', '') or '').strip(),
                )
                self.items[item.id] = item
            print(f"加载了 {len(self.items)} 个物品配置")
        except Exception as e:
            print(f"加载物品配置失败: {e}")
    
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
                    effect_type=str(_col(row, '效果类型', '') or ''),
                    class_id=int(_col(row, '职业限定', 0)),
                    cooldown=max(0, int(_col(row, '冷却', 0))),
                )
                self.skills[skill.id] = skill
            print(f"加载了 {len(self.skills)} 个技能配置")
        except Exception as e:
            print(f"加载技能配置失败: {e}")

    def _load_classes(self):
        """加载职业配置（缺表时静默跳过）"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Classes')
            for _, row in df.iterrows():
                class_data = ClassData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    hp_growth=int(_col(row, 'HP成长', 10)),
                    attack_growth=int(_col(row, '攻击成长', 3)),
                    defense_growth=int(_col(row, '防御成长', 2)),
                    speed_growth=int(_col(row, '速度成长', 1)),
                    signature_skill=str(_col(row, '特技', '') or ''),
                    description=str(_col(row, '描述', '') or ''),
                )
                self.classes[class_data.id] = class_data
            print(f"加载了 {len(self.classes)} 个职业配置")
        except Exception as e:
            if "No sheet named" in str(e) or "Worksheet" in str(e):
                return
            print(f"加载职业配置失败: {e}")

    def get_class_by_id(self, class_id: int) -> Optional[ClassData]:
        return self.classes.get(class_id)
    
    def _load_shops(self):
        """加载商店配置"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Shops')
            for _, row in df.iterrows():
                shop = ShopData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    type=str(row['类型']),
                    map_id=int(row['地图ID']),
                    items=self._parse_id_list(row['商品列表']),
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
    
    @staticmethod
    def _parse_id_list(value) -> list:
        """把单元格解析成 int 列表，兼容 "1,2,3" / "1, 2" / 数字 6 / 6.0"""
        if value is None:
            return []
        if isinstance(value, float) and math.isnan(value):
            return []
        # 数字（含 numpy 数值类型）：单个 ID
        try:
            return [int(value)]
        except (TypeError, ValueError):
            pass
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return []
        result = []
        for part in text.split(','):
            part = part.strip()
            if part:
                try:
                    result.append(int(part))
                except ValueError:
                    continue
        return result

    def _load_chassis(self):
        """加载底盘配置（缺表时静默跳过）"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Chassis')
            for _, row in df.iterrows():
                chassis = ChassisData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    durability=int(row['耐久']),
                    defense=int(row['底盘防御']),
                    defense_max=int(_col(row, '防御上限', row['底盘防御'] * 4)),
                    weight=float(row['自重']),
                    main_slots=int(_col(row, '主炮孔', 1)),
                    sub_slots=int(_col(row, '副炮孔', 1)),
                    se_slots=int(_col(row, 'SE孔', 0)),
                    description=str(_col(row, '描述', '') or ''),
                )
                self.chassis[chassis.id] = chassis
            print(f"加载了 {len(self.chassis)} 个底盘配置")
        except Exception as e:
            if "No sheet named" in str(e) or "Worksheet" in str(e):
                return
            print(f"加载底盘配置失败: {e}")

    def _load_engines(self):
        """加载引擎配置（缺表时静默跳过）"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Engines')
            for _, row in df.iterrows():
                engine = EngineData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    load=float(row['载重']),
                    defense=int(_col(row, '防御', 0)),
                    weight=float(row['自重']),
                    description=str(_col(row, '描述', '') or ''),
                    price=int(_col(row, '价格', 0)),
                )
                self.engines[engine.id] = engine
            print(f"加载了 {len(self.engines)} 个引擎配置")
        except Exception as e:
            if "No sheet named" in str(e) or "Worksheet" in str(e):
                return
            print(f"加载引擎配置失败: {e}")

    def _load_cunits(self):
        """加载 C 装置配置（缺表时静默跳过）"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='CUnits')
            for _, row in df.iterrows():
                cunit = CUnitData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    hit=int(row['命中']),
                    evade=int(row['回避']),
                    defense=int(row['防御']),
                    weight=float(row['自重']),
                    description=str(_col(row, '描述', '') or ''),
                )
                self.cunits[cunit.id] = cunit
            print(f"加载了 {len(self.cunits)} 个C装置配置")
        except Exception as e:
            if "No sheet named" in str(e) or "Worksheet" in str(e):
                return
            print(f"加载C装置配置失败: {e}")

    def _load_weapons(self):
        """加载战车武器配置（缺表时静默跳过）"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Weapons')
            for _, row in df.iterrows():
                weapon = WeaponData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    type=str(row['类型']),
                    attack=int(row['攻击']),
                    weight=float(row['自重']),
                    description=str(_col(row, '描述', '') or ''),
                    price=int(_col(row, '价格', 0)),
                )
                self.weapons[weapon.id] = weapon
            print(f"加载了 {len(self.weapons)} 个战车武器配置")
        except Exception as e:
            if "No sheet named" in str(e) or "Worksheet" in str(e):
                return
            print(f"加载战车武器配置失败: {e}")

    def _load_vehicles(self):
        """加载战车配置

        新版：引用部件 ID 列。旧版（扁平 HP/攻/防 列）自动合成部件。
        """
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Vehicles')
            legacy = '底盘ID' not in df.columns
            for _, row in df.iterrows():
                vid = int(row['ID'])
                name = str(row['名称'])
                if legacy:
                    vehicle = self._synthesize_legacy_vehicle(vid, name, row)
                else:
                    vehicle = VehicleData(
                        id=vid,
                        name=name,
                        chassis_id=int(row['底盘ID']),
                        engine_id=int(row['引擎ID']),
                        cunit_id=int(row['C装置ID']),
                        main_weapon_ids=self._parse_id_list(row['主炮ID列表']),
                        sub_weapon_ids=self._parse_id_list(row['副炮ID列表']),
                        se_weapon_ids=self._parse_id_list(row['SE_ID列表']),
                        armor_plates=int(_col(row, '装甲片', 20)),
                        fuel_capacity=int(row['燃料容量']),
                        fuel_consumption=float(row['燃料消耗']),
                        repair_cost=int(row['修理费用']),
                        description=str(_col(row, '描述', '') or ''),
                        acquire_type=str(_col(row, '获取方式', 'default') or 'default'),
                        acquire_x=int(_col(row, '获取X', 0)),
                        acquire_y=int(_col(row, '获取Y', 0)),
                        acquire_price=int(_col(row, '获取价格', 0)),
                        acquire_bounty_id=int(_col(row, '获取条件', 0)),
                    )
                self.vehicles[vehicle.id] = vehicle
            if legacy:
                print(f"加载了 {len(self.vehicles)} 个战车配置（旧版扁平格式，已自动合成部件）")
            else:
                print(f"加载了 {len(self.vehicles)} 个战车配置")
        except Exception as e:
            print(f"加载战车配置失败: {e}")

    def _synthesize_legacy_vehicle(self, vid: int, name: str, row) -> VehicleData:
        """旧版扁平 Vehicles 行 → 合成一套部件（向后兼容）"""
        hp = int(_col(row, 'HP', 300))
        attack = int(_col(row, '攻击', 0))
        defense = int(_col(row, '防御', 0))
        chassis_id = -(vid * 10 + 1)
        engine_id = -(vid * 10 + 2)
        cunit_id = -(vid * 10 + 3)
        weapon_id = -(vid * 10 + 4) if attack > 0 else 0
        self.chassis[chassis_id] = ChassisData(
            id=chassis_id, name=f"{name}·底盘", durability=hp,
            defense=defense, defense_max=defense * 4, weight=10.0,
            main_slots=1, sub_slots=1, se_slots=1,
            description="旧版配置自动合成",
        )
        self.engines[engine_id] = EngineData(
            id=engine_id, name=f"{name}·引擎", load=30.0,
            defense=0, weight=1.0, description="旧版配置自动合成",
        )
        self.cunits[cunit_id] = CUnitData(
            id=cunit_id, name=f"{name}·C装置", hit=10, evade=5,
            defense=0, weight=1.0, description="旧版配置自动合成",
        )
        main_ids = []
        if attack > 0:
            self.weapons[weapon_id] = WeaponData(
                id=weapon_id, name=f"{name}·主炮", type="主炮",
                attack=attack, weight=1.0, description="旧版配置自动合成",
            )
            main_ids = [weapon_id]
        return VehicleData(
            id=vid, name=name,
            chassis_id=chassis_id, engine_id=engine_id, cunit_id=cunit_id,
            main_weapon_ids=main_ids, sub_weapon_ids=[], se_weapon_ids=[],
            armor_plates=20,
            fuel_capacity=int(_col(row, '燃料容量', 100)),
            fuel_consumption=float(_col(row, '燃料消耗', 1.0)),
            repair_cost=int(_col(row, '修理费用', 100)),
            description=str(_col(row, '描述', '') or ''),
        )

    def get_chassis_by_id(self, chassis_id: int) -> Optional[ChassisData]:
        return self.chassis.get(chassis_id)

    def get_engine_by_id(self, engine_id: int) -> Optional[EngineData]:
        return self.engines.get(engine_id)

    def get_cunit_by_id(self, cunit_id: int) -> Optional[CUnitData]:
        return self.cunits.get(cunit_id)

    def get_weapon_by_id(self, weapon_id: int) -> Optional[WeaponData]:
        return self.weapons.get(weapon_id)

    def get_vehicle_by_id(self, vehicle_id: int) -> Optional[VehicleData]:
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
        遭遇率为 0 的敌人（如赏金首）不参与随机遭遇。
        """
        if not self.enemies:
            return None

        candidates = [e for e in self.enemies.values()
                      if e.region_id == map_id and e.encounter_rate > 0]
        if not candidates:
            candidates = [e for e in self.enemies.values()
                          if e.region_id == 1 and e.encounter_rate > 0]
        if not candidates:
            return None

        weights = [e.encounter_rate for e in candidates]
        total = sum(weights)
        if total <= 0:
            return random.choice(candidates)

        roll = random.uniform(0, total)
        acc = 0.0
        for enemy in candidates:
            acc += enemy.encounter_rate
            if roll <= acc:
                return enemy

        return candidates[-1]

    def _load_bounties(self):
        """加载赏金首配置（缺表时跳过，保持向后兼容）"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Bounties')
            for _, row in df.iterrows():
                bounty = BountyData(
                    id=int(row['ID']),
                    name=str(row['名称']),
                    reward=int(row['悬赏金额']),
                    map_id=int(row['所在地图ID']),
                    x=int(row['坐标X']),
                    y=int(row['坐标Y']),
                    enemy_id=int(row['敌人ID']),
                    on_foot=_to_bool(_col(row, '强制人战', False), False),
                    description=str(_col(row, '描述', '') or ''),
                )
                self.bounties[bounty.id] = bounty
            print(f"加载了 {len(self.bounties)} 个赏金首配置")
        except Exception as e:
            # 没有 Bounties 表属正常（旧配置），静默跳过
            if "No sheet named" in str(e) or "Worksheet" in str(e):
                return
            print(f"加载赏金首配置失败: {e}")

    def get_bounty_by_id(self, bounty_id: int) -> Optional[BountyData]:
        return self.bounties.get(bounty_id)
    
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