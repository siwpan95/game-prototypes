"""
分析主题数据的平衡性

检查：
1. 怪物等级分布
2. 经验奖励是否合理
3. 装备等级分布
4. 游戏进度速度
"""

import json
import os
import sys

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

THEMES_DIR = os.path.join(src_path, "themes", "data")

def analyze_theme(theme_name):
    """分析单个主题"""
    print(f"\n📊 分析主题: {theme_name}")
    print("=" * 60)
    
    theme_dir = os.path.join(THEMES_DIR, theme_name)
    
    # 1. 读取怪物数据
    monsters_file = os.path.join(theme_dir, "monsters.json")
    if os.path.exists(monsters_file):
        with open(monsters_file, 'r', encoding='utf-8') as f:
            monsters = json.load(f)
        
        print(f"\n👹 怪物数据 ({len(monsters)} 种)")
        
        # 等级分布
        levels = [m.get('level', 1) for m in monsters]
        min_level = min(levels)
        max_level = max(levels)
        avg_level = sum(levels) / len(levels)
        
        print(f"  等级范围: {min_level} - {max_level}")
        print(f"  平均等级: {avg_level:.1f}")
        
        # 经验奖励分布
        exp_rewards = [m.get('exp_reward', 0) for m in monsters]
        min_exp = min(exp_rewards)
        max_exp = max(exp_rewards)
        avg_exp = sum(exp_rewards) / len(exp_rewards)
        
        print(f"  经验奖励: {min_exp} - {max_exp} (平均: {avg_exp:.1f})")
        
        # 检查：经验奖励是否与等级匹配
        print(f"\n  ⚠️ 等级-经验匹配检查:")
        for m in monsters[:5]:  # 只显示前5个
            level = m.get('level', 1)
            exp = m.get('exp_reward', 0)
            ratio = exp / level if level > 0 else 0
            print(f"    {m['name']}: 等级 {level}, 经验 {exp} (比例: {ratio:.1f})")
    
    # 2. 读取装备数据
    equipment_file = os.path.join(theme_dir, "equipment.json")
    if os.path.exists(equipment_file):
        with open(equipment_file, 'r', encoding='utf-8') as f:
            equipment = json.load(f)
        
        print(f"\n🗡️ 装备数据 ({len(equipment)} 种)")
        
        # 等级分布
        levels = [e.get('level', 1) for e in equipment]
        min_level = min(levels)
        max_level = max(levels)
        
        print(f"  等级范围: {min_level} - {max_level}")
        
        # 检查：是否有高等级装备
        high_level_equip = [e for e in equipment if e.get('level', 1) > 10]
        print(f"  高等级装备 (>10): {len(high_level_equip)} 种")
    
    # 3. 读取元数据
    meta_file = os.path.join(theme_dir, "meta.json")
    if os.path.exists(meta_file):
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        print(f"\n📋 元数据")
        print(f"  主题名称: {meta.get('name', 'Unknown')}")
        print(f"  可用种族: {len(meta.get('races', []))} 种")
        print(f"  可用职业: {len(meta.get('classes', []))} 种")
        print(f"  可用称号: {len(meta.get('titles', []))} 种")

def main():
    """主函数"""
    print("📊 PQ Multiverse - 主题数据平衡性分析")
    print("=" * 60)
    
    # 获取所有主题
    themes = []
    for item in os.listdir(THEMES_DIR):
        item_path = os.path.join(THEMES_DIR, item)
        if os.path.isdir(item_path):
            themes.append(item)
    
    themes.sort()
    print(f"\n找到 {len(themes)} 个主题: {', '.join(themes)}")
    
    # 分析每个主题
    for theme in themes:
        analyze_theme(theme)
    
    print("\n" + "=" * 60)
    print("✅ 分析完成！")
    print("\n💡 建议：")
    print("  1. 确保怪物等级分布合理（1-50 级）")
    print("  2. 经验奖励应该与怪物等级成正比")
    print("  3. 装备等级应该覆盖整个游戏过程")
    print("  4. 高等级怪物应该提供更有吸引力的奖励")

if __name__ == "__main__":
    main()
