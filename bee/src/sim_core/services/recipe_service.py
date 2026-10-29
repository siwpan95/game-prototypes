# -*- coding: utf-8 -*-
"""配方/合成服务 — 材料→装备/药水/数值提升

在长休时自动检查材料背包，匹配配方并合成。
配方 JSON 可被 Excel 替换。
"""
from __future__ import annotations
import json
import os
import random
from typing import List, Dict, Optional, Tuple


class RecipeService:
    """配方合成引擎"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(src_dir, "resources", "data")
        self.data_dir = data_dir
        self._recipes: List[dict] = []
        self._loaded = False

    def _load_recipes(self) -> List[dict]:
        """加载配方（JSON 优先，后续可扩展 Excel）"""
        if self._loaded:
            return self._recipes

        path = os.path.join(self.data_dir, "recipe_templates.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                self._recipes = json.load(f)
        self._loaded = True
        return self._recipes

    def get_all_recipes(self) -> List[dict]:
        return self._load_recipes()

    def check_craftable(self, materials: Dict[str, int]) -> List[Tuple[dict, str]]:
        """检查哪些配方可以合成

        Returns:
            list of (recipe_dict, reason) — reason 为空表示可合成
        """
        recipes = self._load_recipes()
        craftable = []
        for recipe in recipes:
            needed = recipe.get("materials", {})
            reason = ""
            for mat, qty in needed.items():
                if materials.get(mat, 0) < qty:
                    reason = f"缺少 {mat} ({materials.get(mat, 0)}/{qty})"
                    break
            craftable.append((recipe, reason))
        return craftable

    def craft(self, recipe: dict, materials: Dict[str, int],
              item_service=None, character=None) -> Optional[str]:
        """执行合成，扣除材料，返回结果描述"""
        needed = recipe.get("materials", {})
        for mat, qty in needed.items():
            if materials.get(mat, 0) < qty:
                return None
        # 扣除材料
        for mat, qty in needed.items():
            materials[mat] -= qty
            if materials[mat] <= 0:
                del materials[mat]

        output_type = recipe.get("output_type", "gold")
        output_value = recipe.get("output_value", 0)

        if output_type == "gold" and character:
            character.gold += output_value
            return f"+{output_value}G"

        if output_type == "exp" and character:
            character.gain_exp(output_value)
            return f"+{output_value}EXP"

        if output_type == "permanent" and character:
            effect = recipe.get("output_effect", "")
            if effect == "attack_boost":
                if not hasattr(character, "base_attack_bonus"):
                    character.base_attack_bonus = 0
                character.base_attack_bonus += output_value
            return f"基础攻击力永久 +{output_value}"

        if output_type == "consumable":
            effect = recipe.get("output_effect", "")
            if effect == "heal" and character:
                healed = min(output_value, character.max_hp - character.hp)
                character.hp += healed
                return f"恢复 {healed} HP"
            if effect == "auto_revive":
                if not hasattr(character, "_soul_stones"):
                    character._soul_stones = 0
                character._soul_stones += 1
                return "获得【灵魂石】x1（死亡时自动复活）"
            if effect == "poison_weapon" and character:
                character._poison_weapon_turns = (character._poison_weapon_turns if hasattr(character, '_poison_weapon_turns') else 0) + output_value
                return f"武器附毒 {output_value} 回合"

        if output_type in ("equipment", "accessory") and item_service and character:
            quality_map = {
                "CRUDE": 0, "NORMAL": 1, "FINE": 2, "SUPERIOR": 3,
                "EXCELLENT": 4, "MASTER": 5, "LEGENDARY": 6, "ARTIFACT": 7,
            }
            from ..models.item import EquipmentSlot
            slot_name = recipe.get("output_slot", "CHEST")
            if output_type == "accessory":
                try:
                    slot = getattr(EquipmentSlot, slot_name)
                except (AttributeError, KeyError):
                    slot = EquipmentSlot.RING
                loot = item_service.generate_accessory(character.level, slot)
            else:
                loot = item_service.generate_loot(character.level)
                # target slot
                try:
                    target_slot = getattr(EquipmentSlot, slot_name)
                    loot.slot = target_slot
                except (AttributeError, KeyError):
                    pass

            if loot:
                if character.try_auto_equip(loot):
                    return f"获得并装备: {loot.get_display_name()}"
                else:
                    return f"获得: {loot.get_display_name()}（已有更好的装备）"

        return f"合成完成: {recipe.get('name', '?')}"

    def auto_craft_all(self, materials: Dict[str, int], item_service=None,
                       character=None) -> List[str]:
        """自动合成所有可合成的配方（长休时调用）"""
        results = []
        recipes = self._load_recipes()
        random.shuffle(recipes)  # 随机顺序，避免总是合最前面的

        for recipe in recipes:
            result = self.craft(recipe, materials, item_service, character)
            if result:
                results.append(f"[合成] {recipe.get('name', '?')}: {result}")
        return results
