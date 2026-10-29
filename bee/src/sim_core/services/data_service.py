# -*- coding: utf-8 -*-
"""数据服务 — 基于 JSON 池子，零预加载，随用随取"""
from __future__ import annotations
from typing import Dict, List, Optional, Any

from ..utils.logging_config import get_logger
from ..json_pool import get_pool

logger = get_logger(__name__)


class DataService:
    """统一的数据服务 — 基于 JSON 池子，零预加载，随用随取"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir
        self._pool = get_pool()

    def clear_cache(self):
        """清除 JSON 池子缓存"""
        self._pool.clear_cache()
        logger.info("数据缓存已清除，下次访问将重新加载")

    def set_theme(self, theme_name: str = None):
        """切换主题包（P0：异界 DLC）；None 恢复默认数据目录"""
        self._pool.set_theme(theme_name)
        logger.info("主题切换: %s", theme_name or "默认")

    def get_theme_meta(self) -> Optional[dict]:
        """当前主题元信息（无主题时为 None）"""
        return self._pool.get_theme_meta()

    def get_item_templates(self) -> dict:
        """获取物品模板数据（首次访问时从 JSON 加载）"""
        return self._pool.get_item_templates()

    def get_enemy_templates(self) -> List[dict]:
        """获取敌人模板数据（首次访问时从 JSON 加载）"""
        raw = self._pool.get_data("enemy_templates")
        # 自动生成标签：每次加载时为模板注入 tags 字段
        # 标签 = {全名, race}，去重后用于任务匹配
        self._ensure_tags(raw)
        return raw

    # 种族 → 分类标签映射（第二层生态分类）
    _RACE_CATEGORY = {
        "亡灵": "亡灵系", "暗影": "亡灵系", "不死族": "亡灵系",
        "恶魔": "邪能系", "虚空": "邪能系",
        "龙族": "龙系", "龙裔": "龙系",
        "元素": "元素系",
        "构造体": "机械系",
        "昆虫": "自然系", "野兽": "自然系", "植物": "自然系",
        "史莱姆": "自然系", "魔物": "自然系",
        "人类": "人形系", "天使": "人形系", "兽人": "人形系",
        "哥布林": "人形系", "巨魔": "人形系", "巨人": "人形系",
    }

    # 种族 → 阵营标签（四大阵营）
    _RACE_FACTION = {
        "亡灵": "混沌阵营", "暗影": "混沌阵营", "不死族": "混沌阵营",
        "恶魔": "混沌阵营", "虚空": "混沌阵营",
        "哥布林": "混沌阵营", "兽人": "混沌阵营",
        "野兽": "自然阵营", "昆虫": "自然阵营", "植物": "自然阵营",
        "史莱姆": "自然阵营", "魔物": "自然阵营",
        "人类": "秩序阵营", "天使": "秩序阵营",
        "构造体": "秩序阵营", "龙裔": "秩序阵营",
        "龙族": "中立阵营", "元素": "中立阵营",
        "巨人": "中立阵营", "巨魔": "中立阵营",
    }

    _RACE_SIZE = {
        "巨人": "大型", "龙族": "大型", "巨魔": "大型",
        "昆虫": "中型", "野兽": "中型", "人类": "中型",
        "兽人": "中型", "哥布林": "中型", "龙裔": "中型",
        "天使": "中型", "构造体": "中型",
        "史莱姆": "小型", "亡灵": "小型", "暗影": "小型",
        "恶魔": "中型", "元素": "中型", "虚空": "中型",
        "不死族": "小型", "植物": "小型", "魔物": "中型",
    }

    @classmethod
    def _ensure_tags(cls, templates: list):
        """为敌人模板自动生成四层标签（就地修改）

        标签层级：
        L1: 模板全名 → 标签（如"哥布林战士"）
        L2: race 种族名 → 标签（如"哥布林"）
        L3: 生态分类 → 标签（如"人形系"、"中型"）
        L4: 阵营 → 标签（如"混沌阵营"）
        - 避免重复，不覆盖手动指定的标签
        """
        for tpl in templates:
            if "tags" not in tpl:
                tags = set()
                name = str(tpl.get("name", "")).strip()
                race = str(tpl.get("race", "")).strip()
                if name:
                    tags.add(name)
                if race:
                    tags.add(race)
                # L3: 生态分类标签
                category = cls._RACE_CATEGORY.get(race)
                if category:
                    tags.add(category)
                size = cls._RACE_SIZE.get(race)
                if size:
                    tags.add(size)
                # L4: 阵营标签
                faction = cls._RACE_FACTION.get(race)
                if faction:
                    tags.add(faction)
                tpl["tags"] = list(tags)

    def get_quest_templates(self) -> List[dict]:
        """获取任务模板数据（首次访问时从 JSON 加载）"""
        return self._pool.get_data("quest_templates")

    def get_potion_config(self) -> List[dict]:
        """获取药水配置（首次访问时从 JSON 加载）"""
        return self._pool.get_data("potion_config")

    def get_artifact_config(self) -> List[dict]:
        """获取神器配置（首次访问时从 JSON 加载）"""
        return self._pool.get_data("artifact_config")

    def get_achievement_config(self) -> List[dict]:
        """获取成就配置（首次访问时从 JSON 加载）"""
        return self._pool.get_data("achievement_config")

    def get_race_config(self) -> List[dict]:
        """获取种族配置（首次访问时从 JSON 加载）"""
        return self._pool.get_data("race_config")

    def get_class_config(self) -> List[dict]:
        """获取职业配置（首次访问时从 JSON 加载）"""
        return self._pool.get_data("class_config")

    def get_skill_config(self) -> List[dict]:
        """获取技能配置（首次访问时从 JSON 加载）"""
        return self._pool.get_data("skill_config")

    def get_rest_config(self) -> dict:
        """获取休息配置（首次访问时从 JSON 加载）"""
        return self._pool.get_rest_config()

    # ════════════════════════════════════════════════
    #  新增配置（Excel 可配）
    # ════════════════════════════════════════════════
    def get_affix_effect_config(self) -> list:
        return self._pool.get_data("affix_effect_config")

    def get_racial_ability_config(self) -> list:
        return self._pool.get_data("racial_ability_config")

    def get_material_drop_config(self) -> list:
        return self._pool.get_data("material_drop_config")

    def get_element_reaction_config(self) -> list:
        return self._pool.get_data("element_reaction_config")

    def get_recipe_config(self) -> list:
        return self._pool.get_data("recipe_templates")

    def get_event_config(self) -> list:
        return self._pool.get_data("event_templates")

    def get_environment_config(self) -> list:
        return self._pool.get_data("environment_config")

    def get_rarity_config(self) -> list:
        return self._pool.get_data("rarity_config")

    def get_faction_config(self) -> list:
        return self._pool.get_data("faction_config")

    def get_shop_config(self) -> list:
        return self._pool.get_data("shop_config")

    def get_enemy_by_name(self, name: str) -> Optional[dict]:
        """根据名称获取敌人模板"""
        return self._pool.find_item("enemy_templates", name=name)

    def get_enemies_by_level(self, level: int = 1, level_range: int = 999) -> List[dict]:
        """获取敌人模板（等级参数保留向后兼容，不再按等级过滤）"""
        return self.get_enemy_templates()
