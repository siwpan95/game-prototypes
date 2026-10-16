# 重装机兵同人游戏（maga）

> **非商业同人作品**，致敬 DATA EAST / Crea-Tech《重装机兵 METAL MAX》系列（初代 1991，FC）。
> 全部文案与数值为本作坊原创，不使用原作素材/音乐/立绘，与官方无任何关联。
> 《重装机兵》系列 IP 现属 Cygames（2022 年自角川受让）；本项目仅作学习交流。

末世废土世界观下的赏金猎人 RPG：开车、改车、接悬赏、打赏金首、攒钱变强。

## 技术栈

- **Python 3.13+**（标准库为主）
- **Tkinter** —— GUI 与 ASCII 字符渲染（无第三方引擎依赖）
- **pandas + openpyxl** —— 读写 `config.xlsx` 游戏配置
- **MVVM 架构** —— `model`（纯业务，零 UI 依赖）/ `viewmodel`（命令 + Observable）/ `view`（Tkinter 渲染）

## 快速开始

```bash
# 1. 安装依赖（建议虚拟环境）
pip install -r requirements.txt

# 2. 启动游戏
python main.py
```

配置文件 `config.xlsx` 已随仓库提供；如需重置为模板：

```bash
python create.py --force     # 免确认重置 config.xlsx
```

## 操作

| 按键 | 作用 |
|---|---|
| 方向键 | 移动 |
| 空格 | 交互（进入地图入口/城镇菜单/离开） |
| I | 物品栏（数字键使用/装备/卸下） |
| V | 战车信息 |
| Q | 任务日志 |
| R | 城镇内休息（回满 HP 与燃料） |
| S | 保存（3 槽位） |
| ESC | 暂停菜单 / 返回 |

核心循环：**接任务 → 荒野刷怪攒钱 → 城镇商店买装备 → 打赏金首领赏金 → 改造变强 → 推进剧情**。

## 目录结构

```
maga/
├── main.py               # 入口：组装 Model/ViewModel/View
├── create.py             # 配置模板生成器（--force 重置 config.xlsx）
├── config.xlsx           # 游戏配置（Excel 编辑，8 个 sheet）
├── model/                # 纯数据与业务逻辑（零 Tkinter 依赖，可单测）
│   ├── character.py      #   角色/敌人（人车分离伤害、装备加成）
│   ├── vehicle.py        #   战车（HP/燃料/损坏）
│   ├── battle.py         #   战斗引擎（攻击/防御/技能/逃跑/结算）
│   ├── game_state.py     #   GameData/任务管理/存档序列化
│   ├── map_manager.py    #   地图（荒野无限地形 + 城镇/遗迹有限地图）
│   └── infinite_map.py   #   哈希确定性地形
├── viewmodel/            # 命令与 Observable 属性（存档/读档在此）
├── view/                 # Tkinter 渲染（主窗口/组件）
├── data/                 # Excel 配置加载 + JSON 存档管理
├── tests/                # 冒烟测试（tkinter 桩 + 8 组断言）
└── docs/完善规划.md       # 分阶段完善规划（P0-P3）
```

## 配置说明（config.xlsx）

| Sheet | 内容 | 关键列 |
|---|---|---|
| Enemies | 敌人 | 区域ID（出现地区）、遭遇率、系别（克制）、掉落物品ID/掉落率、是否赏金首 |
| Items | 物品 | 装备槽位（武器/头/身/手/鞋，空=消耗品）、使用场景（人/车/弹/探索）、效果类型 |
| Chassis/Engines/CUnits/Weapons | 战车部件 | 底盘耐久/防御、引擎载重/价格、C装置命中回避、武器类型/攻击/价格 |
| Vehicles | 战车 | 部件引用 ID、装甲片、获取方式（default/site/bounty）+ 坐标/价格/条件 |
| Maps | 地图 | 无限地图（荒野）、是否城镇、入口X/Y（荒野入口坐标） |
| NPCs | NPC | 地图ID + 坐标（走到即对话） |
| Skills | 技能 | 解锁等级、效果类型（连击/修理/贯穿）、职业限定、冷却 |
| Classes | 职业 | 成长率（HP/攻/防/速）、专属特技 |
| Shops | 商店 | 地图ID、商品列表、价格倍数 |
| Quests | 任务 | 类型（kill/collect/explore）、目标ID、目标数量、奖励 |
| Bounties | 赏金首 | 悬赏金额、所在地图ID + 坐标X/Y（明雷）、敌人ID、强制人战 |

新增列均有默认值，旧版配置缺列也能加载（向后兼容）。

## 存档

`saves/save_1..3.json`（已 gitignore），带 `schema_version`，跨版本可迁移。

## 测试

```bash
python tests/run_all.py     # 运行全部冒烟测试
```

覆盖：存档往返、地图进出、区域遇敌、任务判定、技能解锁、装备加成、
人车分离伤害、敌人掉落。

> 注：model 层零 UI 依赖；VM 层经 `tests/tk_stub.py` 注入 tkinter 桩后在
> 无显示环境驱动。GUI 请在带 tkinter 的 Python 环境运行 `python main.py`。

## 路线图

见 [`docs/完善规划.md`](docs/完善规划.md)：P0 缺陷修复与工程化（已完成）→
P1 还原 MM1 核心系统（赏金首/战车结构改造/职业特技）→ P2 剧情内容 →
P3 打磨发布。

## 许可

代码 MIT（见 LICENSE）。同人声明如上，禁止商用。
