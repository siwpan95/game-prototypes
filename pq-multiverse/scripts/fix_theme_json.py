"""
自动修复主题 JSON 结构

为所有主题添加 PQ 架构需要的字段：
1. monsters.json: 添加 gold_reward, prefixes
2. equipment.json: 添加 level, base_stats, prefixes
3. meta.json: 添加 klasses, races, titles
"""
import os
import json
import sys

# 主题目录
THEMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'themes', 'data')

# PQ 架构需要的修饰符（通用）
DEFAULT_PREFIXES = {
    "sick": ["Dead", "Comatose", "Crippled", "Sick", "Undernourished"],
    "young": ["Baby", "Preadolescent", "Teenage", "Underage"],
    "big": ["Greater", "Massive", "Enormous", "Giant", "Titanic"],
    "special": ["Veteran", "Cursed", "Warrior", "Undead", "Demon"]
}

def fix_monsters(theme_name: str, theme_dir: str):
    """修复 monsters.json"""
    filepath = os.path.join(theme_dir, 'monsters.json')
    if not os.path.exists(filepath):
        print(f"⚠️  {theme_name}/monsters.json 不存在")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        monsters = json.load(f)
    
    modified = False
    
    for monster in monsters:
        # 添加 gold_reward (如果不存在)
        if 'gold_reward' not in monster:
            # 根据 exp_reward 计算 gold_reward
            exp = monster.get('exp_reward', 50)
            monster['gold_reward'] = max(1, exp // 3)
            modified = True
        
        # 添加 prefixes (如果不存在)
        if 'prefixes' not in monster:
            monster['prefixes'] = DEFAULT_PREFIXES.copy()
            modified = True
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(monsters, f, ensure_ascii=False, indent=2)
        print(f"✅ 修复 {theme_name}/monsters.json")
        return True
    else:
        print(f"⏭️  {theme_name}/monsters.json 无需修复")
        return False


def fix_equipment(theme_name: str, theme_dir: str):
    """修复 equipment.json"""
    filepath = os.path.join(theme_dir, 'equipment.json')
    if not os.path.exists(filepath):
        print(f"⚠️  {theme_name}/equipment.json 不存在")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        equipment = json.load(f)
    
    modified = False
    
    for item in equipment:
        # 添加 level (如果不存在)
        if 'level' not in item:
            item['level'] = 1
            modified = True
        
        # 添加 base_stats (如果不存在)
        if 'base_stats' not in item:
            # 根据 slot 生成基础属性
            slot = item.get('slot', 'weapon')
            base_stats = {}
            
            if slot == 'weapon':
                base_stats['attack'] = 5 * item.get('level', 1)
            elif slot == 'offhand':
                base_stats['defense'] = 3 * item.get('level', 1)
            elif slot in ['head', 'chest', 'legs', 'feet']:
                base_stats['hp'] = 10 * item.get('level', 1)
            elif slot == 'accessory':
                base_stats['charm'] = 2 * item.get('level', 1)
            
            item['base_stats'] = base_stats
            modified = True
        
        # 添加 prefixes (如果不存在)
        if 'prefixes' not in item:
            item['prefixes'] = []
            modified = True
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(equipment, f, ensure_ascii=False, indent=2)
        print(f"✅ 修复 {theme_name}/equipment.json")
        return True
    else:
        print(f"⏭️  {theme_name}/equipment.json 无需修复")
        return False


def fix_meta(theme_name: str, theme_dir: str, theme_obj):
    """修复 meta.json"""
    filepath = os.path.join(theme_dir, 'meta.json')
    if not os.path.exists(filepath):
        print(f"⚠️  {theme_name}/meta.json 不存在")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    modified = False
    
    # 添加 klasses (如果不存在)
    if 'klasses' not in meta:
        meta['klasses'] = theme_obj.classes if theme_obj else []
        modified = True
    
    # 添加 races (如果不存在)
    if 'races' not in meta:
        meta['races'] = theme_obj.races if theme_obj else []
        modified = True
    
    # 添加 titles (如果不存在)
    if 'titles' not in meta:
        meta['titles'] = ['the Slayer', 'the Slain', 'the Brave', 'the Wise']
        modified = True
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"✅ 修复 {theme_name}/meta.json")
        return True
    else:
        print(f"⏭️  {theme_name}/meta.json 无需修复")
        return False


def fix_theme(theme_name: str):
    """修复单个主题"""
    print(f"\n{'='*50}")
    print(f"修复主题: {theme_name}")
    print(f"{'='*50}")
    
    theme_dir = os.path.join(THEMES_DIR, theme_name)
    if not os.path.exists(theme_dir):
        print(f"❌ 主题目录不存在: {theme_dir}")
        return False
    
    # 加载主题对象 (用于获取 classes, races)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from themes.theme_loader import get_theme
        theme_obj = get_theme(theme_name)
    except Exception as e:
        print(f"⚠️ 无法加载主题对象: {e}")
        theme_obj = None
    
    # 修复 monsters.json
    fix_monsters(theme_name, theme_dir)
    
    # 修复 equipment.json
    fix_equipment(theme_name, theme_dir)
    
    # 修复 meta.json
    fix_meta(theme_name, theme_dir, theme_obj)
    
    return True


def main():
    """主函数"""
    print("📊 开始修复主题 JSON 结构 (PQ 架构适配)")
    print(f"主题目录: {THEMES_DIR}\n")
    
    # 获取所有主题
    themes = [d for d in os.listdir(THEMES_DIR) 
               if os.path.isdir(os.path.join(THEMES_DIR, d))]
    
    print(f"发现 {len(themes)} 个主题: {', '.join(themes)}\n")
    
    # 修复每个主题
    success_count = 0
    for theme_name in themes:
        try:
            fix_theme(theme_name)
            success_count += 1
        except Exception as e:
            print(f"❌ 修复失败: {e}")
    
    print(f"\n{'='*50}")
    print(f"✅ 完成！成功修复 {success_count}/{len(themes)} 个主题")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
