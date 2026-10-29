"""
简单修复主题装备等级（按索引分配）

根据装备在文件中的顺序，均匀分配 1-30 级。
"""

import json
import os
import sys

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

THEMES_DIR = os.path.join(src_path, "themes", "data")

def fix_equipment_levels_simple(theme_name, min_level=1, max_level=30):
    """简单修复：按索引分配等级"""
    print(f"\n🛠️  修复主题: {theme_name}")
    
    theme_dir = os.path.join(THEMES_DIR, theme_name)
    equipment_file = os.path.join(theme_dir, "equipment.json")
    
    if not os.path.exists(equipment_file):
        print(f"  ⚠️  装备文件不存在: {equipment_file}")
        return False
    
    # 读取装备数据
    with open(equipment_file, 'r', encoding='utf-8') as f:
        equipment = json.load(f)
    
    print(f"  📋 读取 {len(equipment)} 种装备")
    
    # 按索引分配等级
    num_equipment = len(equipment)
    for i, eq in enumerate(equipment):
        # 线性分配：第 1 个装备 = min_level，最后一个 = max_level
        level = min_level + int((max_level - min_level) * i / max(num_equipment - 1, 1))
        eq['level'] = level
    
    print(f"  ✅ 已分配等级 {min_level}-{max_level}")
    
    # 保存
    with open(equipment_file, 'w', encoding='utf-8') as f:
        json.dump(equipment, f, ensure_ascii=False, indent=2)
    
    print(f"  💾 已保存: {equipment_file}")
    return True

def main():
    """主函数"""
    print("🛠️  简单修复主题装备等级（按索引分配）")
    print("=" * 60)
    
    # 获取所有主题
    themes = []
    for item in os.listdir(THEMES_DIR):
        item_path = os.path.join(THEMES_DIR, item)
        if os.path.isdir(item_path):
            themes.append(item)
    
    themes.sort()
    print(f"\n找到 {len(themes)} 个主题")
    
    # 修复每个主题
    success_count = 0
    for theme in themes:
        if fix_equipment_levels_simple(theme, min_level=1, max_level=30):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ 修复完成！成功修复 {success_count}/{len(themes)} 个主题")
    print("\n💡 建议：")
    print("  1. 运行 analyze_theme_balance.py 重新分析")
    print("  2. 如果等级分配不合理，手动调整 equipment.json")

if __name__ == "__main__":
    main()
