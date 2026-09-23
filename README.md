# 麻将连连看 (上海麻将) · MVVM 架构

> 仓库：<https://gitee.com/siwpan/mahjong> ｜ 许可：MIT（见 [LICENSE](LICENSE)）

单人麻将牌配对解谜游戏。使用标准 144 张麻将牌，按经典乌龟形多层堆叠，
配对两张相同的「自由牌」即可消除，清空全部 144 张牌即通关。

> 本项目由旧版单文件 `chess.py` (634 行 God Class) 重构为 MVVM 分层架构，
> 并按上海麻将标准规则全面完善。
>
> **引擎接入 (allin_engine)**：基础设施层（事件总线 / 固定步长主循环 / 字体加载）
> 已替换为内联的 `allin_engine/`（见下方说明），并对牌与棋盘做了**深度 ECS 化**
> —— 每张牌是引擎 `World` 中的一个 `Entity`，携带 `Tile`（本身即 Component）与
> `PositionComponent`（三维坐标）。`Board` 是 `World` 的适配器，对外 API 不变，
> 因此 `services/` 与 `views/` 无需改动即可运行在 ECS 之上。

## 运行

```bash
pip install Pillow
python main.py
```

> 需 Python 3.8+，tkinter (Python 自带)，Pillow。
> 字体文件位于 `assets/SimHei.ttf` 与 `assets/Arial.ttf`。

## 玩法

游戏含两种模式，按 **[M]** 切换：

### 上海麻将 (默认)
- **目标**：配对消除全部 144 张牌
- **自由牌**：上方无牌压住 **且** 左右至少一侧露边
- **配对规则**：
  - 同名同牌可配对 (如一万配一万、东风配东风)
  - 季节牌 (春/夏/秋/冬) 任意两张互配
  - 花牌 (梅/兰/菊/竹) 任意两张互配

### 连连看 (按 [M] 切换)
- **布局**：单层平面 **12 行 × 18 列、每 3 列留 1 列气道** = 144 张牌 (无堆叠，每张牌都在同一平面)
  - 气道是关键：满铺棋盘会把内部牌夹死，看着"同行同列都消不了"；留气道后
    ≤2 拐弯 + 绕外规则下可消对数从 ~13 提升到 ~39
- **选择**：任意两张牌均可先点选，不要求"自由牌"
- **连通规则**：两张相同牌 (或同组季/花) 若能用**不超过 2 个拐弯**的折线连通
  (路径可绕到棋盘外侧空格) 即可消除。**0 折(直线)、1 折(L 形)、2 折(U 形) 都合法**
- **提示 [H]**：标出一对当前可连通的牌，并画出**真实连通路径** (蓝线，含绕外段)，一眼看清怎么连
- **消除动画**：用黄色折线画出两张牌的真实连线 (含绕外)，让 ≤2 拐弯规则可见

### 计分 (两种模式通用)
基础 10/对，季花额外 +5，连击 +2/级，通关有时间剩余奖励

## 模式与布局

- **模式 [M]**：上海麻将 (3D 分层自由牌配对) / 连连看 (单层平面两折连通配对)
- **布局 [L]**：仅上海麻将模式可切换 — 乌龟 (标准 86+40+14+4) / 金字塔 / 矩形；
  连连看固定为单层平面布局，按 [L] 无效

## 快捷键

| 键 | 功能 | 键 | 功能 |
|----|------|----|------|
| H | 提示 | Z | 撤销 |
| S | 洗牌 | R | 重开 |
| M | 切换模式 | L | 切换布局 |
| ESC | 暂停 | ? | 帮助 |

## MVVM 架构

```
mahjong/
├── main.py                  # 入口：组装 root + ViewModel + Views；用 FixedTimestepLoop 驱动计时
├── allin_engine/            # 内联的引擎副本 (事件总线/World/固定步长循环/字体工具)
│                             #   （排除 .git，字体 SimHei.ttf/Arial.ttf 已并入 fonts/）
├── models/                  # Model 层 (纯数据/ECS，无 UI 依赖)
│   ├── components.py        #   Pos + PositionComponent(引擎 Component)：三维坐标
│   ├── tile.py              #   Tile: 麻将牌不可变数据，**同时是引擎 ECS Component**
│   ├── board.py             #   Board: World 适配器 (坐标 -> Entity)，对外 API 不变
│   └── game_state.py        #   GameState: 一局完整可变状态 (分数/时间/历史/...)
├── services/                # Service 层 (纯算法，无状态)
│   ├── deck.py              #   build_standard_deck: 标准 144 张牌堆生成
│   ├── layouts.py           #   generate_layout: 乌龟/金字塔/矩形/连连看平面 布局坐标
│   ├── matcher.py           #   is_free/can_link/find_hint: 自由牌/连通/配对/死局
│   └── scorer.py            #   score_for_match: 计分 (基础+季花+连击)
├── viewmodel/
│   └── game_viewmodel.py    # ViewModel: 状态机+命令；事件走引擎 EventBus，计时由循环注入
├── views/                   # View 层 (纯渲染+事件转发)
│   ├── tile_renderer.py     #   TileRenderer: PIL 绘制牌面，字体走引擎 discover_local_fonts
│   ├── board_canvas.py      #   BoardCanvas: Canvas 棋盘+点击+动画
│   └── hud.py               #   Hud: 顶栏信息+按钮，字体走引擎 load_local_tk_font
├── assets/                  # 字体 (已被引擎 fonts/ 接管发现，此处保留作兼容)
│   ├── SimHei.ttf
│   └── Arial.ttf
├── chess.py                 # 旧版单文件实现 (保留作对比)
└── README.md
```

### 数据流

```
View 点击 ──> ViewModel.select(pos) ──> Model 更新 (Board/GameState)
                │                            │
                │<─── 事件回调 (GameEvent) ──┘
                │
                └──> View 刷新 (重绘/动画/HUD)
```

ViewModel 通过 `add_listener` 注册回调，自身不持有任何 UI 引用，
可脱离 tkinter 独立测试。

## 引擎接入 (allin_engine)

`allin_engine` 以**静态内联副本**方式存在于 `mahjong/allin_engine/`（与 dwarf_scrolls
同模式，零跨项目硬引用；更新引擎时在此副本内同步）。mahjong 用到的引擎能力：

- **事件总线 `EventBus`**（`core/event_bus.py`）：替换 ViewModel 原手写 `add_listener`/`_emit`
  列表分发。ViewModel 保留 `GameEvent` 信封与 `add_listener` 对外 API（视图层零改动），
  内部用 `GAME_EVENTS` 枚举注册分发器，获得引擎的递归保护 + 单回调容错。
- **固定步长主循环 `FixedTimestepLoop`**（`core/game_loop.py`）：`main.py` 用其驱动计时，
  `ViewModel.tick(dt)` 改为接收循环注入的固定步长 `dt`（去掉 `time.time()` 墙钟），
  逻辑与帧率解耦，单帧上限钳制防死亡螺旋。
- **字体工具 `utils.font`**：`TileRenderer` 用 `discover_local_fonts()` 按别名
  （`simhei`/`arial`，已并入引擎 `fonts/`）解析字体路径；`Hud` 用 `load_local_tk_font()`
  替换硬编码 `("SimHei", 10)`，字体统一由引擎发现机制托管。
- **深度 ECS 化**：`Tile` 是引擎 `Component`；每张牌是 `World` 中的 `Entity`，
  带 `Tile` + `PositionComponent`。`Board` 是 `World` 的适配器（坐标 -> Entity），
  `get/place/remove/restore/occupied_positions/remaining` 等 API 与原版一致，
  故 `services/`（deck/layouts/matcher/scorer）与 `views/` 完全无需改动即运行在 ECS 之上。

运行：`python main.py`（需 Python 3.8+，tkinter，Pillow；字体由引擎 `fonts/` 提供）。

## 与旧版 `chess.py` 的主要改进

| 维度 | 旧版 chess.py | 新版 (MVVM) |
|------|--------------|-------------|
| 架构 | 单文件 God Class 634 行 | Model/Service/ViewModel/View 四层分离 |
| 布局 | 简化矩形堆叠 (非标准) | 标准乌龟 86+40+14+4，交叉堆叠支撑合法 |
| 堆叠模型 | 柱状 (同 r,c 叠层) | 交叉堆叠 (上层压 4 张下层中心，标准上海麻将) |
| 牌面渲染 | 纯色方块+文字 | 圆角象牙底+筒画圆圈/条画竖条/万画数字 |
| 撤销 | 无 | 完整撤销栈 (Z 键) |
| 连击 | 无 | 快速配对触发连击加成 |
| 死局检测 | 仅 mahjong 自动洗牌 | 双模式死局检测+提示洗牌 |
| 提示 bug | lambda 闭包变量陷阱 (i,j 错乱) | 已修复 |
| 连通算法 | 2 折逻辑"对称略"残缺 | 完整 0/1/2 折 + 边界外绕行 |
| 布局种类 | 1 种 | 3 种 (乌龟/金字塔/矩形) |
| 牌名 | 筒1/条2 (简写) | 一筒/一条 (标准中文麻将牌名) |
| 事件系统 | 无（过程式直调） | 引擎 EventBus（递归保护 + 单回调容错）|
| 计时循环 | `after` + `time.time()` 墙钟 | 引擎 FixedTimestepLoop（固定步长、防死亡螺旋）|
| 字体加载 | 手写路径搜索 + 硬编码 | 引擎 `utils.font`（discover/load_local_tk_font）|
| 牌/棋盘存储 | 单文件 dict | **深度 ECS**：Tile 为 Component，牌为 World 中 Entity，Board 为 World 适配器 |

## 技术要点

- **交叉堆叠遮挡判定**：上层牌 (l+1,r,c) 压住下层 (l,r,c)/(l,r,c+1)/(l,r+1,c)/(l,r+1,c+1)，
  故牌 (l,r,c) 被遮挡当且仅当 layer l+1 存在 (r-1,c-1)/(r-1,c)/(r,c-1)/(r,c) 任一有牌。
- **布局支撑合法性**：每张上层牌的下方 4 张下层牌必须都存在 (不悬空)，
  由 `tests/test_layouts.py` 自动验证（`test_cross_stack_support`）。
- **两折连通**：投影到 (row,col) 平面，允许绕到棋盘边界外一格，
  覆盖 0/1/2 折三种情况。
- **洗牌保证有解**：洗牌时最多尝试 20 次重排，直到 `has_solution` 为真。
- **渲染缓存**：按 `tile.short` 缓存 `ImageTk.PhotoImage`，144 张牌仅 42 种唯一牌面。
