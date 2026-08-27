#!/usr/bin/env python3
"""
create.py - 重装机兵同人游戏配置生成器
快速创建初始的Excel配置文件
"""
import pandas as pd
import os
import sys

def create_config_excel(filename="config.xlsx"):
    """创建完整的游戏配置Excel文件"""
    
    print(f"正在创建配置文件: {filename}")
    
    # 1. 敌人配置表
    enemies_data = {
        'ID': [1, 2, 3, 4, 5, 6, 7, 8],
        '名称': ['野犬', '流氓', '装甲虫', '战车', '变异鼠', '赏金猎人', '钢铁巨蝎', '诺亚碎片'],
        'HP': [30, 45, 60, 100, 25, 80, 120, 200],
        '攻击': [8, 12, 15, 25, 6, 18, 22, 35],
        '防御': [3, 5, 10, 20, 2, 8, 15, 25],
        '速度': [10, 8, 5, 3, 12, 7, 4, 2],
        '经验值': [20, 35, 50, 100, 15, 70, 90, 150],
        '金币': [50, 80, 120, 300, 30, 200, 250, 500],
        '遭遇率': [0.3, 0.25, 0.2, 0.1, 0.35, 0.15, 0.08, 0.05],
        '描述': [
            '凶猛的野狗，经常成群结队出现',
            '拦路抢劫的恶棍，装备简陋武器',
            '覆盖厚重装甲的昆虫，防御极高',
            '废弃的战争机器，火力强大',
            '体型小速度快的啮齿动物',
            '专业的赏金猎人，战斗力强',
            '巨大的机械蝎子，尾部有剧毒',
            '诺亚系统的碎片，终极BOSS'
        ]
    }
    
    # 2. 物品配置表
    items_data = {
        'ID': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        '名称': ['药草', '万能药', '兴奋剂', '猎枪', '激光枪', '火箭筒', '钢盔', '防弹衣', '动力装甲', '汽油'],
        '类型': ['heal', 'heal', 'buff', 'weapon', 'weapon', 'weapon', 'armor', 'armor', 'armor', 'fuel'],
        '效果值': [30, 100, 20, 20, 35, 50, 10, 25, 40, 50],
        '价格': [50, 200, 150, 500, 1200, 2000, 300, 800, 2500, 100],
        '描述': [
            '恢复30点HP',
            '完全恢复HP',
            '暂时提升攻击力',
            '基础远程武器，攻击力+20',
            '高科技激光武器，攻击力+35',
            '重型反装甲武器，攻击力+50',
            '基础头部防护，防御力+10',
            '军用防弹背心，防御力+25',
            '外骨骼动力装甲，防御力+40',
            '恢复战车50点燃料'
        ],
        '战斗中可用': [True, True, True, False, False, False, False, False, False, True]
    }
    
    # 3. 战车配置表
    vehicles_data = {
        'ID': [1, 2, 3, 4, 5],
        '名称': ['吉普车', '坦克', '摩托车', '装甲车', '越野车'],
        'HP': [200, 500, 100, 350, 250],
        '攻击': [25, 60, 10, 40, 30],
        '防御': [15, 40, 5, 25, 20],
        '速度': [8, 5, 15, 6, 10],
        '燃料容量': [100, 150, 80, 120, 110],
        '燃料消耗': [1.0, 2.0, 0.5, 1.5, 1.2],
        '修理费用': [100, 300, 50, 200, 150],
        '描述': [
            '轻型侦察车辆，机动性好',
            '重型战斗车辆，火力强大',
            '快速机动载具，适合侦察',
            '中型战斗车辆，攻守平衡',
            '全天候作战车辆，适应性强'
        ]
    }
    
    # 4. 地图配置表
    maps_data = {
        'ID': [1, 2, 3, 4, 5],
        '名称': ['荒野', '伊尔镇', '罗克镇', '索鲁镇', '地下遗迹'],
        '宽度': [20, 15, 15, 18, 25],
        '高度': [20, 15, 15, 18, 25],
        '地形类型': [
            '平原,山地,水域,森林',
            '城镇,建筑,道路',
            '城镇,港口,建筑',
            '城镇,工厂,建筑',
            '废墟,洞穴,机械'
        ],
        '遭遇率': [0.05, 0.0, 0.0, 0.0, 0.08],
        '音乐': [
            'battle_wild.mp3',
            'town_theme.mp3',
            'town_theme2.mp3',
            'industrial.mp3',
            'dungeon.mp3'
        ]
    }
    
    # 5. NPC配置表
    npcs_data = {
        'ID': [1, 2, 3, 4, 5, 6, 7],
        '名称': ['老人', '商人', '机械师', '赏金猎人', '镇长', '神秘女子', '博士'],
        '角色': ['向导', '商店老板', '修理工', '任务发布者', '镇长', '神秘人物', '科学家'],
        '对话': [
            '欢迎来到这个世界！小心外面的怪物。',
            '想买些什么吗？我有最好的装备！',
            '需要修理战车吗？价格公道！',
            '听说附近有通缉犯，你能帮我解决吗？',
            '我们的小镇很安全，请好好休息。',
            '命运之轮已经开始转动...',
            '诺亚系统已经失控，我们必须阻止它！'
        ],
        'X坐标': [5, 10, 8, 12, 7, 15, 3],
        'Y坐标': [5, 10, 12, 8, 7, 3, 10],
        '地图ID': [1, 2, 2, 3, 3, 4, 4]
    }
    
    # 6. 技能配置表（新增）
    skills_data = {
        'ID': [1, 2, 3, 4, 5],
        '名称': ['普通攻击', '蓄力射击', '防御姿态', '紧急回避', '必杀技'],
        '类型': ['attack', 'attack', 'defense', 'evade', 'special'],
        '消耗': [0, 10, 5, 8, 30],
        '效果': ['造成物理伤害', '蓄力一击，伤害翻倍', '减少受到的伤害', '提高闪避率', '无视防御的强力攻击'],
        '描述': [
            '基础的物理攻击',
            '需要一回合蓄力的强力攻击',
            '暂时提高防御力',
            '暂时提高闪避率',
            '消耗大量能量的终极技能'
        ]
    }
    
    # 7. 商店配置表（新增）
    shops_data = {
        'ID': [1, 2, 3, 4],
        '名称': ['伊尔镇商店', '罗克镇武器店', '索鲁镇防具店', '黑市'],
        '类型': ['general', 'weapon', 'armor', 'black_market'],
        '地图ID': [2, 3, 4, 1],
        '商品列表': [
            '1,2,3,4',  # 药草,万能药,猎枪,钢盔
            '3,4,5',    # 猎枪,钢盔,激光枪
            '4,5,6,7',  # 钢盔,激光枪,火箭筒,防弹衣
            '5,6,7,8,9' # 激光枪,火箭筒,防弹衣,动力装甲,汽油
        ],
        '价格倍数': [1.0, 1.2, 1.0, 2.5]
    }
    
    # 8. 任务配置表（新增）
    quests_data = {
        'ID': [1, 2, 3, 4],
        '名称': ['清理野犬', '消灭赏金猎人', '找回被盗物品', '调查地下遗迹'],
        '类型': ['kill', 'kill', 'collect', 'explore'],
        '描述': [
            '镇外的野犬威胁到了居民安全，请消灭它们。',
            '一个危险的赏金猎人在附近活动，请将其消灭。',
            '我的传家宝被偷了，请帮我找回来。',
            '地下遗迹可能有诺亚的线索，去调查一下。'
        ],
        '目标ID': [1, 5, 2, 8],  # 对应敌人ID
        '奖励经验': [100, 200, 150, 300],
        '奖励金币': [200, 500, 300, 800],
        '奖励物品': ['1', '3', '2', '9']  # 药草,猎枪,万能药,动力装甲
    }
    
    # 创建DataFrame字典
    dataframes = {
        'Enemies': pd.DataFrame(enemies_data),
        'Items': pd.DataFrame(items_data),
        'Vehicles': pd.DataFrame(vehicles_data),
        'Maps': pd.DataFrame(maps_data),
        'NPCs': pd.DataFrame(npcs_data),
        'Skills': pd.DataFrame(skills_data),
        'Shops': pd.DataFrame(shops_data),
        'Quests': pd.DataFrame(quests_data)
    }
    
    # 保存到Excel文件
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        for sheet_name, df in dataframes.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # 自动调整列宽
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
    
    print(f"✅ 配置文件 '{filename}' 创建成功！")
    print(f"📊 包含 {len(dataframes)} 个工作表:")
    for sheet_name in dataframes.keys():
        print(f"   - {sheet_name}")
    
    return filename

def create_default_game_files():
    """创建完整的游戏文件结构"""
    
    # 创建目录结构
    directories = [
        "assets",
        "assets/maps",
        "assets/sprites",
        "assets/sounds",
        "assets/fonts",
        "saves"
    ]
    
    print("\n📁 创建目录结构...")
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"   ✓ {directory}")
    
    # 创建配置文件
    config_file = create_config_excel()
    
    # 创建README文件
    readme_content = """# 重装机兵同人游戏

## 文件说明

### 核心文件
- `main.py` - 主游戏程序
- `loader.py` - Excel配置加载器
- `create.py` - 配置文件生成器

### 配置文件
- `config.xlsx` - 游戏配置数据（用Excel编辑）

### 目录结构
- `assets/` - 游戏资源文件
- `saves/` - 游戏存档

## 使用方法

1. 运行 `create.py` 生成初始配置文件
2. 用Excel编辑 `config.xlsx` 自定义游戏内容
3. 运行 `main.py` 启动游戏

## 配置说明

### 编辑Excel文件
- **Enemies**: 敌人配置
- **Items**: 物品配置
- **Vehicles**: 战车配置
- **Maps**: 地图配置
- **NPCs**: NPC配置
- **Skills**: 技能配置
- **Shops**: 商店配置
- **Quests**: 任务配置

## 注意事项
- 不要修改Excel的列名
- ID必须唯一
- 数值类型要正确
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print(f"\n📝 README.md 文件已创建")
    
    return config_file

def check_dependencies():
    """检查依赖库"""
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("⚠️  缺少以下依赖库:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("重装机兵同人游戏 - 配置生成器")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查是否已存在配置文件
    if os.path.exists("config.xlsx"):
        response = input("\n⚠️  config.xlsx 已存在，是否覆盖？(y/n): ")
        if response.lower() != 'y':
            print("操作取消。")
            return
    
    # 创建完整文件结构
    config_file = create_default_game_files()
    
    print("\n" + "=" * 60)
    print("✨ 配置生成完成！")
    print("=" * 60)
    print("\n下一步:")
    print("1. 用Excel打开 config.xlsx 编辑游戏配置")
    print("2. 运行 python main.py 启动游戏")
    print("3. 修改配置后重启游戏生效")
    print("\n提示: 可以随时重新运行 create.py 重置配置")

if __name__ == "__main__":
    main()