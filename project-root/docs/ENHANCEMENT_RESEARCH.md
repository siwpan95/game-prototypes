# 诡秘之主 · 序列途径模拟系统 —— 增强调研报告

> 调研日期：2026-08-14
> 方法：联网检索（原著设定科普 / 官方手游攻略 / 现代文字模拟游戏设计范式）＋ 本地代码核对
> 目的：在现有 v2.1（Canvas Edition）架构基础上，找出可落地的增强方向，按收益/成本排序

---

## 0. 一句话结论

当前项目的**规则引擎已经相当完整**（22 途径、扮演消化、锚、污染失控、途径切换、性别转换、唯一性/序列1 争夺、旧日晋升、封印物映射），但**「养成循环」和「可重玩性」是明显短板**：

- 魔药配方/材料收集完全缺失（晋升是「一键自动消化+自动仪式通过」）；
- 污染是离散 0–4 等级、无连续理智值（SAN）、无恢复机制；
- 扮演消化是「动作清单打勾即 100%」，没有贴合度/质量维度；
- 事件系统只有 5 条硬编码的「扣污染」事件，无叙事、无选择、无分支；
- 没有任何存档/读档、阵营社交、AI 对手、成就图鉴。

官方手游与同类文字模拟游戏（千世书、BitLife、本科生模拟器、LOTM Craft）都把**「扮演即管理 SAN + 收集材料酿魔药 + 事件驱动叙事 + 存档/多结局」**作为核心循环。这正是本项目最值得补齐的方向。

---

## 1. 当前能力盘点（已实现，且设计良好）

| 能力 | 实现位置 | 说明 |
|---|---|---|
| 22 条途径 · 序列 9→0 | `pathways_data.py` + `sequences.py`（`Sequence` 数据驱动） | 单文件配置即可扩展，无需为每序列写类 |
| 扮演法 / 消化度 | `BaseSequence.perform_action` / `digestion_ratio` / `digested` | 已建模「完成本序列全部 required_actions → 消化」 |
| 锚（人性锚定） | `anchor.py`（`Anchor.required_for_level`） | 高序列晋升强制校验锚强度 |
| 污染 / 失控 | `pollution.py`（`PollutionLevel` 枚举 + `PollutionManager` + `PollutionSource` 来源追踪） | 已有来源分类与等级跃迁日志 |
| 仪式 | `pathways_data` 各序列 `ritual` 字段 | 数据齐全，**但控制器里 `_do_ascend` 直接 `ritual_check = lambda: True` 跳过** |
| 途径切换 / 相邻互换 | `pathway_groups.py`（`PathwaySwitchValidator`）+ `ascension.switch_pathway` | 同组序列3+ 互换规则已落地 |
| 性别转换 | `will_gender_change` / `get_gender_change_message` | 魔女/红祭司/母亲/月亮等已处理 |
| 唯一性 / 序列1 争夺 | `uniqueness.py` + `gui/controllers.py`（`_do_collect_*`） | GUI 已接入「权柄收集」面板 |
| 旧日晋升 | `promote_to_old_one` + `_do_promote_old_one` | 聚合途径组唯一性+序列1 |
| 封印物等级映射 | `sealed_artifact_level` | 序列↔封印物对应 |
| GUI（Canvas 自绘） | `gui/` 包，`draw_*(canvas, state, callbacks)` 自由函数 | **完全可独立单测**（已 64 项测试通过） |
| 三视图 | 角色视图 / 途径全景 / 权柄体系 | 左栏途径列表联动 |

**架构优势**：面板已拆成无 `self` 的自由函数，GUIState 中介 + 控制器分离，事件日志 `add_log`/`draw_log` 已拆分。这意味着**新增系统（库存、事件、存档）都可以不破坏现有测试地接入**。

---

## 2. 联网调研核心发现

### 2.1 原著设定（科普/百科一致结论）
- **晋升三要素**：魔药（对应序列非凡材料调配）+ 扮演（按序列名行为模式固化认知、消化污染）+ 锚（情感纽带/执念，防止被权柄同化）。三者缺一 → 失控或死亡。
- **污染与代价**：服食魔药即开始承受精神污染；序列越高污染越深，**人性本身成为最脆弱的锚点**；唯一性争夺会引发「途径冲突」导致全途径集体失控。
- **扮演法精髓**：序列名不仅是能力，更是「工作」——占卜家要真的去占卜，小丑要外表松弛内心冷静。**越贴合身份，消化效率越高**。
- **相邻途径可互换，跨途径晋升风险极高**。

### 2.2 官方手游（阅文正版授权，灰雾测试）
- **核心循环 = 扮演法 + 魔药晋升**，彻底区别于传统 MMO 的刷经验升级。
- **魔药材料是晋升核心资源**：通过主线/副本/世界探索/阵营任务/玩家交易获取；配方各途径不同。
- **SAN 值管理是底层逻辑**：每次用非凡能力、服魔药、接触诡异都降 SAN；低于阈值出现幻觉/低语，归零即失控，成长进度清零。教堂/安全屋/旅馆缓慢回 SAN，**镇定剂/圣水**快速回少量。
- **扮演分主动/被动**：主动（占卜家摆摊算命）、被动（剧情/支线里做符合身份的选择）；**敷衍扮演（占卜家不占卜直接动手）只得极少消化甚至为零**。
- **消化归零重置**：晋升成功后消化度清零，需重新扮演积累才能准备下一次晋升。

### 2.3 现代文字模拟游戏设计范式（千世书 / BitLife / 本科生模拟器 / LOTM Craft）
- **数据驱动事件池**：随机事件带条件筛选 + 分支选项 + 数值结算；选项不预告加减，下一段才揭晓增减（命运无常）。
- **连续型核心属性**：SAN/理智/精力等连续值，归零即失败结局；数值落入命名状态（清醒/动摇/濒临崩溃）作为硬叙事指令。
- **存档/读档 + 多槽位 + 多结局图鉴**：重玩价值来自「不同选择→不同结局」与「成就收集」。
- **阵营/NPC/社交**：好感度被动影响行动力与 SAN；创作者工具自制剧本/NPC。
- **AI 对手 / 多人协作**：LOTM Craft 让玩家在 22 途径中互相竞争权柄。

---

## 3. 差距分析（Gap Table）

| 维度 | 原著/参考标杆 | 当前项目 | 差距等级 |
|---|---|---|---|
| 魔药材料/配方 | 材料收集→酿造→服食，配方各途径不同 | `pathways_data` **无 materials 字段**；GUI 晋升直接 `ascend()` 跳过材料 | 🔴 高 |
| 理智管理 | 连续 SAN 值，阈值/幻觉/失控，安全区恢复，镇定剂 | 离散 `PollutionLevel` 0–4，无连续值、无恢复、无道具 | 🔴 高 |
| 扮演质量 | 主动/被动、贴合度加权、敷衍得 0 消化 | 动作清单打勾即 100%，无质量维度 | 🟠 中 |
| 事件系统 | 数据驱动、叙事+选择+分支效果 | 5 条硬编码「扣污染」事件，无叙事无选项 | 🔴 高 |
| 存档/读档 | 多槽位 + 本地持久化 | 完全无持久化，重启即丢 | 🟠 中 |
| 阵营/社交 | 塔罗会/教会/秘密结社、声望、NPC 好感 | 无 | 🟡 低 |
| AI 对手 | 竞争唯一性/序列1、PvP | 争夺仅抽象为「击败未知对手」 | 🟡 低 |
| 能力系统 | 能力带效果，参与战斗/探索/事件结算 | `abilities` 仅是字符串列表 | 🟠 中 |
| 成就/图鉴 | 成就系统 + 结局图鉴 + 多结局 | 无 | 🟡 低 |
| 仪式 | 序列5+ 需仪式，带入叙事 | 数据有，但 `ritual_check=lambda:True` 直接跳过 | 🟠 中 |
| 沉浸包装 | 灰雾之上、能力风味文本、考据 tooltip | 暗色神秘主题已就位，缺叙事层 | 🟡 低 |

---

## 4. 增强路线图（按优先级）

### 🔴 P0 —— 核心循环补全（投入小、回报最大）

> **状态（2026-08-14）：✅ 路线图已全部落地（P0 E1/E2/E3 + P1 E4–E7 + P2 E8–E11）。** 验证：`tests/test_panels_suite.py` → PASS=75（含面板+控制器+核心逻辑，含 P2 全部新面板）；纯逻辑 + `tests/test_all.py` 基线 PASS=42（仅 3 条 tkinter 环境缺失用例 FAIL，非代码问题）；`main.py --demo journey` 完整养成循环 demo 跑通且存读档往返断言通过。

#### E1. 魔药配方与材料收集系统
- **动机**：这是「扮演法+魔药晋升」这一核心循环的**另一半**，当前完全缺失（参考 2.2）。
- **改动点**：
  1. `pathways_data.py`：为每序列补 `materials`（主材料+辅助材料列表）字段；
  2. 新增 `inventory.py`（`Inventory`：材料持有、配方匹配）；
  3. `gui/panels/` 新增 `brewing_panel.py`（`draw_brewing_panel(canvas, state, callbacks)`）——展示当前序列所需材料、已收集/未收集、一键/逐步酿造；
  4. `gui/controllers.py`：`_do_ascend` 改为**前置校验材料齐备**；`_do_collect_material` 从事件/探索获取材料。
- **影响**：晋升从「按钮」变成「资源经营」，直接对齐原著与官方手游。
- **状态**：✅ 已落地。`pathways_data.POTION_MATERIALS`(22 途径主题池)+`get_potion_formula`；新增 `inventory.py`(`Inventory`)；`gui/panels/brewing_panel.py`(`draw_brewing_panel`)；`controllers._do_ascend` 做材料前置校验、`_do_gather_materials` 模拟探索搜集；`action_panel` 内嵌酿造段。

#### E2. 连续 SAN / 理智值管理
- **动机**：SAN 是「扮演对抗污染」的底层逻辑（参考 2.2、2.3）。
- **改动点**：
  1. `pollution.py`：保留 `PollutionManager` 的连续 `_points`，新增 `san` 连续值（0–100）与阈值（清醒/低语/幻觉/失控/神殒）；`accumulate` 涨污染、`recover` 降污染；
  2. 新增「安全区恢复」与「镇定剂/圣水」道具恢复接口；
  3. `gui/panels/character_view.py` 的 `draw_gauges` 改画连续 SAN 条（现有仪表盘基础设施可复用）；
  4. `gui/controllers.py` `_do_random_event` 改为按来源对 SAN 结算。
- **影响**：把「污染」从静态标签变成可经营资源，失控真正有张力。
- **状态**：✅ 已落地。`pollution.PollutionManager` 新增连续 `san`(0–100，=100−points×20) 与 `san_status()`；阈值表与离散等级 `label_cn` 严格对齐（清醒/低语/幻觉/失控/神殒）。`accumulate/recover` 同步更新；旧 API(`level/is_lost/try_purify/.value/.name/.label_cn/report`)全兼容。`draw_gauges` 改画连续 SAN 条。`role_playing.loop` 改用 `accumulate` 并仍返回 `level` 枚举（测试契约保持）。

#### E3. 数据驱动事件系统
- **动机**：可重玩性的核心（参考 2.3）。当前 `_do_random_event` 只有 5 条硬编码扣污染事件。
- **改动点**：
  1. 新增 `events.py` + `data/events.json`：每条事件含 `id / condition / narrative / choices[{text, effects}]`；
  2. `effects` 统一作用到 SAN/锚/消化/材料/金钱；
  3. `gui/controllers.py` `_do_random_event` 改为从池中抽取满足条件的事件 → 弹窗（tkinter `messagebox` 或自绘选择面板）→ 结算；
  4. 事件可来自「探索/战斗/接触封印物」等不同触发源。
- **影响**：从「演示脚本」变成「能反复玩下去的模拟」。
- **状态**：✅ 已落地。新增 `events.py`(纯逻辑：`pick_event`/`resolve_choice`，不依赖 tkinter)+ `data/events.json`(8 条主题事件，含 `min_level/max_level` 条件筛选)；`gui/panels/event_panel.py`(`draw_event_overlay`)自绘选择浮层；`controllers._do_random_event` 优先抽数据驱动事件并置 `pending_event`，`_do_event_choice` 结算后清除；`app.refresh_all` 在 `pending_event` 时切到浮层。`effects` 已支持 `san/anchor/digestion/materials/needed_materials/log` 且与 E1 材料、E2 SAN 联动。

### 🟠 P1 —— 系统深度与可重玩

#### E4. 存档 / 读档（GameSession 序列化）✅ 已落地
- **动机**：现代文字模拟标配（参考 2.3）；当前重启即丢全部进度。
- **改动点**：抽取 `GameSession` 持有 `character + anchor + pollution(SAN) + inventory + event_log + view`，`to_dict()/from_dict()`；GUI 工具栏加「存档/读档」按钮，多槽位 JSON 落盘（`~/.workbuddy/...` 或项目 `saves/`）。
- **依赖**：与 E2（SAN）、E1（库存）协同，建议在它们之后做。
- **落地记录（2026-08-14）**：
  - `save_load.py` 新增 `GameSession`（from_state / apply_to_state / to_dict / save / load）+ `slot_path`（防路径穿越）/ `list_slots` / `SAVES_DIR`；纯逻辑，无 tkinter。
  - `pollution.py` / `anchor.py` / `sequences.py` 各加 `to_dict()` 实例方法 + `from_dict(cls, d)` 类方法；`Sequence.from_dict` 先 `make_sequence` 重建静态数据再叠加污染/锚/消化/能力。
  - `gui/state.py` 加 `self.factions`（E7 占位）；`gui/controllers.py` 加 `_do_save` / `_do_load`（try/except + 日志）；`gui/app.py` 加「存档/读档」工具栏按钮与 `do_save`/`do_load` 回调。
  - 单测：`tests/test_e4_save_load.py`（4 项纯逻辑全绿）+ `tests/test_controller_e4.py`（2 项控制器层，需 tkinter，已并入面板套件）。面板套件 PASS=34、核心 PASS=4，无回归。

#### E5. 扮演质量维度 ✅ 已落地
- **动机**：敷衍扮演只得零消化（参考 2.2）。
- **改动点**：`BaseSequence` 消化改为**按动作贴合度加权累积**（主动扮演满分、被动剧情选择半分、背离身份扣分）；允许重复扮演渐进消化；`_do_action` 增加「情境」参数区分主动/被动。
- **落地记录（2026-08-14）**：
  - `sequences.py`：`action_weight` 字典 + `perform_action(action, quality)`（active=+1.0 / passive=+0.5 / divergent=-0.5）+ `add_digestion(action, weight)`；`digestion_ratio` 改为所需行为的加权均值，`digested` 据此判定；`to_dict`/`from_dict` 序列化 `action_weight`。
  - `events.py`：`resolve_choice` 的消化分支改走 `ch.add_digestion(a, 0.5)`（被动扮演），修复了此前因 `digestion_ratio` 改读 `action_weight` 而 `digestion_actions` 直写导致比例恒为 0 的回归。
  - `gui/panels/action_panel.py`：每个扮演行为渲染「主动/被动/背离」质量按钮（E5），主按钮=主动，另列被动/背离小标签。
  - `gui/controllers.py`：`_do_action(action, quality="active")` 接受质量参数并在日志标注（主动/被动/背离）+ 实时消化度。
  - 单测：`tests/test_e5_quality.py`（3 项纯逻辑）+ `tests/test_controller_e5.py`（2 项控制器，需 tkinter）+ `test_panel_action.py` 新增 `panel_action_e5_quality_pills`。面板套件 PASS=40、纯逻辑 PASS=3，无回归。

#### E6. 能力效果化 ✅ 已落地
- **动机**：能力当前仅是字符串（参考 1 表）。
- **改动点**：`sequences.abilities` 升级为带 `effect` 的结构；在事件结算中可被调用（如「占卜」→ 揭示线索、「观众」→ 读情绪解锁选项）。让不同途径在事件中真正有差异。
- **落地记录（2026-08-14）**：
  - `abilities.py` 新增：ABILITY_EFFECTS 注册表（占卜/观众/阅读者/神秘学家/考古学家/聆听，含 san_relief / bonus_material / clue / desc）+ `apply_ability_effects(character, state, logs)` + `effective_abilities` 辅助。
  - `events.py`：`resolve_choice` 末尾调用 `apply_ability_effects`，让角色能力在事件中产生 SAN 安抚 / 额外材料 / 隐秘线索。
  - `gui/panels/character_view.py`：角色卡片新增「能力效果」区块，列出具效果能力的风味描述。
  - 单测：`tests/test_e6_abilities.py`（5 项纯逻辑，含「未注册能力零副作用」回归保护）+ `test_panel_character.py` 新增 `panel_character_e6_ability_effects`。面板套件 PASS=46、纯逻辑 PASS=5，无回归。

#### E7. 组织 / 阵营 / 塔罗会社交层 ✅ 已落地
- **动机**：塔罗会/教会是原著核心势力（参考 2.1、2.2）。
- **改动点**：新增 `factions.py`（声望值）+ 第四视图 `draw_factions_view`；塔罗会作为资源/情报交换中枢（与 E1 材料、E3 事件联动）。
- **落地记录（2026-08-14）**：
  - `factions.py` 新增：FACTIONS（塔罗会/教会/隐秘组织 元信息与配色）+ ACTIONS（tarot_exchange / church_purify / secret_anchor，消耗声望换取材料/SAN/锚）+ `FactionSystem`（reputation/earn/can_afford/do_action 包装）+ `grant_reputation`（供事件提升声望）。`state.factions` 仍为纯 dict，随 GameSession 序列化（与 E4 兼容）。
  - `events.py`：`resolve_choice` 支持可选 `faction` 效果字段（事件结算提升阵营声望）；`data/events.json` 的「灰雾之上的聚会」「教堂的庇护」已埋入 tarot/church 声望奖励。
  - `gui/panels/factions_view.py`：新增第四视图，渲染三大阵营声望与社交动作按钮，绑定 `do_faction_action(faction, action)`。
  - `gui/app.py`：工具栏新增「阵营社交」按钮；`switch_view` / `refresh_all` 增加 `factions` 分支；`_draw_factions_view` 薄包装；`_callbacks` 注册 `do_faction_action`。
  - `gui/controllers.py`：新增 `_do_faction_action(faction_key, action_key)`（try/except + 日志 + 刷新）。
  - 单测：`tests/test_e7_factions.py`（6 项纯逻辑）+ `tests/test_panel_factions.py`（2 项面板）+ `tests/test_controller_e7.py`（2 项控制器，需 tkinter）。面板套件 PASS=56、纯逻辑 PASS=6，无回归。
  - **P1 路线全部完成**：E4 存档/读档、E5 扮演质量维度、E6 能力效果化、E7 阵营/塔罗会社交均已落地并通过测试。

### 🟡 P2 —— 长线 / 沉浸

#### E8. AI 对手非凡者 ✅ 已落地
- **动机**：让「权柄争夺」变成有实际对手的博弈，而非抽象「击败未知对手」（参考 1.1 的「竞争唯一性/序列1」）。
- **改动点**：新增 `rivals.py`（`Rival`/`RivalSystem`）；rival 在其它途径上随 tick 推进、消化、晋升、争夺唯一性/序列1 槽位；复用 `uniqueness.py` 的全局 owner 模型（玩家「击败并夺取」逻辑不变）。
- **落地记录（2026-08-14）**：
  - `rivals.py` 新增：`Rival(name, pathway_key, start_level=9, gender=None, aggression=1.0)`，`advance_one_tick`（按 aggression 步执行 `perform_action`、消化后晋升、`LEVEL<=1` 时争抢权柄），`_try_claim_authority`（仅当 owner is None 时绑定唯一性/序列1）；`RivalSystem(rivals=None, seed=None, tick_count=0)`、`add_rival`/`tick`/`status`/`count` 与 `to_dict`/`from_dict`（反序列化时重跑 `_try_claim_authority` 以重新占据空闲槽位，不抢占玩家）。`Random` 不入库（加载时重建）。
  - `gui/panels/rivals_view.py`：新增 `draw_rivals_view`（渲染对手列表并绑定 `do_rival_tick` / `do_add_rival`）。
  - `gui/app.py`：工具栏新增「对手」按钮；`switch_view`/`refresh_all` 增加 `rivals` 分支；`_callbacks` 注册 `do_rival_tick`/`do_add_rival`。
  - `gui/controllers.py`：新增 `_ensure_rival_system` / `_do_rival_tick`（首次 tick 自动建一个对手）/ `_do_add_rival` / `_warn_rival_contention`（权柄被对手占走时提示玩家去「击败并夺取」）。
  - `save_load.py`：`GameSession` 新增 `rival_system` 字段并随存档序列化。
  - 单测：`tests/test_e8_rivals.py`（5 项纯逻辑）+ `tests/test_controller_e8.py`（2 项控制器）+ `tests/test_panel_rivals.py`（2 项面板）。面板套件 PASS=64、纯逻辑 PASS=5，无回归。

#### E9. 成就 / 图鉴 / 多结局 ✅ 已落地
- **动机**：重玩价值来自「不同选择→不同结局」与「成就收集」（参考 1.2 的「多结局图鉴」）。
- **改动点**：新增 `achievements.py`（纯逻辑：成就/图鉴/结局）；10 项成就 + 序列与能力图鉴进度 + 按路线而异的多结局判定。
- **落地记录（2026-08-14）**：
  - `achievements.py` 新增：`ACHIEVEMENTS` 注册表（10 项：first_step/first_ascend/true_god/old_one/first_loss/first_event/full_digest/faction_friend/collector/rivals_rise）；`AchievementSystem`（evaluate/is_unlocked/progress/to_dict/from_dict）；`CodexSystem`（see_* + sequence_progress）；`record_codex(state)`、`evaluate_achievements(state)`（返回展示名）、`ENDINGS` 与 `evaluate_ending(state)`（loss/old_one/true_god/high/wanderer 五结局）。
  - `gui/panels/codex_view.py`：新增 `draw_codex_view`（渲染成就+进度、图鉴进度、当前结局，只读）。
  - `gui/state.py`：`achievements`/`codex`/`seen_events` 字段注入。
  - `gui/app.py`：工具栏新增「图鉴」按钮；`switch_view`/`refresh_all` 增加 `codex` 分支；每次刷新调用 `record_codex` + `evaluate_achievements` 并在解锁时打 🏆 日志；`_callbacks` 无需新键（图鉴只读）。
  - `save_load.py`：`GameSession` 新增 `achievements`/`codex` 并随存档序列化。
  - 单测：`tests/test_e9_achievements.py`（6 项纯逻辑）+ `tests/test_panel_codex.py`（2 项面板）。面板套件 PASS=68、纯逻辑 PASS=6，无回归。

#### E10. 主题沉浸包装 ✅ 已落地
- **动机**：暗色神秘主题已就位，但缺叙事层（参考 2.2 的「考据 tooltip / 灰雾之上」）。
- **改动点**：新增 `lore.py`（22 途径考据 + 组织背景）；角色卡内嵌序列考据；新增「灰雾之上·源堡」叙事与可选环境音效。
- **落地记录（2026-08-14）**：
  - `lore.py` 新增：`PATHWAY_LORE`（22 条途径考据）+ `GROUP_LORE` + `pathway_lore(pathway_key)` / `group_lore(pathway_key)`（纯数据，不依赖 tkinter）。
  - `gui/panels/character_view.py`：角色卡在途径名下方渲染考据文本（`_wrap_text(pathway_lore(...), 44)`）；塔罗行加入「· 灰雾之上·源堡」。
  - `gui/controllers.py`：新增 `_do_toggle_ambient` / `_play_ambient`（`winsound.Beep(180,500)`，try/except 容错），按钮在 `gui/app.py` 工具栏「氛围音」。
  - 单测：考据渲染复用 `test_panel_character.py` 既有用例（字符卡结构未破坏），氛围音靠 try/except 不阻断。

#### E11. CLI↔GUI 共享核心（架构统一）✅ 已落地
- **动机**：抽出 `GameSession` 让 `main.py` 的 demo 与 GUI 共用同一引擎，统一推进 E4/E8（参考 1.3 架构友好原则）。
- **改动点**：扩展 `GameSession` 携带 `rival_system/achievements/codex`，并补齐 `from_dict`；新增 `journey` 完整养成循环 demo 证明 CLI 与 GUI 共用一套引擎。
- **落地记录（2026-08-14）**：
  - `save_load.py`：`GameSession.__init__` 纳入 `rival_system/achievements/codex`；`from_state`/`to_dict`/`apply_to_state` 序列化三者；新增 `from_dict(cls, d)` 与 `_from_dict_payload(cls, d)`；`version` 升到 2（旧档向下兼容）。
  - `main.py`：新增 `run_journey_demo()` / `demo_journey()`（完整循环：消化→晋升→事件→阵营→对手 tick→成就/图鉴/结局→GameSession 存读档往返断言），并在 `demos` 字典与参数白名单登记 `"journey"`。
  - 单测：`tests/test_e11_shared_core.py`（2 项，含 `e11_journey_demo_runs` 真实跑通 demo + `e11_gamesession_roundtrip_with_p2` 带 P2 字段的存读档往返）。面板套件 PASS=75、纯逻辑 + `test_all` 的 journey demo 用例通过，无回归。
  - **P2 路线全部完成**：E8 AI 对手、E9 成就/图鉴/多结局、E10 沉浸包装、E11 CLI↔GUI 共享核心均已落地并通过测试。

---

## 5. 推荐实施顺序（建议的下一步）

若只挑 3 件先做，按「对齐原著核心循环 + 架构友好」原则：

1. **E1 魔药材料**（让晋升有资源闭环）—— 数据+库存+前置校验，纯增量、不破坏现有 64 测试。
2. **E2 连续 SAN**（让污染可经营）—— 改造 `pollution.py` 的连续值 + 复用 `draw_gauges`。
3. **E3 事件系统**（让模拟能反复玩）—— 数据驱动 `events.json` + 选择结算。

做完这三项，项目就从「规则引擎 Demo」跃迁为「可游玩的养成模拟」，且全部可挂到现有 `draw_*` 自由函数体系与单测框架上。

> 注：所有增强都建议新增独立 `test_*` 文件（沿用 `tests/_panel_harness.py` 的 `FakeCanvas`/`CallbackRecorder` 模式），保持「面板=可独立单测自由函数」这一已验证的优势。

---

## 6. 信息来源（本次联网检索）

- 序列途径设定（QQ 阅读/起点百科）：https://ubook.reader.qq.com/baike/3dyr9wrwx7x2t
- 诡秘之主原著/动画设定科普：https://weread.qq.com/book-detail 、https://m.hongxiu.com/baike/1pcbn19zp4h3h
- Lord of the Mysteries 力量体系科普（TechWiser）：https://techwiser.com/lord-of-mysteries-magic-power-system-explained/
- 官方手游·魔药扮演法/晋升系统（18183 攻略）：https://m.18183.com/gonglue/202606/kebrdfd4.html
- 官方手游·灰雾测试开局攻略：https://www.18183.com/gonglue/202606/ctcbr1hb.html
- 官方手游·扮演法/SAN 详解：https://www.jiaoyimao.com/news/349136.html
- LOTM Craft（Minecraft 模组，22 途径竞争）：https://klauncher.gg/ko/minecraft/mods/lord-of-the-mysteries-craft
- 千世书·AI 文字人生模拟器（事件/属性/结局范式）：https://github.com/rockbenben/thousand-lives
- BitLife（文字人生模拟属性范式）：https://porkgames.com/bitlife
- 本科生模拟器（Vue 文字模拟：事件系统/存档范式）：https://gitee.com/wei-rain-light-dust/undergrad_-simulator
