# ADR-0001：游戏技术基座与引擎迁移决策（Gate 0 · 架构决策门）

| 字段 | 内容 |
| --- | --- |
| **ADR ID** | ADR-0001 |
| **标题** | 引擎迁移 vs 维持 Python/Tkinter 技术基座 |
| **状态** | 已签核（SIGNED-OFF） |
| **日期** | 2025-07（Gate 0） |
| **作者** | eng-lead-adr（工程负责人 / 主程序） |
| **评审强度** | Full（每道质量门严格 PASS / CONCERNS / FAIL） |
| **关联门控** | Gate 0 · 架构决策门（P0 阻塞质量门） |
| **决策字段** | **SIGNED-OFF — 用户签核采纳 B/C 迁移 Godot/Unity；前置条件=先抽 sim_core（ADR 风险 R1/R8 要求），再评具体桥接方案** |

> **本文档仅做评估与推荐，不含任何迁移代码、新引擎骨架或对现有源文件的修改。** 全部结论均基于对 `D:\allin\right\bee` 现有代码的实际阅读（见各章节引用文件名/行号）。

---

## 0. 摘要（TL;DR · 给主理人与用户）

BeeIdleRPG 是一款 **Progress Quest 风格、玩家零输入的文字挂机 RPG**。通过实际阅读代码确认：**项目约 9,570 行 `src/` 源码中，约 8,319 行（~87%）是引擎无关的纯 Python 模拟/内容生成逻辑，仅约 1,251 行（~13%，集中在 4 个 controller + `main.pyw`）绑定 Tkinter/pystray**。运行时内容来自 **JSON 池**（`src/json_pool.py`）而非 Excel，存档是 **引擎无关的 JSON**（`save.json`）。

证据指向一个工程结论：**当前模拟核心已经事实解耦，产品价值的绝大部分存在于纯 Python 逻辑中。对"零操作文字挂机"这一品类，游戏引擎（Godot/Unity）的渲染/场景/物理/着色器能力几乎全部用不上；迁移引擎意味着把约 8,319 行已工作的领域逻辑用 GDScript/C# 整体重写，或引入子进程/IPC 桥接——对一人团队是高风险、低回报的动作。**

因此本 ADR 推荐 **方案 A（维持 Python/Tkinter，可选抽取 `sim_core`，把精力投向 Phase 6 打磨）**；方案 B/C（整体迁移 Godot/Unity）**当前不推荐**；方案 D（仅换 UI 框架）收益不足以覆盖其成本。用户"先打磨 + 迁移引擎"两项选择在该品类下互斥，正确解法是 **先打磨（低风险的 A 路线），把"是否迁移引擎"作为未来触发式决策保留**。

---

## 1. 现状架构摘要

### 1.1 技术栈
- **语言/运行时**：Python 3.8+（CPython）。
- **UI**：标准库 `tkinter` + `tk.Canvas`（文本/日志/分隔条绘制），`pystray`（系统托盘）。
- **音频**：`numpy` + `scipy` 程序化合成，`sounddevice` 实时播放（纯 Python 音频管线，非引擎音频）。
- **内容配置**：`openpyxl` 读取 Excel（**构建期**），`json`（**运行期**）由 `src/json_pool.py` 单例池按需加载。
- **存档**：JSON（`save.json`，引擎无关序列化）。
- **打包**：PyInstaller（`BeeIdleRPG.spec` + `build_exe.py`），输出 Windows exe，Excel/JSON 资源外放至 `dist/resources/`。
- **架构风格**：MVC + Mixin 控制器拆分；含一个轻量 ECS 包 `src/app/ecs/__init__.py`（`__init__.py` 约 238 行）。

### 1.2 模块划分与代码规模（`src/` 共 9,570 行）

| 分层 | 目录/文件 | 规模 | 引擎耦合 |
| --- | --- | --- | --- |
| **模拟/服务层** | `src/app/services/`（19 个 service：`combat_service` 26KB、`difficulty_service` 30KB、`excel_service` 44KB、`audio_*` 44KB、`quest/castle/dungeon/event/item/...`） | ~270 KB | **零 Tkinter**（已验证） |
| **模型层** | `src/app/models/`（6 个：`character.py` 31KB 最大、`item/dungeon/potion/quest/world`） | ~73 KB | **零 Tkinter**（已验证） |
| **数据/工具** | `src/json_pool.py`、`src/app/utils/logging_config.py` | ~10 KB | 无 |
| **ECS 层** | `src/app/ecs/__init__.py` | 8 KB / ~238 行 | 无，但 **当前无引用（休眠）** |
| **控制器/UI 层** | `game_controller.py`(306)、`game_render.py`(422)、`game_init.py`(310)、`game_tray.py`(144)、`main.pyw`(69) | **1,251 行** | **绑定 Tkinter/pystray** |
| **总计** | | **9,570 行** | UI 耦合占比 ~13% |

> 规模数字来源：`find src -name "*.py" | xargs wc -l` → 9,570 行；UI 层各行数由 `wc -l` 实测（306+422+310+144+69=1,251）。

### 1.3 内容驱动方式（关键澄清）
- **运行期只读取 JSON 池**，不读 Excel。证据：`src/json_pool.py` 文件头注释明确写明"**只读 JSON，不读 Excel（Excel→JSON 由 excel_to_json.py 构建阶段完成）**"；`src/app/services/data_service.py:7,17` 通过 `from src.json_pool import get_pool` / `get_pool()` 取数据。
- Excel 是**构建期内容创作工具**：`excel_to_json.py`、`gen_new_excels.py`、`excel_service.py`(44KB) 把约 24 张配置表（种族/职业/装备/任务/敌人/神器/词缀/元素反应/阵营/技能…）转成 JSON 放入 `src/resources/data`，再由 `build_exe.py` 的 `EXTERNAL_RESOURCES` 外放至 `dist/resources/config/sheets` 与 `dist/resources/data`。
- **推论（用于风险章节）**：所谓"24 张 Excel 配置如何迁移"在很大程度上是**误述**——运行期不依赖 Excel，迁移时只需保留纯 Python 的 Excel→JSON 导出器（继续在构建期跑），或在目标引擎构建期重新生成 JSON。内容迁移风险被显著高估。

### 1.4 构建/发布现状
- 入口 `main.pyw`：初始化 `sys.path`、设置崩溃钩子、`tk.Tk()` 创建根窗口、`GameController(root)`、`root.mainloop()`（`main.pyw:51-65`）。
- 主循环驱动在 UI 线程：`game_controller.py:172-179` 的 `_game_loop` 用 `self.root.after(50, self._game_loop)`（即 20 FPS，与 `settings.py:16 FPS=20` 一致）；每帧 `self._update_game(dt)`（模拟）后 `self._redraw()`（UI 绘制）。
- `BeeIdleRPG.spec` 的 `hiddenimports` 含 `pystray/win32gui/PIL/openpyxl/numpy/scipy/sounddevice`——这些是与 UI 框架**正交**的第三方库（音频/Excel/托盘），与 Tkinter 无强绑定。

### 1.5 ★ 模拟逻辑 vs UI 渲染的边界（本 ADR 的命门）
这是判断迁移代价的根本。实际阅读结论：

1. **模拟/内容逻辑已事实解耦于 UI**。对 `src/app/services/` 与 `src/app/models/` 全量 Grep（模式 `tkinter|tk\.|Canvas|messagebox|pystray|Tk\(\)|GameController`）**零命中**；`combat_service.py:19` 仅 `from ..models.item import Weapon, EquipmentSlot`，无任何 UI 引用。即 **19 个 service + 6 个 model ≈ 价值主体，可原样在任意宿主运行**。

2. **UI 耦合高度集中在 4 个控制器文件**：
   - `game_render.py`（422 行）：全部 `tk.Canvas.create_text/rectangle/line` 文本与日志绘制。
   - `game_init.py`（310 行）：`tk.Toplevel/Frame/Label/Entry/Radiobutton/Button` 角色创建对话框。
   - `game_tray.py`（144 行）：`pystray` 托盘。
   - `game_controller.py`（306 行）：**上帝对象**——混合了模拟编排（`_update_game`, `:181-307`）与 UI 胶水（`_build_ui`, `:112-128`；`_on_resize/_on_split_*/_on_close/_on_minimize`, `:129-170`；键盘绑定 `:122-126`）。其中 `_update_game` 本身只是**按顺序调用各 service 的 `tick()`/`update()`**，逻辑是纯 Python，仅通过 `self._add_log(...)`（向 `self.log_messages` 列表追加文本）和 `self.audio.*`（音频 service）回写——这两处都非 UI 原语，可无损迁移到 `sim_core`。

3. **存档与内容已是引擎无关格式**（见 1.3、1.4 及风险章节），进一步降低迁移/保留的切换成本。

> **架构体检结论**：当前唯一结构性缺陷是 `game_controller.py` 的"上帝对象"把模拟编排与 Tkinter 循环绑死（违反单一职责）。但这是**指向"抽取 sim_core"的重构信号，而非"迁移引擎"的信号**——因为解耦点本身已经存在（service/model 层）。

---

## 2. 候选方案

### 方案 A — 维持 Tkinter 现状（推荐附加：抽取引擎无关的 `sim_core` 纯 Python 包）
- **做法**：保持 Python 3.8+ / Tkinter 栈不变。将 `game_controller.py` 中的 `_update_game` 编排循环 + 全部 `services/` + `models/` + `json_pool` 抽为独立的 `src/sim_core/`（纯 Python、零 UI 依赖、可被 `pytest` 直接 headless 测试）。`controllers/` 仅保留 Tkinter 渲染与输入胶水，作为 `sim_core` 的一个"前端"。UI 对当前品类（文字/日志）充分够用，可不改。
- **受益**：**零模拟逻辑重写**；保留团队已积累的约 8,319 行领域知识；直接服务于用户所选的"先打磨"（Phase 6：测试/性能/资产审计）；`sim_core` 抽离后反而**为未来任何引擎迁移铺平道路**（届时只需重写 ~1,251 行 UI，而非 ~8,319 行模拟）。

### 方案 B — 迁移到 Godot（GDScript）
- **做法**：用 Godot 4 场景/节点做 UI 与主循环；模拟逻辑要么**整体重写为 GDScript**，要么走 **GDExtension（C++/Python 绑定，重）** 或 **子进程 + IPC（Python 模拟跑在外部，Godot 只渲染）**。
- **受益**：跨平台导出（含移动端/Web）、内置编辑器/场景工具、未来可上 GPU 粒子/着色器做更丰富表现。

### 方案 C — 迁移到 Unity（C#）
- **做法**：同理，模拟逻辑整体重写为 C#（或 IL2CPP + 外部 Python 子进程）。
- **受益**：生态/资产商店最大、C# 类型系统强、未来扩展天花板最高；但打包体积与学习曲线最重。

### 方案 D — 维持 Python，仅替换 UI 框架（PyQt6 / textual / 浏览器）
- **做法**：保留全部 `services/`+`models/` 纯 Python 不变，仅把 ~1,251 行 Tkinter UI 重写为 PyQt6（桌面富控件）或 `textual`（终端 TUI）或浏览器（HTML/JS 前端 + Python 后端 WebSocket）。
- **受益**：模拟零风险保留；若想获得更好排版/可访问性/跨桌面，是比 B/C 轻得多的升级路径。

---

## 3. 各方案成本-收益矩阵

> 行数口径：A 的"重写"仅指可选的 `sim_core` 边界抽取（移动而非重写）；B/C 的"重写"含模拟整体转语言或 IPC 桥接；D 的"重写"仅 UI 层。

| 维度 | A. 维持 Tkinter + 抽 sim_core | B. 迁移 Godot | C. 迁移 Unity | D. 换 UI 框架 |
| --- | --- | --- | --- | --- |
| **模拟逻辑重写量** | ~0 行（仅抽取 ~150–300 行编排） | ~8,319 行转 GDScript **或** IPC 桥接 | ~8,319 行转 C# **或** IPC 桥接 | 0 行 |
| **UI 重写量** | 0（如需可不动） | ~1,095 行（render/init/tray/glue） | ~1,095 行 | ~1,095 行 |
| **可复用资产** | 全部 9,570 行（仅重排） | 仅 JSON 内容 + 存档格式；Excel 导出器（Python）保留 | 同 B | 全部模拟 8,319 行 + JSON + 存档 |
| **被丢弃/搁置资产** | 无（ECS 休眠层可顺手启用或删） | Tkinter UI、Python 音频管线需重做；pystray 逻辑改 Godot 托盘 | 同 B + 更重 | Tkinter UI 1,251 行 |
| **对"零操作文字挂机"品类的实际收益** | 直接（测试/性能/内容可维护性↑） | 极低（品类无渲染需求；收益在跨平台/未来扩展，属投机） | 极低（同 B，且更重） | 低–中（仅当想要更好排版/可访问性时） |
| **音频系统影响** | 无（保留 numpy/scipy/sounddevice） | 需改用 Godot AudioStream（44KB 音频代码部分返工） | 需改用 Unity Audio（部分返工） | 无 |
| **构建/分发变化** | 无（PyInstaller 不变） | 改 Godot 导出管线（跨平台，但需重搭资源流） | 改 Unity 构建（更重） | 无（或加 Web 服务） |
| **一人团队维护成本** | 最低（沿用已熟栈） | 高（学引擎 + 重写模拟 + 内容管线重搭） | 最高 | 低–中 |
| **切换风险** | 低 | 高（领域逻辑重写易出语义漂移） | 高 | 中（仅 UI 风险） |
| **适合度（本品类+本团队）** | ★★★★★ | ★★☆☆☆ | ★☆☆☆☆ | ★★★☆☆ |

**诚实补充**：该品类渲染需求极低（文本 + 滚动日志 + 简单分隔条），Godot/Unity 的 **场景图 / 物理 / 着色器 / 3D / GPU 粒子** 能力在本作中**几乎全部闲置**。引擎迁移的"真实收益"集中在 **工具链 / 跨平台 / 未来扩展性**，而非玩法或当前体验。而这三项目前均非用户痛点（用户自己选了"先打磨"= 解决测试/性能/资产，而非扩平台/加表现）。

---

## 4. 风险与缓解

| 风险 | 严重度 | 说明（含证据） | 缓解 |
| --- | --- | --- | --- |
| **R1 Python↔引擎语言边界** | 高（仅对 B/C） | 全量模拟 ~8,319 行纯 Python。B/C 若整体重写，领域知识（战斗/难度 DDA/词缀/元素反应/任务）需 GDScript/C# 重表达，易语义漂移、回归难。 | 若坚持迁移，应走 **A 先抽 sim_core → 再用 GDExtension/子进程 托管 Python**，避免语言重写；但 IPC 引入下述 R6。 |
| **R2 存档格式兼容** | 低 | `save.json` 由 `to_dict()` 序列化（`game_io.py:69-87`），引擎无关；字段含 `character/party/game_time/world_seed/*_service` 快照。 | **非阻塞**。任何方案均直接复用；若重写 service，必须冻结 `to_dict/from_dict` schema（加版本号字段）做向后兼容。 |
| **R3 24 张 Excel 配置迁移** | 低（被高估） | 运行期只读 JSON（`json_pool.py` 注释）；Excel 是构建期工具。 | 保留 `excel_to_json.py`/`excel_service.py`（纯 Python）继续在构建期产出 JSON；目标引擎构建期重跑导出器即可。**无需逐表手工迁移**。 |
| **R4 构建/分发变化** | 中 | PyInstaller → Godot 导出 / Unity IL2CPP，资源流与签名不同。 | 仅 B/C 涉及；需新建 CI 与资源管线，单人团队负担重。 |
| **R5 一人团队维护成本** | 高（仅对 B/C） | 重写 + 学引擎 + 内容工具重搭，极易停滞。 | 现状 Python 栈是团队已积累资产；优先 A。 |
| **R6 混合桥接（Python 子进程 + 引擎渲染）的额外风险** | 高 | "保留 Python 模拟、引擎只渲染"需 IPC（管道/共享内存/网络）。本作 20 FPS、日志高频追加，IPC 序列化开销与延迟对**文字挂机**无意义，且复杂度陡增。 | **不建议**为本品类引入桥接；若要做，等价于 D（换 UI）更便宜。 |
| **R7 音频系统** | 中 | `numpy/scipy/sounddevice` 程序化音频（44KB）是 Python 专属。B/C 需改引擎音频；D 保留。 | B/C 时音频需部分返工；A/D 零影响。 |
| **R8 现有架构气味（上帝对象）** | 中 | `game_controller.py` 把模拟编排与 Tkinter 绑死（1.5 节）。 | **无论选哪个方案都应修**：A 路线下抽 `sim_core` 即解决；这是"先打磨"范围内的技术债清理，不是迁移理由。 |

---

## 5. 推荐（ADR 结论）

### 推荐项：**方案 A — 维持 Python/Tkinter 技术基座，并抽取引擎无关的 `sim_core`；把资源投向 Phase 6（测试/性能/资产审计）。**

### 理由（证据链）
1. **价值主体已解耦**：9,570 行中 ~8,319 行（87%）纯 Python、零 UI 引用（1.5 节 Grep 零命中）。迁移引擎不会"提升"这部分，只会"重写"或"桥接"它——对零输入文字品类无玩法增益。
2. **品类不需引擎能力**：本作渲染仅为文本+日志（1.4 节 20 FPS Canvas 文本绘制），Godot/Unity 的渲染/物理/着色器能力闲置；引擎迁移的真实收益（跨平台/工具链/未来扩展）非当前痛点，且属投机。
3. **迁移代价与团队规模错配**：B/C 需重写 ~8,319 行领域逻辑或引入 IPC（R1/R5/R6），对一人团队是高停滞风险；D 仅换 UI，但 Tkinter 对本品类够用，收益不足覆盖成本。
4. **"先打磨 vs 迁移引擎"的互斥被证据化解**：二者并非真矛盾——因为模拟已解耦，正确的"先打磨"就是 **在现有 Python 栈上做 A 路线（含抽 `sim_core` 清理上帝对象）**。这既满足用户"先打磨"的诉求，又**为未来可能的引擎迁移预留了最小代价的切换点**（届时只重写 ~1,251 行 UI）。
5. **内容/存档风险被高估**：运行期 JSON（`json_pool.py`）+ 引擎无关 `save.json` 使内容与存档迁移近乎零成本（R2/R3）。

### 直面用户两项选择的裁决
- "**先打磨**" → 采纳，落地为 A 路线下的 Phase 6（测试覆盖、性能剖析、24 表资产审计、抽 `sim_core` 清理技术债）。
- "**迁移引擎**" → **当前不执行**。降级为"**触发式未来决策**"：仅当出现明确信号（如：需移动端/Web 跨平台、需富媒体表现、或 Tkinter 出现不可逆阻塞）时，再基于已抽离的 `sim_core` 做 B/D 评估。届时模拟层可原样复用，重写面仅为 UI。

> 结论不迎合"迁移引擎"的字面选择，而基于代码实情：**保留并打磨 Python 栈，是确定性的低风险高回报；迁移是投机的高风险动作。** 最终拍板权在用户。

---

## 6. 决策记录

- **Decision**：`SIGNED-OFF — 用户签核采纳 B/C 迁移 Godot/Unity；前置条件=先抽 sim_core（ADR 风险 R1/R8 要求），再评具体桥接方案`
- **签核结论（用户裁决议）**：用户已签核采纳 B/C（迁移 Godot/Unity）高风险路径。本 ADR 原推荐 A；但按自身风险计划（R1/R8），采纳 B/C 的**强制前置条件**是先抽取引擎无关的 `sim_core`（这同时是"先打磨"范围内的上帝对象清理 R8），待 `sim_core` 就绪后再评估具体桥接方案（GDExtension / 子进程 IPC / 整体重写，见 `migration-plan.md`）。即：模拟层要先可 headless 独立运行与测试，迁移面才能收敛到仅 UI。
- **若签核 A（采纳）的后果（Consequences）**：
  - 正面：零模拟重写、保留领域资产、直接改善测试/性能/可维护性；`sim_core` 抽离后未来迁移成本降至仅 UI 层。
  - 负面/代价：Tkinter 表现力上限低（对本品类无影响）；需投入少量精力做 `sim_core` 抽取与测试基建。
  - 下一步门控：进入 **Phase 6 打磨**，先产出测试/性能/资产审计报告（建议作为 Gate 1 输入）。
- **若签核 B/C（迁移）的后果（Consequences）**：
  - 正面：跨平台/未来扩展潜力。
  - 负面/代价：~8,319 行模拟重写或 IPC 桥接、音频返工、构建管线重搭、一人团队高停滞风险；且对当前品类无玩法增益。强烈建议先做 A 的 `sim_core` 抽取再评估。
- **若签核 D（换 UI）的后果（Consequences）**：模拟零风险保留；仅 UI 层重写 ~1,095 行；仅在确有排版/可访问性/跨桌面需求时值得。

### 建议的下一步门控（Gate 1 输入）
1. **Phase 6 打磨启动**：测试（为 `services/` 补 `pytest` headless 用例）、性能（20 FPS 主循环剖析、内存/日志上限 `MAX_LOG_ENTRIES=500` 审计）、资产审计（24 表 JSON 完整性/冗余）。
2. **`sim_core` 抽取 spike**（≤ 小迭代）：验证 `game_controller._update_game` + `services/` + `models/` 可脱离 Tkinter 独立运行与测试，量化抽取成本。
3. **品类扩展信号监测**：若后续出现跨平台/富媒体需求，再触发 B/D 重评，届时因 `sim_core` 已就绪，迁移面仅剩 UI。

---

*本文档为 Gate 0 架构决策门产出，仅含评估与推荐，未创建任何迁移代码、未修改现有源文件。所有论断均引用具体文件名与行号，可供主理人与用户回溯核验。*
