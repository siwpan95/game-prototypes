# text_adventure

文字冒险解谜游戏（英文 + 中文双版本）。

## 简介
基于 pygame 的文字冒险/解谜游戏，整合多种小谜题（数学、谜语、填字、数独、猜数字、扫雷、数织、2048 等），由引擎驱动谜题生命周期与计分。含英文版 `text_adventure/` 与中文版 `text_adventure_zh/` 两个并行实现。

## 语言 / 类型
- 语言：Python
- 类型：桌面 GUI 游戏（pygame 文字解谜）

## 快速开始

> 下文的 `<PATH>` 是路径占位符，请替换成本机实际克隆位置。**不要**把绝对路径写进代码或配置。

```powershell
cd <PATH>\text-adventure

# 一次性：建好可用的虚拟环境（会顺带跑一次无头冒烟测试）
pwsh -NoProfile -File scripts\rebuild_venv.ps1

# 开玩（中文版 / 英文版）
.\.venv\Scripts\python.exe text_adventure_zh\main.py
.\.venv\Scripts\python.exe text_adventure\main.py
```

不需要虚拟环境也可以，直接 `python scripts\smoke_headless.py` 与 `python text_adventure_zh\main.py` 即可（需已装 `pygame-ce`）。

## 目录要点
- `text_adventure/`：英文版（`main.py` 入口）
- `text_adventure_zh/`：中文版（`main.py` 入口）
- 各版本内：`engine.py`（引擎）、`ui.py`（pygame 界面）、`events.py`（事件总线）、`domain.py`（状态）、`gameplay_pool/`（谜题库）
- `shared/`：两版共用层——`font_utils.py`（跨平台 CJK 字体，按字体族名解析，不写死路径）、`paths.py`（项目根发现与导入路径引导）、`ui_boot.py`（把界面跑到无头环境里的启动器）、`cli.py`（控制台入口）
- `scripts/`：`rebuild_venv.ps1`（重建并验证虚拟环境）、`smoke_headless.py`（无头端到端冒烟测试）
- `docs/`：文档枢纽（`records/` 记录实测证据，`spec/` 放长期有效的规范）
- `pyproject.toml`：依赖与打包声明；`pip install -e .` 后 `shared` 在任何启动方式下都可导入

## 两个版本的隔离（重要）
两个版本各自导出同名的顶层模块（`engine`、`events`、`domain`、`gameplay_pool`）。**同一进程里只能有一个版本生效**：
谁先进入 `sys.path` 谁赢，另一个会被静默遮蔽。因此：

- 启动某一版时用 `shared.paths.bootstrap_import_path("zh" | "en")` 显式声明；
- 需要同时验证两版时**必须分进程**（`scripts/smoke_headless.py` 就是这么做的）；
- 后续平台化会把两侧收敛到带包名的导入（`text_adventure_zh.engine`），届时这条限制消失。

## 运行方式与依赖
```
python text_adventure/main.py          # 英文版
python text_adventure_zh/main.py       # 中文版
python scripts/smoke_headless.py       # 无头冒烟测试（不需显示器）
pwsh -NoProfile -File scripts/rebuild_venv.ps1   # 重建 .venv 并验证
```
- 依赖：`pygame-ce >= 2.5`（导入名仍是 `pygame`）。`pyproject.toml` 里声明，`dev` 额外装 `pytest`。
- 虚拟环境：`.venv/` 不入库。仓库里曾经提交过一个**在别的机器/路径下建的** `.venv`（其 `pyvenv.cfg` 指向已不存在的解释器），
  已改为用 `scripts/rebuild_venv.ps1` 在本地重建；脚本运行期探测解释器（`$env:TEXT_ADVENTURE_PYTHON` → `python3` → `python`），
  不钉死版本、不写死盘符。

## 测试状态（2026-10-16 复核）
- `python scripts/smoke_headless.py`：**通过**。4 项检查＝谜题注册表（14 种全部可生成并给出提示）、CJK 字体解析、
  中文版 菜单→答题→结果 三个画面、英文版同样三个画面；本机 `pygame-ce 2.5.8 / Python 3.14.7`。
- 修复前两个版本**都无法启动**：`ui.py` 从一个从未存在的模块 `shared.font_utils` 导入字体，
  `UI.__init__` 直接 `ModuleNotFoundError`。`py_compile` 只做语法检查，因此历史上「语法检查通过」并不代表能运行。
- 已知行为（既有，非本轮引入）：`MathPuzzle`、`RiddlePuzzle`、`GuessNumberPuzzle`、`PatternPuzzle` 四种的 `check_answer`
  对类型不对的入参抛 `ValueError`/`TypeError` 而非返回 `False`。详见 `docs/records/text-adventure-boot-crash-fix_2026-10-16.md`。

## 架构方向（进行中）
目标是把「谜题 = 插件」做实，让**加一道谜题、换一层渲染**都不必改引擎：

```
浏览器（通用控件，无 pygame 依赖）
  │  HTTP / WebSocket
Node Cordis 宿主   plugin-loader + 插件：谜题服务 / Web 服务 / 会话 / 计分
  │  JSON-RPC 2.0 over stdio（Python 侧零依赖标准库协议层）
Python 无头谜题进程  谜题注册表 + 视图模型 + 计分规则（状态的唯一真相源）
  └─ pygame 版 ui.py 作为共存的旧客户端保留
```

分阶段推进；当前进度与下一步见 `docs/`。

## 治理
- 规则来自治理仓（分发版落地见 `governance/`），本仓自有的文档按四分类（枢纽 / 规范 / 事实源 / 记录）放在 `docs/`。
- 本仓**没有** Node 治理运行时，因此不假装跑过 `check:governance`：相关规则按条目人工机械核对并在提交信息里记账。

## 规则内核接入判定（R2 · 2026-08-27，2026-10-16 复核不变）

勘查结论：本作为谜题引擎（计分/连击/时间奖励，无骰子与角色属性），alloy.trpg
（D&D 三宝书 + GURPS Basic Set）无同构原语可接——按「只接同构原语、绝不破坏行为
契约」原则**不接入**（记账声明）。将来若引入检定/角色成长：
`from alloy.trpg import Character, roll_3d6`（接入模式参照 running-group-simulator
的 `core/dice.py`）。
