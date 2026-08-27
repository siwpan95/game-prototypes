# 代码风格与规范（STYLE_GUIDE）

> 适用范围：text_fps_zh 全部 Python 代码。
> 当前状态：项目**尚无 black / 任何格式化器或 lint 配置**。本规范定义「目标态」——**新代码必须遵守**，存量代码随改动逐步靠拢。

## 1. 核心原则

- 可读性优先，风格统一只是手段。
- **新代码必须加类型注解**（见 §3）——这是当前最该补的缺口（审查指出 `execute_enemy_turn` 的 `room`、`use_item` 的 `combat_system` / `enemies` 等多处缺注解）。
- **「导入即崩」类 bug 应通过 CI 导入冒烟门禁预防，而非靠人肉 review**：典型如漏写 `from typing import Dict` 导致下游 `NameError`，由 `scripts/import_smoke.py` 在 CI 拦截（见 §5）。

## 2. 模块分层约定

依赖方向（自上而下，禁止反向 / 循环）：

| 层 | 目录 | 职责 | 允许依赖 |
|----|------|------|----------|
| 入口 | `main.py` | 编排游戏循环，组装各系统 | 所有层 |
| UI | `ui/` | pygame 渲染、面板、字体加载 | `core`, `models`, `data` |
| 系统 | `systems/` | 战斗 / 移动 / 背包 / 潜行等业务逻辑 | `core`, `models`, `data` |
| 模型 | `models/` | 实体（敌人 / 武器 / 物品） | 仅标准库 + `typing` |
| 数据 | `data/` | 敌人 / 武器 / 关卡 等静态模板 | `models` |
| 核心 | `core/` | 游戏状态、常量、事件总线 | `models` |
| 存档 | `save/` | JSON 读写 | `core`, `models`, `data` |

- 方向约束：`models/` 不依赖任何业务层；`data/ → models/`；`core/ → models/`；`systems/ → core+models+data`；`main → {ui, systems, save, data, core}`（与审查报告依赖图一致）。
- **禁止** `from shared import ...` 这类未登记内部包路径的硬依赖（曾导致 F1 启动崩溃）。任何可选 / 易缺失依赖一律 `try/except ImportError` + 回退。

## 3. 类型注解（强制）

- 所有**新函数 / 方法**必须带参数与返回类型注解：

  ```python
  def create_enemy(template_name: str, loot: list[Item] | None = None) -> Enemy: ...
  ```

- 存量缺注解处随改动补齐（优先：`execute_enemy_turn` 的 `room`、`use_item` 的 `combat_system` / `enemies`）。
- 项目最低 Python 3.12，可直接用内置泛型 `list` / `dict` / `tuple`；可选值用 `X | None` 或 `Optional[X]`。

## 4. 命名规范

| 对象 | 约定 | 示例 |
|------|------|------|
| 模块 / 包 | `snake_case` | `combat.py`, `save_manager.py` |
| 函数 / 变量 | `snake_case` | `fire()`, `selected_enemy_index` |
| 类 | `PascalCase` | `CombatSystem`, `GameState` |
| 常量 | `UPPER_SNAKE_CASE` | `SCREEN_WIDTH`, `MAX_SAVE_SLOTS` |
| 私有成员 | 前缀 `_` | `_load_font()`, `_start_new_game()` |

- 布尔命名用谓词：`is_alive`、`has_save`、`can_fire`。
- 中文化硬编码（如方向映射 `dir_names`）应集中到单一映射表 / 本地化模块，避免散落重复（审查指出 `main.py` 与 `movement.py` 重复硬编码）。

## 5. 导入规范（防「导入即崩」）

- **顶层导入优先**，避免在函数内随意延迟导入（审查指出的代码债之一）。
- 每个导入都应可解析；**不要把 `typing` 里的名字（`Dict` / `List` / `Optional`）当内建用**——漏写 `from typing import ...` 会在导入期抛 `NameError`，被下游模块连带崩（即 `data/enemies.py` / `data/weapons.py` 历史事故）。
- 可选 / 易缺失依赖用 `try/except ImportError` 包裹并给回退，绝不写裸硬依赖。
- **运行门禁**：`python scripts/import_smoke.py` 会在 CI 导入 `core/systems/models/save/data` 全部模块 + 校验 `requirements.txt` 依赖可达（含 `pygame-ce` → `pygame_ce` 映射）。**提交前务必本地跑一遍**。

## 6. 格式化（暂无自动配置）

- 当前无 black / isort / ruff 配置。团队临时约定：
  - 缩进 4 空格，不用 Tab。
  - 行宽尽量 ≤100 字符。
  - 引号：双引号优先（与现有代码一致）。
  - import 分组：标准库 → 第三方 → 项目内（各组间空一行）。
- 建议下一步：引入 `ruff` / `black` + pre-commit，把本规范固化成自动门禁，与 CI 导入门禁并列（呼应报告行动项 #3）。

## 7. 文档字符串

- 公共模块、类、函数写 docstring（既有成员产物对 docstring 覆盖率有专门评估，建议补齐）。
- 简洁说明「做什么 / 返回什么 / 可能抛什么」，不必过度。

## 8. 关联文档

- 启动 / 存档 / 事故：见根目录 [RUNBOOK.md](../RUNBOOK.md)
- 项目简介与操作：见根目录 [README.md](../README.md)
