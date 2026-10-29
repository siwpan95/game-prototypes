# ADR-009：测试与 CI 策略

**状态**：Accepted
**日期**：2026-07-25
**作者**：Archi（系统架构师）
**关联**：ADR-001（移除死 EventBus）、ADR-008（字体/共享依赖显式化）；综合审查报告 F1/F2/F3/F4/F16

---

## 背景 / 问题

项目原本**无 CI、无自动化测试**。综合审查暴露出这一类缺陷的系统性根因：

- `data/enemies.py` 曾漏写 `from typing import Dict`、`data/weapons.py` 也出现过导入崩溃——这类纯**导入期**缺陷不触发任何运行时报错，直到人工审查才被发现。
- **F1 启动即崩溃**（`ui/renderer.py` 硬依赖不存在的 `shared.font_utils`），连现有 smoke test 都 import 失败，印证"导入期缺陷没有任何门禁"是 Rex 5-Why 的第 4、5 层根因（缺发布期校验 + 缺依赖治理）。
- 唯一测试文件 `tests/test_game.py` 1830 行、无 unit/integration 分层、无 CI、无覆盖率，且因 F1 直接 import 失败（Tessa 测试债 🔴×7）。

根因：发布流水线缺「导入冒烟 + 依赖可达性」门禁，缺失模块可被硬依赖写进任意层而**不被任何自动检查捕获**。

---

## 决策

采用**双层防护**；测试分层与现有 `core / systems / models / save`（及被冒烟覆盖的 `data`）分层**严格对齐**。

**1. 导入冒烟门禁（CI 必跑，零额外依赖）**

即 Rex 正在落地的 `scripts/import_smoke.py` + `.github/workflows/ci.yml`，用 stdlib `importlib` 实现：

- 每次 push/PR 导入 `core/ systems/ models/ save/ data/` 全部模块；任一失败 → CI 红。
- 附带**依赖可达性门禁**：import `requirements.txt` 中每个包，捕获拼写/幽灵依赖（如 `pygam-ce`）。
- 明确排除 `main.py` 与 `ui/**`（pygame 耦合，见权衡）。

**2. 关键路径单测（pytest 轻量运行器，行为断言优先）**

按源分层组织测试包，聚焦高价值/曾出事的不变式：

| 测试包 | 守卫的不变式 | 防回归 |
|---|---|---|
| `tests/unit/systems/test_combat.py` | 护甲扣减**只发生一次** | F3 双重扣甲 |
| `tests/unit/save/test_save_manager.py` | 存档 round-trip 完整恢复 `current_room`/`levels` + `schema_version` 迁移 | F2 丢状态 / F16 无版本 |
| `tests/unit/core/test_game_state.py` | 阶段状态机合法迁移 | 状态机错乱 |
| `tests/unit/systems/test_inventory.py` | 背包 `use_item`/`modify_weapon` 可观察效果（mod 挂载、物品消耗、投掷物生效） | 背包逻辑 / 静默 no-op |

所有单测断言**可观察结果**而非"代码跑通"，以暴露 F4 类静默 no-op。

---

## 权衡

**为何不引入重型测试框架**

- 项目 ~6182 行、36 模块、无 git、小团队、无现成 CI 主机。重型框架（hypothesis 属性测试、behave/pytest-bdd、factory_boy 夹具工厂、容器化显示编排、mock-everything 集成套件）的搭建与维护成本远超其在本离线游戏上的收益。
- 采用"足够好"组合：stdlib `importlib` 冒烟（零依赖）+ pytest（轻量、近事实标准）+ 原生 `assert` + 仅在必需处用 `unittest.mock`。拒绝覆盖率虚荣门禁（先取基线，P4 再设 ≥80% 阈值）。
- 代价：属性/边界探索较弱，靠关键路径断言 + 人工 playtest 补足。

**为何 pygame 层（main/ui）暂不纳入自动测试**

- `main.py` 与 `ui/**` 直接 `import pygame`，需 SDL + 显示设备；headless CI 无显示，导入即失败（F1 正位于此层）。
- 渲染正确性（像素/布局）在无显示环境下难以有意义地断言；UI 交互（F5 目标不可点、F6 滚轮双处理）自动化下易 flaky。
- 处置：F1 由 ADR-008（vendored `ui/font_utils.py` + try/except 优雅降级）消除硬依赖；pygame 层靠发布清单「导入校验★」手动门禁 + 人工 playtest；P3 再引入 headless UI smoke（`SDL_VIDEODRIVER=dummy` + 已装 pygame）闭环残余缺口。

---

## 防护映射（如何防止同类回归）

| 历史缺陷 | 类别 | 防护层 | 机制 | 覆盖度 |
|---|---|---|---|---|
| data/enemies.py 导入崩溃 | 非pygame层导入崩溃 | 导入冒烟 | 每次 push 导入 `data/` 全部模块 | 直接 / 高 |
| data/weapons.py 导入崩溃 | 同上 | 同上 | 同上 | 直接 / 高 |
| F1 启动崩溃（ui/renderer.py 缺 shared.font_utils） | pygame层导入崩溃 | ADR-008 治理 + 发布清单手动门禁 +（P3）headless UI smoke | 冒烟门禁**不直接**覆盖 ui/；靠 ADR-008 删 `shared.` 硬依赖 + 优雅降级，加发布清单「导入校验★」与未来 headless smoke 闭环 | 间接 / 中（残余缺口已命名） |
| F4 死 EventBus（core/event_bus.py） | 架构诚度 / 静默 no-op | 关键路径单测 + ADR-001 治理 | 单测断言可观察效果（投掷物真造成伤害）而非静默 no-op；ADR-001 移除死总线；代码审查纪律 | 间接 / 中 |

> 关键认知：导入冒烟门禁是**第一道、也是最便宜的一道**防线，专治非pygame层导入期缺陷（data-enemies / data-weapons 同型）。pygame 层的 F1 型与架构诚度型的 F4，由治理决策（ADR-008/001）+ 行为断言单测 + 发布清单共同防护；其自动化闭环为已知残余，已列入 P3。

---

## 后果

**变容易**

- 任一非pygame模块导入崩溃（data/enemies、data/weapons、缺 typing、环形导入）在 push 即被拦下，不再潜伏到人工审查。
- 幽灵/拼写依赖（如 `pygam-ce`）在 CI 被捕获。
- F3 护甲双扣、F2 存档丢状态、F4 静默 no-op 获得回归护栏。

**变困难 / 需注意**

- UI 层（~1043 行）仍无自动防护，依赖 ADR-008 + 人工 playtest，直至 P3 headless smoke 落地。
- 关键路径单测依赖 ADR-003（可种子 RNG）、ADR-004（Game 编排解耦）先落地，否则易退化成脆弱的逐模块 patch（Tessa 已标注）。
- 须将 `scripts/import_smoke.py` 接入实际 CI 主机：当前仓库无 git/无 CI host，`ci.yml` 为参考定义；若迁 GitLab/Gitea 须原样移植「装 Python 3.13 → pip install → python scripts/import_smoke.py」三步。

**需重新审视**

- 覆盖率阈值（现仅取基线，P4 设 ≥80% 后评估是否对 ui 放宽）。
- ADR-004 拆分 `main.Game` god-object 后，编排层单测归属需同步调整。
