"""
智能修复主题装备等级

根据装备名称或属性，估算合理的等级。
"""

import json
import os
import sys
import re

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

THEMES_DIR = os.path.join(src_path, "themes", "data")

def estimate_level_from_name(name):
    """根据名称估算等级"""
    name_lower = name.lower()
    
    # 关键词映射
    level_keywords = {
        # 低级
        '初级': 1, '新手': 1, '简单': 1, '基础': 1,
        'broken': 1, 'rusty': 1, 'wooden': 1, 'cloth': 1,
        
        # 中级
        '中级': 10, '进阶': 10, '精良': 10,
        'iron': 10, 'leather': 10, 'steel': 10,
        
        # 高级
        '高级': 20, '专家': 20, '史诗': 20, '稀有': 20,
        'silver': 20, 'golden': 20, 'enchanted': 20,
        
        # 传说
        '传说': 30, '神话': 30, '传奇': 30, '唯一': 30,
        'diamond': 30, 'legendary': 30, 'mythical': 30,
    }
    
    for keyword, level in level_keywords.items():
        if keyword in name_lower:
            return level
    
    # 默认：根据名称长度估算（简单启发式）
    # 名称越长，可能是越高级的装备
    return min(len(name) // 3, 30)

def estimate_level_from_stats(stats):
    """根据属性估算等级"""
    if not stats:
        return 1
    
    # 计算总属性值
    total_stat = 0
    for stat_name, stat_value in stats.items():
        if isinstance(stat_value, (int, float)):
            total_stat += stat_value
    
    # 根据总属性值估算等级
    if total_stat < 10:
        return 1
    elif total_stat < 30:
        return 5
    elif total_stat < 50:
        return 10
    elif total_stat < 100:
        return 15
    elif total_stat < 200:
        return 20
    else:
        return 30

def fix_equipment_levels(theme_name):
    """修复单个主题的装备等级"""
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
    
    # 修复等级
    fixed_count = 0
    for i, eq in enumerate(equipment):
        old_level = eq.get('level', 1)
        
        # 方法1：根据名称估算
        name_level = estimate_level_from_name(eq.get('name', ''))
        
        # 方法2：根据属性估算
        stats_level = estimate_level_from_stats(eq.get('base_stats', {}))
        
        # 取最大值
        new_level = max(name_level, stats_level)
        
        # 如果旧等级是 1（默认值），则更新
        if old_level == 1:
            eq['level'] = new_level
            fixed_count += 1
            print(f"    {eq.get('name', 'Unknown')}: {old_level} → {new_level}")
    
    print(f"  ✅ 修复了 {fixed_count} 种装备的等级")
    
    # 保存
    with open(equipment_file, 'w', encoding='utf-8') as f:
        json.dump(equipment, f, ensure_ascii=False, indent=2)
    
    print(f"  💾 已保存: {equipment_file}")
    return True

def main():
    """主函数"""
    print("🛠️  智能修复主题装备等级")
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
        if fix_equipment_levels(theme):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ 修复完成！成功修复 {success_count}/{len(themes)} 个主题")
    print("\n💡 建议：")
    print("  1. 检查修复后的等级是否合理")
    print("  2. 如果不合理，手动调整 equipment.json")
    print("  3. 运行 analyze_theme_balance.py 重新分析")

if __name__ == "__main__":
    main()
