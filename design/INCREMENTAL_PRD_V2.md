# DOOM 风格伪3D 光线投射游戏 — 增量 PRD V2（仅描述新增/变更部分）

> 本文档是 `design/INCREMENTAL_PRD.md`（上一轮增量）的后续增量，只描述本轮 3 项新需求的「新增/变更了什么」，不复述已有功能。
> 读者：架构师（增量设计）、工程师（落地）、QA（验收）。语言：中文。
> 现状基线：209 测试全过；编辑器（GUI + JSON/ASCII）、敌人追逐 AI、拾取物、`--map` 加载、headless 自测均已可用。

---

## 1. 增量产品目标

1. **编辑器可撤销**：编辑器内所有网格/实体编辑操作支持多步撤销（undo），降低误操作成本，让关卡创作可放心试错。
2. **敌人具备远程威胁**：敌人在有视线、有射程、受冷却约束的前提下发射直线投射物对玩家造成伤害，丰富战斗压迫感且不破坏性能与 headless 测试。
3. **多关卡递进闭环**：游戏由「单关沙盒」升级为「多关顺序推进 → 最终胜利」的完整流程，关卡进度在 `GameWorld` / `main.py` 层统一管理。

## 2. 用户故事

1. 作为**关卡设计者**，我在编辑器里误放/误擦了墙或实体时，希望按 `Ctrl+Z` 逐步撤销最近的编辑，而不必手工恢复或重新加载文件。
2. 作为**玩家**，我希望敌人在看到我且在射程内时朝我发射能量弹，被击中会掉血，从而产生「找掩体、拉距离」的玩法；同时敌人不应每帧狂射（有冷却）。
3. 作为**玩家**，我希望完成当前关卡的目标后自动进入下一关，屏幕出现明确的过关提示；通过最后一关后看到胜利画面。
4. 作为**玩家**，我希望死亡后按 `R` 重开**当前关**而不是回到第一关，保留已通关进度。
5. 作为**贡献者/QA**，我希望三项新功能都能在 headless（无显示/无声卡）下被自动化测试覆盖，不破坏现有 209 个测试。

## 3. 增量需求池（P0/P1/P2，附验收标准）

> P0 = 必须交付；P1 = 建议交付；P2 = 可选。验收使用 must/should/could，均可测试。

### 3.1 编辑器撤销（需求 1，编号 U）

| ID | 优先级 | 需求条目 | 验收标准 |
|---|---|---|---|
| U1 | P0 | 编辑器必须维护撤销栈：每次**成功改变状态**的操作（左键放置墙/玩家起点/敌人/拾取、右键或橡皮擦除）执行前压入一份状态快照 | 单测：连续 N 次编辑后栈深 = N（≤上限）；对空白格重复擦除等**无效操作不入栈** |
| U2 | P0 | 必须支持多步撤销：`Ctrl+Z` 弹栈并整体恢复（`world_map.cells` + `player_start` + `enemies` + `pickups` 四者一致回滚） | 单测：放墙→放敌人→擦除，连按 3 次 `Ctrl+Z` 后编辑器状态与初始快照逐字段相等 |
| U3 | P0 | 撤销栈深度必须有上限（推荐 50 步），超限丢弃最旧快照，不得内存无界增长 | 单测：执行 上限+10 次编辑后栈深 == 上限；再全部撤销可回到第 10 次编辑后的状态 |
| U4 | P0 | `Ctrl+O` 加载与 `load_level_data` 整体替换状态时必须**清空撤销栈**（跨文件撤销无意义且易错） | 单测：编辑若干步→load→`Ctrl+Z` 无效果（栈空，状态不变，不崩溃） |
| U5 | P1 | 撤销不可用（栈空）时 should 静默忽略并可选给出一行提示，不得抛异常 | 空栈按 `Ctrl+Z` 无异常 |
| U6 | P1 | 编辑器帮助文本 should 加入 undo 说明（palette 帮助行 + README 操作表同步更新） | 帮助行含 "Ctrl+Z undo" |
| U7 | P2 | could 支持重做 `Ctrl+Y`（redo 栈，新的编辑操作发生时清空 redo 栈） | 撤销后 `Ctrl+Y` 恢复；见待确认 Q2 |

### 3.2 敌人远程攻击（需求 2，编号 A）

| ID | 优先级 | 需求条目 | 验收标准 |
|---|---|---|---|
| A1 | P0 | 必须新增投射物基础类型 `Projectile`（建议落在 `core/entities.py`，遵守「基础类型只在 core 定义一次」规则）：`pos/dir(或 vx,vy)/speed/damage/alive` | 可 `from doom_game.core.entities import Projectile` 导入 |
| A2 | P0 | 敌人开火条件必须同时满足：`state == "chasing"`（即已有 LOS + 感知范围逻辑）、玩家距离 ≤ `ENEMY_ATTACK_RANGE`、攻击冷却就绪；发射方向为发射瞬间指向玩家的**直线**（不追踪） | 单测：玩家在射程内且 LOS 通 → 冷却期内恰好产生 1 枚投射物；LOS 被墙挡 / 超射程 → 0 枚 |
| A3 | P0 | 攻击冷却必须生效（推荐 `ENEMY_ATTACK_COOLDOWN = 1.5s`，实现方式对齐现有 `_contact_cd` 的 dt 递减模式），禁止每帧发射 | 单测：模拟 3 秒（`FRAME_DT` 步进）内发射次数 ≤ ⌈3/冷却⌉ |
| A4 | P0 | 投射物必须逐帧直线飞行；命中判定：与玩家距离 < `PROJECTILE_HIT_DIST` → 扣 `PROJECTILE_DAMAGE` 后消亡；进入墙格（`world_map.is_wall`）→ 消亡；超出最大飞行距离/出界 → 消亡。消亡后从列表移除，不得泄漏 | 单测三例：命中扣血一次且投射物消失；打墙消失且玩家血量不变；飞满射程自然消失 |
| A5 | P0 | 投射物必须可见：3D 视图沿用现有 billboard 叠加通道渲染为小色块（建议亮橙/青色，区别于敌红/血绿/分黄），小地图叠加同色小点 | headless 自测注入「敌人开火中」场景渲染一帧不崩；肉眼可见弹体 |
| A6 | P0 | 数值必须集中在 `config.py`：`ENEMY_ATTACK_RANGE`（建议 5.0，≤ 感知范围）、`ENEMY_ATTACK_COOLDOWN`（1.5）、`PROJECTILE_SPEED`（建议 0.15/帧，> ENEMY_SPEED）、`PROJECTILE_DAMAGE`（建议 8，< 接触伤害 10）、`PROJECTILE_HIT_DIST`（0.4）、`PROJECTILE_MAX_DIST`（8.0） | 常量存在且被引用；改常量即可调平衡，无魔法数字散落 |
| A7 | P1 | 关卡 JSON 的 `enemies[]` should 可选扩展远程参数（如 `attack_range`/`attack_cooldown`，缺省用 config），保持旧关卡文件**无需修改即可加载** | `maps/level_01.json` 原样加载通过；带新字段的关卡按字段生效 |
| A8 | P2 | could 引入 `EnemyType.RANGED`（远程型与近战型区分：远程型保持距离射击）；本轮默认所有 BASIC 敌人均具备「接触 + 远程」双伤害 | 见待确认 Q3 |

### 3.3 多关卡递进（需求 3，编号 L）

| ID | 优先级 | 需求条目 | 验收标准 |
|---|---|---|---|
| L1 | P0 | 必须定义关卡序列来源：`config.py` 新增 `LEVEL_SEQUENCE = ["maps/level_01.json", "maps/level_02.json", "maps/level_03.json"]`（显式清单，不做目录扫描），并**新增至少 2 个新关卡文件**（level_02/03，难度递增） | 常量存在；3 个关卡文件均可被 `load_map` 解析且 `--map` 单独加载可玩 |
| L2 | P0 | `GameWorld` 必须持有并管理关卡进度：`level_index` 属性 + 通关判定 + `advance_level()`（加载下一关：重建网格/实体，玩家移到新关起点）。进度状态**只在 GameWorld 维护**，`main.py` 只做事件/流程路由 | 单测：满足通关条件后 `level_index` +1 且世界内容 == 下一关文件内容 |
| L3 | P0 | 通关判定必须实现（默认方案：**消灭当前关全部敌人**，即 `all(not e.alive)` 且敌人列表非空；无敌人关卡视为立即可过——见待确认 Q1，若用户改为「到达出口」则以 Q1 结论为准） | 单测：将所有敌人 `alive=False` 后一帧内触发进入下一关 |
| L4 | P0 | 因通关判定默认依赖击杀，玩家必须获得**最小攻击手段**（现有 `Enemy.take_damage` 已存在但无人调用）：推荐「按空格/鼠标左键沿视线方向即时射线攻击（hitscan），有 LOS、限射程、带冷却」 | 单测：敌人在准星方向射程内 → 攻击后 `enemy.hp` 下降、归零时 `alive=False`；隔墙攻击无效 |
| L5 | P0 | 最后一关通关必须进入**胜利态**：HUD 全屏 "YOU WIN"（对齐现有 `render_death` 风格），停止敌人/投射物更新，`R` 可从第一关重开 | headless 单测：胜利态渲染一帧不崩；胜利后实体不再更新 |
| L6 | P0 | `main.py` 的 `R` 重开语义必须变为**重开当前关**（保留 `level_index`）；`--map <path>` 保持向后兼容 = 单关模式（不进多关流程，通关即胜利或不判定——见待确认 Q4） | 手动/单测：第 2 关死亡按 R 仍在第 2 关；`--map maps/level_01.json --headless 20` 返回码 0 |
| L7 | P0 | 关卡切换必须有明确提示：进入新关时 HUD 显示 `LEVEL n/total`（常驻或数秒），切换瞬间显示 "LEVEL CLEAR" 过场文字（可简化为 1–2 秒文字帧，headless 下跳过等待） | 截图/自测可见文字；headless 不因过场阻塞 |
| L8 | P1 | 跨关状态策略 should 明确：`score` 累计带入下一关；`hp` 带入下一关但不低于下限（或回满——见待确认 Q5）；死亡重开当前关时 hp 回满、score 回退到本关进入时的值 | 单测按 Q5 结论断言 |
| L9 | P1 | 编辑器 should 与多关兼容：游玩第 n 关按 `E` 编辑的即当前关文件（现有 `map_path` 传递机制沿用，指向 `LEVEL_SEQUENCE[level_index]`），`ESC` 返回按编辑结果重建当前关 | 手动验证编辑→返回闭环仍成立 |
| L10 | P2 | could 提供关卡选择/跳关调试参数（如 `--level 2`）与通关计时 | 可选 |

## 4. 与现有架构的交互点（基于真实代码）

> 原则不变：`update` 只改状态 / `render` 只绘制；基础类型只在 `core/` 定义一次；JSON 权威格式向后兼容。

| 文件 | 变更类型 | 关键改动点 |
|---|---|---|
| `doom_game/editor/level_editor.py` | 修改 | 新增 `self._undo_stack`（快照列表）与 `_snapshot()` / `undo()`；在 `_apply_brush` / `_erase` 生效前压栈（`_remove_entity_at` 由二者间接覆盖，不单独压栈）；`_handle_key` 增加 `ctrl and K_z` 分支（对齐现有 `Ctrl+S/O` 写法）；`load_level_data()` 末尾清空撤销栈；`_render_palette` 帮助行追加 undo 说明 |
| `doom_game/core/entities.py` | 修改 | 新增 `Projectile` 类（含 `update(world_map, player, dt) -> damage` 或等价接口）；`Enemy` 新增 `_attack_cd` 字段与开火逻辑：`Enemy.update` 现返回接触伤害 float，需扩展为**同时产出新投射物**（建议返回值改为 `(damage, new_projectile|None)` 或新增 `try_fire(player, world_map) -> Projectile|None` 由 GameWorld 调用，二选一由架构师定）；复用已有 `_can_see`（`world_map.line_of_sight`）做开火 LOS 判定 |
| `doom_game/world/game_world.py` | 修改 | 新增 `self.projectiles: list`；`_update_entities(dt)` 内：收集敌人开火产物、逐帧推进投射物、命中扣 `player.hp`、打墙/超程移除；新增 `level_index` / `victory` 状态、`_check_level_complete()`、`advance_level()`（内部走既有 `_load_map_file` / `load_level_data`，注意 `load_level_data` 现在会把 hp/score 重置——需按 L8 结论调整为可保留）；`render()` 的 `render_sprites` 调用传入 projectiles；玩家攻击（L4）入口：`update(keys)` 读攻击键或由 `main.py` 事件转发（建议 KEYDOWN 事件转发，避免按住连发） |
| `doom_game/render/renderer.py` | 修改 | `render_sprites(player, world_map, enemies, pickups)` 签名扩展支持投射物（新增参数或新增 `render_projectiles`），沿用现有 billboard 色块叠加路径 |
| `doom_game/world/hud.py` | 修改 | 小地图叠加投射物点；新增 `LEVEL n/total` 文本、"LEVEL CLEAR" 过场与 "YOU WIN" 胜利覆盖层（对齐现有 `render_death` 实现风格） |
| `doom_game/config.py` | 修改 | 新增 A6 全部投射物/攻击常量 + `LEVEL_SEQUENCE` + 玩家攻击常量（`PLAYER_ATTACK_DAMAGE`/`PLAYER_ATTACK_RANGE`/`PLAYER_ATTACK_COOLDOWN`）+ 撤销栈深度 `EDITOR_UNDO_DEPTH = 50` |
| `main.py` | 修改 | 主循环：胜利态/过关提示的流程路由；`R` 重开改为传入当前关路径（现逻辑复用 `game.map_path`，需改为按 `level_index` 取 `LEVEL_SEQUENCE`）；玩家攻击键事件转发；`--map` 保持单关兼容；`_headless_validate` 增补投射物场景渲染一帧 |
| `doom_game/world/level_io.py` | 基本不动 | JSON 格式向后兼容（A7 可选新字段走 `dict.get` 默认值，`build_enemies` 增读可选字段即可）；不改 ASCII 字符表 |
| `maps/level_02.json`、`maps/level_03.json` | 新增 | 难度递增关卡（敌人更多/布局更复杂） |
| `README.md` | 修改 | 操作表补 `Ctrl+Z`、攻击键；特性/FAQ 补远程敌人与多关流程 |
| `tests/` | 新增 | `test_editor_undo.py`、`test_projectiles.py`、`test_level_progression.py`；现有 209 测试必须保持全过 |

**明确不改**：DDA 渲染管线、`WorldMap` 网格与 `line_of_sight`、音频子系统、ASCII 字符表、`LevelData` 既有字段语义。

## 5. UI / 交互设计要点

### 5.1 编辑器撤销
- **快捷键**：`Ctrl+Z`（与现有 `Ctrl+S/O` 一致，不新增工具栏按钮，保持编辑器极简）。
- **粒度**：一次鼠标点击 = 一步（一次左键放置或一次右键/橡皮擦除为一个撤销单元）。
- **栈深度**：50 步（`EDITOR_UNDO_DEPTH`），超限丢最旧。
- **快照内容**：`cells` 深拷贝 + `player_start` + `enemies` + `pickups`（当前地图 24×24 量级，整体快照成本可忽略，无需做增量 diff）。
- **反馈**：撤销成功后可在帮助区短暂显示 `undo (n left)`；空栈时静默。

### 5.2 敌人远程攻击
- **弹体视觉**：3D 视图小号亮色 billboard（建议橙色，直径约敌人色块 1/3）；小地图同色 2px 点。
- **节奏**：冷却 1.5s、弹速明显快于敌人移动但玩家可侧移躲避（strafe 有价值）。
- **反馈**：玩家被弹体命中时沿用现有掉血表现（HUD 血条变化）；P1 可加全屏红闪一帧。

### 5.3 多关递进
- **常驻提示**：HUD 信息面板加 `LEVEL n/total`。
- **过关**：达成条件瞬间中央大字 "LEVEL CLEAR"（约 1.5s 或按任意键跳过；headless 不等待），随后自动加载下一关。
- **胜利**：末关通关显示全屏 "YOU WIN — press R to restart"（风格对齐现有 YOU DIED 覆盖层）。
- **死亡**：沿用 YOU DIED 覆盖层，`R` = 重开当前关。

## 6. 待确认问题（需主理人/用户拍板；均给出推荐默认，不阻塞架构设计）

| # | 问题 | 选项 | 推荐默认 | 影响 |
|---|---|---|---|---|
| Q1 | **通关判定条件**是什么？ | a) 清空所有敌人；b) 到达出口格；c) 二者结合 | **a) 清空所有敌人**（无需扩展地图格式/ASCII 字符表；但**连带要求 L4 玩家最小攻击**——现有代码玩家没有任何攻击手段，`Enemy.take_damage` 从未被调用。若选 b 则无需玩家攻击，但需新增出口格类型并动 `level_io`/编辑器笔刷/ASCII 表，改动面更大） | L3、L4、地图格式 |
| Q2 | 撤销是否要配套**重做（redo）**？ | 要 / 不要 | **本轮不要**（P2 预留 `Ctrl+Y`；undo 已覆盖误操作主场景，redo 使状态机复杂一倍） | U7 |
| Q3 | 远程弹是**直线弹还是追踪弹**？所有敌人都会远程吗？ | 直线/追踪；全员/仅新类型 | **直线弹 + 现有 BASIC 全员具备**（追踪弹难躲挫败感强；新增 RANGED 类型留 P2） | A2、A8 |
| Q4 | `--map` 单关模式下的通关行为？ | a) 达成条件即 YOU WIN；b) 不判定通关（纯沙盒） | **a) 达成条件即 YOU WIN**（语义一致，测试也更好写） | L6 |
| Q5 | 过关后 **hp/score 是否带入下一关**？ | hp 带入 / 回满；score 累计 / 清零 | **score 累计带入；hp 带入但进新关时至少回到 50%**（保留资源管理压力又不至于卡关） | L8 |
| Q6 | 玩家攻击的按键与形式（若 Q1 选 a）？ | 空格/鼠标左键；hitscan/发射弹体 | **空格键 + hitscan 即时射线**（不引入玩家弹体，实现与测试最简；鼠标左键留给未来） | L4 |
| Q7 | "LEVEL CLEAR" 过场时长与跳过方式 | 固定 1.5s / 按键跳过 / 二者 | **固定 1.5s，任意键可跳过；headless 直接跳过** | L7 |

---

> 交付说明：本 PRD 仅覆盖三项增量的「变更部分」；数值均为推荐初值，集中于 `config.py` 便于平衡调整。架构师可在不违背第 4 节交互点与第 6 节已拍板结论的前提下细化接口形态（如 `Enemy.update` 返回值 vs `try_fire` 二选一）。
