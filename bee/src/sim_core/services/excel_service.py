# -*- coding: utf-8 -*-
"""
Excel 配置导入服务
支持从 .xlsx 文件读取游戏配置，方便策划通过 Excel 更新游戏内容。
Excel 文件优先于 JSON 文件加载。
"""
import os
import sys
from typing import Dict, List, Optional

try:
    import openpyxl
    from openpyxl import Workbook, load_workbook
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


class ExcelService:
    """Excel 配置服务 — 读取 .xlsx 配置文件，返回与 JSON 一致的数据结构"""

    # 各 Sheet 的列映射
    ENEMY_COLS = ["名称", "等级", "HP", "伤害", "防御", "经验", "金币", "掉落表", "种族", "描述"]
    QUEST_COLS = ["任务ID", "任务名称", "类型", "描述", "目标", "目标数量",
                  "等级需求", "前置任务", "奖励经验", "奖励金币", "是否史诗", "故事文本", "完成文本"]
    WEAPON_TYPE_NAMES = ["SWORD", "AXE", "MACE", "DAGGER", "STAFF", "BOW", "CROSSBOW", "POLEARM"]
    ARMOR_TYPE_NAMES = ["LIGHT", "MEDIUM", "HEAVY", "ROBE"]
    QUALITY_NAMES = ["CRUDE", "NORMAL", "FINE", "SUPERIOR", "EXCELLENT", "MASTER", "LEGENDARY", "ARTIFACT"]
    POTION_COLS = ["药水名称", "描述", "持续时间(秒)", "掉落权重"]
    ARTIFACT_COLS = ["神器ID", "名称", "描述", "效果类型", "效果值", "来源"]
    ACHIEVEMENT_COLS = ["成就ID", "名称", "描述", "目标值", "奖励类型", "奖励值", "隐藏"]
    RACE_COLS = ["种族ID", "名称", "描述", "str_mod", "dex_mod", "con_mod",
                 "int_mod", "wis_mod", "cha_mod"]
    CLASS_COLS = ["职业ID", "名称", "分类名", "基础HP", "主属性1", "主属性2"]
    SKILL_COLS = ["技能ID", "所属职业", "名称", "描述", "effect_type",
                  "effect_value", "cooldown", "level_req"]
    REST_COLS = ["配置项", "值"]

    def __init__(self, excel_path: str = None):
        """初始化 Excel 服务

        Args:
            excel_path: Excel 文件路径，默认与 JSON 同目录
        """
        if not HAS_OPENPYXL:
            raise ImportError(
                "openpyxl 未安装。请运行: pip install openpyxl\n"
                "或添加到 requirements.txt: openpyxl>=3.1.0"
            )

        if excel_path is None:
            if getattr(sys, 'frozen', False):
                # 打包为 exe 后，从 exe 同目录下的 resources/config/ 读取外部 Excel 配置
                base_dir = os.path.dirname(sys.executable)
                excel_path = os.path.join(base_dir, "resources", "config", "game_config.xlsx")
            else:
                # 开发环境：从源码目录读取
                current_dir = os.path.dirname(os.path.abspath(__file__))
                src_dir = os.path.dirname(os.path.dirname(current_dir))
                config_dir = os.path.join(src_dir, "resources", "config")
                excel_path = os.path.join(config_dir, "game_config.xlsx")
        self.excel_path = excel_path
        self._cache = {}

    # ======================== 核心读取方法 ========================

    def file_exists(self) -> bool:
        """检查 Excel 配置文件是否存在"""
        return os.path.isfile(self.excel_path)

    def _open_workbook(self) -> Workbook:
        """打开工作簿（带缓存）"""
        if "_wb" in self._cache:
            return self._cache["_wb"]
        if not self.file_exists():
            raise FileNotFoundError(f"Excel 配置文件不存在: {self.excel_path}")
        wb = load_workbook(self.excel_path, read_only=True, data_only=True)
        self._cache["_wb"] = wb
        return wb

    def clear_cache(self):
        """清除缓存，强制重新读取 Excel"""
        if "_wb" in self._cache:
            self._cache["_wb"].close()
        self._cache.clear()

    @staticmethod
    def _parse_bool(value) -> bool:
        """将 Excel 中的值解析为布尔类型"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "是", "yes", "1")
        if isinstance(value, (int, float)):
            return bool(value)
        return False

    @staticmethod
    def _parse_float(value) -> float:
        """安全解析为浮点数"""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_int(value) -> int:
        """安全解析为整数"""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0

    def _read_sheet_to_dicts(self, sheet_name: str, columns: List[str],
                             start_row: int = 2) -> List[dict]:
        """通用方法：将 Sheet 数据读取为字典列表

        Args:
            sheet_name: Sheet 名称
            columns:  列名列表
            start_row: 数据起始行（默认第2行，第1行为表头）

        Returns:
            字典列表
        """
        wb = self._open_workbook()
        if sheet_name not in wb.sheetnames:
            print(f"警告: Sheet '{sheet_name}' 不存在")
            return []

        ws = wb[sheet_name]
        result = []
        for row in ws.iter_rows(min_row=start_row, values_only=True):
            if row is None or all(c is None for c in row):
                continue  # 跳过空行
            row_dict = {}
            for i, col_name in enumerate(columns):
                if i < len(row):
                    row_dict[col_name] = row[i]
                else:
                    row_dict[col_name] = None
            result.append(row_dict)
        return result

    # ======================== 敌人模板 ========================

    def get_enemy_templates(self) -> List[dict]:
        """读取敌人模板 → 只返回基础名称、种族、描述（数值由DDA硬编码基准值+动态缩放）"""
        raw = self._read_sheet_to_dicts("敌人模板", ["基础名称", "种族", "描述"])
        result = []
        for r in raw:
            result.append({
                "name": str(r.get("基础名称", "")).strip(),
                "race": str(r.get("种族", "")).strip(),
                "description": str(r.get("描述", "")).strip(),
            })
        return result

    # ======================== 任务模板 ========================

    def get_quest_templates(self) -> List[dict]:
        """读取任务模板 → 与 JSON quest_templates 一致的格式"""
        raw = self._read_sheet_to_dicts("任务模板", self.QUEST_COLS)
        result = []
        for r in raw:
            quest = {
                "quest_id": str(r.get("任务ID", "")).strip(),
                "name": str(r.get("任务名称", "")).strip(),
                "type": str(r.get("类型", "")).strip().upper(),
                "description": str(r.get("描述", "")).strip(),
                "target": str(r.get("目标", "")).strip(),
                "target_count": self._parse_int(r.get("目标数量")),
                "level_req": self._parse_int(r.get("等级需求")),
                "reward_exp": self._parse_int(r.get("奖励经验")),
                "reward_gold": self._parse_int(r.get("奖励金币")),
                "story_text": str(r.get("故事文本", "")).strip(),
                "completion_text": str(r.get("完成文本", "")).strip(),
            }
            prev = str(r.get("前置任务", "")).strip()
            if prev:
                quest["previous_quest"] = prev
            is_epic = self._parse_bool(r.get("是否史诗"))
            if is_epic:
                quest["is_epic"] = True
            result.append(quest)
        return result

    # ======================== 物品模板 ========================

    def get_item_templates(self) -> dict:
        """读取物品模板 → 与 JSON item_templates 一致的格式"""
        return {
            "weapon_templates": self._read_weapon_templates(),
            "armor_templates": self._read_armor_templates(),
            "jewelry_names": self._read_jewelry_names(),
            "quality_settings": self._read_quality_settings(),
            "prefixes": self._read_prefixes(),
            "effect_pool": self._read_effect_pool(),
            "prefix_settings": self._read_prefix_settings(),
        }

    def _read_weapon_templates(self) -> dict:
        """读取武器模板 Sheet"""
        wb = self._open_workbook()
        if "武器模板" not in wb.sheetnames:
            return {}
        ws = wb["武器模板"]
        result = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(c is None for c in row):
                continue
            weapon_type = str(row[0]).strip() if row[0] else ""
            if not weapon_type:
                continue
            names = [str(row[i]).strip() for i in range(1, 6) if i < len(row) and row[i]]
            result[weapon_type] = names
        return result

    def _read_armor_templates(self) -> dict:
        """读取护甲模板 Sheet"""
        wb = self._open_workbook()
        if "护甲模板" not in wb.sheetnames:
            return {}
        ws = wb["护甲模板"]
        result = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(c is None for c in row):
                continue
            armor_type = str(row[0]).strip() if row[0] else ""
            if not armor_type:
                continue
            names = [str(row[i]).strip() for i in range(1, 6) if i < len(row) and row[i]]
            result[armor_type] = names
        return result

    def _read_jewelry_names(self) -> dict:
        """读取饰品名称 Sheet"""
        wb = self._open_workbook()
        if "饰品模板" not in wb.sheetnames:
            return {"NECK": [], "RING": []}
        ws = wb["饰品模板"]
        result = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(c is None for c in row):
                continue
            jewelry_type = str(row[0]).strip() if row[0] else ""
            if not jewelry_type:
                continue
            names = [str(row[i]).strip() for i in range(1, 6) if i < len(row) and row[i]]
            result[jewelry_type] = names
        return result

    def _read_quality_settings(self) -> dict:
        """读取品质设置 Sheet"""
        wb = self._open_workbook()
        if "品质设置" not in wb.sheetnames:
            return {"QUALITY_DAMAGE_MULT": {}, "QUALITY_DEFENSE_MULT": {}}
        ws = wb["品质设置"]
        damage_mult = {}
        defense_mult = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(c is None for c in row):
                continue
            quality = str(row[0]).strip().upper() if row[0] else ""
            if not quality:
                continue
            if len(row) >= 2:
                damage_mult[quality] = self._parse_float(row[1])
            if len(row) >= 3:
                defense_mult[quality] = self._parse_float(row[2])
        return {
            "QUALITY_DAMAGE_MULT": damage_mult,
            "QUALITY_DEFENSE_MULT": defense_mult,
        }

    def _read_prefixes(self) -> list:
        """读取前缀词缀 Sheet → 返回扁平列表（无类型、无属性，适用于所有物品和怪物）"""
        wb = self._open_workbook()
        if "前缀模板" not in wb.sheetnames:
            return []
        ws = wb["前缀模板"]
        result = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or row[0] is None:
                continue
            prefix_text = str(row[0]).strip()
            if prefix_text:
                result.append(prefix_text)
        return result

    def _read_effect_pool(self) -> list:
        """读取特效池 Sheet"""
        wb = self._open_workbook()
        if "特效池" not in wb.sheetnames:
            return []
        ws = wb["特效池"]
        effects = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or row[0] is None:
                continue
            effects.append(str(row[0]).strip())
        return effects

    def _read_prefix_settings(self) -> dict:
        """读取前缀设置 Sheet → {min_prefixes, max_prefixes}"""
        wb = self._open_workbook()
        if "前缀设置" not in wb.sheetnames:
            return {"min_prefixes": 1, "max_prefixes": 3}
        ws = wb["前缀设置"]
        result = {"min_prefixes": 1, "max_prefixes": 3}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or not row[0]:
                continue
            key = str(row[0]).strip()
            val = row[1] if len(row) >= 2 else None
            if key == "min_prefixes" and val is not None:
                result["min_prefixes"] = self._parse_int(val)
            elif key == "max_prefixes" and val is not None:
                result["max_prefixes"] = self._parse_int(val)
        return result

    # ======================== 药水配置 ========================

    def get_potion_config(self) -> List[dict]:
        """读取药水配置"""
        raw = self._read_sheet_to_dicts("药水配置", self.POTION_COLS)
        if not raw:
            return []
        result = []
        for r in raw:
            result.append({
                "name": str(r.get("药水名称", "")).strip(),
                "description": str(r.get("描述", "")).strip(),
                "duration": self._parse_float(r.get("持续时间(秒)")),
                "weight": self._parse_int(r.get("掉落权重")),
            })
        return result

    # ======================== 神器配置 ========================

    def get_artifact_config(self) -> List[dict]:
        """读取神器配置"""
        raw = self._read_sheet_to_dicts("神器配置", self.ARTIFACT_COLS)
        if not raw:
            return []
        result = []
        for r in raw:
            result.append({
                "artifact_id": str(r.get("神器ID", "")).strip(),
                "name": str(r.get("名称", "")).strip(),
                "description": str(r.get("描述", "")).strip(),
                "effect_type": str(r.get("效果类型", "")).strip(),
                "effect_value": self._parse_float(r.get("效果值")),
                "source": str(r.get("来源", "")).strip(),
            })
        return result

    # ======================== 成就配置 ========================

    def get_achievement_config(self) -> List[dict]:
        """读取成就配置"""
        raw = self._read_sheet_to_dicts("成就配置", self.ACHIEVEMENT_COLS)
        if not raw:
            return []
        result = []
        for r in raw:
            result.append({
                "ach_id": str(r.get("成就ID", "")).strip(),
                "name": str(r.get("名称", "")).strip(),
                "description": str(r.get("描述", "")).strip(),
                "target": self._parse_int(r.get("目标值")),
                "reward_type": str(r.get("奖励类型", "")).strip(),
                "reward_value": self._parse_float(r.get("奖励值")),
                "hidden": self._parse_bool(r.get("隐藏")),
            })
        return result

    # ======================== 种族配置 ========================

    def get_race_config(self) -> List[dict]:
        """读取种族配置 → 供 character.py 动态加载"""
        raw = self._read_sheet_to_dicts("种族配置", self.RACE_COLS)
        if not raw:
            return []
        result = []
        for r in raw:
            result.append({
                "race_id": str(r.get("种族ID", "")).strip(),
                "display_name": str(r.get("名称", "")).strip(),
                "description": str(r.get("描述", "")).strip(),
                "str_mod": self._parse_int(r.get("str_mod")),
                "dex_mod": self._parse_int(r.get("dex_mod")),
                "con_mod": self._parse_int(r.get("con_mod")),
                "int_mod": self._parse_int(r.get("int_mod")),
                "wis_mod": self._parse_int(r.get("wis_mod")),
                "cha_mod": self._parse_int(r.get("cha_mod")),
            })
        return result

    # ======================== 职业配置 ========================

    def get_class_config(self) -> List[dict]:
        """读取职业配置 → 供 character.py 动态加载"""
        raw = self._read_sheet_to_dicts("职业配置", self.CLASS_COLS)
        if not raw:
            return []
        result = []
        for r in raw:
            result.append({
                "class_id": str(r.get("职业ID", "")).strip(),
                "display_name": str(r.get("名称", "")).strip(),
                "category_name": str(r.get("分类名", "")).strip(),
                "base_hp": self._parse_int(r.get("基础HP")),
                "primary_stat1": str(r.get("主属性1", "")).strip(),
                "primary_stat2": str(r.get("主属性2", "")).strip(),
            })
        return result

    # ======================== 技能配置 ========================

    def get_skill_config(self) -> List[dict]:
        """读取技能配置 → 供 character.py 的 CLASS_SKILL_DEFS 动态加载"""
        raw = self._read_sheet_to_dicts("技能配置", self.SKILL_COLS)
        if not raw:
            return []
        result = []
        for r in raw:
            result.append({
                "skill_id": str(r.get("技能ID", "")).strip(),
                "class_id": str(r.get("所属职业", "")).strip(),
                "name": str(r.get("名称", "")).strip(),
                "description": str(r.get("描述", "")).strip(),
                "effect_type": str(r.get("effect_type", "")).strip(),
                "effect_value": self._parse_float(r.get("effect_value")),
                "cooldown": self._parse_float(r.get("cooldown")),
                "level_req": self._parse_int(r.get("level_req")),
            })
        return result

    # ======================== 休息配置 ========================

    def get_rest_config(self) -> dict:
        """读取休息配置 → 返回与 rest_service.DEFAULT_REST_CONFIG 一致的格式

        降级原则: Excel 不存在该 Sheet 时返回 {}，调用方使用 JSON/硬编码默认值。
        """
        wb = self._open_workbook()
        if "休息配置" not in wb.sheetnames:
            return {}

        raw = self._read_sheet_to_dicts("休息配置", self.REST_COLS)
        if not raw:
            return {}

        flat: dict = {}
        for r in raw:
            key = str(r.get("配置项", "")).strip()
            val = r.get("值")
            if not key:
                continue
            flat[key] = val

        # 组装为嵌套结构
        short_rest = {}
        long_rest = {}

        for k, v in flat.items():
            if k.startswith("short_rest_"):
                short_rest[k.replace("short_rest_", "")] = self._parse_rest_value(v)
            elif k.startswith("long_rest_"):
                long_rest[k.replace("long_rest_", "")] = self._parse_rest_value(v)

        result = {}
        if short_rest:
            result["short_rest"] = short_rest
        if long_rest:
            result["long_rest"] = long_rest
        return result

    @staticmethod
    def _parse_rest_value(value):
        """解析休息配置值：bool / int / float 自动判断"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "是", "yes", "1"):
                return True
            if v in ("false", "否", "no", "0"):
                return False
            try:
                if "." in v:
                    return float(v)
                return int(v)
            except ValueError:
                return value
        return value

    # ======================== 新增：词缀效果/种族技能/材料掉落/元素反应/配方/事件/环境/稀有度/阵营/商店 ========================

    AFFIX_EFFECT_COLS = ["关键词", "效果类型", "效果值"]
    RACIAL_ABILITY_COLS = ["种族", "技能类型", "参数值", "描述"]
    MATERIAL_DROP_COLS = ["标签", "材料名", "基础价值", "掉落概率"]
    ELEMENT_REACTION_COLS = ["触发元素", "环境标签", "种族标签", "叙事文本", "效果JSON"]
    RECIPE_COLS = ["配方ID", "名称", "描述", "材料1", "数量1", "材料2", "数量2", "材料3", "数量3", "材料4", "数量4", "产出类型", "产出品质", "产出效果", "产出数值"]
    EVENT_COLS = ["事件ID", "类型", "权重", "模板文本", "效果类型", "效果值"]
    ENVIRONMENT_COLS = ["环境标签", "效果字段", "效果值", "描述"]
    RARITY_COLS = ["稀有度", "属性倍率", "最小词缀数", "最大词缀数", "概率阈值", "前缀标识"]
    FACTION_COLS = ["种族", "阵营", "分类标签", "体型标签"]
    SHOP_COLS = ["商人名", "刷新间隔(秒)", "商品数量下限", "商品数量上限", "价格系数"]

    def get_affix_effect_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("词缀效果", self.AFFIX_EFFECT_COLS)

    def get_racial_ability_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("种族技能", self.RACIAL_ABILITY_COLS)

    def get_material_drop_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("材料掉落", self.MATERIAL_DROP_COLS)

    def get_element_reaction_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("元素反应", self.ELEMENT_REACTION_COLS)

    def get_recipe_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("配方模板", self.RECIPE_COLS)

    def get_event_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("事件模板", self.EVENT_COLS)

    def get_environment_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("环境配置", self.ENVIRONMENT_COLS)

    def get_rarity_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("稀有度设置", self.RARITY_COLS)

    def get_faction_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("阵营配置", self.FACTION_COLS)

    def get_shop_config(self) -> List[dict]:
        return self._read_sheet_to_dicts("商店配置", self.SHOP_COLS)

    # ======================== 便捷查询方法 ========================

    def get_enemy_by_name(self, name: str) -> Optional[dict]:
        """根据名称获取敌人模板"""
        for enemy in self.get_enemy_templates():
            if enemy["name"] == name:
                return enemy
        return None

    def get_enemies_by_level(self, level: int = 1, level_range: int = 999) -> List[dict]:
        """获取敌人模板（等级参数保留向后兼容，不再按等级过滤）"""
        return self.get_enemy_templates()

    # ======================== 导出 Excel 方法 ========================

    @classmethod
    def export_from_json(cls, json_data_dir: str, output_path: str):
        """从 JSON 文件生成 Excel 模板（策划操作入口）"""
        import json

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # 移除默认 sheet

        # --- Sheet 1: 敌人模板 ---
        ws_enemy = wb.create_sheet("敌人模板")
        for i, col in enumerate(cls.ENEMY_COLS, 1):
            ws_enemy.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        enemy_file = os.path.join(json_data_dir, "enemy_templates.json")
        if os.path.isfile(enemy_file):
            with open(enemy_file, "r", encoding="utf-8") as f:
                enemy_data = json.load(f)
            enemies = enemy_data.get("enemy_templates", [])
            for r_idx, e in enumerate(enemies, 2):
                ws_enemy.cell(row=r_idx, column=1, value=e.get("name", ""))
                ws_enemy.cell(row=r_idx, column=2, value=e.get("level", 0))
                ws_enemy.cell(row=r_idx, column=3, value=e.get("hp", 0))
                ws_enemy.cell(row=r_idx, column=4, value=e.get("damage", 0))
                ws_enemy.cell(row=r_idx, column=5, value=e.get("defense", 0))
                ws_enemy.cell(row=r_idx, column=6, value=e.get("exp", 0))
                ws_enemy.cell(row=r_idx, column=7, value=e.get("gold", 0))
                ws_enemy.cell(row=r_idx, column=8, value=e.get("loot_table", "normal"))
                ws_enemy.cell(row=r_idx, column=9, value=e.get("race", ""))
                ws_enemy.cell(row=r_idx, column=10, value=e.get("description", ""))

        # --- Sheet 2: 任务模板 ---
        ws_quest = wb.create_sheet("任务模板")
        for i, col in enumerate(cls.QUEST_COLS, 1):
            ws_quest.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        quest_file = os.path.join(json_data_dir, "quest_templates.json")
        if os.path.isfile(quest_file):
            with open(quest_file, "r", encoding="utf-8") as f:
                quest_data = json.load(f)
            quests = quest_data.get("quest_templates", [])
            for r_idx, q in enumerate(quests, 2):
                ws_quest.cell(row=r_idx, column=1, value=q.get("quest_id", ""))
                ws_quest.cell(row=r_idx, column=2, value=q.get("name", ""))
                ws_quest.cell(row=r_idx, column=3, value=q.get("type", ""))
                ws_quest.cell(row=r_idx, column=4, value=q.get("description", ""))
                ws_quest.cell(row=r_idx, column=5, value=q.get("target", ""))
                ws_quest.cell(row=r_idx, column=6, value=q.get("target_count", 0))
                ws_quest.cell(row=r_idx, column=7, value=q.get("level_req", 1))
                ws_quest.cell(row=r_idx, column=8, value=q.get("previous_quest", ""))
                ws_quest.cell(row=r_idx, column=9, value=q.get("reward_exp", 0))
                ws_quest.cell(row=r_idx, column=10, value=q.get("reward_gold", 0))
                is_epic = q.get("is_epic", False)
                ws_quest.cell(row=r_idx, column=11, value="是" if is_epic else "否")
                ws_quest.cell(row=r_idx, column=12, value=q.get("story_text", ""))
                ws_quest.cell(row=r_idx, column=13, value=q.get("completion_text", ""))

        # --- Sheet 3: 武器模板 ---
        ws_weapon = wb.create_sheet("武器模板")
        ws_weapon.cell(row=1, column=1, value="武器类型").font = openpyxl.styles.Font(bold=True)
        for i, name in enumerate(["粗劣", "普通", "精良", "卓越", "神器"], 2):
            ws_weapon.cell(row=1, column=i, value=name).font = openpyxl.styles.Font(bold=True)

        item_file = os.path.join(json_data_dir, "item_templates.json")
        if os.path.isfile(item_file):
            with open(item_file, "r", encoding="utf-8") as f:
                item_data = json.load(f)
            weapons = item_data.get("weapon_templates", {})
            for r_idx, (wtype, names) in enumerate(weapons.items(), 2):
                ws_weapon.cell(row=r_idx, column=1, value=wtype)
                for i, n in enumerate(names[:5], 2):
                    ws_weapon.cell(row=r_idx, column=i, value=n)

        # --- Sheet 4: 护甲模板 ---
        ws_armor = wb.create_sheet("护甲模板")
        ws_armor.cell(row=1, column=1, value="护甲类型").font = openpyxl.styles.Font(bold=True)
        for i, name in enumerate(["粗劣", "普通", "精良", "卓越", "神器"], 2):
            ws_armor.cell(row=1, column=i, value=name).font = openpyxl.styles.Font(bold=True)

        if os.path.isfile(item_file):
            armors = item_data.get("armor_templates", {})
            for r_idx, (atype, names) in enumerate(armors.items(), 2):
                ws_armor.cell(row=r_idx, column=1, value=atype)
                for i, n in enumerate(names[:5], 2):
                    ws_armor.cell(row=r_idx, column=i, value=n)

        # --- Sheet 5: 饰品名称 ---
        ws_jewelry = wb.create_sheet("饰品模板")
        ws_jewelry.cell(row=1, column=1, value="饰品类型").font = openpyxl.styles.Font(bold=True)
        for i, name in enumerate(["粗劣", "普通", "精良", "卓越", "神器"], 2):
            ws_jewelry.cell(row=1, column=i, value=name).font = openpyxl.styles.Font(bold=True)

        if os.path.isfile(item_file):
            jewelry = item_data.get("jewelry_names", {})
            for r_idx, (jtype, names) in enumerate(jewelry.items(), 2):
                ws_jewelry.cell(row=r_idx, column=1, value=jtype)
                for i, n in enumerate(names[:5], 2):
                    ws_jewelry.cell(row=r_idx, column=i, value=n)

        # --- Sheet 6: 品质设置 ---
        ws_quality = wb.create_sheet("品质设置")
        ws_quality.cell(row=1, column=1, value="品质").font = openpyxl.styles.Font(bold=True)
        ws_quality.cell(row=1, column=2, value="伤害倍率").font = openpyxl.styles.Font(bold=True)
        ws_quality.cell(row=1, column=3, value="防御倍率").font = openpyxl.styles.Font(bold=True)

        if os.path.isfile(item_file):
            quality = item_data.get("quality_settings", {})
            dmg_mult = quality.get("QUALITY_DAMAGE_MULT", {})
            def_mult = quality.get("QUALITY_DEFENSE_MULT", {})
            for r_idx, qname in enumerate(cls.QUALITY_NAMES, 2):
                ws_quality.cell(row=r_idx, column=1, value=qname)
                ws_quality.cell(row=r_idx, column=2, value=dmg_mult.get(qname, 1.0))
                ws_quality.cell(row=r_idx, column=3, value=def_mult.get(qname, 1.0))

        # --- Sheet 7: 前缀词缀 ---
        ws_prefix = wb.create_sheet("前缀模板")
        ws_prefix.cell(row=1, column=1, value="前缀").font = openpyxl.styles.Font(bold=True)

        if os.path.isfile(item_file):
            prefixes = item_data.get("prefixes", [])
            for r, pv in enumerate(prefixes, 2):
                ws_prefix.cell(row=r, column=1, value=pv)

        # --- Sheet 8: 特效池 ---
        ws_effect = wb.create_sheet("特效池")
        ws_effect.cell(row=1, column=1, value="特效名称").font = openpyxl.styles.Font(bold=True)

        if os.path.isfile(item_file):
            effects = item_data.get("effect_pool", [])
            for r_idx, ef in enumerate(effects, 2):
                ws_effect.cell(row=r_idx, column=1, value=ef)

        # --- Sheet 9: 前缀设置 ---
        ws_prefix_setting = wb.create_sheet("前缀设置")
        ws_prefix_setting.cell(row=1, column=1, value="配置项").font = openpyxl.styles.Font(bold=True)
        ws_prefix_setting.cell(row=1, column=2, value="值").font = openpyxl.styles.Font(bold=True)

        if os.path.isfile(item_file):
            prefix_setting = item_data.get("prefix_settings", {})
            ws_prefix_setting.cell(row=2, column=1, value="min_prefixes")
            ws_prefix_setting.cell(row=2, column=2, value=prefix_setting.get("min_prefixes", 1))
            ws_prefix_setting.cell(row=3, column=1, value="max_prefixes")
            ws_prefix_setting.cell(row=3, column=2, value=prefix_setting.get("max_prefixes", 3))

        # --- Sheet 10: 药水配置 ---
        ws_potion = wb.create_sheet("药水配置")
        for i, col in enumerate(cls.POTION_COLS, 1):
            ws_potion.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        # 从 potion.py 硬编码值导出
        try:
            from ..models.potion import POTION_DROP_WEIGHTS
            potion_details = {
                "DOUBLE_GOLD":   ("双倍金币",   "怪物多掉一堆金币", 120.0, 15),
                "DOUBLE_ITEM":   ("双倍物品",   "怪物多掉一件装备", 120.0, 15),
                "FRAIL_MONSTER": ("脆弱怪物",   "怪物属性降低50%",   90.0, 10),
                "DOCILE_MONSTER":("温顺怪物",   "怪物几乎不还手",   90.0,  8),
                "ITEM_VALUE":    ("物品价值提升","装备品质权重上移", 120.0, 12),
                "GUARANTEED_DROP":("必掉装备",  "每只怪物必掉装备",  90.0,  8),
                "MORE_MONSTERS": ("更多怪物",   "每房间怪物+5",    120.0,  5),
                "FREE_CAST":     ("免费施法",   "技能不消耗精神力",  90.0,  5),
                "SPEED_EXPLORE": ("加速探索",   "房间推进间隔减半", 120.0, 12),
                "MORE_EXP":      ("更多经验",   "经验获取+50%",    120.0, 10),
            }
            for r_idx, (key, weight) in enumerate(POTION_DROP_WEIGHTS.items(), 2):
                name, desc, dur, _w = potion_details.get(key.name, (key.name, "", 0.0, 0))
                ws_potion.cell(row=r_idx, column=1, value=name)
                ws_potion.cell(row=r_idx, column=2, value=desc)
                ws_potion.cell(row=r_idx, column=3, value=dur)
                ws_potion.cell(row=r_idx, column=4, value=weight)
        except ImportError:
            pass

        # --- Sheet 10: 神器配置 ---
        ws_art = wb.create_sheet("神器配置")
        for i, col in enumerate(cls.ARTIFACT_COLS, 1):
            ws_art.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        try:
            from ..services.artifact_service import ARTIFACT_DEFS
            for r_idx, (aid, name, desc, etype, evalue, src) in enumerate(ARTIFACT_DEFS, 2):
                ws_art.cell(row=r_idx, column=1, value=aid)
                ws_art.cell(row=r_idx, column=2, value=name)
                ws_art.cell(row=r_idx, column=3, value=desc)
                ws_art.cell(row=r_idx, column=4, value=etype)
                ws_art.cell(row=r_idx, column=5, value=evalue)
                ws_art.cell(row=r_idx, column=6, value=src)
        except ImportError:
            pass

        # --- Sheet 11: 成就配置 ---
        ws_ach = wb.create_sheet("成就配置")
        for i, col in enumerate(cls.ACHIEVEMENT_COLS, 1):
            ws_ach.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        try:
            from ..services.achievement_service import ACHIEVEMENT_DEFS
            for r_idx, (aid, name, desc, target, rtype, rval, hidden) in enumerate(ACHIEVEMENT_DEFS, 2):
                ws_ach.cell(row=r_idx, column=1, value=aid)
                ws_ach.cell(row=r_idx, column=2, value=name)
                ws_ach.cell(row=r_idx, column=3, value=desc)
                ws_ach.cell(row=r_idx, column=4, value=target)
                ws_ach.cell(row=r_idx, column=5, value=rtype)
                ws_ach.cell(row=r_idx, column=6, value=rval)
                ws_ach.cell(row=r_idx, column=7, value="是" if hidden else "否")
        except ImportError:
            pass

        # --- Sheet 12: 种族配置 ---
        ws_race = wb.create_sheet("种族配置")
        for i, col in enumerate(cls.RACE_COLS, 1):
            ws_race.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        race_fallback = [
            ("HUMAN",      "人类",   "适应力强",           1,  1,  1,  1,  1,  1),
            ("ELF",        "精灵",   "敏捷与智力出众",    -1,  2, -1,  2,  1,  0),
            ("DWARF",      "矮人",   "体质与力量见长",     2, -1,  2, -1,  1, -1),
            ("HALFLING",   "半身人", "幸运与敏捷并存",    -2,  2,  0,  1,  0,  2),
            ("GNOME",      "侏儒",   "智力与感知出众",    -2,  1,  0,  2,  0,  1),
            ("HALFORC",    "半兽人", "力量与体质混合",     2,  0,  1, -2, -1, -1),
            ("TIEFFLING",  "提夫林", "魅力与智力兼具",     0,  1,  0,  1, -1,  2),
            ("DRAGONBORN", "龙裔",   "力量与魅力并存",     2,  0,  1, -1,  0,  1),
        ]
        for r_idx, (rid, dname, desc, sm, dm, cm, im, wm, chm) in enumerate(race_fallback, 2):
            ws_race.cell(row=r_idx, column=1, value=rid)
            ws_race.cell(row=r_idx, column=2, value=dname)
            ws_race.cell(row=r_idx, column=3, value=desc)
            ws_race.cell(row=r_idx, column=4, value=sm)
            ws_race.cell(row=r_idx, column=5, value=dm)
            ws_race.cell(row=r_idx, column=6, value=cm)
            ws_race.cell(row=r_idx, column=7, value=im)
            ws_race.cell(row=r_idx, column=8, value=wm)
            ws_race.cell(row=r_idx, column=9, value=chm)

        # --- Sheet 13: 职业配置 ---
        ws_class = wb.create_sheet("职业配置")
        for i, col in enumerate(cls.CLASS_COLS, 1):
            ws_class.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        class_fallback = [
            ("WARRIOR",   "战士",   "战士",   12, "strength",     "constitution"),
            ("MAGE",      "法师",   "法师",    6, "intelligence", ""),
            ("CLERIC",    "牧师",   "牧师",    8, "wisdom",       "charisma"),
            ("ROGUE",     "盗贼",   "盗贼",    8, "dexterity",    "intelligence"),
            ("RANGER",    "游侠",   "游侠",   10, "dexterity",    "wisdom"),
            ("PALADIN",   "圣骑士", "圣骑士", 10, "strength",     "charisma"),
            ("WARLOCK",   "术士",   "术士",    8, "charisma",     "constitution"),
            ("MONK",      "武僧",   "武僧",    8, "dexterity",    "wisdom"),
            ("DRUID",     "德鲁伊", "德鲁伊",  8, "wisdom",       "constitution"),
            ("BARBARIAN", "野蛮人", "野蛮人", 12, "strength",     "constitution"),
        ]
        for r_idx, (cid, dname, cname, hp, ps1, ps2) in enumerate(class_fallback, 2):
            ws_class.cell(row=r_idx, column=1, value=cid)
            ws_class.cell(row=r_idx, column=2, value=dname)
            ws_class.cell(row=r_idx, column=3, value=cname)
            ws_class.cell(row=r_idx, column=4, value=hp)
            ws_class.cell(row=r_idx, column=5, value=ps1)
            ws_class.cell(row=r_idx, column=6, value=ps2 if ps2 else "")

        # --- Sheet 14: 技能配置 ---
        ws_skill = wb.create_sheet("技能配置")
        for i, col in enumerate(cls.SKILL_COLS, 1):
            ws_skill.cell(row=1, column=i, value=col).font = openpyxl.styles.Font(bold=True)

        skill_fallback = [
            ("WARRIOR_1",  "WARRIOR",   "猛击",     "强力一击，伤害×1.5",    "damage_multiplier", 1.5,  3.0,   1),
            ("WARRIOR_2",  "WARRIOR",   "防御姿态", "防御提高50%",          "defense_buff",      0.5, 30.0,   5),
            ("WARRIOR_3",  "WARRIOR",   "旋风斩",   "范围攻击×1.2",         "area_damage",       1.2, 15.0,  10),
            ("MAGE_1",     "MAGE",      "火球术",   "发射火球，法术伤害×1.8","magic_damage",      1.8,  2.5,   1),
            ("MAGE_2",     "MAGE",      "冰锥术",   "喷射冰锥，减速敌人",    "magic_damage_slow", 1.2,  4.0,   5),
            ("MAGE_3",     "MAGE",      "闪电链",   "闪电弹射×2.0",         "lightning_chain",   2.0,  8.0,  10),
            ("CLERIC_1",   "CLERIC",    "治疗术",   "恢复生命",             "heal",              1.0,  5.0,   1),
            ("CLERIC_2",   "CLERIC",    "神圣之光", "神圣伤害×1.5",         "holy_damage",       1.5,  8.0,   5),
            ("CLERIC_3",   "CLERIC",    "庇护所",   "防护罩减伤50%",        "shield",            0.5, 20.0,  10),
            ("ROGUE_1",    "ROGUE",     "背刺",     "背后暴击×2.0",         "damage_multiplier", 2.0,  4.0,   1),
            ("ROGUE_2",    "ROGUE",     "毒刃",     "涂毒持续伤害",         "poison",            0.3, 12.0,   5),
            ("ROGUE_3",    "ROGUE",     "隐身",     "潜行必暴击",           "stealth",           1.0, 30.0,  10),
            ("RANGER_1",   "RANGER",    "精准射击", "必中要害",             "guaranteed_crit",   1.0,  6.0,   1),
            ("RANGER_2",   "RANGER",    "陷阱",     "放置陷阱",             "trap",              1.0, 15.0,   5),
            ("RANGER_3",   "RANGER",    "野兽伙伴", "召唤野兽助战",         "summon",            1.0, 60.0,  10),
            ("PALADIN_1",  "PALADIN",   "审判",     "神圣审判×1.5",         "holy_damage",       1.5,  5.0,   1),
            ("PALADIN_2",  "PALADIN",   "圣光术",   "治疗",                 "heal",              1.0,  8.0,   5),
            ("PALADIN_3",  "PALADIN",   "无敌",     "无敌3秒",              "invincible",        3.0,120.0,  15),
            ("BARBARIAN_1","BARBARIAN", "狂暴",     "攻击×1.5 防御降低",    "berserk",           1.5, 20.0,   1),
            ("BARBARIAN_2","BARBARIAN", "斩杀",     "低血量额外伤害×2",     "execute",           2.0,  5.0,   5),
            ("BARBARIAN_3","BARBARIAN", "战吼",     "全体buff+30%",         "battle_cry",        0.3, 30.0,  10),
            ("WARLOCK_1",  "WARLOCK",   "暗影箭",   "暗影伤害×1.5",         "shadow_damage",     1.5,  2.5,   1),
            ("WARLOCK_2",  "WARLOCK",   "生命汲取", "吸血50%伤害",          "life_drain",        0.5,  4.0,   5),
            ("WARLOCK_3",  "WARLOCK",   "恶魔召唤", "召唤恶魔",             "summon_demon",      1.0, 60.0,  10),
            ("MONK_1",     "MONK",      "疾风连击", "连续攻击×1.3",         "flurry",            1.3,  3.0,   1),
            ("MONK_2",     "MONK",      "振魂掌",   "真气伤害×1.5",         "chi_damage",        1.5,  6.0,   5),
            ("MONK_3",     "MONK",      "金钟罩",   "减伤80%",              "shield",            0.8, 45.0,  10),
            ("DRUID_1",    "DRUID",     "变形术",   "变熊+生存",            "shape_shift",       1.0, 10.0,   1),
            ("DRUID_2",    "DRUID",     "荆棘术",   "缠绕敌人",             "entangle",          1.0,  8.0,   5),
            ("DRUID_3",    "DRUID",     "自然之怒", "自然伤害×2.0",         "nature_wrath",      2.0, 20.0,  10),
        ]
        for r_idx, (sid, cid, name, desc, etype, evalue, cd, lv) in enumerate(skill_fallback, 2):
            ws_skill.cell(row=r_idx, column=1, value=sid)
            ws_skill.cell(row=r_idx, column=2, value=cid)
            ws_skill.cell(row=r_idx, column=3, value=name)
            ws_skill.cell(row=r_idx, column=4, value=desc)
            ws_skill.cell(row=r_idx, column=5, value=etype)
            ws_skill.cell(row=r_idx, column=6, value=evalue)
            ws_skill.cell(row=r_idx, column=7, value=cd)
            ws_skill.cell(row=r_idx, column=8, value=lv)

        # 调整列宽
        for ws in wb.worksheets:
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)) * 2)
                ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wb.save(output_path)
        print(f"Excel 配置文件已生成: {output_path}")
        print(f"包含 {len(wb.sheetnames)} 个工作表: {', '.join(wb.sheetnames)}")
