# DOOM 风格伪3D 光线投射游戏 — 增量 PRD（仅描述新增/变更部分）

> 本文档是 `design/ARCHITECTURE.md`（基础架构）的**增量补充**，只描述 4 项新需求的「新增/变更了什么」，不再复述已有功能。
> 读者：架构师（做增量设计）、工程师（落地）、QA（验收）。
> 语言：中文。状态：已与用户确认 3 条关键决策（见第 4 节）。

---

## 1. 变更概述（4 项各一句话目标）

1. **README 文档**：为项目根目录补一份 `README.md`（现位于 `G:\repos\loly`，早期路径为 `G:/loly/README.md`），统一说明安装、运行、操作、特性、关卡文件格式、架构与各模块职责、测试方式。
2. **敌人 / 拾取物**：在 `GameWorld` 中新增实体层（敌人、拾取物），并实现「简单追逐」敌人 AI、玩家生命/分数模型与对应碰撞、HUD 生命条与分数显示。
3. **纹理生成改用 surfarray 提速**：将 `render/noise.py` 的 `generate_wall_texture` 由逐像素 `set_at` 改为 numpy + `pygame.surfarray` 向量化生成，**保持确定性且 4 种纹理视觉一致**。
4. **简易关卡编辑器**：提供「游戏内 pygame GUI 编辑器 + JSON/ASCII 文本地图格式」，二者读写同一份地图格式；主游戏启动时支持从地图文件加载关卡。

---

## 2. 用户故事（针对新增能力）

1. 作为**玩家**，我希望在迷宫中看到敌人并被其追击、受伤，同时能拾取血量/分数，从而让游戏具备目标与挑战（生存 + 计分）。
2. 作为**关卡设计者**，我希望用游戏内编辑器和文本格式创作并分享关卡（含墙、玩家起点、敌人、拾取物），而不必改代码或手写网格。
3. 作为**贡献者/运维**，我希望有 README 且纹理生成更快、可复现，从而能快速上手、让 CI 更快且稳定（确定性）。
4. 作为**玩家**，我希望 HUD 上有生命条和分数，从而能实时掌握生存进度与得分。

---

## 3. 需求池（P0 / P1 / P2）

> 优先级定义：P0 = 核心可用（必须随本次增量交付）；P1 = 体验增强（建议本次交付，可后续）；P2 = 可选（后续迭代）。
> 验收条目使用 must / should / could。

### 3.1 README 文档（需求 1）

| ID | 优先级 | 需求条目 | 验收 |
|---|---|---|---|
| R1.1 | P0 | 项目根目录必须新增 `README.md`（现位于 `G:\repos\loly`） | 文件存在且 `python -c "import os; assert os.path.exists('README.md')"` 通过 |
| R1.2 | P0 | README 必须覆盖：项目简介、环境依赖与安装（pygame-ce / numpy / sounddevice）、运行方式（含 `--headless N` CI 模式与 `DISABLE_AUDIO`）、操作说明（WASD 移动、←/→ 旋转、1–4 切 RenderMode、ESC 退出）、游戏特性 | 上述小节全部存在 |
| R1.3 | P0 | README 必须含「关卡文件格式说明」（对应需求 4 的 JSON schema 与 ASCII 字符表，见第 5.3 节） | 给出 JSON 字段与 ASCII 字符表示例 |
| R1.4 | P0 | README 必须含「架构概览（模块职责）」与「测试运行方式」 | 列出 `core/ render/ audio/ world/` 各模块一句话职责；给出 `pytest` 运行命令 |
| R1.5 | P1 | README should 提供常见问题（headless 无显示、无声卡降级）与编辑器进入方式的简短说明 | 含「F.A.Q」小节 |

### 3.2 敌人 / 拾取物（需求 2）

| ID | 优先级 | 需求条目 | 验收 |
|---|---|---|---|
| R2.1 | P0 | 必须新增实体类型 `Enemy` 与 `Pickup`（建议落于新模块 `doom_game/core/entities.py`，与现有 `core/types.py` 同源，遵守架构规则 #1/#6：基础类型只从 `core/` 导入） | 可被 `from doom_game.core.entities import Enemy, Pickup, PickupType` 导入 |
| R2.2 | P0 | `GameWorld` 必须持有 `self.enemies: List[Enemy]` 与 `self.pickups: List[Pickup]`，并在构造/加载关卡时填充 | 构造后两列表存在（可为空） |
| R2.3 | P0 | `Player` 必须扩展生命与分数字段（`hp`、`max_hp`、`score`）；初始 `hp = max_hp` | `player.hp <= player.max_hp`，`player.score == 0` |
| R2.4 | P0 | **敌人 AI（已确认：简单追逐）**：敌人进入「感知范围」（玩家无墙遮挡 + 距离 ≤ `ENEMY_PERCEPTION_RANGE`）时追踪玩家，具备基础移动与墙体碰撞（复用 `WorldMap.is_wall` 网格判定），脱离范围后停下 | headless 单测：模拟玩家进入/离开范围，敌人状态在 `idle/chasing` 间正确切换；移动不穿墙 |
| R2.5 | P0 | 敌人须有最小生命/伤害模型：与玩家碰撞（距离 < `ENEMY_CONTACT_DIST`）时对玩家造成伤害，并有接触冷却避免每帧扣血 | 碰撞一次扣 `ENEMY_DAMAGE`，且 `player.hp` 下降有冷却（如每秒至多 1 次） |
| R2.6 | P0 | **拾取物（已确认：生命 + 分数）**：两种类型 `PickupType.HEALTH` / `PickupType.SCORE`；玩家靠近即拾取（距离 < `PICKUP_CONTACT_DIST`），分别回血/加分，拾取后消失 | 单测：玩家接近 health 拾取 → `hp` 上升；接近 score 拾取 → `score` 增加；拾取后 `taken=True` |
| R2.7 | P0 | 敌人须在 3D 视图以 sprite/色块绘制（在墙体渲染后做 billboard/精灵叠加），并在小地图以标点（如红点）显示 | HUD 小地图出现敌人标点；3D 视图出现敌人色块 |
| R2.8 | P0 | HUD 必须扩展：显示生命条（基于 `player.hp/max_hp`）与分数（`player.score`） | 渲染出生命条与分数文本，headless 下不报错 |
| R2.9 | P0 | 地图需支持存放「玩家起点、敌人出生点、拾取物位置」（扩展 `WorldMap` 或新增实体层；编辑器也要写这些，见 3.4） | 关卡加载后敌人/拾取物/玩家起点与文件一致 |
| R2.10 | P1 | 敌人 should 有简单动画（如色块闪烁/朝向变化/两帧贴图）以区分静置与移动 | 移动与静置外观可区分 |
| R2.11 | P1 | 玩家死亡（hp ≤ 0）应给出明确反馈（如 HUD 提示「YOU DIED」并可重开） | hp≤0 时 HUD 显示死亡态 |
| R2.12 | P2 | could 增加更多敌人类型（不同速度/血量）或拾取类型（弹药/钥匙），由 `EnemyType`/`PickupType` 枚举扩展 | 枚举可扩展且不影响既有逻辑 |

### 3.3 纹理生成改用 surfarray 提速（需求 3）

| ID | 优先级 | 需求条目 | 验收 |
|---|---|---|---|
| R3.1 | P0 | 必须替换 `render/noise.py` 的 `generate_wall_texture` 逐像素 `set_at` 实现，改为「numpy 向量化噪声 + `pygame.surfarray.blit_array` / `array3d`」生成 | 不再存在显式 `for y in range ... for x in range ... surface.set_at` 循环 |
| R3.2 | P0 | **必须保持确定性**：相同 `seed` 两次生成像素完全一致（不依赖全局 `random` 副作用；沿用架构歧义 #6 约定） | `np.array_equal(surf1, surf2)` 为 True（同 seed），且与旧实现逐像素相等 |
| R3.3 | P0 | 输出仍是 `64×64` Surface、4 种纹理（brick/stone/metal/wood）视觉一致 | `textures` 仍为 4 张；同 seed 下与旧实现像素级相等（或人眼不可分） |
| R3.4 | P0 | 必须提供提速验收：对比旧/新实现生成 4 张纹理的耗时，新实现应明显更快 | 测试断言新实现耗时 < 旧实现（或仅断言功能等价 + 记录相对提速） |
| R3.5 | P2 | could 同步将 `apply_surface_noise` 的逐像素 `get_at/set_at` 也向量化（本增量不在强制范围，仅建议） | 可选；不影响 R3.1–R3.4 |

### 3.4 简易关卡编辑器（需求 4）

| ID | 优先级 | 需求条目 | 验收 |
|---|---|---|---|
| R4.1 | P0 | 必须定义统一地图文件格式（**JSON 为权威格式**，含网格尺寸、cells、玩家起点、敌人列表、拾取物列表；见第 5.3 节） | 提供 schema 与示例文件 |
| R4.2 | P0 | 主游戏启动时必须支持从地图文件加载关卡（替代/扩展现有 `generate_maze`）：如 `python main.py --map maps/level_01.json`；无 `--map` 时沿用 `generate_maze` | 指定 `--map` 后，`GameWorld` 用文件构建网格与实体；缺省仍随机迷宫 |
| R4.3 | P0 | 必须提供**游戏内 GUI 编辑器**：进入编辑模式后可鼠标点格放置/擦除墙、放置玩家起点/敌人/拾取物，并保存到文件、从文件加载 | headless 之外，手动验证编辑→保存→重载闭环 |
| R4.4 | P0 | GUI 编辑器与文本格式**读写同一份地图格式（JSON）**，保证一致性 | 编辑器保存的 JSON 可被主游戏 `--map` 直接加载，反之亦然 |
| R4.5 | P1 | should 提供 ASCII 地图作为人类可读等价/导入导出中间格式：定义 ASCII 字符表（见 5.3）并实现 ASCII ↔ JSON 互转 | `ascii_to_json` / `json_to_ascii` 往返一致（元数据用默认值补全） |
| R4.6 | P1 | should 编辑器提供「撤销（undo）」与「清除/重置」 | 至少支持单步撤销最近一次放置/擦除 |
| R4.7 | P1 | should 编辑器提供工具栏选择当前笔刷（不同墙纹理/玩家/敌人/拾取/橡皮），并实时预览 | 可在墙纹理、实体、橡皮间切换 |
| R4.8 | P2 | could 支持多关卡选择菜单、或导出为多种文件名/目录 | 可选 |

---

## 4. 关键设计决策记录（已与用户确认，不偏离）

| # | 决策 | 说明 | 影响范围 |
|---|---|---|---|
| D1 | **敌人 = 简单追逐 AI** | 进入「直线无墙遮挡 + 距离阈值」感知范围时追踪，复用 `WorldMap` 网格做墙体碰撞，脱离范围停下；含最小生命/伤害模型（碰撞玩家造成伤害，带冷却）。不做寻路 A*、不做射击/远程。 | R2.4、R2.5、R2.7 |
| D2 | **编辑器 = 游戏内 GUI + 文本，二者同格式** | GUI 编辑器与 JSON 文本地图读写同一份格式（JSON 权威，ASCII 为可读中间格式）；主游戏 `--map` 加载该格式。 | R4.1–R4.5 |
| D3 | **拾取物 = 生命（回血）+ 分数（加分）两类** | 仅此两类；玩家生命/分数模型 + HUD 生命条/分数。不引入弹药/钥匙等（留作 P2）。 | R2.3、R2.6、R2.8 |

> 以上决策为硬约束，增量设计不得偏离。

---

## 5. 数据 / 交互模型草案

### 5.1 敌人 `Enemy`（建议 `doom_game/core/entities.py`）

```text
Enemy:
  pos: Vector2            # 浮点网格坐标（同 Player 约定，世界单位=1格）
  angle: float            # 朝向（弧度，用于 sprite 方向/动画，可选）
  hp: float               # 生命值（默认 ENEMY_HP = 30）
  damage: float           # 每次接触对玩家的伤害（默认 ENEMY_DAMAGE = 10）
  speed: float            # 追逐速度（默认 ENEMY_SPEED = 0.06，< 玩家 MOVE_SPEED）
  type: EnemyType         # 枚举，默认 BASIC（P2 可扩展）
  state: "idle" | "chasing"
  alive: bool
  _contact_cd: float      # 接触伤害冷却计时（实现细节）
```

- **存储**：`GameWorld.enemies: List[Enemy]`。
- **感知判定点**：`los_clear(e, player)`（复用 `WorldMap` 射线/网格步进判断无墙遮挡）且 `e.pos.distance_to(player.pos) <= ENEMY_PERCEPTION_RANGE`（默认 6.0）。二者满足 → `state = chasing`。
- **移动**：朝玩家方向移动 `speed`，逐轴做 `WorldMap.is_wall` 碰撞滑动（复用 `GameWorld._move_with_collision` 思路）。
- **与玩家碰撞判定点**：`e.pos.distance_to(player.pos) < ENEMY_CONTACT_DIST`（默认 0.5）→ 施加伤害（受冷却约束）。

### 5.2 拾取物 `Pickup`（建议 `doom_game/core/entities.py`）

```text
PickupType: Enum
  HEALTH = "health"
  SCORE  = "score"

Pickup:
  pos: Vector2
  kind: PickupType
  amount: float          # HEALTH: 回血量（默认 HEALTH_PICKUP_AMOUNT = 25）；SCORE: 加分（默认 SCORE_PICKUP_AMOUNT = 100）
  taken: bool
```

- **存储**：`GameWorld.pickups: List[Pickup]`。
- **碰撞检测**：`p.pos.distance_to(player.pos) < PICKUP_CONTACT_DIST`（默认 0.5）→ 应用效果并 `taken = True`（从渲染/逻辑中移除）。
- **放置来源**：关卡文件 `pickups` 列表（需求 4）；编辑器写入。

### 5.3 地图文件格式（JSON 权威 + ASCII 可读中间格式）

#### JSON Schema（权威，存储全部元数据）

```json
{
  "version": 1,
  "width": 24,
  "height": 24,
  "cells": [[0, 1, 2, 3, 0], [ ... ]],   // cells[gy][gx]；0=空, 1=BRICK, 2=STONE, 3=METAL, 4=WOOD（对应 TextureType 枚举序）
  "player_start": { "x": 1.5, "y": 1.5, "angle": 0.0 },
  "enemies": [ { "x": 5.5, "y": 5.5, "hp": 30, "type": "basic" } ],
  "pickups": [ { "x": 8.5, "y": 8.5, "kind": "health", "amount": 25 } ]
}
```

- 单元格整数 → `TextureType`：0=None(空), 1=BRICK, 2=STONE, 3=METAL, 4=WOOD。
- 坐标 `x/y` 为格中心浮点（如 `gx + 0.5`）。

#### ASCII 字符表（人类可读 / 导入导出中间格式）

| 字符 | 含义 | 映射到 JSON |
|---|---|---|
| ` ` 或 `.` | 空地 | cells=0 |
| `#` | 墙（默认 STONE） | cells=2 |
| `B` | 砖墙 | cells=1 |
| `S` | 石墙 | cells=2 |
| `M` | 金属墙 | cells=3 |
| `W` | 木墙 | cells=4 |
| `P` | 玩家起点 | player_start（取该格中心） |
| `E` | 敌人出生点 | enemies（hp/type 用默认值） |
| `H` | 生命拾取 | pickups{kind:health} |
| `$` | 分数拾取 | pickups{kind:score} |

- ASCII 为单字符/格，无法表达敌人 hp/type、拾取 amount 等元数据 → 导出为 ASCII 时这些字段用配置默认值补全；**JSON 为往返无损的权威格式**。
- **加载链路**：`main.py --map path` → `GameWorld(map_path=...)` → `level_io.load_map(path)`（识别 `.json`/`.txt|.asc`）→ 返回 `LevelData`（网格 + 实体）→ 填充 `world_map.cells`、`player` 起点、`enemies`、`pickups`。
- **保存链路（编辑器）**：编辑器状态 → `level_io.save_map(level_data, path)` → 写 JSON（或导出 ASCII）。

---

## 6. UI / 交互要点

### 6.1 编辑器操作方式（游戏内 GUI）

- **进入/退出**：推荐 `E` 键在主游戏中切换「编辑模式」；编辑模式下 `ESC` 退出编辑器（保留 ESC=退出仅限游玩模式，避免冲突；编辑模式 ESC 可弹「是否保存」或直接退回游玩）。具体由架构师在 `main.py` 事件循环中编排（见待确认 Q4）。
- **放置/擦除**：鼠标左键 = 用当前笔刷放置；右键 = 擦除（置为空地或删除该格实体）。屏幕像素 → 网格 `(gx, gy)` 映射（复用小地图或独立网格视图）。
- **笔刷选择**：屏幕侧边工具栏按钮（鼠标点击切换），或数字键 `1–7` 映射：墙纹理(B/S/M/W)、玩家起点、敌人、生命拾取、分数拾取、橡皮。
- **保存/加载**：`Ctrl+S` 保存到默认/指定 JSON 文件；`Ctrl+O` 从文件加载。编辑器退出后回到游玩（按文件构建的关卡）。
- **预览**：编辑模式实时显示网格、实体标点与玩家起点。

### 6.2 HUD 扩展（游玩模式）

- **生命条**：屏幕底部或左上角绘制矩形血条，`width ∝ player.hp / player.max_hp`，颜色随血量（绿→黄→红）。
- **分数**：HUD 信息面板新增 `Score: {player.score}`（沿用 `render_info` 文本行，或独立高亮显示）。
- **小地图扩展**：在现有 `render_minimap` 上叠加敌人标点（红点）与拾取物标点（绿=health、黄=score）；玩家起点无需额外标记（玩家已在）。
- **死亡态**（P1）：`player.hp <= 0` 时叠加「YOU DIED」提示并可重开（重置关卡）。

---

## 7. 待确认问题（不阻塞工程师，给出推荐默认）

| # | 歧义点 | 推荐默认 | 备注 |
|---|---|---|---|
| Q1 | 敌人伤害/生命/速度数值 | `ENEMY_HP=30`、`ENEMY_DAMAGE=10`、`ENEMY_SPEED=0.06`、`ENEMY_CONTACT_DIST=0.5`、`ENEMY_PERCEPTION_RANGE=6.0` | 落入 `config.py`；数值后续可平衡调整 |
| Q2 | 玩家生命上限与拾取数值 | `PLAYER_MAX_HP=100`、`HEALTH_PICKUP_AMOUNT=25`、`SCORE_PICKUP_AMOUNT=100`、`PICKUP_CONTACT_DIST=0.5` | 同上 |
| Q3 | 地图文件默认路径 | `maps/`（项目根下，现为 `G:\repos\loly\maps`），默认文件名 `level_01.json`；`--map` 缺省时仍走 `generate_maze` | 由 `DEFAULT_MAP_PATH` 常量控制（2026-08-28 起随仓库推导，不再写死） |
| Q4 | GUI 编辑器如何进入/退出 | `E` 切换编辑模式；编辑模式 `ESC` 退回游玩（退出时可选保存）；游玩模式 `ESC` 仍为退出程序 | 需与 `main.py` 现有 ESC=quit 协调，避免误触 |
| Q5 | 实体模块/编辑器模块落点 | 实体 `doom_game/core/entities.py`；关卡 I/O `doom_game/world/level_io.py`；编辑器 `doom_game/editor/level_editor.py`（新建子包） | 最终由架构师定，保持「基础类型只从 core 导入」约定 |
| Q6 | 敌人 3D 渲染形式 | 先用纯色 billboard 色块（贴墙后叠加矩形/圆），后续 P1 再做 sprite 图集/动画 | 最小可用即可 |
| Q7 | surfarray 视觉一致验收 | 旧实现输出 `surf_old`，新实现 `surf_new`，断言 `np.array_equal(array3d(surf_old), array3d(surf_new))` 且新实现耗时更低 | 写进 `tests/test_noise.py` 增量用例 |

---

## 8. 与现有架构的衔接（给架构师的落点提示）

- **不破坏**：DDA 渲染管线、`WorldMap` O(1) 网格、`RenderMode`、音频 headless 安全、主循环 `update(无绘制)/render(不更新)` 契约（规则 #9）均保持不变。
- **新增/扩展点**：
  - `core/entities.py`：新增 `Enemy`、`Pickup`、`PickupType`、`EnemyType`（遵守规则 #1/#6）。
  - `core/player.py`：扩展 `hp/max_hp/score`。
  - `world/level_io.py`：新增 JSON/ASCII 读写（`load_map`/`save_map`/`ascii_to_json`/`json_to_ascii`）。
  - `editor/level_editor.py`：新增游戏内编辑器（处理鼠标/笔刷/保存加载）。
  - `world/game_world.py`：新增 `enemies/pickups` 字段、`update` 内敌人 AI + 拾取 + 伤害逻辑、`render` 内敌人 sprite 叠加、`__init__` 支持 `map_path`。
  - `world/hud.py`：扩展生命条 + 分数 + 小地图实体标点。
  - `render/renderer.py`：新增敌人 sprite/billboard 叠加 pass（墙体之后）。
  - `render/noise.py`：`generate_wall_texture` 改 surfarray 实现（R3）。
  - `config.py`：新增 Q1/Q2/Q3 相关常量与 `DEFAULT_MAP_PATH`。
  - `main.py`：新增 `--map` 参数、`E` 键编辑模式路由、`README` 所述控制说明。
  - `README.md`：新增文档。
- **测试**：`tests/` 现有 headless 框架可直接复用；新增 `test_entities.py`（敌人 AI/拾取）、`test_level_io.py`（JSON/ASCII 往返）、`test_noise.py` 增量（surfarray 等价 + 提速）。`main.py --headless N` 需覆盖新实体渲染路径不崩。

---

> 交付：本增量 PRD 仅描述「新增/变更」，工程师可直接据此做增量设计与实现，无需重读完整 PRD。
