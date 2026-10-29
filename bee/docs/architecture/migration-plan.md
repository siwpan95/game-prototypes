# BeeIdleRPG 引擎迁移计划（B/C 路线 · Gate 0 签核后执行）

| 字段 | 内容 |
| --- | --- |
| **文档 ID** | migration-plan |
| **关联 ADR** | ADR-0001（Decision: SIGNED-OFF 采纳 B/C，前置=先抽 sim_core） |
| **日期** | Gate 0 签核后 |
| **作者** | eng-lead-adr（工程负责人 / 主程序） |
| **路线** | 高风险路径：迁移 Godot 或 Unity，但**强制前置**先抽 `sim_core` |
| **约束** | 本文档与 sim_core 抽取 spike 阶段**只动文档与新增独立包**；不修改 `src/` 现有游戏源码逻辑语义、不 git commit，直到 Gate 1 评审通过 |

> 本计划是 ADR-0001 签核后的**执行蓝图**。核心纪律：**先抽 `sim_core`（纯 Python、可 headless 测试），再评桥接**。绝不在模拟层未解耦之前动手重写或桥接——否则将触发 ADR 的 R1/R5/R6 高风险。

---

## 1. 引擎选型建议（Godot vs Unity）

### 推荐：**优先 Godot 4（GDScript）**，Unity（C#）作为备选。

### 理由（结合本项目 87% 纯 Python 模拟的事实）
1. **模拟层是 Python，且将被托管而非重写**：本项目约 8,319 行（87%）纯 Python 模拟/内容逻辑，按 ADR 纪律应**尽量保留**（避免 R1 语义漂移、R5 一人团队停滞）。Godot 的 **GDExtension + Python 绑定**（如 `godot-python` / `pybind11` 包装）或**子进程 + IPC** 托管现有 Python `sim_core` 的路径，比 Unity 更直接——Unity 没有官方 Python 宿主，整体重写 C# 的概率更高（违反纪律）。
2. **GDScript vs C#**：GDScript 语法近似 Python，若未来确有少量引擎侧逻辑需脚本化，团队（已是 Python 栈）上手成本远低于 C#；Unity 的强项（C# 生态/资产商店/IL2CPP）对"零操作文字挂机"品类是过度配置。
3. **场景/UI 工具**：Godot 的场景树 + Control 节点做文字/日志 UI 比 Tkinter Canvas 更结构化，且导出管线天然跨平台（Windows/Linux/macOS/Web/移动），对应"未来扩展性"这一迁移真实收益。
4. **打包体积与一人团队**：Godot 导出体积极小、编辑器一体化；Unity 构建更重、概念更庞杂，单人维护成本更高（R5）。

### 桥接可能性提示（关键）
- **GDExtension 托管 Python**：把 `sim_core` 编译/包装为 GDExtension，Godot 主循环每帧调用 `sim_core.tick(dt)`，Godot 仅负责渲染 `sim_core` 产出的日志/状态。避免整体重写。
- **子进程 + IPC**：`sim_core` 作为独立 Python 进程，经管道/共享内存/本地 socket 与 Godot 通信。隔离最彻底，但 20 FPS 高频日志序列化引入延迟与复杂度（R6）。

> **选型裁定**：先以 Godot 4 为目标做原型验证（里程碑 M2）；最终桥接方式在 `sim_core` 就绪后于 M2 定夺。Unity 仅当 Godot 在跨平台/特定表现上不满足时启用。

---

## 2. sim_core 抽取范围与成功标准

### 2.1 抽取范围（新建独立包 `src/sim_core/`）
将以下内容迁入 `src/sim_core/`，**全部纯 Python、零 `tkinter`/`pystray` 依赖、可被 `pytest` headless 直接 import 与运行**：

| 来源 | 文件 | 处理方式 |
| --- | --- | --- |
| 编排循环 | `src/app/controllers/game_controller.py` 的 `_update_game(self, dt)`（:181-307）及其调用的内部编排逻辑 | **移动**（非重写）到 `sim_core/engine.py` 的 `SimCore.update(dt)`；`self._add_log` 改为向 `sim_core` 自有日志缓冲（如 `deque`）追加；`self.audio.*` 调用改为发布"音频事件"到事件队列，由前端消费 |
| 服务层 | `src/app/services/` 全部 19 个 service（`combat_service` 26KB、`difficulty_service` 30KB、`excel_service` 44KB、`audio_service`/`audio_engine`/`audio_presets`、`quest/castle/dungeon/event/item/potion/recipe/rest/town/world/achievement/artifact/data` 等） | **原样移动**到 `sim_core/services/`；已验证零 UI 引用（ADR 1.5 Grep 零命中），几乎无改动 |
| 模型层 | `src/app/models/` 6 个（`character`/`item`/`dungeon`/`potion`/`quest`/`world`） | **原样移动**到 `sim_core/models/` |
| 数据池 | `src/json_pool.py` | **移动**到 `sim_core/data/json_pool.py`（运行期只读 JSON，见 ADR 1.3） |
| 配置/日志工具 | `src/config/settings.py`、`src/app/utils/logging_config.py` | 移入 `sim_core/config/` 与 `sim_core/utils/`（settings 中 `FPS`、`REGION_CHANGE_INTERVAL` 等是模拟参数，属 sim_core；`WINDOW_WIDTH/HEIGHT` 等是 UI 参数，留在前端） |
| ECS（可选） | `src/app/ecs/__init__.py`（238 行，当前休眠、零引用） | **移动**到 `sim_core/ecs/`，择机决定是否接入（不强制） |

### 2.2 明确**不**动（留在 Tkinter 前端，不改写）
- `src/app/controllers/game_render.py`（422 行 Canvas 文本/日志绘制）
- `src/app/controllers/game_init.py`（310 行角色创建对话框）
- `src/app/controllers/game_tray.py`（144 行 pystray 托盘）
- `src/app/controllers/game_controller.py` 的 `_build_ui`/`_on_resize`/`_on_split_*`/`_on_close`/`_on_minimize` 及键盘绑定（:112-170, :122-126）——这些是 Tkinter 胶水，迁移前保持不变
- `main.pyw`（Tkinter 入口）
- `src/` 下任何业务语义代码在抽取阶段**只改 import 路径、不改逻辑**

### 2.3 20 FPS 主循环如何改为由 sim_core 驱动
- **现状**（`game_controller.py:172-179`）：`root.after(50, _game_loop)` → 每帧 `_update_game(dt)` + `_redraw()`，循环由 Tkinter 事件循环驱动。
- **目标**：sim_core 自带**与 UI 无关的定时驱动**。两种落地：
  1. **headless 模式**（测试/服务器）：`while running: dt = clock.tick(1/20); sim_core.update(dt)`（可用 `time` 或 `pytest` 手动喂 `dt`）。
  2. **前端模式**（Tkinter/Godot/Unity）：前端每帧以 `dt≈0.05s` 调用 `sim_core.update(dt)`，再读取 `sim_core` 的状态快照与日志缓冲做渲染。循环归属前端，sim_core 不持有任何时钟/UI 引用。
- 关键契约：`SimCore.update(dt)` 是**纯函数式推进**——输入 `dt` 与内部状态，输出状态变更 + 日志/音频事件队列；不调用 `tk`、`pystray`、`canvas`。

### 2.4 成功标准（Gate 1 验收）
1. `import sim_core` 不触发任何 `tkinter`/`pystray`/GUI 导入（用 `pytest` 在 headless 环境验证，可 `import tkinter` 被禁或 mock）。
2. 现有 `_update_game` 的全部行为可经 `SimCore.update(dt)` 复现：给定相同初始存档 + 相同 `dt` 序列，产出**逐字节一致的日志序列与状态变更**（提供 golden-test 夹具，回归 ADR R1 语义漂移）。
3. `services/`+`models/`+`json_pool` 全量 `pytest` headless 用例通过（Phase 6 测试覆盖目标）。
4. `game_controller.py` 缩减为"薄前端"：仅持 `SimCore` 实例 + 渲染 + 输入胶水，不再含模拟编排。
5. 存档 `save.json` 的 `to_dict`/`from_dict` schema 不变（ADR R2）。

---

## 3. 桥接方案评估（M2 定夺，强烈建议避免整体重写）

| 方案 | 代价 | 适配度 | 评价 |
| --- | --- | --- | --- |
| **A. GDExtension 托管 Python** | 中：需包装 `sim_core` 为 GDExtension（C++/pybind 或 godot-python），处理 Python GIL 与 Godot 线程 | ★★★★☆ | **首选**。保留全部 Python 领域逻辑，Godot 仅渲染；最贴合 87% 纯 Python 事实 |
| **B. 子进程 + IPC** | 中–高：序列化开销、20 FPS 日志高频传递的延迟、进程生命周期管理 | ★★★☆☆ | 隔离最彻底，但本作文字挂机无需此隔离，R6 复杂度不划算；仅当 A 不可行时降级使用 |
| **C. 整体重写 GDScript/C#** | **极高**：~8,319 行领域逻辑重表达，语义漂移、回归难、一人团队停滞（R1/R5） | ★☆☆☆☆ | **强烈避免**。违反 ADR 纪律；仅在 sim_core 无法被托管时（几乎不可能）才考虑 |

> 裁定原则：**桥接而非重写**。无论选 Godot 还是 Unity，目标都是让 `sim_core`（纯 Python）作为"模拟内核"被宿主调用，宿主负责 UI/循环/音频。`sim_core` 抽好后，C 方案风险已被消除，A/B 二选一即可。

---

## 4. 里程碑 / 分阶段

- **M0 · 准备（文档）**：ADR-0001 签核、本计划定稿、Gate 1 验收标准明确。（已完成）
- **M1 · sim_core spike（强制前置）**：抽 `src/sim_core/`，跑通 headless `SimCore.update(dt)` + golden-test 复现 `_update_game` 行为；产出 `sim_core` 抽取成本实测与覆盖率报告。**这是 Gate 1 的输入**。
- **M2 · 引擎原型验证**：以 Godot 4 为目标，建最小场景（日志文本框 + 状态面板），用 GDExtension（或子进程）托管 `sim_core`，跑通"前端每帧喂 dt → sim_core 推进 → 渲染日志/状态"。验证桥接延迟与跨平台导出。定夺桥接方式（A/B）。
- **M3 · 内容/存档迁移**：JSON 内容池与 `save.json` 直接复用（ADR R2/R3，几乎零成本）；Excel→JSON 导出器保留在构建期；音频管线按宿主重做（R7）。
- **M4 · 切换发布**：双轨并行（Tkinter 旧前端 + 引擎新前端）一段时间，验证一致后切换默认入口；保留 Tkinter 前端作为回退，直至新前端稳定。更新 PyInstaller/引擎导出 CI。

---

## 5. 明确声明：哪些不动

- **`save.json` 存档格式**：引擎无关 JSON，schema 冻结 + 版本号，跨 Tkinter/Godot/Unity 直接复用（ADR R2）。
- **`data/` 存档目录与运行数据**：不迁不分叉，`sim_core` 仍读写同一目录。
- **Excel 配置**：保持 `excel_to_json.py`/`excel_service.py` 在构建期产出 JSON；**不逐表手工迁移**（ADR R3 风险被高估的澄清）。
- **24 张表 JSON**：运行期内容即 JSON 池（`src/resources/data`），原样复用；仅做完整性/冗余审计（Phase 6 资产审计），不改结构。
- 上述资产在 M1–M4 全程保持不变，确保"先打磨"与"迁移"可并行不破坏现有玩家数据。

---

## 6. 已知风险与缓解（引用 ADR R1–R8）

| 风险 | 缓解（本计划对应动作） |
| --- | --- |
| **R1** Python↔引擎语言边界（~8,319 行重写风险） | M1 抽 `sim_core` + M2 桥接（A/B）而非重写（C）；golden-test 防语义漂移 |
| **R2** 存档格式兼容 | `save.json` schema 冻结 + 版本号，全程不动（§5） |
| **R3** 24 张 Excel 配置迁移 | 运行期只读 JSON，Excel 构建期保留；不手工迁移（§5） |
| **R4** 构建/分发变化 | M4 双轨并行 + 新 CI；Tkinter 前端留作回退 |
| **R5** 一人团队维护成本 | 优先 Godot（轻量）；sim_core 保留 Python 知识资产；避免 C# 重写 |
| **R6** 混合桥接 IPC 额外风险 | 首选 GDExtension（A）而非子进程 IPC（B）；文字挂机无需重隔离 |
| **R7** 音频系统（Python 专属） | M3 按宿主重做音频（44KB 音频代码部分返工），sim_core 仅发"音频事件" |
| **R8** 上帝对象（game_controller 绑死 UI） | **M1 直接解决**：`_update_game` 迁入 `sim_core`，`game_controller` 退化为薄前端 |

---

## 7. 下一步（Gate 1 输入）
M1（sim_core spike）是强制前置闸门。建议第一个里程碑动作与切入点见回传 team-lead 的消息。完成后以 M1 报告（抽取成本实测、headless 测试覆盖、golden-test 复现率）作为 **Gate 1 评审**材料。
