# 重装机兵同人游戏

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
