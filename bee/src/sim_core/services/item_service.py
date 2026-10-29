# -*- coding: utf-8 -*-
"""物品生成服务 - 逻辑与数据解耦，优先从 Excel 加载"""
from __future__ import annotations
import json
import os
import random
from typing import Dict, List, Optional, Union
from ..models.item import (
    ItemQuality, EquipmentSlot, WeaponType, ArmorType,
    Weapon, Armor, Accessory
)
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class ItemService:
    """物品生成服务 - Excel 优先 → JSON 回退"""

    def __init__(self, data_dir: str = None, data_service=None):
        if data_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(src_dir, "resources", "data")
        self.data_dir = data_dir
        self._cache = {}
        self._data_service = data_service  # 可注入 DataService 实现 Excel 加载

    def _load_config(self) -> dict:
        """加载物品配置（Excel 优先，JSON 回退）"""
        if "item_templates" in self._cache:
            return self._cache["item_templates"]

        # 优先从 DataService (Excel) 加载
        if self._data_service is not None:
            data = self._data_service.get_item_templates()
            self._cache["item_templates"] = data
            return data

        # 回退到直接加载 JSON
        filepath = os.path.join(self.data_dir, "item_templates.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache["item_templates"] = data
                return data
        except FileNotFoundError:
            logger.warning("数据文件不存在: %s", filepath)
            return {}
        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败: %s, %s", filepath, e)
            return {}
    
    def _get_quality_mult(self, quality: ItemQuality, mult_type: str) -> float:
        """获取品质倍率"""
        data = self._load_config()
        if mult_type == "damage":
            mult_dict = data.get("quality_settings", {}).get("QUALITY_DAMAGE_MULT", {})
        elif mult_type == "defense":
            mult_dict = data.get("quality_settings", {}).get("QUALITY_DEFENSE_MULT", {})
        else:
            return 1.0
        
        return mult_dict.get(quality.name, 1.0)
    
    def _roll_quality(self, player_level: int) -> ItemQuality:
        """根据玩家等级 roll 物品品质"""
        # 权重配置（可以从 JSON 加载，这里简化）
        weights = [50, 30, 15, 8, 4, 2, 0.8, 0.2]
        
        if player_level >= 20:
            weights = [10, 20, 30, 20, 12, 5, 2, 1]
        elif player_level >= 10:
            weights = [30, 35, 20, 10, 4, 1, 0, 0]
        
        idx = random.choices(range(len(weights)), weights=weights)[0]
        return list(ItemQuality)[idx]
    
    def _random_bonuses(self, quality: ItemQuality, level: int) -> Dict[str, int]:
        """生成随机属性加成"""
        bonuses = {}
        num_bonus = quality.value[1]
        if num_bonus <= 0:
            return bonuses

        data = self._load_config()
        stat_pool = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma",
                      "crit_chance", "attack_speed", "hp_bonus", "mp_bonus"]
        
        chosen = random.sample(stat_pool, k=min(num_bonus, len(stat_pool)))
        for stat in chosen:
            if stat in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
                bonuses[stat] = random.randint(1, max(2, level // 3 + 1))
            elif stat == "crit_chance":
                bonuses[stat] = random.randint(1, 8)
            elif stat == "attack_speed":
                bonuses[stat] = random.randint(1, 15)
            else:
                bonuses[stat] = random.randint(5, 10 + level * 2)
        return bonuses
    
    def _assemble_name(self, base_name: str, prefix_pool: list, data: dict = None) -> str:
        """拼装物品名称：随机 min~max 个前缀 + 基础名称（数量由配置控制）"""
        if not prefix_pool:
            return base_name
        # 从配置中读取前后缀数量
        prefix_settings = data.get("prefix_settings", {}) if data else {}
        min_p = prefix_settings.get("min_prefixes", 1)
        max_p = prefix_settings.get("max_prefixes", 3)
        n = random.randint(min_p, max_p)
        n = min(n, len(prefix_pool))
        chosen = random.sample(prefix_pool, k=n)
        return "".join(chosen) + base_name
    def generate_weapon(self, player_level: int, weapon_type: Optional[WeaponType] = None) -> Weapon:
        """生成一把程序化武器"""
        quality = self._roll_quality(player_level)
        if weapon_type is None:
            weapon_type = random.choice(list(WeaponType))
        if weapon_type == WeaponType.SHIELD:
            weapon_type = WeaponType.SWORD
        
        # 从配置加载武器模板
        data = self._load_config()
        templates = data.get("weapon_templates", {})
        type_key = weapon_type.name
        if type_key in templates:
            base_name = random.choice(templates[type_key])
        else:
            base_name = "未知武器"
        
        # 统一拼装：随机1~3个前缀 + 基础名称
        prefix_pool = data.get("prefixes", [])
        name = self._assemble_name(base_name, prefix_pool, data)
        
        base_damage = 5 + player_level * 2
        damage = int(base_damage * self._get_quality_mult(quality, "damage") + random.randint(-3, 5))
        damage = max(1, damage)
        
        speed = round(random.uniform(1.2, 3.5), 1)
        crit = round(0.05 + quality.value[1] * 0.01 + random.uniform(-0.01, 0.03), 3)
        
        bonuses = self._random_bonuses(quality, player_level)
        
        return Weapon(
            name=name,
            item_type="weapon",
            quality=quality,
            level_req=max(1, player_level - 3),
            value=damage * 5 + quality.value[1] * 20,
            weapon_type=weapon_type,
            damage=damage,
            speed=speed,
            crit_chance=max(0.01, min(0.5, crit)),
            bonuses=bonuses,
        )
    
    def generate_armor(self, player_level: int, slot: EquipmentSlot) -> Armor:
        """生成一件程序化护甲"""
        quality = self._roll_quality(player_level)
        
        # 根据 slot 选择护甲类型
        if slot in (EquipmentSlot.HEAD, EquipmentSlot.HANDS, EquipmentSlot.FEET):
            armor_type = random.choice([ArmorType.LIGHT, ArmorType.MEDIUM])
        elif slot == EquipmentSlot.CHEST:
            armor_type = random.choice(list(ArmorType))
        elif slot == EquipmentSlot.LEGS:
            armor_type = random.choice([ArmorType.MEDIUM, ArmorType.HEAVY, ArmorType.ROBE])
        else:
            armor_type = random.choice(list(ArmorType))
        
        # 从配置加载护甲模板
        data = self._load_config()
        templates = data.get("armor_templates", {})
        type_key = armor_type.name
        if type_key in templates:
            base_name = random.choice(templates[type_key])
        else:
            base_name = "未知护甲"
        
        slot_suffix = {
            EquipmentSlot.HEAD: "头盔",
            EquipmentSlot.CHEST: "胸甲",
            EquipmentSlot.HANDS: "手套",
            EquipmentSlot.LEGS: "护腿",
            EquipmentSlot.FEET: "靴子",
        }
        
        # 统一拼装：随机1~3个前缀 + 基础名称
        prefix_pool = data.get("prefixes", [])
        suffix = slot_suffix.get(slot, "")
        name = self._assemble_name(base_name, prefix_pool, data) + suffix
        
        base_defense = 3 + player_level * 1.5
        defense = int(base_defense * self._get_quality_mult(quality, "defense") + random.randint(-2, 4))
        defense = max(1, defense)
        
        bonuses = self._random_bonuses(quality, player_level)
        
        return Armor(
            name=name,
            item_type="armor",
            quality=quality,
            level_req=max(1, player_level - 3),
            value=defense * 4 + quality.value[1] * 15,
            armor_type=armor_type,
            defense=defense,
            slot=slot,
            bonuses=bonuses,
        )
    
    def generate_loot(self, player_level: int, loot_table: str = "normal"):
        """生成战利品 - 统一入口"""
        roll = random.random()
        if roll < 0.15:
            # 饰品
            slot = random.choice([EquipmentSlot.NECK, EquipmentSlot.RING])
            return self.generate_accessory(player_level, slot)
        elif roll < 0.55:
            # 武器
            return self.generate_weapon(player_level)
        else:
            # 护甲
            slot = random.choice([
                EquipmentSlot.HEAD, EquipmentSlot.CHEST,
                EquipmentSlot.HANDS, EquipmentSlot.LEGS, EquipmentSlot.FEET
            ])
            return self.generate_armor(player_level, slot)

    # ═══════════════════════════════════════════════════════
    #  标签驱动材料掉落
    # ═══════════════════════════════════════════════════════

    # 标签 → 材料映射（掉落名称, 基础价值, 掉落概率）
    TAG_MATERIALS = {
        "龙系":   [("龙鳞",  30, 0.25), ("龙牙",   40, 0.15), ("龙血精华", 60, 0.05)],
        "亡灵系": [("灵魂精华", 15, 0.25), ("暗影碎片", 12, 0.20), ("亡灵之骨", 10, 0.15)],
        "邪能系": [("恶魔之角", 20, 0.20), ("虚空碎片", 18, 0.15), ("混沌精华", 35, 0.05)],
        "元素系": [("元素结晶", 15, 0.25), ("魔力粉尘", 10, 0.20), ("元素之心", 50, 0.03)],
        "自然系": [("野兽毛皮", 8,  0.30), ("毒腺",    12, 0.15), ("生命精华", 25, 0.05)],
        "机械系": [("齿轮组件", 12, 0.25), ("魔力核心", 20, 0.15), ("古代零件", 30, 0.05)],
        "人形系": [("破损武器", 10, 0.20), ("金币袋",  15, 0.15), ("战术手册", 25, 0.03)],
    }

    # 稀有度 → 材料掉落加成
    RARITY_MATERIAL_BONUS = {
        "普通":  1.0,
        "精英":  1.5,
        "稀有":  3.0,
        "传说":  5.0,
    }

    def roll_materials(self, tags: list, rarity: str = "普通", level: int = 1) -> list:
        """根据敌人标签和稀有度摇材料掉落

        Returns:
            list of (材料名, 金币价值) 元组
        """
        if not tags:
            return []

        materials = []
        bonus = self.RARITY_MATERIAL_BONUS.get(rarity, 1.0)

        for tag in tags:
            material_list = self.TAG_MATERIALS.get(tag)
            if not material_list:
                continue
            for name, base_value, chance in material_list:
                effective_chance = chance * bonus
                if random.random() < effective_chance:
                    scaled_value = max(1, int(base_value * (1.0 + level * 0.05)))
                    materials.append((name, scaled_value))

        return materials
    
    def generate_accessory(self, player_level: int, slot: EquipmentSlot) -> Accessory:
        """生成一个饰品"""
        quality = self._roll_quality(player_level)
        if quality.value[1] < ItemQuality.FINE.value[1]:
            quality = ItemQuality.FINE
        
        data = self._load_config()

        if slot == EquipmentSlot.RING:
            name = random.choice(data.get("jewelry_names", {}).get("RING", ["铁戒指"]))
        else:
            slot = EquipmentSlot.NECK
            name = random.choice(data.get("jewelry_names", {}).get("NECK", ["铁项链"]))
        
        # 统一拼装：随机1~3个前缀 + 基础名称
        prefix_pool = data.get("prefixes", [])
        name = self._assemble_name(name, prefix_pool, data)
        
        effect_pool = data.get("effect_pool", ["生命恢复", "法力恢复", "暴击提升", "速度提升", "经验加成"])
        effect = random.choice(effect_pool)
        
        bonuses = self._random_bonuses(quality, player_level)
        
        return Accessory(
            name=name,
            item_type="accessory",
            quality=quality,
            level_req=max(1, player_level - 5),
            value=quality.value[1] * 30 + player_level * 5,
            slot=slot,
            effect=effect,
            bonuses=bonuses,
        )
