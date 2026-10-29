# 代码审查报告 · text_fps（文字 FPS 战术射击）

> 审查范围：全量 36 个 .py 文件 / 6182 行（main.py + core/ + models/ + systems/ + ui/ + save/ + data/ + tests/）
> 审查维度：安全 / 性能 / 正确性 / 可维护性 + 代码债 / 依赖债
> 方式：静态审查（Read / Grep / Bash 目录核对），未修改任何文件

---

## 一、发现汇总表

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 |
|---|--------|------|---------|----------|----------|
| F1 | 🔴严重 | 依赖债/正确性 | ui/renderer.py:29 | `from shared.font_utils import load_cjk_font` 引用了项目中**不存在**的模块（全工程无 `shared/` 目录，assets 下仅 `FiraCode-Regular.ttf`），且该 import 未被 try/except 包裹；`Renderer.__init__` 一旦调用 `_load_font` 即抛 `ModuleNotFoundError` → 游戏**根本无法启动**（集成测试 `test_pygame_init_dummy` 同样会崩）。 | 移除对缺失 `shared` 包的依赖：直接用 `pygame.font.Font(path, size)` 加载内置 FiraCode，或把 `from shared.font_utils import ...` 包进 `try/except ImportError` 再走回退；并把字体加载器纳入项目/requirements。 |
| F2 | 🟠高 | 正确性 | game_state.py:58-67 / save_manager.py:47-86 / main.py:343-352 | 存档**不持久化房间与敌人状态**。`to_dict` 只存 `player` + `current_room`(room_id) + 轻量字段；`save_manager.load` 用 `load_level(current_level)` 重建一个**全新静态关卡** → 所有被击杀的敌人满血复活、地面物品/已访问/掉落状态全部重置。存档只保留玩家数值，等于进度丢失（且一旦 level 数据发生改名即 `current_room=None`，游戏软锁）。 | 在 `to_dict` 序列化 `current_room` 的完整 `Room.to_dict()`（含 enemies/items/visited），并在 `from_dict`/load 中恢复；或序列化整个 `levels`。加 `"version"` 字段以支持迁移。 |
| F3 | 🔴严重 | 正确性 | combat.py:55,175-183 + models/enemy.py:99-108 | **敌人护甲被减两次**。`calculate_damage(weapon, target.armor)` 已经 `base - min(armor, base)` 扣过一次护甲，随后 `target.take_damage(damage)` 又 `self.armor` 扣一次 → 实际伤害 ≈ `D - 2A`。对高护甲敌人（士兵10/重装兵20/狙击手5/指挥官25）会造成**0 伤害**：例如手枪(12)打重装兵(20)→`12-20`再`-20`=0，霰弹(30)打重装兵(20)→`30-20`再`-20`=0。大部分武器对重甲敌人近乎**无效/打不死**。 | 护甲只扣一次。建议：删除 `calculate_damage` 里的护甲逻辑，`Enemy.take_damage` 独占护甲；或 `execute_fire` 直接 `target.take_damage(weapon.effective_damage())` 让敌人自己处理护甲。 |
| F4 | 🟠高 | 可维护性/代码债 | core/event_bus.py:29-31 + combat.py:66-71,84-89,163-166 + movement.py:98-104 + inventory.py:40-43,74-76,147-150,172-174,232-234 + stealth.py:53-56,132-134 + game_state.py:37 | **EventBus 是死基础设施**：全工程生产代码（systems/models/main）**零处调用 `event_bus.subscribe`**（grep 确认仅测试文件订阅）。所有 `publish(...)`（combat.fire/grenade、movement.enter*、inventory.*、stealth.*、log_updated）都是**静默空转**，发布/订阅的“解耦”目标完全没有达成，且极具误导性。 | 要么落地真实订阅者（HUD 刷新、音效、统计），要么移除 EventBus 及相关 publish 调用，避免留下永不触发的“幽灵事件”。 |
| F5 | 🟡中 | 正确性 | main.py:59,118 + ui/panels/button_bar.py:176-188 | `selected_enemy_index` 初始化为 0 后**再无任何 UI 写入它**；底部 `ButtonBar` 虽然绘制了“目标列表”（敌人名+血量），但这些只是纯文本、不可点击 → 玩家**永远无法选择攻击哪个敌人**，开火恒为 `enemies[0]`（或 `len` 取模）。目标指示器是误导性的死 UI。 | 让目标名可点击以设置 `selected_enemy_index`；或改为自动锁定最低血量/最近敌人；或移除该指示器。 |
| F6 | 🟡中 | 正确性 | main.py:364-371 | 滚轮事件被**双重处理**：`MOUSEBUTTONDOWN` 的 button 4/5 与 `MOUSEWHEEL` 在同一次滚轮滚动中都会调用 `handle_scroll`，导致日志**一次滚动两格**。 | 仅保留 `MOUSEWHEEL`（现代事件，`event.y`），删除 button 4/5 分支，或加去重判断。 |
| F7 | 🟡中 | 可维护性 | core/constants.py:9 | `SIDE_PANEL_WIDTH = 324  # 1024 - 700` 是预计算的魔法数字，与 `SCREEN_WIDTH - MAIN_TEXT_WIDTH` 无推导关系；一旦改 `SCREEN_WIDTH`/`MAIN_TEXT_WIDTH` 会悄悄错位。 | 改为 `SCREEN_WIDTH - MAIN_TEXT_WIDTH`，消除硬编码差。 |
| F8 | 🟡中 | 代码债 | main.py:379 + 全工程 `state.dirty=True` | `game_state.dirty` 被到处置 True、在循环末置 False，但**从不读取**来决定是否渲染（render 每帧无条件执行）。这是“未完成的脏标记优化”，属于误导性死状态。 | 要么在 `run()` 中用 `if self.game_state.dirty:` 包住 render，要么删除 dirty 字段与所有赋值。 |
| F9 | 🟡中 | 代码债 | systems/inventory.py:10 + ui/panels/inventory_panel.py:67 | 库存上限 `MAX_INVENTORY_SIZE = 10` 与 `constants.MAX_INVENTORY = 10` 重复；面板又硬编码 `"/10"`。两处不同步风险（改一处另一处不变）。 | `inventory.py` 与面板统一 `from core.constants import MAX_INVENTORY`。 |
| F10 | 🟡中 | 代码债 | models/weapon.py:75-102 | `Weapon.fire()` 是**死代码**：战斗逻辑在 `combat.execute_fire` 里另行实现，且 `fire()` 的伤害计算未含护甲（与 F3 的双扣逻辑不一致）。 | 删除 `Weapon.fire()`，或让 `combat` 复用它并统一护甲处理；避免两份并行真相。 |
| F11 | 🟡中 | 代码债 | systems/inventory.py:181-216 vs 125-141 | `modify_weapon()` 整段重复了 `use_item()` 中 WeaponModItem 的“取当前武器→add_mod→弹栈”逻辑，未来改一处另一处会分叉。 | 抽一个 `_attach_mod_to_current_weapon(player, mod)` helper，两处共用。 |
| F12 | 🟡中 | 正确性/健壮性 | systems/movement.py:184 | `_check_traps` 用 `trap['name']` **直取下标**，陷阱字典若缺 `"name"` 会抛 `KeyError`。（当前 data 均带 name，但属脆弱写法，且 `_check_random_event` 还有 15% 触发概率与 `_event_trap` 直接扣血，链路较长。） | 改为 `trap.get("name", "陷阱")`。 |
| F13 | 🟡中 | 代码债 | main.py:45 与 66 | `Game.__init__` 先建一个 `GameState`（line 45），紧接着 `_start_new_game()` 又 **重建并替换** 一个（line 66）；首个被丢弃。且 `_start_new_game` 没有重置 `selected_enemy_index` 等瞬态字段。 | 只在 `_start_new_game` 里构建一次状态；重建时一并复位瞬态（selected_enemy_index、systems 不需要，但保持清晰）。 |
| F14 | 🟡中 | 可维护性/正确性 | main.py:354-382 | `Game.run()` 主循环**无 try/finally** 包裹 `pygame.quit()`；渲染或事件处理一旦异常，pygame 不清理、SDL 资源泄漏。 | `try: ... finally: pygame.quit()`；并对单帧渲染包轻量异常保护。 |
| F15 | 🟡中 | 性能 | ui/panels/main_panel.py:30-46 | `_wrap_text` 逐字符调用 `self.font.size(test)`，对不断增长的前缀串做宽度测量，单行内 O(n²)；每帧对全部日志行重算 → 长日志时主循环有可感知卡顿。 | 缓存“已渲染日志”的换行结果，仅在 `log` 变化时重算；或用增量累计宽度避免重复测量整串。 |
| F16 | 🟡中 | 依赖债/正确性 | game_state.py:58-67 / save_manager.py:65-86 | 存档**无 schema 版本号**，`to_dict`/`from_dict` 对模型字段强耦合；日后给 Player/Weapon/Enemy 加字段即静默破坏旧档（无迁移）。 | 在存档根加 `"version": N`，load 时校验并按版本迁移。 |
| F17 | 🟢低 | 可维护性 | core/constants.py:31 | `PHASE_LEVEL_COMPLETE = "level_complete"` 定义后**全工程无引用**（关卡完成在 main 内联处理，未存为 phase）。 | 删除或真正接入状态机（如新增 `PHASE_LEVEL_COMPLETE` 过渡态）。 |
| F18 | 🟢低 | 代码债 | systems/stealth.py:21 | `NOISE_MAP["sneak"]` 键对应**不存在的 "sneak" 动作**（游戏无潜行动作），死键。 | 删除该键，或实现对应潜行动作。 |
| F19 | 🟢低 | 代码债 | ui/panels/main_panel.py:17 | `MAX_VISIBLE_LINES = 100` 定义后从未使用。 | 删除，或真正用于可见行上限控制。 |
| F20 | 🟢低 | 代码债 | systems/movement.py:147 | `_event_supply_drop` 内 `import random as rng` 重复导入顶部已 import 的 `random`（且未给别名新语义）。 | 直接用已导入的 `random`，删除冗余 import。 |
| F21 | 🟢低 | 性能 | ui/button.py:52 / 各 panel 每帧 `font.render` | 按钮/面板每帧 `font.render(...)` 新建 Surface（含 overlay `pygame.Surface`），产生持续 GC 压力。 | 对静态文本（按钮标签、固定标题）做 Surface 缓存。 |
| F22 | 🟢低 | 可维护性 | core/event_bus.py:29-31 | `publish` 对未订阅事件**静默 no-op**，会掩盖“本应订阅却忘记订阅”的接线 bug（叠加 F4 更是雪上加霜）。 | 可在 DEBUG 模式对未订阅事件打印告警；或见 F4 移除死总线。 |
| F23 | 🟢低 | 正确性 | models/enemy.py:63 | `_act_boss` 中 `self.health / self.max_health` 若 `max_health==0` 会除零。 | 用 `max(1, self.max_health)` 防御。 |
| F24 | 🟢低 | 可维护性 | tests/test_game.py:1732 | 注释写 `cover_objects=["concrete pillar"]`，但实际数据为中文 `"水泥柱"`（注释漂移，易误导维护者）。 | 修正注释或改为不依赖具体字符串。 |
| F25 | 🟡中 | 可维护性/架构 | systems/inventory.py:88-94,122 + main.py:190 | `InventorySystem.use_item(..., combat_system=None)` 直接调用 `CombatSystem.execute_grenade`，main 又把 `self.combat` 注入 inventory。所谓“系统经 EventBus 解耦”并不成立——系统间是**具体同步耦合**（inventory 依赖 combat 具体类），与 F4 的死总线并存。 | 收紧边界：手雷结算回归 CombatSystem 单一职责，inventory 只负责“从背包移除手雷并回调/发事件”；或用协议/接口而非直接持有 CombatSystem 实例。 |
| F26 | 🟡中 | 可维护性/正确性 | main.py:106-242 + ui/panels/*（get_action） | UI 与 Game 之间用裸字符串字典契约 `{"action":"fire",...}` 传递意图，无 schema/校验；一旦 action 名拼写错误或 UI/后端不一致，`_process_player_action` 的 else 分支**静默 no-op**，极难排查。 | 定义 `Action` 枚举或 TypedDict/pydantic 模型；在 `_process_player_action` 入口对未知 action 显式报错/日志，而非静默 return。 |
| F27 | 🟡中 | 可维护性 | main.py:93 vs systems/movement.py:41 | 方向→中文映射被硬编码两份：`main.py:93` 的 `dir_names` 与 `movement.py:41` 的 `dir_name`（同内容不同变量名）。改一处另一处不跟随。 | 收敛到 `core/constants.py`（如 `DIR_DISPLAY = {"north":"北",...}`）统一引用。 |
| F28 | 🟢低 | 代码债 | ui/renderer.py:100-103 + core/event_bus.py:17-23 | 死代码：`Renderer.setup_panels()` 全工程无人调用且函数体是把 panels 清空再重建同一列表的空操作；`EventBus.unsubscribe()` 生产代码零调用（仅测试用）。叠加 F4，EventBus 的“订阅/卸载”API 大半是摆设。 | 删除 `setup_panels` 与 `unsubscribe`（或真正接入）；保持 API 与真实使用一致。 |
| F29 | 🟡中 | 可维护性 | core/game_state.py:46 + systems/movement.py:146 + combat.py:185 + inventory.py:88-94 | 类型/导入债：为绕开循环导入的延迟导入（`game_state.py:46 from data.weapons import...`、`movement.py:146 from data.items import...`）散落多处；缺类型标注 `combat.execute_enemy_turn` 的 `room` 参数、`inventory.use_item` 的 `combat_system`/`enemies: Optional[List]`（缺内层 `List[Enemy]`）等。 | 用 `TYPE_CHECKING` 守卫类型导入、统一运行时导入；补全方法签名与返回值注解，引入 `mypy`/CI 类型检查。 |

---

## 二、🔴/🟠 重点发现说明（问题 + 代码级修复）

### F1 · 启动即崩溃：缺失 `shared.font_utils` 模块 🔴
**具体问题**：`ui/renderer.py` 第 29 行在 `_load_font()` 内无条件执行 `from shared.font_utils import load_cjk_font`。项目目录（含 assets）中**不存在 `shared/` 包**，该模块也不在 `requirements.txt`。所以 `Renderer.__init__`（main.py:55 触发）会抛 `ModuleNotFoundError` 并向上冒泡到 `main()`，整个游戏无法进入主循环；集成测试 `TestIntegrationPygameInit.test_pygame_init_dummy`（test_game.py:1570）实例化 `Renderer` 时同样会崩。这是最高优先级阻断项。

**代码级修复**（renderer.py `:27-41`）：
```python
def _load_font(size: int) -> pygame.font.Font:
    # 不再依赖外部 shared 包；优先用项目内置 FiraCode，否则回退默认字体
    font_path = os.path.join(BASE_DIR, "assets", "fonts", "FiraCode-Regular.ttf")
    if os.path.exists(font_path):
        try:
            return pygame.font.Font(font_path, size)
        except (FileNotFoundError, OSError):
            pass
    return pygame.font.Font(None, size)
```
（若仍要保留 CJK 加载器，把 `from shared.font_utils import load_cjk_font` 放进 `try/except ImportError` 并继续回退即可。）

**治理升级（行动项，与 ADR-008 定稿对齐）**：上述 try/except 仅是即时止血（方案 C）。架构评估已将此问题上升为依赖治理决策 **P2 / ADR-008**，要求从根因（裸依赖一个全仓无任何第二处引用、非可安装包、且不在 `requirements.txt` 的 `shared`）消除，而非靠 try/except 掩盖。建议行动项：

1. **方案 A（vendored，推荐）**：把 `load_cjk_font` 落地进本仓库——新建 `ui/font_utils.py` 实现该加载器，`renderer.py` 改为 `from ui.font_utils import load_cjk_font` 并 **彻底删除裸 `from shared.font_utils`**。理由：`shared` 全仓零第二处引用，做成外部包（方案 B）只会重演同一次 SEV-1。
2. **依赖清单治理**：给 `pygame-ce` 加上限版本钉（如 `pygame-ce>=2.4,<2.6`）、补 `lockfile`（pip-tools/`requirements.lock`）、在 `requirements.txt` 声明**全部真实运行时依赖**（而非仅 `pygame` 一类）。避免「代码 import 了、清单没写」再次导致启动即崩。
3. **CI 可达性检查**：在 CI 加一条导入冒烟（`python -c "import main"` 或 pytest 的 `test_pygame_init_dummy` 常驻运行），确保「缺模块/缺依赖即崩」这一类 P2 问题无法再静默溜进主干。

### F2 · 存档不持久化敌人/房间状态 🟠
**具体问题**：`GameState.to_dict()`（game_state.py:58-67）只序列化 `player` 与 `current_room` 的 **room_id**，不含房间里敌人的生死/血量、地面物品、visited 等。`save_manager.load`（save_manager.py:69-79）用 `load_level(current_level)` 从静态数据重建关卡，得到的是**满血满编的敌人**。结果：玩家清完房间后存档、读档，敌人全部复活、掉落物丢失、房间重置——等于进度未保存。若 level 数据后续改名/删房间，`get_room(room_id)` 返回 None，`current_room` 变 None，游戏软锁。

**代码级修复**：序列化当前房间完整状态，并在读档时恢复：
```python
# game_state.py to_dict()
"current_room": self.current_room.to_dict() if self.current_room else None,
"levels": [lv.to_dict() for lv in self.levels],
"version": 1,
```
```python
# save_manager.load() 中：直接由数据重建 Room/Enemy，而非依赖 load_level 静态副本
room_data = save_data.get("current_room")
if room_data:
    gs.current_room = Room.from_dict(room_data)
```
（Room/Enemy 已有完备的 `to_dict`/`from_dict`，能力现成却未被存档使用——见架构债信号。）

### F3 · 敌人护甲被扣两次（可致 0 伤害） 🔴
**具体问题**：`combat.execute_fire`（combat.py:55）调用 `damage = self.calculate_damage(weapon, target.armor)`，而 `calculate_damage`（:175-183）已执行 `armor_absorb = min(target_armor, base); return base - armor_absorb`；随后 `target.take_damage(damage)`（enemy.py:99-108）又 `armor_absorb = min(self.armor, amount)` 再扣一次。最终伤害 = `D - 2A`。对高甲敌人这会归零：手枪(12)打重装兵(20)、霰弹(30)打重装兵(20)、步枪(18)打指挥官(25) 均为 **0 伤害**，使重甲敌人在起始武器下近乎无敌。

**代码级修复**（二选一，护甲只扣一次）：
```python
# 方案 A（推荐）：combat 不再处理护甲，交给 Enemy 独占
damage = int(weapon.effective_damage() * random.uniform(0.8, 1.2))
target.take_damage(damage)   # enemy.take_damage 内部处理 self.armor
```
或方案 B：保留 `calculate_damage` 的护甲扣除，并让 `Enemy.take_damage` 不再扣甲（需同步改敌人之间互殴逻辑）。注意同时修正 F10 中 `Weapon.fire()` 的护甲口径，避免三处不一致。

### F4 · EventBus 为死基础设施（零订阅者） 🟠
**具体问题**：grep 全工程，生产代码**没有一处 `event_bus.subscribe(...)`**（`subscribe` 仅出现在 test_game.py 的 EventBus 自测）。`combat/movement/inventory/stealth/game_state` 里所有 `event_bus.publish(...)` 都发布到无人订阅的事件类型，纯属空转。这意味着“发布/订阅解耦”的架构意图完全未落地，且给阅读者强烈的“有监听者在响应”的错觉，极容易误导后续修改。

**代码级修复**：两种方向——(a) 落地真实订阅者：例如 `inventory.use`/`log_updated` 驱动 HUD 红点、音效、统计面板；或 (b) 若暂不需要，直接删除 EventBus 及相关 publish/import，避免幽灵事件。至少应补注释说明当前 pipeline 为直接方法调用、EventBus 预留未用。

---

## 三、架构债信号（供 Archi 交叉印证）

1. **GameState 上帝对象 + 中枢可变状态**：`GameState` 持有 `player / current_room / levels / turn / phase / log / dirty`，被 `main.py` 与全部四个 system 直接读写，是事实上的全局可变状态中心；systems 同时持有 `event_bus` 又接收 `game_state` 参数（movement/stealth），**与 GameState 强耦合**。新增玩法都要回头改这个中心对象。
2. **EventBus 死基础设施**：见 F4——publish 全空转，解耦目标未达成，且与“直接方法调用”两套并存，是典型“过度设计但未落地”。
3. **存档与领域模型割裂**：`Room`/`Enemy`/`Level` 已具备完整 `to_dict`/`from_dict`，能力现成；但 `save` 只序列化 player+room_id，重建时依赖静态 `load_level`，导致状态丢失与能力浪费并存——模型层“可序列化”与存档层“不序列化”严重不一致。
4. **UI 布局魔法数与三处重复坐标计算**：`inventory_panel` 的 item 行 Y 坐标在 `render`(:207-224)、`handle_click`(:207-224)、`update_hover`(:272-290) 三处各算一遍，且共用魔法数 `-60`；任何布局改动需三处同步，是脆弱耦合信号。叠加 `dirty` 死标记（F8），提示 UI 与状态层职责划分尚不清。
5. **单一依赖 pygame-ce 且为唯一硬依赖**：`requirements.txt` 仅 `pygame-ce>=2.3.0`，未锁次版本上限（跨版本渲染/事件 API 风险），且实际还隐含了一个不在依赖清单里的 `shared` 包（F1）。测试/类型检查/格式化工具链缺失，`requirements.txt` 只覆盖运行时。
6. **系统间并非真解耦（架构交叉复核）**：除 F4 的死 EventBus 外，`InventorySystem.use_item` 直接持有并调用 `CombatSystem.execute_grenade`（main 注入 `self.combat`），系统间是具体同步耦合；UI 与 Game 之间还以裸字符串 `{"action":...}` 字典契约通信（无 schema/校验，错名静默 no-op，见 F25/F26）。配合延迟导入与零散缺注解（F29），整体“分层/解耦”意图与落地严重脱节。

**依赖债补充**：
- 可复现性差：无 lockfile、版本不锁上限（`pygame-ce` 仅 `>=2.3.0` 无次版本上限）；缺失 `shared` 模块（F1，已上升为依赖治理决策 **P2 / ADR-008**）。治理行动项：① 将 `load_cjk_font` vendored 进 `ui/font_utils.py` 并彻底删除裸 `from shared.font_utils`；② 给 `pygame-ce` 加上限版本钉、补 lockfile、在 `requirements.txt` 声明全部真实运行时依赖；③ CI 加导入冒烟（`python -c "import main"` 或常驻 `test_pygame_init_dummy`），杜绝「缺模块即崩」类 P2 再次进主干。详见 F1 治理升级段。
- 可测试性差：`Game` 主类与 pygame/SDL 强耦合（`Renderer` 构造即需显示驱动），故集成测试只能靠 `SDL_VIDEODRIVER=dummy` + 直调 system；`Game.run()` 事件循环、键鼠处理、存档点击流程**无单元测试覆盖**。

---

## 四、严重度计数

> 交叉复核：架构师 Archi 的主报告 #3/#1/#9 与本报告 F1/F4/F9 **完全一致**；其 #7/#10/#12/#13/#15/#16 已补入下方 F25–F29。

> 同根因合成（与 architect 双向确认）：经交叉复核，F3（护甲吸收规则在 `combat.py:175-183` 与 `enemy.py:99-108` **双源实现** → 双重扣减）与 F4（系统间通信无单一归属：EventBus 半拉子 + Inventory→Combat 直接引用并存）同源于「**每条不变量/设计意图应有且仅有一个权威归属（single owner）**」这一跨切原则；architect 主报告 #4（`main.Game` god-object，掉落/通关/噪音/警觉等本属各系统的规则全挤在编排器）是同一原则的**第三表现**。该原则由 architect 在 ADR 层以跨切注解贯穿 ADR-001/004/005 与战斗建模，**不新开 ADR-009**，ADR 集维持 8 条（避免同根因重复计数）。注意：本报告 F3/F4 **仍作为独立发现保留**——二者是不同症状、各自需独立代码修复（F3 为正确性 bug 须即修；F4 为死设施须落地或删除）；根因合成是治理层框定，不改变「每个可观测缺陷 = 一条发现」的审查粒度。F3 即时修（删除两处护甲扣减中任一）与 F4 处置（接入 EventBus 或删死总线 + 去除 Inventory→Combat 直耦）不受 ADR 框定影响，须照常推进。

🔴 严重：2（F1 启动崩溃 / F3 双重护甲致 0 伤害）
🟠 高：2（F2 存档丢状态 / F4 死 EventBus）
🟡 中：16（F5–F16, F25–F29）
🟢 低：9（F17–F24, F28）

> 合计 29 条（原 24 + 架构交叉复核新增 5：F25–F29）。

> 合计 29 条。建议优先处置两个 🔴（F1 阻断启动、F3 破坏战斗）、以及两个 🟠（F2 存档完整性、F4 架构诚实度），再批量清理 🟡 魔法数/死代码/重复逻辑。
