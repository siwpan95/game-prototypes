import openpyxl
import os

# 2026-09-23 去本地化：配置表路径改由 命令行参数 → 仓内相对路径 推导
# （原路径已不存在）
import sys
from pathlib import Path

_DEFAULT_XLSX = Path(__file__).resolve().parent / "src" / "resources" / "config" / "game_config.xlsx"
xlsx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_XLSX
if not xlsx_path.is_file():
    raise SystemExit(f"[错误] 找不到敌人配置表：{xlsx_path}\n  用法：python normalize_enemies.py [game_config.xlsx 路径]")

wb = openpyxl.load_workbook(xlsx_path)
ws = wb['敌人模板']

# 衰减率：每级 5%，反推 1 级基础值
R = 1.05

print("正在将全部敌人归一化到 1 级基础数值...")
print(f"衰减率：每级 {int((R-1)*100)}%\n")

updated = 0
for row in range(2, ws.max_row + 1):
    name = ws.cell(row=row, column=1).value
    if not name:
        continue

    level = ws.cell(row=row, column=2).value or 1
    hp = ws.cell(row=row, column=3).value or 20
    dmg = ws.cell(row=row, column=4).value or 3
    defense = ws.cell(row=row, column=5).value or 0
    exp = ws.cell(row=row, column=6).value or 10
    gold = ws.cell(row=row, column=7).value or 5

    # 反推 1 级基础值
    factor = R ** (level - 1)
    base_hp = max(1, int(hp / factor))
    base_dmg = max(1, int(dmg / factor))
    base_def = max(0, int(defense / factor))
    base_exp = max(1, int(exp / factor))
    base_gold = max(1, int(gold / factor))

    # 写回 Excel：等级=1，数值=基础值
    ws.cell(row=row, column=2).value = 1
    ws.cell(row=row, column=3).value = base_hp
    ws.cell(row=row, column=4).value = base_dmg
    ws.cell(row=row, column=5).value = base_def
    ws.cell(row=row, column=6).value = base_exp
    ws.cell(row=row, column=7).value = base_gold

    updated += 1
    print(f"  {name:10s} Lv.{level}→Lv.1  HP {hp}→{base_hp}  DMG {dmg}→{base_dmg}")

print(f"\n共更新 {updated} 种敌人")
print("保存中...")

backup = xlsx_path + '.bak'
if os.path.exists(backup):
    os.remove(backup)
os.rename(xlsx_path, backup)
wb.save(xlsx_path)
print(f"完成！原文件已备份为：{backup}")
print(f"新文件已保存：{xlsx_path}")
print("\n等级列已全部清为 1，数值已归一化为 1 级基础值。")
print("下一步：在游戏内重新导入 Excel，生成新的 enemy_templates.json。")
