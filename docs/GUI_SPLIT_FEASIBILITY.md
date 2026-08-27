# gui_app.py 拆分可行性分析

> 分析对象：`G:\project_root\gui_app.py`（当前 1262 行，单文件单类 `LordOfMysteriesGUI`）
> 目标：评估将其按职责拆分为 `gui/` 包的可行性与风险，并给出推荐结构。
> 结论先行：**可行，且强烈推荐**——代码已高度按"区域"内聚，拆分是低风险、增收益的工程改进。

---

## 1. 现状诊断

### 1.1 单文件内部构成（职责分布）

| 区域 | 行号（约） | 职责 | 行数占比 |
|---|---|---|---|
| 主题/常量 | 20–52 | `CLR` 配色、`TAROT_ICONS` 图标、字体路径 | ~3% |
| 模块导入 | 54–63 | 引入 `pathways_data / sequences / anchor / pollution / ascension / uniqueness / pathway_groups` | ~1% |
| 绘制辅助 | 70–110 | `pathway_sort_key`、`draw_rounded_rect`、`draw_gauge`、`group_key_of` | ~3% |
| 窗口骨架 | 104–393 | `__init__`、`_register_fonts`、`_build_ui/toolbar/left/center/right`、`_on_resize` | ~23% |
| 角色卡/仪表盘 | 398–574 | `set_character`、`refresh_all`、`_draw_character_card`、`_draw_gauges` | ~14% |
| 操作面板 | 575–709 | `_draw_action_panel`（扮演/晋升/切换/随机事件/权柄收集/旧日晋升） | ~11% |
| 操作逻辑 | 651–745 | `_do_action/_ascend/_switch/_random_event` + 高级机制 `_do_collect_*/_do_promote_old_one` | ~8% |
| 日志 | 746–791 | `add_log`、`_draw_log` | ~4% |
| 视图切换 | 793–977 | `switch_view`、`_draw_pathways_view`、`_draw_groups_view` | ~15% |
| 入口 | 994–1262 | `_wrap_text`、主入口 | ~2% |

### 1.2 核心痛点

1. **上帝类（God Object）**：`LordOfMysteriesGUI` 同时承担"窗口容器 + 主题 + 三视图渲染 + 操作面板渲染 + 操作逻辑 + 日志"六类职责，超 1200 行。
2. **渲染与逻辑耦合**：`_draw_action_panel` 既画按钮又通过 `tag_bind` 直接调用 `_do_*` 处理方法，视图与控制器混在一起；任何一处 UI 微调都要在巨型类里滚动定位。
3. **新人上手成本高**：想改"旧日晋升面板"要在一千多行里找 `_draw_old_one_panel` + `_do_promote_old_one`，二者物理距离远。
4. **测试只能走集成**：当前唯一 GUI 测试（`gui_advanced_flow`）必须构造真实 Tk 根，无法对单个面板/处理器做单元验证。

### 1.3 已具备的拆分利好（本次新增代码已"拆分就绪"）

本轮接入的"权柄收集 / 旧日晋升"代码，已刻意拆成**独立小方法**（`_draw_collection_panel`、`_draw_old_one_panel`、`_do_collect_seq1`、`_do_collect_uniqueness`、`_do_promote_old_one`、`_has_full_authority`、`_release_pathway_authority`、`_pathway_uniqueness`），彼此通过 `self.character / self.old_one_info` 这一明确状态通信——这正是拆分时迁移到 `controllers` 与 `panels` 的天然边界。

---

## 2. 推荐的目标结构

```
gui_app.py                 # 仅保留薄启动器（向后兼容）
   ↓
gui/
├── __init__.py            # 导出 LordOfMysteriesGUI
├── theme.py               # CLR / TAROT_ICONS / 字体路径 / _register_fonts
├── drawing.py             # draw_rounded_rect / draw_gauge / pathway_sort_key / group_key_of / _wrap_text
├── state.py               # GUIState：封装 character / old_one_info / event_log / view_mode（当前散落在实例字段）
├── app.py                 # LordOfMysteriesGUI：__init__ + _build_* + switch_view + refresh_all + set_character
├── panels/
│   ├── character_view.py  # _draw_character_card / _draw_gauges
│   ├── pathways_view.py   # _draw_pathways_view
│   ├── groups_view.py     # _draw_groups_view
│   ├── action_panel.py    # _draw_action_panel / _draw_collection_panel / _draw_old_one_panel
│   └── log_panel.py       # add_log / _draw_log
└── controllers.py         # _do_action / _do_ascend / _do_switch / _do_random_event
                           # + _do_collect_seq1 / _do_collect_uniqueness / _do_promote_old_one
                           # + _has_full_authority / _release_pathway_authority / _pathway_uniqueness
```

### 2.1 关键设计决策

- **引入 `GUIState` 中介对象**：把 `character / old_one_info / event_log / view_mode` 抽到 `state.py`。所有 panel 只读 `state.character`，所有 controller 只写 `state`——解除"面板直接持有根窗口、控制器直接吃根窗口字段"的环形依赖。
- **面板只画、控制器只动**：`panels/*` 收到 `(canvas, state, callbacks)`，用 `callbacks` 把按钮点击转交 `controllers`。这样面板可被**无头测试**（传入假 canvas + 录制 callback 调用）。
- **`gui_app.py` 保留为 launcher**（避免破坏 `run_gui.bat` 与既有文档）：
  ```python
  from gui.app import LordOfMysteriesGUI
  if __name__ == "__main__":
      LordOfMysteriesGUI().run()
  ```
- **字体注册 OS 相关逻辑**单独留在 `theme.py`，不与业务混。

---

## 3. 工作量与风险评估

| 维度 | 评估 |
|---|---|
| 静态工作量 | 约 1–1.5 人日：纯文件搬迁 + import 改写 + `self.`→`state.` 替换；无算法改动 |
| 技术风险 | **低**。无行为变更，仅重排；`refresh_all` 调用图保持稳定 |
| 主要风险点 | ① Canvas 重绘依赖 `winfo_width()` 等几何值，搬迁后需在 `__init__` 顺序上保证先 `pack` 再 `draw`；② `tag_bind` 闭包捕获的 `self` 在拆分后指向 controller 而非 panel，需改为显式传参；③ 字体加载的 ctypes 调用留在主线程 |
| 回归保障 | 已有 `gui_advanced_flow` 集成测试（收集→序列0→旧日 全链路）。**拆分后该测试必须仍 43/43 通过**方可合并 |
| 渐进式策略 | 不必一次性切：可先抽 `theme.py`+`drawing.py`（零行为影响），再抽 `panels`，最后抽 `controllers` 并引入 `GUIState` |

---

## 4. 结论与建议

1. **可行性：高**。职责边界清晰、依赖单向，拆分是"整理"而非"重写"。
2. **建议时机**：当前功能刚落地并验证通过，建议**在下一轮冻结期**做拆分，避免在活跃开发期并行改动导致冲突。
3. **执行顺序**：`theme/drawing` → `panels`（配无头测试）→ `controllers`+`GUIState` → 瘦身 `gui_app.py` 为 launcher。
4. **验收门槛**：`python tests/test_all.py` 维持 `PASS=43 FAIL=0 ERROR=0`，且新增 `panels/` 各自至少有 1 个无头渲染冒烟测试。

> **状态：已落地（2026-08-14）。** 按本方案实际执行了拆分，`gui_app.py`（原 1262 行上帝类）已瘦身为 11 行薄启动器，逻辑迁至 `gui/` 包。采用「mixin 组合 + 切片零转录」策略：所有方法体逐字节保留，仅调整归属与缩进；`GUIState` 经属性代理四个字段（`character / old_one_info / event_log / view_mode`），外部访问 `self.character` 等写法完全不变。
>
> **最终结构（与 2. 推荐结构一致）：**
> ```
> gui_app.py              # 11 行薄启动器：from gui.app import LordOfMysteriesGUI; .run()
> gui/
> ├── __init__.py        # 包入口 + 项目根 sys.path 引导
> ├── theme.py           # CLR / TAROT_ICONS / 字体路径 / register_fonts
> ├── drawing.py         # draw_rounded_rect / draw_gauge / pathway_sort_key / group_key_of / _wrap_text
> ├── state.py           # GUIState 运行时状态中介
> ├── app.py             # LordOfMysteriesGUI(ControllersMixin)：__init__/_build_*/switch_view/refresh_all/set_character + GUIState 属性 + _callbacks 字典；绘制方法为薄包装，转调 panels 自由函数
> ├── controllers.py     # 所有 _do_* 处理器 + _has_full_authority/_release_pathway_authority/_pathway_uniqueness
> ├── helpers.py         # 面板/控制器共享纯函数（如 get_pathway_uniqueness）
> └── panels/
>     ├── character_view.py  # draw_character_card / draw_gauges        —— 角色卡 / 仪表盘
>     ├── pathways_view.py   # draw_pathway_list / draw_pathways_view    —— 序列途径列表与全途径视图
>     ├── groups_view.py     # draw_groups_view                        —— 权柄体系（途径组）视图
>     ├── action_panel.py    # draw_action_panel / draw_collection_panel / draw_old_one_panel —— 操作/权柄收集/旧日晋升
>     └── log_panel.py       # add_log（写）/ draw_log（画）            —— 事件日志
> ```
>
> **验收（3. 回归保障 + 4. 无头冒烟）：** `python tests/test_all.py` → `PASS=44 FAIL=0 ERROR=0`（43 项原有 + 新增 `gui_panel_render` 逐面板无头渲染冒烟，仍走 GUI 薄包装方法）。`python tests/test_panels_suite.py` → `PASS=20 FAIL=0 ERROR=0`（各面板自由函数的完全独立单元测试：FakeCanvas + CallbackRecorder，覆盖 无角色/序列9/序列1/序列0 全状态与回调绑定）。两套合计 `PASS=64`。`run_gui.bat` 仍经 `python gui_app.py` 工作，向后兼容。`_register_fonts` 已迁为 `theme.register_fonts(root)` 并由 `__init__` 调用。
>
> **面板已是「接收 (canvas, state, callbacks) 的自由函数」：** 进一步把每个面板从 mixin 方法改为无 self 的 `draw_*(canvas, state, callbacks)`——`state` 提供 character / old_one_info / fonts / pathway_items / event_log，`callbacks` 是 `{动作名: 处理器}` 字典（由 `app._callbacks()` 把点击映射到 `ControllersMixin._do_*`）。因此 `tests/test_panel_*.py` 可用 FakeCanvas + CallbackRecorder 在无 Tk 环境下逐面板、逐状态覆盖，验证「面板确实渲染且绑定了正确回调」。日志拆为 `add_log(state,msg)`（纯状态）与 `draw_log(canvas,state)`（纯绘制）。`GUIState` 通过属性代理实现，未改任何对 `self.character` 等的外部访问。
