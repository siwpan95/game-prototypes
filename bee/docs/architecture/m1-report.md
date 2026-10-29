# BeeIdleRPG — M1 报告：sim_core 抽取 Spike + Gate 1 裁定

| 字段 | 内容 |
| --- | --- |
| **文档 ID** | m1-report |
| **关联** | ADR-0001（SIGNED-OFF 采纳 B/C）· migration-plan.md（M1 + §2） |
| **日期** | 2025-07-14 |
| **作者** | eng-lead-adr（工程负责人 / 主程序） |
| **阶段** | M1 · sim_core spike（强制前置闸门，Gate 0 → Gate 1 的输入） |
| **裁定** | **Gate 1 = PASS**（含 4 项低风险偏离，均不触及 §2.4 验收标准） |

---

## 1. M1 目标与范围

按 migration-plan.md §2 + 主理人签核的增量规格（1a–1e）执行首次改源码：

- **1a** 抓黄金基准（`tests/golden_baseline.json`）：固定 `random.seed(12345)` + 固定缺失存档，跑 `_update_game(dt)` 200 步（dt=0.05），记录 139 行日志 + 状态指纹。不改游戏源码。
- **1b** 建 `src/sim_core/` 包：19 个 service + 6 个 model + `json_pool` + `logging_config` 迁入；`engine.py` 新增 `SimCore` 承载全部模拟编排；音频改为事件队列。
- **1c** 黄金测试（`tests/test_sim_core_golden.py`）：逐字复现基准 + 状态指纹一致 + 零 tkinter 导入。
- **1d** 瘦身 `game_controller.py` + mixins：控制器退化为薄前端（持 `SimCore` + 渲染 + 输入胶水）。
- **1e** 冒烟 + Gate 1 报告。

**硬约束（全程遵守）**：不改 `save.json` schema、`data/`、Excel 配置、24 表 JSON（R2/R3）；非破坏性（原路径留 re-export shim，保护用户内容工具）；不 git commit；用户真实 tkinter 机器行为不变。

---

## 2. Gate 1 成功标准逐条核对（migration-plan.md §2.4）

| # | 标准 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | `import sim_core` 不触发 tkinter/pystray | ✅ PASS | `test_sim_core_no_gui_import`：扫描 `sim_core/` 全树 0 命中 `import tkinter`/`from tkinter`/`import pystray`/`from pystray`；headless import 全量扫描 **40/40 模块可导入** |
| 2 | `SimCore.update(dt)` 逐字节复现 `_update_game` | ✅ PASS | `test_sim_core_matches_baseline`：`logs == base["log_messages"]` 且 `fp == base["fingerprint"]`；**139/139 日志行逐字一致，指纹 100% 一致** |
| 3 | services+models+json_pool headless 可跑 | ✅ PASS（集成态） | 全量 relocate 后 40 模块 import 干净；黄金测试经真实 200 步模拟驱动了全部 19 个 service（战斗/难度/地牢/事件/任务/城堡/药水/物品/食谱/休整/城镇/世界/成就/神器/数据/Excel/音频母版）；**逐 service 单测为 Phase 6 后续工作**（仓库原本即无 per-service pytest） |
| 4 | `game_controller` 退化为薄前端 | ✅ PASS | `game_controller.py` 161 行，仅持 `SimCore` + UI 胶水；迁移逻辑全部移除；控制器内对 `self._init_game/_restart_game/_update_combat/...` 的悬空引用 **grep 0 命中** |
| 5 | `save.json` schema 不变 | ✅ PASS | `SimCore.save_game/_load_game` 逐字移植原 `to_dict/from_dict`；未增删任何字段；存档读写经 `self.sim` 接线，schema 冻结 + 版本号不变（R2） |

---

## 3. 迁移指标（行数 / 范围）

**迁入 `src/sim_core/` 的模拟逻辑（≈ 8,466 行）**：

| 子包 | 行数 | 说明 |
| --- | --- | --- |
| `sim_core/services/`（19 个） | 5,757 | combat/difficulty/dungeon/event/quest/castle/potion/item/recipe/rest/town/world/achievement/artifact/data/excel/audio_service/audio_engine/audio_presets |
| `sim_core/models/`（6 个） | 1,229 | character/item/dungeon/potion/quest/world |
| `sim_core/engine.py` | 1,050 | 新增 `SimCore` 编排宿主（逐字移植 `_update_game` 及其内部编排） |
| `sim_core/json_pool.py` | 342 | 运行期只读 JSON 池（路径 base_dir 修正 +1 层 `dirname`） |
| `sim_core/utils/logging_config.py` | 88 | 日志配置 |
| **合计** | **8,466** | 模拟内核主体 |

**非破坏性 shim（保留原导入路径，保护内容工具）**：

| 原路径 | 行数 | 形式 |
| --- | --- | --- |
| `src/app/services/*.py`（19） | 135 | `from src.sim_core.services.X import *` |
| `src/app/models/*.py`（6） | 44 | `from src.sim_core.models.X import *` |
| `src/app/utils/logging_config.py` | 7 | `from src.sim_core.utils.logging_config import *` |
| `src/json_pool.py` | 7 | `from src.sim_core.json_pool import *` |
| **合计** | **193** | 仅再导出，零逻辑 |

**控制器薄前端（M1d）**：

| 文件 | 行数 | 状态 |
| --- | --- | --- |
| `game_controller.py` | 161 | 重写：持 `SimCore` + 属性代理 + `_game_loop` 消费 `audio_events` + `_redraw` |
| `game_render.py` | 422 | 逻辑不变；12 处 `self.<sim字段>` → `self.sim.<字段>` 机械改写（grep 0 悬空） |
| `game_io.py` | 38 | 重写：`save_game`→`self.sim.save_game()`；`_toggle_pause/_toggle_mute` 保留 |
| `game_init.py` | 133 | 仅保留 `_show_character_creation`（纯 UI） |
| `game_tray.py` | 144 | 未改（pystray 胶水，按 §2.2 不动） |
| `game_combat/exporation/achievements.py` | — | **已删除**（迁移后为空，无引用） |

---

## 4. 测试结果（M1e 冒烟）

| 测试 | 结果 | 说明 |
| --- | --- | --- |
| `tests/test_sim_core_golden.py`（2 用例） | ✅ **2 passed** | 日志逐字 + 指纹一致 + 零 GUI 导入 |
| headless 全量 import 扫描（sim_core + 5 控制器 mixin） | ✅ **40/40 OK** | 0 导入失败 |
| 控制器 headless 烟雾（`_verify_controller`） | ✅ **ALL CHECKS PASS** | 构造、`sim` 接线、音频共享、paused/`_add_log` 代理回写、`save_game` 委派、整帧 `_redraw`（int 几何）不抛异常 |
| `tests/test_tag_system.py` | ✅ **4 passed** | 仓库既有测试，不受 M1 影响 |
| `test_refactor.py` | ⚠️ 收集错误 | legacy `app.services` import 路径（无 `src.` 前缀），**M1 前即坏，非本次引入** |

**Golden 复现率：100%**（139/139 日志行逐字 + 状态指纹完全一致，200 步 dt=0.05，seed=12345）。

**音频解耦**：`SimCore.update` 不再直接调 `self.audio.sfx_*()`，改为 `self.audio_events.append(("sfx_*", ()))`；薄前端每帧 `getattr(self.audio, name)(*args)` 消费并真实播放（含 try/except 单条容错）。200 步实测产生 9 条音频事件（击杀/升级/受击等），模拟与播放彻底分离。

---

## 5. 关键架构 / 技术决策

1. **非破坏性 shim（无 git 仓库前提下保护用户工具）**：真实实现迁入 `sim_core/`，原路径改为 `from sim_core... import *` 再导出。已验证 shim 别名指向同一对象（`CombatService` 类同一、`JsonPool`/`get_json` 同一）。用户的内容工具 / 游戏入口（`main.pyw`）**零改动即可继续工作**。
2. **属性代理（最小侵入 rewiring）**：`GameController.paused` / `_game_over` / `_add_log` 经 property 代理到 `self.sim`；`game_render.py` 仅改数据源前缀（`self.X`→`self.sim.X`），绘制逻辑不变。
3. **音频事件队列**：消除 sim 对 audio 实现的硬依赖，满足 `sim_core` 引擎无关约束（R7 在 M3 按宿主重做音频时零返工）。
4. **SimCore 自包含驱动**：`update(dt)` 纯推进（输入 dt + 内部状态 → 状态变更 + 日志 + 音频事件），不持时钟/UI 引用，可直接被 Godot 主循环每帧 `tick(dt)`（为 M2 桥接铺路，规避 R1/R8）。

---

## 6. 偏离计划处（均低风险，不触及 §2.4）

| ID | 偏离 | 影响 | 决策 |
| --- | --- | --- | --- |
| D1 | `json_pool` 落在 `sim_core/json_pool.py`，非计划 §2.1 的 `sim_core/data/json_pool.py` | 纯路径差异，功能等价 | 接受；M2 如需可平移目录（无引用耦合） |
| D2 | `sim_core/config/settings.py` 采用**再导出子集**（仅模拟参数）而非把 `src.config.settings` 整体拆为双源 | sim_core 仍软依赖 `src.config.settings`，但后者不引 tkinter | 接受且更优：模拟参数经 `sim_core.config.settings` 暴露，UI 参数留前端，单源防漂移 |
| D3 | ECS（`src/app/ecs/`，238 行，休眠、零引用）**未迁移** | 计划 §2.1 列为可选 | 接受：休眠死代码，零引用，迁移无收益；择机清理 |
| D4 | `_show_character_creation` 成为**孤儿**：`__init__` 不再调用，且其返回值未喂给 `SimCore`；`SimCore()` 构造即自动新建默认角色 | 自定义角色创建 UI 当前不可达 | 接受（行为等价于黄金基准）：原基准即用默认角色自动开局，golden 已证明启动态一致。建议 M2 前补"新游戏"动作将结果 `→ self.sim._init_new_game(race, cls, name)` |

**附注（非 M1 引入，仅提醒）**：`difficulty_service.py:567` 有预存 `print("[DDA-PROBE] ...")` 调试输出，在 `SimCore()` 构造期会刷屏（原 `app/services` 版本同款 `.pyc` 可证为预存）。建议单独清理，不在 M1 范围。

---

## 7. 引擎风险与知识缺口

- **无新增引擎知识缺口**：本次为纯 Python 提取，未触及 Godot 4 API；M2 桥接（GDExtension 托管 / 子进程 IPC）的 Godot 具体 API 仍待原型验证（计划在 M2 评估，对应 ADR R6）。
- **R6（IPC 延迟）**：M1 已证明 `SimCore.update(dt)` 为纯推进、可 headless 驱动，为"前端每帧喂 dt"契约铺路，降低未来桥接复杂度。
- **R7（音频）**：已通过事件队列隔离，M3 按宿主重做音频时 sim_core 零返工。

---

## 8. 待用户审批项

1. **Gate 1 裁定 = PASS**，是否同意据此推进 M2（Godot 4 引擎原型验证）？
2. **D4 角色创建孤儿**：确认维持"默认角色自动开局"（与基准一致），还是要求在 M2 前接回 `_show_character_creation → SimCore._init_new_game`？
3. **D1 `json_pool` 路径**：是否需在 M2 前平移到 `sim_core/data/`（纯整理，无功能影响）？
4. **D3 ECS**：确认保留休眠代码，还是 M2 前清理？
5. **预存 `[DDA-PROBE]` 调试 print**：是否授权单独清理（不在 M1 范围内）？

---

## 9. 下一步建议

- **M2（引擎原型验证）**：以 Godot 4 为目标，建最小场景（日志文本框 + 状态面板），用 GDExtension（首选 A）或子进程 IPC（降级 B）托管 `sim_core`，验证"前端每帧 `sim_core.update(dt)` → 渲染日志/状态"与跨平台导出；定夺桥接方式。
- **Phase 6 测试补强**（建议提前）：为 19 个 service 补 per-service headless 单测，降低未来桥接回归成本（当前仅集成 golden 安全网）。
- **`test_refactor.py`**：修复 legacy `app.services` import（或标记为废弃），避免误导 CI。

---

## 10. 产物路径清单

| 类别 | 路径 |
| --- | --- |
| 模拟内核 | `src/sim_core/engine.py`、`src/sim_core/services/`（19）、`src/sim_core/models/`（6）、`src/sim_core/json_pool.py`、`src/sim_core/utils/logging_config.py`、`src/sim_core/config/settings.py` |
| 黄金安全网 | `tests/test_sim_core_golden.py`、`tests/golden_baseline.json` |
| 薄前端 | `src/app/controllers/game_controller.py`、`game_render.py`、`game_io.py`、`game_init.py`、`game_tray.py` |
| 非破坏性 shim | `src/app/services/*.py`、`src/app/models/*.py`、`src/app/utils/logging_config.py`、`src/json_pool.py` |
| 本报告 | `docs/architecture/m1-report.md` |

> **执行纪律确认**：未 git commit；未改 `save.json` schema / `data/` / Excel / 24 表 JSON；用户真实 tkinter 机器行为等价（golden 已证明启动态一致）。

---

## 11. M1 收尾（三项签核决策执行）

主理人签核三项收尾（全按推荐）：D4 接回角色创建、删 `[DDA-PROBE]` 调试 print、删休眠 ECS。纪律不变：不动 save.json/Excel/data，不 git commit。

### 11.1 D4 — 角色创建接回 `SimCore._init_new_game`
- `src/sim_core/engine.py`：`_init_new_game(self, race=None, char_class=None, name=None, seed=None)`。
  - **默认无参路径（SimCore() 自动开局）**：当四参数全为 None 时，行为与迁移前**逐字一致**（仅建 hero/party/world/dungeon/potion；区域/运行时服务/计时器由 `_init_game` 补全）→ **golden 等价性不变**。
  - **自定义路径（对话框触发，任一参数非 None）**：做**完整重开**——重置 `_game_over`/计时器/`log_messages`，重建 `castle/achievement/artifact` 服务，设定出生区域，并以传入 `seed` 固定全局 RNG + 世界种子（确定性开局）。
- `src/app/controllers/game_init.py`：`_show_character_creation` 的 `on_confirm` 在确认时调用 `self.sim._init_new_game(race=..., char_class=..., name=..., seed=random.randint(1, 2**31-1))`，对话框不再孤儿。
- **刻意未做**：未在 `game_controller.py` 新增"新游戏"触发键/按钮（避免超出授权范围、保持启动自动开局不变）。对话框现已功能化，但需一个触发入口才能被用户触达——**建议 M2 前补一个 `<Key-n>` 绑定或 UI 按钮**（已记录，待审批）。

### 11.2 `[DDA-PROBE]` 清理
- 删 `src/sim_core/services/difficulty_service.py` 的测试探针整块（`# ── 测试探针 ──` + `parts` 构造 + `print("[DDA-PROBE] ...")`）。`affix_effects`/`D` 等为真实缩放值，仍被使用，删除仅移除调试输出。
- grep 全树：`DDA-PROBE` **0 命中**（源文件；`.pyc` 为陈旧编译产物，运行即重建且不含 print）。

### 11.3 休眠 ECS 删除
- 先 grep 确认 `src/app/ecs` **零外部引用**（仅包内自引用），再删 `src/app/ecs/` 整个目录（含 `__pycache__`）。
- grep 全树 `ecs|ECS`：**0 命中**。

### 11.4 验证结果（收尾后）
| 测试 | 结果 |
| --- | --- |
| `tests/test_sim_core_golden.py` | ✅ **2 passed**（DDA-PROBE + ECS 删除未破坏等价性；D4 默认路径不变） |
| `tests/test_init_new_game.py`（新增 D4 回归） | ✅ **2 passed**：自定义开局 `sim.character.name == "测试"` 且 race/class 匹配；默认无参开局仍工作 |
| `tests/` 全量 | ✅ **4 passed** |
| `sim_core` 零 tkinter/pystray | ✅ grep **0 命中**（重申） |
| headless import 全扫描 | ✅ **38/38** 模块可导入（较 M1 少 2 = 已删 ECS 包） |

### 11.5 改动文件清单
| 文件 | 改动 |
| --- | --- |
| `src/sim_core/engine.py` | `_init_new_game` 增加 `race/char_class/name/seed` 参数 + 自定义完整重开分支（默认路径不变） |
| `src/sim_core/services/difficulty_service.py` | 删 `[DDA-PROBE]` 测试探针块 |
| `src/app/controllers/game_init.py` | `on_confirm` 接 `self.sim._init_new_game(...)` |
| `src/app/ecs/` | **删除**（休眠、零引用） |
| `tests/test_init_new_game.py` | 新增 D4 回归测试 |

### 11.6 Gate 1 收尾结论
**Gate 1 = PASS 维持**。三项收尾均纯 Python、headless 验证通过，未触及存档/Excel/data，未 git commit。D4 在不破坏 golden 等价性的前提下让角色创建对话框生效；音频/渲染/存档接线不变。可据此推进 **M2（Godot 4 引擎原型验证）**。

> **待审批随访**：是否授权在 `game_controller.py` 增加"新游戏"触发入口（建议 `<Key-n>` 或 UI 按钮），使 D4 对话框真正可被用户触达。
