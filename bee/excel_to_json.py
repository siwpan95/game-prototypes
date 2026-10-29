"""
从独立的 Excel 文件读取数据，生成对应的 JSON 文件
支持 JSON 池子机制：不预加载，需要时从池子调取

使用方法:
  python excel_to_json.py              # 从 sheets/ 目录读取所有 Excel，生成 JSON
  python excel_to_json.py --watch      # 监控 Excel 变化，自动重新生成
"""

import openpyxl
import json
import os
import time
import glob
from pathlib import Path

# 基础目录（相对脚本位置，可移植）
BASE_DIR = str(Path(__file__).resolve().parent)
SHEETS_DIR = os.path.join(BASE_DIR, "src", "resources", "config", "sheets")
SRC_JSON_DIR = os.path.join(BASE_DIR, "src", "resources", "data")
DIST_JSON_DIR = os.path.join(BASE_DIR, "dist", "resources", "data")

# Sheet 名称到 JSON 文件名的映射
SHEET_TO_JSON = {
    "敌人模板": "enemy_templates.json",
    "任务模板": "quest_templates.json",
    "武器模板": "weapon_templates.json",
    "护甲模板": "armor_templates.json",
    "饰品模板": "accessory_templates.json",
    "品质设置": "quality_settings.json",
    "前缀模板": "prefix_templates.json",
    "特效池": "effect_pool.json",
    "药水配置": "potion_config.json",
    "神器配置": "artifact_config.json",
    "成就配置": "achievement_config.json",
    "种族配置": "race_config.json",
    "职业配置": "class_config.json",
    "技能配置": "skill_config.json",
    "休息配置": "rest_config.json",
    "前缀设置": "prefix_settings.json",
    # ★ 新增配置表
    "词缀效果": "affix_effect_config.json",
    "种族技能": "racial_ability_config.json",
    "材料掉落": "material_drop_config.json",
    "元素反应": "element_reaction_config.json",
    "配方模板": "recipe_templates.json",
    "事件模板": "event_templates.json",
    "环境配置": "environment_config.json",
    "稀有度设置": "rarity_config.json",
    "阵营配置": "faction_config.json",
    "商店配置": "shop_config.json",
}


def read_excel_sheet(excel_path: str) -> list:
    """读取单个 Excel 文件的所有数据"""
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active
    
    # 读取表头
    headers = [cell.value for cell in ws[1]]
    
    # 读取数据行
    data = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:  # 跳过空行
            continue
        d = dict(zip(headers, row))
        
        # 字段名转换（中文 -> 英文）
        d_new = {}
        for k, v in d.items():
            # 敌人模板
            if k == "基础名称":
                d_new["name"] = v
            elif k == "种族":
                d_new["race"] = v
            elif k == "描述":
                d_new["description"] = v
            # 任务模板
            elif k == "任务ID":
                d_new["quest_id"] = v
            elif k == "任务名称":
                d_new["name"] = v
            elif k == "类型":
                d_new["type"] = v
            elif k == "描述":
                d_new["description"] = v
            elif k == "目标":
                d_new["target"] = v
            elif k == "目标数量":
                d_new["target_count"] = v
            elif k == "前置任务":
                d_new["previous_quest"] = v
            elif k == "后续任务":
                d_new["next_quest"] = v
            elif k == "奖励经验":
                d_new["reward_exp"] = v
            elif k == "奖励金币":
                d_new["reward_gold"] = v
            elif k == "是否史诗":
                d_new["is_epic"] = v
            elif k == "故事文本":
                d_new["story_text"] = v
            elif k == "完成文本":
                d_new["completion_text"] = v
            # 其他字段保持原样
            else:
                d_new[k] = v
        
        # 添加默认值（如果缺失）
        if "hp" not in d_new:
            d_new["hp"] = 1
        if "damage" not in d_new:
            d_new["damage"] = 1
        if "defense" not in d_new:
            d_new["defense"] = 0
        if "exp" not in d_new:
            d_new["exp"] = 0
        if "gold" not in d_new:
            d_new["gold"] = 0
        if "loot_table" not in d_new:
            d_new["loot_table"] = ""
        
        data.append(d_new)
    
    wb.close()
    return data


def convert_enemy_template(row_data: dict) -> dict:
    """转换敌人模板数据（row_data 已经有英文字段名）"""
    return {
        "name": row_data.get("name") or row_data.get("名称"),
        "hp": int(row_data.get("hp", 1) or 1),
        "damage": int(row_data.get("damage", 1) or 1),
        "defense": int(row_data.get("defense", 0) or 0),
        "exp": int(row_data.get("exp", 0) or 0),
        "gold": int(row_data.get("gold", 0) or 0),
        "loot_table": row_data.get("loot_table") or row_data.get("掉落表", ""),
        "race": row_data.get("race") or row_data.get("种族", ""),
        "description": row_data.get("description") or row_data.get("描述", "") or "",
    }


def convert_quest_template(row_data: dict) -> dict:
    """转换任务模板数据"""
    return {
        "quest_id": str(row_data.get("任务ID") or row_data.get("quest_id", "")),
        "name": row_data.get("任务名称") or row_data.get("name", ""),
        "type": row_data.get("类型") or row_data.get("type", "KILL"),
        "description": row_data.get("描述") or row_data.get("description", ""),
        "target": row_data.get("目标") or row_data.get("target", ""),
        "target_count": int(row_data.get("目标数量") or row_data.get("target_count", 5)),
        "level_req": 1,
        "previous_quest": row_data.get("前置任务") or row_data.get("previous_quest"),
        "next_quest": row_data.get("后续任务") or row_data.get("next_quest"),
        "reward_exp": int(row_data.get("奖励经验") or row_data.get("reward_exp", 0) or 0),
        "reward_gold": int(row_data.get("奖励金币") or row_data.get("reward_gold", 0) or 0),
        "is_epic": bool(row_data.get("是否史诗") or row_data.get("is_epic", False)),
        "story_text": row_data.get("故事文本") or row_data.get("story_text", ""),
        "completion_text": row_data.get("完成文本") or row_data.get("completion_text", ""),
    }


def _expand_typed_names(row_data: dict, type_keys: tuple, max_names: int = 6) -> list:
    """把一行「类型列 + 名称1..N 列」展开为多条 {type, name}

    JSON 池（json_pool）按 type 分组收集 name，因此一行多个名称
    必须展开为多条记录（Excel 表头：武器类型/护甲类型/饰品类型 + 名称1..6）。
    """
    t = ""
    for key in type_keys:
        if row_data.get(key):
            t = str(row_data[key]).strip()
            break
    if not t:
        return []
    entries = []
    for i in range(1, max_names + 1):
        name = row_data.get(f"名称{i}")
        if name is None:
            continue
        name = str(name).strip()
        if name:
            entries.append({"type": t, "name": name})
    return entries


def convert_weapon_template(row_data: dict) -> list:
    """转换武器模板数据：一行（武器类型 + 名称1..6）→ 多条 {type, name}"""
    return _expand_typed_names(row_data, ("武器类型", "类型"))


def convert_armor_template(row_data: dict) -> list:
    """转换护甲模板数据：一行（护甲类型 + 名称1..6）→ 多条 {type, name}"""
    return _expand_typed_names(row_data, ("护甲类型", "类型"))


def convert_accessory_template(row_data: dict) -> list:
    """转换饰品模板数据：一行（饰品类型 + 名称1..6）→ 多条 {type, name}"""
    entries = _expand_typed_names(row_data, ("饰品类型", "类型"))
    return [{"type": e["type"].upper(), "name": e["name"]} for e in entries]


def convert_prefix_template(row_data: dict) -> dict:
    """转换前缀模板数据"""
    return {
        "type": str(row_data.get("类型") or row_data.get("type", "")).strip(),
        "prefix": str(row_data.get("前缀") or row_data.get("prefix", "")).strip(),
        "effect": str(row_data.get("效果") or row_data.get("effect", "")).strip(),
        "value": float(row_data.get("数值") or row_data.get("value", 0) or 0),
    }


def convert_race_template(row_data: dict) -> dict:
    """转换种族配置数据（中文 → 英文）"""
    return {
        "race_id": str(row_data.get("种族ID") or row_data.get("race_id", "")).strip(),
        "display_name": str(row_data.get("名称") or row_data.get("display_name", "")).strip(),
        "description": str(row_data.get("描述") or row_data.get("description", "")).strip(),
        "str_mod": int(row_data.get("str_mod", 0) or 0),
        "dex_mod": int(row_data.get("dex_mod", 0) or 0),
        "con_mod": int(row_data.get("con_mod", 0) or 0),
        "int_mod": int(row_data.get("int_mod", 0) or 0),
        "wis_mod": int(row_data.get("wis_mod", 0) or 0),
        "cha_mod": int(row_data.get("cha_mod", 0) or 0),
        "hp": int(row_data.get("hp", 1) or 1),
        "damage": int(row_data.get("damage", 1) or 1),
        "defense": int(row_data.get("defense", 0) or 0),
        "exp": int(row_data.get("exp", 0) or 0),
        "gold": int(row_data.get("gold", 0) or 0),
        "loot_table": str(row_data.get("loot_table", "") or ""),
    }


def convert_class_template(row_data: dict) -> dict:
    """转换职业配置数据（中文 → 英文）"""
    return {
        "class_id": str(row_data.get("职业ID") or row_data.get("class_id", "")).strip(),
        "display_name": str(row_data.get("名称") or row_data.get("display_name", "")).strip(),
        "category_name": str(row_data.get("分类名") or row_data.get("category_name", "")).strip(),
        "base_hp": int(row_data.get("基础HP") or row_data.get("base_hp", 8) or 8),
        "primary_stat1": str(row_data.get("主属性1") or row_data.get("primary_stat1", "")).strip(),
        "primary_stat2": str(row_data.get("主属性2") or row_data.get("primary_stat2", "")).strip(),
        "hp": int(row_data.get("hp", 1) or 1),
        "damage": int(row_data.get("damage", 1) or 1),
        "defense": int(row_data.get("defense", 0) or 0),
        "exp": int(row_data.get("exp", 0) or 0),
        "gold": int(row_data.get("gold", 0) or 0),
        "loot_table": str(row_data.get("loot_table", "") or ""),
    }


def convert_skill_template(row_data: dict) -> dict:
    """转换技能配置数据（中文 → 英文）"""
    return {
        "skill_id": str(row_data.get("技能ID") or row_data.get("skill_id", "")).strip(),
        "class_id": str(row_data.get("所属职业") or row_data.get("class_id", "")).strip(),
        "name": str(row_data.get("名称") or row_data.get("name", "")).strip(),
        "description": str(row_data.get("描述") or row_data.get("description", "")).strip(),
        "effect_type": str(row_data.get("效果类型") or row_data.get("effect_type", "")).strip(),
        "effect_value": float(row_data.get("效果数值") or row_data.get("effect_value", 1.0) or 1.0),
        "cooldown": float(row_data.get("冷却时间") or row_data.get("cooldown", 5.0) or 5.0),
        "level_req": int(row_data.get("等级需求") or row_data.get("level_req", 1) or 1),
        "hp": int(row_data.get("hp", 1) or 1),
        "damage": int(row_data.get("damage", 1) or 1),
        "defense": int(row_data.get("defense", 0) or 0),
        "exp": int(row_data.get("exp", 0) or 0),
        "gold": int(row_data.get("gold", 0) or 0),
        "loot_table": str(row_data.get("loot_table", "") or ""),
    }


# ★ 新增转换器

def convert_affix_effect(row_data: dict) -> dict:
    """词缀效果"""
    return {
        "keyword": str(row_data.get("关键词", "")).strip(),
        "effect_type": str(row_data.get("效果类型", "")).strip(),
        "effect_value": float(row_data.get("效果值", 0) or 0),
    }


def convert_racial_ability(row_data: dict) -> dict:
    """种族技能"""
    return {
        "race": str(row_data.get("种族", "")).strip(),
        "ability_type": str(row_data.get("技能类型", "")).strip(),
        "value": float(row_data.get("参数值", 0) or 0),
        "description": str(row_data.get("描述", "")).strip(),
    }


def convert_material_drop(row_data: dict) -> dict:
    """材料掉落"""
    return {
        "tag": str(row_data.get("标签", "")).strip(),
        "material_name": str(row_data.get("材料名", "")).strip(),
        "base_value": int(row_data.get("基础价值", 0) or 0),
        "drop_chance": float(row_data.get("掉落概率", 0) or 0),
    }


def convert_element_reaction(row_data: dict) -> dict:
    """元素反应"""
    import json as _json
    effect_str = str(row_data.get("效果JSON", "{}")).strip()
    try:
        effect = _json.loads(effect_str)
    except Exception:
        effect = {}
    return {
        "element": str(row_data.get("触发元素", "")).strip(),
        "env_tag": str(row_data.get("环境标签", "")).strip(),
        "race_tag": str(row_data.get("种族标签", "")).strip(),
        "narrative": str(row_data.get("叙事文本", "")).strip(),
        "effect": effect,
    }


def convert_recipe(row_data: dict) -> dict:
    """配方模板"""
    materials = {}
    for i in range(1, 5):
        mat = str(row_data.get(f"材料{i}", "")).strip()
        qty = int(row_data.get(f"数量{i}", 0) or 0)
        if mat and qty > 0:
            materials[mat] = qty
    return {
        "recipe_id": str(row_data.get("配方ID", "")).strip(),
        "name": str(row_data.get("名称", "")).strip(),
        "description": str(row_data.get("描述", "")).strip(),
        "materials": materials,
        "output_type": str(row_data.get("产出类型", "")).strip(),
        "output_quality": str(row_data.get("产出品质", "")).strip(),
        "output_effect": str(row_data.get("产出效果", "")).strip(),
        "output_value": int(row_data.get("产出数值", 0) or 0),
    }


def convert_event(row_data: dict) -> dict:
    """事件模板"""
    return {
        "event_id": str(row_data.get("事件ID", "")).strip(),
        "type": str(row_data.get("类型", "")).strip(),
        "weight": int(row_data.get("权重", 10) or 10),
        "template": str(row_data.get("模板文本", "")).strip(),
        "effect": str(row_data.get("效果类型", "")).strip(),
        "effect_value": int(row_data.get("效果值", 0) or 0),
    }


def convert_environment(row_data: dict) -> dict:
    """环境配置"""
    return {
        "env_tag": str(row_data.get("环境标签", "")).strip(),
        "effect_field": str(row_data.get("效果字段", "")).strip(),
        "effect_value": float(row_data.get("效果值", 0) or 0),
        "description": str(row_data.get("描述", "")).strip(),
    }


def convert_rarity(row_data: dict) -> dict:
    """稀有度设置"""
    return {
        "rarity_name": str(row_data.get("稀有度", "")).strip(),
        "stat_mult": float(row_data.get("属性倍率", 1.0) or 1.0),
        "min_affix": int(row_data.get("最小词缀数", 1) or 1),
        "max_affix": int(row_data.get("最大词缀数", 3) or 3),
        "threshold": float(row_data.get("概率阈值", 1.0) or 1.0),
        "prefix": str(row_data.get("前缀标识", "")).strip(),
    }


def convert_faction(row_data: dict) -> dict:
    """阵营配置"""
    return {
        "race": str(row_data.get("种族", "")).strip(),
        "faction": str(row_data.get("阵营", "")).strip(),
        "category": str(row_data.get("分类标签", "")).strip(),
        "size": str(row_data.get("体型标签", "")).strip(),
    }


def convert_shop(row_data: dict) -> dict:
    """商店配置"""
    return {
        "merchant_name": str(row_data.get("商人名", "")).strip(),
        "refresh_interval": int(row_data.get("刷新间隔(秒)", 300) or 300),
        "min_items": int(row_data.get("商品数量下限", 2) or 2),
        "max_items": int(row_data.get("商品数量上限", 4) or 4),
        "price_coeff": float(row_data.get("价格系数", 1.0) or 1.0),
    }


# 转换器映射
CONVERTERS = {
    "敌人模板": convert_enemy_template,
    "任务模板": convert_quest_template,
    "武器模板": convert_weapon_template,
    "护甲模板": convert_armor_template,
    "饰品模板": convert_accessory_template,
    "前缀模板": convert_prefix_template,
    "种族配置": convert_race_template,
    "职业配置": convert_class_template,
    "技能配置": convert_skill_template,
    # ★ 新增
    "词缀效果": convert_affix_effect,
    "种族技能": convert_racial_ability,
    "材料掉落": convert_material_drop,
    "元素反应": convert_element_reaction,
    "配方模板": convert_recipe,
    "事件模板": convert_event,
    "环境配置": convert_environment,
    "稀有度设置": convert_rarity,
    "阵营配置": convert_faction,
    "商店配置": convert_shop,
}


def process_sheet(excel_path: str, sheet_name: str) -> list:
    """处理单个 sheet，返回转换后的数据"""
    try:
        rows = read_excel_sheet(excel_path)
        converter = CONVERTERS.get(sheet_name)
        
        if converter:
            # 转换器可返回单条 dict 或多条 list（名称展开），统一扁平化
            converted = []
            for row in rows:
                result = converter(row)
                if isinstance(result, list):
                    converted.extend(result)
                else:
                    converted.append(result)
            return converted
        else:
            # 通用转换：直接转换为字典列表
            return rows
    except Exception as e:
        print(f"  ❌ 处理 {sheet_name} 失败: {e}")
        return []


def save_json(data: list, path: str):
    """保存数据为 JSON 文件"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 已写入 {len(data)} 条 → {os.path.basename(path)}")


def process_all_sheets():
    """处理所有 sheet，生成对应的 JSON 文件"""
    print(f"读取: {SHEETS_DIR}\n")
    
    total_sheets = 0
    total_records = 0
    
    for sheet_name, json_file in SHEET_TO_JSON.items():
        excel_file = os.path.join(SHEETS_DIR, f"{sheet_name}.xlsx")
        
        if not os.path.exists(excel_file):
            print(f"⚠ 跳过（文件不存在）: {sheet_name}.xlsx")
            continue
        
        print(f"📄 处理: {sheet_name}.xlsx")
        
        # 处理 sheet
        data = process_sheet(excel_file, sheet_name)
        
        if not data:
            print(f"  无数据，跳过\n")
            continue
        
        # 保存到 src/data（开发用）
        src_json_path = os.path.join(SRC_JSON_DIR, json_file)
        save_json(data, src_json_path)
        
        # 保存到 dist/data（打包用）
        if os.path.exists(os.path.join(BASE_DIR, "dist")):
            dist_json_path = os.path.join(DIST_JSON_DIR, json_file)
            save_json(data, dist_json_path)
        
        total_sheets += 1
        total_records += len(data)
        print()
    
    print(f"=" * 50)
    print(f"完成！共处理 {total_sheets} 个 sheet，{total_records} 条记录")
    print(f"JSON 文件已保存到:")
    print(f"  - {SRC_JSON_DIR}/")
    if os.path.exists(os.path.join(BASE_DIR, "dist")):
        print(f"  - {DIST_JSON_DIR}/")
    print(f"=" * 50)


def watch_mode():
    """监控模式：当 Excel 文件变化时自动重新生成"""
    print("🔍 监控模式已启动，按 Ctrl+C 退出\n")
    
    # 记录文件修改时间
    file_times = {}
    
    def update_file_times():
        times = {}
        for excel_file in glob.glob(os.path.join(SHEETS_DIR, "*.xlsx")):
            times[excel_file] = os.path.getmtime(excel_file)
        return times
    
    file_times = update_file_times()
    
    while True:
        time.sleep(2)
        new_times = update_file_times()
        
        # 检查是否有文件变化
        changed = False
        for f, t in new_times.items():
            if f not in file_times or file_times[f] != t:
                print(f"\n📝 检测到变化: {os.path.basename(f)}")
                changed = True
                file_times[f] = t
        
        if changed:
            print("\n" + "=" * 50)
            process_all_sheets()
            print("\n继续监控...")
            print("=" * 50)


if __name__ == "__main__":
    import sys
    
    if "--watch" in sys.argv:
        watch_mode()
    else:
        process_all_sheets()
