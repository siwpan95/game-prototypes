# -*- coding: utf-8 -*-
"""
从 JSON 生成 Excel 配置模板（含全部 8 个 Sheet）。
运行: python gen_excel.py
生成: config/game_data.xlsx
"""

import sys, os, json
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = _SCRIPT_DIR
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def load_json(name):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def style_header(ws, headers):
    header_font = Font(name="Microsoft YaHei", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border
    ws.freeze_panes = "A2"


def _auto_width(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value:
                val = str(cell.value)
                length = sum(2.5 if ord(c) > 127 else 1 for c in val)
                max_len = max(max_len, length)
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)


# ---- Sheet 定义 ----

def create_jobs_sheet(wb):
    ws = wb.active; ws.title = "职业"
    headers = ["职业名称", "图标", "颜色", "基础HP", "基础ATK", "基础DEF", "基础SPD", "初始技能(逗号分隔)"]
    style_header(ws, headers)
    data = load_json("jobs") or {}
    for row, (key, d) in enumerate(data.items(), 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["emoji"])
        ws.cell(row=row, column=3, value=d["color"])
        ws.cell(row=row, column=4, value=d["base_hp"])
        ws.cell(row=row, column=5, value=d["base_atk"])
        ws.cell(row=row, column=6, value=d["base_def"])
        ws.cell(row=row, column=7, value=d["base_spd"])
        ws.cell(row=row, column=8, value=",".join(d.get("initial_skills", [])))
    _auto_width(ws)


def create_skills_sheet(wb):
    ws = wb.create_sheet("技能")
    headers = ["技能名称", "描述", "类型", "威力", "MP消耗", "冷却回合", "职业限制", "等级要求", "属性要求(JSON)"]
    style_header(ws, headers)
    data = load_json("skills") or {}
    for row, (key, d) in enumerate(data.items(), 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["desc"])
        ws.cell(row=row, column=3, value=d["skill_type"])
        ws.cell(row=row, column=4, value=d["power"])
        ws.cell(row=row, column=5, value=d.get("mp_cost", 0))
        ws.cell(row=row, column=6, value=d.get("cooldown", 0))
        # 新增3列
        job_limit = d.get("job_limit", [])
        ws.cell(row=row, column=7, value=",".join(job_limit) if isinstance(job_limit, list) else job_limit)
        ws.cell(row=row, column=8, value=d.get("level_req", 0))
        stat_req = d.get("stat_req", {})
        ws.cell(row=row, column=9, value=json.dumps(stat_req, ensure_ascii=False) if stat_req else "")
    _auto_width(ws)


def create_equipment_sheet(wb):
    ws = wb.create_sheet("装备")
    headers = ["装备名称", "槽位", "HP加成", "ATK加成", "DEF加成", "SPD加成", "品级(1-4)"]
    style_header(ws, headers)
    data = load_json("equipment") or {}
    for row, (key, d) in enumerate(data.items(), 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["slot"])
        ws.cell(row=row, column=3, value=d.get("hp_bonus", 0))
        ws.cell(row=row, column=4, value=d.get("atk_bonus", 0))
        ws.cell(row=row, column=5, value=d.get("def_bonus", 0))
        ws.cell(row=row, column=6, value=d.get("spd_bonus", 0))
        ws.cell(row=row, column=7, value=d.get("tier", 1))
    _auto_width(ws)


def create_monsters_sheet(wb):
    ws = wb.create_sheet("怪物")
    headers = ["怪物名称", "HP", "ATK", "DEF", "SPD", "金币", "经验", "图标", "颜色", "技能(逗号分隔)"]
    style_header(ws, headers)
    data = load_json("monsters") or {}
    for row, (key, d) in enumerate(data.items(), 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["hp"])
        ws.cell(row=row, column=3, value=d["atk"])
        ws.cell(row=row, column=4, value=d["def_"])
        ws.cell(row=row, column=5, value=d["spd"])
        ws.cell(row=row, column=6, value=d["gold"])
        ws.cell(row=row, column=7, value=d["exp"])
        ws.cell(row=row, column=8, value=d.get("emoji", "👾"))
        ws.cell(row=row, column=9, value=d.get("color", "#ff4444"))
        ws.cell(row=row, column=10, value=",".join(d.get("skills", [])))
    _auto_width(ws)


def create_dungeons_sheet(wb):
    ws = wb.create_sheet("地下城")
    headers = ["名称", "层数", "怪物列表", "BOSS", "难度", "金币倍率", "经验倍率", "事件概率", "陷阱概率"]
    style_header(ws, headers)
    data = load_json("dungeons") or []
    for row, d in enumerate(data, 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["floors"])
        ws.cell(row=row, column=3, value=",".join(d["monster_names"]))
        ws.cell(row=row, column=4, value=d["boss_name"])
        ws.cell(row=row, column=5, value=d["difficulty"])
        ws.cell(row=row, column=6, value=d.get("gold_mult", 1.0))
        ws.cell(row=row, column=7, value=d.get("exp_mult", 1.0))
        ws.cell(row=row, column=8, value=d.get("event_chance", 0.25))
        ws.cell(row=row, column=9, value=d.get("trap_chance", 0.15))
    _auto_width(ws)


def create_races_sheet(wb):
    ws = wb.create_sheet("种族")
    headers = ["种族名称", "描述", "HP修正", "ATK修正", "DEF修正", "SPD修正", "MP修正"]
    style_header(ws, headers)
    data = load_json("races") or {}
    for row, (key, d) in enumerate(data.items(), 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["desc"])
        ws.cell(row=row, column=3, value=d.get("hp_mod", 0))
        ws.cell(row=row, column=4, value=d.get("atk_mod", 0))
        ws.cell(row=row, column=5, value=d.get("def_mod", 0))
        ws.cell(row=row, column=6, value=d.get("spd_mod", 0))
        ws.cell(row=row, column=7, value=d.get("mp_mod", 0))
    _auto_width(ws)


def create_consumables_sheet(wb):
    ws = wb.create_sheet("消耗品")
    headers = ["物品名称", "描述", "类型", "效果值", "价格", "图标"]
    style_header(ws, headers)
    data = load_json("consumes") or {}
    for row, (key, d) in enumerate(data.items(), 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["desc"])
        ws.cell(row=row, column=3, value=d["item_type"])
        ws.cell(row=row, column=4, value=d.get("effect_value", 0))
        ws.cell(row=row, column=5, value=d.get("price", 10))
        ws.cell(row=row, column=6, value=d.get("emoji", "🧪"))
    _auto_width(ws)


def create_events_sheet(wb):
    ws = wb.create_sheet("事件")
    headers = ["事件名称", "描述", "类型", "选项(JSON)"]
    style_header(ws, headers)
    data = load_json("events") or {}
    for row, (key, d) in enumerate(data.items(), 2):
        ws.cell(row=row, column=1, value=d["name"])
        ws.cell(row=row, column=2, value=d["desc"])
        ws.cell(row=row, column=3, value=d["event_type"])
        ws.cell(row=row, column=4, value=json.dumps(d.get("choices", []), ensure_ascii=False))
    _auto_width(ws)


def create_narratives_sheet(wb):
    ws = wb.create_sheet("叙事")
    headers = ["叙事文字"]
    style_header(ws, headers)
    data = load_json("narratives") or {}
    texts = data.get("narratives", [])
    for row, text in enumerate(texts, 2):
        ws.cell(row=row, column=1, value=text)
    _auto_width(ws)


def main():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    wb = Workbook()
    create_jobs_sheet(wb)
    create_skills_sheet(wb)
    create_equipment_sheet(wb)
    create_monsters_sheet(wb)
    create_dungeons_sheet(wb)
    create_races_sheet(wb)
    create_consumables_sheet(wb)
    create_events_sheet(wb)
    create_narratives_sheet(wb)

    path = os.path.join(CONFIG_DIR, "game_data.xlsx")
    wb.save(path)
    print(f"Excel config generated: {path}")
    print(f"Sheets ({len(wb.sheetnames)}): {', '.join(wb.sheetnames)}")


if __name__ == "__main__":
    main()
