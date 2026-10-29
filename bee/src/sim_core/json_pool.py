"""
JSON 池子机制 — 零预加载，随用随取

设计原则:
1. 启动时不读取任何文件
2. 首次访问时才从 JSON 文件加载
3. 加载后缓存，避免重复 I/O
4. 只读 JSON，不读 Excel（Excel→JSON 由 excel_to_json.py 构建阶段完成）

使用方法:
    from json_pool import JSONPool

    pool = JSONPool()

    # 首次访问 → 从磁盘加载 → 缓存
    enemies = pool.get_data("enemy_templates")

    # 再次访问 → 命中缓存，不读磁盘
    enemies = pool.get_data("enemy_templates")
"""

import json
import os
from typing import List, Dict, Any, Optional


class JSONPool:
    """JSON 数据池子 — 单例，零预加载，随用随取"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 防止重复初始化
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.base_dir = self._get_base_dir()
        self.data_dir = os.path.join(self.base_dir, "resources", "data")
        self._cache = {}
        self._theme_dir = None  # 主题包目录（异界 DLC），None = 默认数据

        # JSON 文件名映射（key → filename.json）
        self.json_files = {
            "enemy_templates":     "enemy_templates.json",
            "quest_templates":     "quest_templates.json",
            "weapon_templates":    "weapon_templates.json",
            "armor_templates":     "armor_templates.json",
            "accessory_templates": "accessory_templates.json",
            "quality_settings":    "quality_settings.json",
            "prefix_templates":    "prefix_templates.json",
            "effect_pool":         "effect_pool.json",
            "potion_config":       "potion_config.json",
            "artifact_config":     "artifact_config.json",
            "achievement_config":  "achievement_config.json",
            "race_config":         "race_config.json",
            "class_config":        "class_config.json",
            "skill_config":        "skill_config.json",
            "rest_config":         "rest_config.json",
            "prefix_settings":     "prefix_settings.json",
            # ★ 新增
            "affix_effect_config":       "affix_effect_config.json",
            "racial_ability_config":     "racial_ability_config.json",
            "material_drop_config":      "material_drop_config.json",
            "element_reaction_config":   "element_reaction_config.json",
            "recipe_templates":          "recipe_templates.json",
            "event_templates":           "event_templates.json",
            "environment_config":        "environment_config.json",
            "rarity_config":             "rarity_config.json",
            "faction_config":            "faction_config.json",
            "shop_config":               "shop_config.json",
        }

    def _get_base_dir(self) -> str:
        """获取基础目录（兼容开发模式和打包模式）"""
        import sys
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src")

    # ── 核心：随用随取 ──────────────────────────────────

    def get_data(self, key: str) -> List[Dict]:
        """按需从 JSON 加载数据（首次读盘 → 缓存 → 复用时命中缓存）

        Args:
            key: 数据键名（如 "enemy_templates"）
        Returns:
            数据列表，未找到则返回空列表
        """
        if key in self._cache:
            return self._cache[key]

        data = self._read_json(key)
        if data is None:
            data = []
        self._cache[key] = data
        return data

    def get_item(self, key: str, index: int) -> Optional[Dict]:
        """获取单条数据"""
        data = self.get_data(key)
        if 0 <= index < len(data):
            return data[index]
        return None

    def find_item(self, key: str, **kwargs) -> Optional[Dict]:
        """按条件查找第一条匹配数据"""
        data = self.get_data(key)
        for item in data:
            if all(item.get(k) == v for k, v in kwargs.items()):
                return item
        return None

    def filter_items(self, key: str, **kwargs) -> List[Dict]:
        """按条件过滤数据"""
        data = self.get_data(key)
        return [item for item in data
                if all(item.get(k) == v for k, v in kwargs.items())]

    def get_raw_json(self, key: str) -> Optional[Any]:
        """获取原始 JSON 数据（不缓存，用于 item_templates 等非列表结构）"""
        json_file = self.json_files.get(key)
        if not json_file:
            return None
        path = os.path.join(self.data_dir, json_file)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 读取 JSON 失败 {json_file}: {e}")
            return None

    # ── 缓存管理 ──────────────────────────────────────

    def clear_cache(self, key: Optional[str] = None):
        """清除缓存"""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def reload_data(self, key: str) -> List[Dict]:
        """强制重新加载"""
        self.clear_cache(key)
        return self.get_data(key)

    # ── 主题包（P0：异界 DLC，数据优先于默认目录）────────

    def set_theme(self, theme_name: str = None):
        """切换主题包：resources/themes/<name> 优先，缺失文件回退默认数据目录"""
        self._theme_dir = None
        if theme_name:
            candidate = os.path.join(self.base_dir, "resources", "themes", str(theme_name))
            if os.path.isdir(candidate):
                self._theme_dir = candidate
        self.clear_cache()

    def get_theme_meta(self) -> Optional[dict]:
        """返回当前主题的 meta.json（无主题或缺失时返回 None）"""
        if not self._theme_dir:
            return None
        path = os.path.join(self._theme_dir, "meta.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ── 内部：读 JSON 文件 ────────────────────────────

    def _read_json(self, key: str) -> Optional[List[Dict]]:
        json_file = self.json_files.get(key)
        if not json_file:
            return None
        # 主题优先：主题目录存在同名文件则用它，否则回退默认目录
        path = os.path.join(self.data_dir, json_file)
        if self._theme_dir:
            theme_path = os.path.join(self._theme_dir, json_file)
            if os.path.exists(theme_path):
                path = theme_path
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 读取 JSON 失败 {json_file}: {e}")
            return None

    # ── 物品模板（组合结构） ──────────────────────────

    def get_item_templates(self) -> dict:
        """获取物品模板（dict 结构，包含武器/护甲/饰品/品质/前缀/特效）"""
        raw = self.get_raw_json("item_templates")
        if raw and isinstance(raw, dict):
            return raw

        # 回退：从独立 JSON 文件组装
        return {
            "weapon_templates":    self._load_weapon_dict(),
            "armor_templates":     self._load_armor_dict(),
            "jewelry_names":       self._load_jewelry_dict(),
            "quality_settings":    self._load_quality_settings(),
            "prefixes":            self._load_prefixes(),
            "effect_pool":         self._load_effect_pool(),
            "prefix_settings":     self._load_prefix_settings(),
        }

    def __load_typed_dict(self, key: str, type_field: str, name_field: str) -> dict:
        """通用：将列表数据按类型分组为 {type: [name, ...]}（跳过 null/空名）"""
        result: dict = {}
        for item in self.get_data(key):
            t = str(item.get(type_field) or "").strip()
            raw_name = item.get(name_field)
            n = str(raw_name).strip() if raw_name is not None else ""
            if t and n:
                result.setdefault(t, []).append(n)
        return result

    def _load_weapon_dict(self) -> dict:
        data = self.__load_typed_dict("weapon_templates", "type", "name")
        return data if data else _DEFAULT_WEAPONS

    def _load_armor_dict(self) -> dict:
        data = self.__load_typed_dict("armor_templates", "type", "name")
        return data if data else _DEFAULT_ARMORS

    def _load_jewelry_dict(self) -> dict:
        result = {"NECK": [], "RING": []}
        for item in self.get_data("accessory_templates"):
            t = str(item.get("type") or "").strip().upper()
            raw_name = item.get("name")
            n = str(raw_name).strip() if raw_name is not None else ""
            if t in result and n:
                result[t].append(n)
        if any(result.values()):
            return result
        return _DEFAULT_JEWELRY

    def _load_quality_settings(self) -> dict:
        data = self.get_data("quality_settings")
        dm, dd = {}, {}
        qnames = ["CRUDE", "NORMAL", "FINE", "SUPERIOR", "EXCELLENT", "MASTER", "LEGENDARY", "ARTIFACT"]
        defaults_dmg = [0.7, 1.0, 1.2, 1.5, 2.0, 2.5, 3.5, 5.0]
        defaults_def = [0.7, 1.0, 1.2, 1.5, 2.0, 2.5, 3.5, 5.0]
        for item in data:
            q = str(item.get("品质", item.get("quality", ""))).strip().upper()
            if not q:
                continue
            if "伤害倍率" in item or "damage_mult" in item:
                try:
                    dm[q] = float(item.get("伤害倍率", item.get("damage_mult", 1.0)))
                except (ValueError, TypeError):
                    pass
            if "防御倍率" in item or "defense_mult" in item:
                try:
                    dd[q] = float(item.get("防御倍率", item.get("defense_mult", 1.0)))
                except (ValueError, TypeError):
                    pass
        for i, q in enumerate(qnames):
            dm.setdefault(q, defaults_dmg[i])
            dd.setdefault(q, defaults_def[i])
        return {"QUALITY_DAMAGE_MULT": dm, "QUALITY_DEFENSE_MULT": dd}

    def _load_prefixes(self) -> list:
        prefixes = [str(item.get("prefix", item.get("name", item.get("前缀", "")))).strip()
                    for item in self.get_data("prefix_templates")]
        prefixes = [p for p in prefixes if p]
        return prefixes if prefixes else _DEFAULT_PREFIXES

    def _load_effect_pool(self) -> list:
        effects = [str(item.get("name", item.get("特效名称", ""))).strip()
                   for item in self.get_data("effect_pool")]
        effects = [e for e in effects if e]
        return effects if effects else _DEFAULT_EFFECTS

    def _load_prefix_settings(self) -> dict:
        result = {"min_prefixes": 1, "max_prefixes": 3}
        for item in self.get_data("prefix_settings"):
            key = str(item.get("配置项", item.get("key", ""))).strip()
            val = item.get("值", item.get("value"))
            if key == "min_prefixes" and val is not None:
                try: result["min_prefixes"] = int(val)
                except (ValueError, TypeError): pass
            elif key == "max_prefixes" and val is not None:
                try: result["max_prefixes"] = int(val)
                except (ValueError, TypeError): pass
        return result

    # ── 休息配置 ──────────────────────────────────────

    def get_rest_config(self) -> dict:
        data = self.get_data("rest_config")
        flat = {}
        for item in data:
            key = str(item.get("配置项", item.get("key", ""))).strip()
            val = item.get("值", item.get("value"))
            if key:
                flat[key] = val
        short_rest = {}
        long_rest = {}
        for k, v in flat.items():
            if k.startswith("short_rest_"):
                short_rest[k.replace("short_rest_", "")] = self._parse_rest_value(v)
            elif k.startswith("long_rest_"):
                long_rest[k.replace("long_rest_", "")] = self._parse_rest_value(v)
        result = {}
        if short_rest: result["short_rest"] = short_rest
        if long_rest: result["long_rest"] = long_rest
        return result

    @staticmethod
    def _parse_rest_value(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "是", "yes", "1"): return True
            if v in ("false", "否", "no", "0"): return False
            try: return float(v) if "." in v else int(v)
            except ValueError: return value
        return value


# ── 硬编码回退 ──────────────────────────────────────────

_DEFAULT_WEAPONS = {
    "SWORD": ["铁剑", "钢剑", "符文剑", "秘银剑", "圣剑"],
    "AXE": ["铁斧", "战斧", "符文斧", "双刃斧", "破甲斧"],
    "MACE": ["铁锤", "钉锤", "符文锤", "战锤", "圣锤"],
    "DAGGER": ["铁匕", "淬毒匕", "符文匕", "暗影匕", "噬魂匕"],
    "STAFF": ["木杖", "法杖", "符文杖", "元素杖", "虚空杖"],
    "BOW": ["短弓", "长弓", "复合弓", "精灵弓", "龙筋弓"],
    "CROSSBOW": ["轻型弩", "重型弩", "连发弩", "破甲弩", "狙击弩"],
    "POLEARM": ["长矛", "戟", "薙刀", "符文长柄", "龙枪"],
}

_DEFAULT_ARMORS = {
    "LIGHT": ["皮甲", "硬皮甲", "精灵甲", "影甲", "虚空甲"],
    "MEDIUM": ["链甲", "鳞甲", "板链甲", "龙鳞甲", "秘银甲"],
    "HEAVY": ["板甲", "重板甲", "符文板甲", "圣板甲", "泰坦甲"],
    "ROBE": ["布袍", "法袍", "符文袍", "星辰袍", "虚空袍"],
}

_DEFAULT_JEWELRY = {
    "NECK": ["项链", "护符", "符文项链", "圣徽", "龙牙项链"],
    "RING": ["铜戒", "银戒", "金戒", "符文戒", "龙血戒"],
}

_DEFAULT_PREFIXES = ["破旧的", "生锈的", "普通的", "精良的", "卓越的", "传说的", "神器的"]
_DEFAULT_EFFECTS = ["火焰", "冰霜", "闪电", "毒素", "神圣", "暗影", "吸血", "暴击"]


# ── 全局单例 ────────────────────────────────────────────

_pool_instance = None

def get_pool() -> JSONPool:
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = JSONPool()
    return _pool_instance
