# text_adventure

文字冒险解谜游戏（英文 + 中文双版本），现在也可以**在浏览器里玩**。

## 简介
基于 pygame 的文字冒险/解谜游戏，整合多种小谜题（数学、谜语、填字、数独、猜数字、扫雷、数织、2048 等），由引擎驱动谜题生命周期与计分。含英文版 `text_adventure/` 与中文版 `text_adventure_zh/` 两个并行实现。

谜题逻辑（14 种）现在跑在一个**无头 Python 谜题服务**里，外面套一层 **Cordis 宿主**（Node）负责编排与渲染，因此同一个谜题服务可以同时供 pygame 客户端和浏览器客户端使用——加一道谜题不必改任何客户端。

## 语言 / 类型
- 语言：Python（谜题与 pygame 客户端）、JavaScript（Cordis 宿主与浏览器客户端）
- 类型：桌面 GUI 游戏 + 浏览器可玩游戏

## 快速开始

> 下文的 `<PATH>` 是路径占位符，请替换成本机实际克隆位置。**不要**把绝对路径写进代码或配置。

### 命令行版（终端可玩，不需要 pygame 也不需要浏览器）
```powershell
cd <PATH>\text-adventure

pwsh -NoProfile -File scripts\play.ps1                       # 交互模式
pwsh -NoProfile -File scripts\play.ps1 new math easy         # 单条命令
pwsh -NoProfile -File scripts\play.ps1 new sudoku ';' hint   # 多条命令共用同一局
```

包装脚本只做两件事：找一个**能跑的解释器**（`$env:TEXT_ADVENTURE_PYTHON` → 项目 `.venv` → `python3`/`python`/`py`，不写死任何路径），
并把子进程的编码设成 UTF-8（否则中文在默认代码页的控制台上是乱码）。也可以直接用：
```powershell
.\.venv\Scripts\python.exe -m puzzle_service.cli            # 交互
.\.venv\Scripts\python.exe -m puzzle_service.cli kinds      # 列出全部谜题种类
```

命令：`kinds` `content` `new [种类] [难度]` `daily [YYYY-MM-DD]` `submit <答案>` `act <动作> [k=v ...]` `hint` `state` `json` `help` `quit`。
交互模式下直接输入选项序号即可作答；stdin 是管道时**不打印提示符**（提示符只给真人看），所以同一套代码既能手动玩也能被脚本驱动。
出错的命令以非零码退出，脚本可直接分支判断。

**每日一题**：`daily 2026-10-16` 按日期确定性地选题（类型与内容都由日期种子驱动），
所以同一天在任何机器上都是同一题，也不需要服务端排期或预生成列表。
```powershell
pwsh -NoProfile -File scripts\play.ps1 daily            # 今天
pwsh -NoProfile -File scripts\play.ps1 daily 2026-10-16 # 指定日期（可复现）
pwsh -NoProfile -File scripts\play.ps1 profile          # 进度：玩过几天、连续天数
pwsh -NoProfile -File scripts\play.ps1 history          # 最近 14 天（新在前）
pwsh -NoProfile -File scripts\play.ps1 share            # 无剧透分享卡片（文字）
pwsh -NoProfile -File scripts\play.ps1 card 2026-10-16 out.svg   # 图形卡片
node scripts/render-share-card.mjs out.svg out.png      # 想要位图就再转一层
```
进度存在 `saves/profile.json`（**不入库**，且**不保存谜底与题目内容**）；
连续天数是**从记录推导**的，不是计数器——漏一天会自动断，改存档也编不出没有证据的连续记录。
用 `$env:TEXT_ADVENTURE_PROFILE` 可指定别的档案路径。
网页端对应「每日一题 / 分享卡片 / 卡片图 / 历史」四个入口。

> 注意：多条命令用 `;` 分隔只在直接传参数时成立；在 PowerShell 里 `;` 是语句分隔符，请分次调用。

### 桌面版（pygame）
```powershell
cd <PATH>\text-adventure

# 一次性：建好可用的虚拟环境（会顺带跑一次无头冒烟测试）
pwsh -NoProfile -File scripts\rebuild_venv.ps1

.\.venv\Scripts\python.exe text_adventure_zh\main.py    # 中文版
.\.venv\Scripts\python.exe text_adventure\main.py       # 英文版
```

### 浏览器版（Cordis 宿主）
```powershell
npm install        # 一次性：装 cordis、官方插件与 playwright-core（浏览器测试用）
npm start          # 启动宿主，打印的地址（默认 http://127.0.0.1:8080）直接用浏览器打开
npm test           # 客户端检查 + 宿主冒烟 + 真浏览器端到端（16 项）
npm run e2e:browser -- --headful   # 留 60 秒人工观察
```

端口、绑定地址、谜题语言都在 `cordis.json` 里改（默认只绑回环地址，不对局域网开放）。
浏览器测试用 Playwright 驱动本机已有的 Chromium；没有任何缓存时会提示
`npx playwright install chromium`（`src/browser.mjs` 会依次尝试几种启动方式并说明各自失败原因）。

## 架构（三层，谜题逻辑只有一个真相源）

```
命令行 puzzle_service/cli.py        终端客户端：把视图模型渲染成文字
浏览器 public/                       Web 客户端：把视图模型渲染成语义 HTML
pygame text_adventure*_zh/ui.py      桌面客户端（历史实现，保留）
   │  POST 动作 + SSE 快照（Web）／直接调用（终端）
Node Cordis 宿主 src/               编排层：插件装载、生命周期、HTTP/SSE
   │  JSON-RPC 2.0 over stdio（src/core/bridge.mjs ↔ python/rpc_server.py）
Python 谜题进程 python/ + puzzle_service/   领域层：状态、规则、计分、视图模型
```

- **谜题即插件**：一种谜题在 `puzzle_service/registry.py` 里登记一次（名称、交互模型、可执行动作、
  答案类型、靠提交还是靠动作判定），选择器、RPC 方法面、视图模型全部读注册表，不再有硬编码的种类列表。
- **客户端只认少量渲染原语**（10 个：文本 / 输入框 / 选项 / 列表 / 线索 / 网格 / 序列 / 字母键盘 / 颜色 / 棋盘）。
  未知原语会**响亮失败**，不会渲染成空白页——半成品谜题因此暴露在测试里，而不是用户面前。
- **谜底不进视图模型**：数独只发题目网格、填字只发玩家网格与线索（有测试守着）。

## 目录要点
- `gameplay_pool/`：**统一的谜题实现**（14 种）+ `messages.py`（全部文案的分语言表）
- `text_adventure/`、`text_adventure_zh/`：英文与中文 **pygame 客户端**（`main.py` 入口、`ui.py` 界面、`engine.py` 引擎）
- `puzzle_service/`：无头领域层——`registry.py`（按语言建键的注册表）、`views.py`（视图模型）、`service.py`（会话/计分/动作）、`profile.py`（进度与分享卡片）、`content.py`（内容包）、`cli.py`（终端客户端）
- `python/rpc_server.py`：JSON-RPC 2.0 stdio 服务端（仅标准库）
- `src/`：Cordis 宿主——`boot.mjs`（唯一启动入口）、`core/bridge.mjs`（Node 侧桥）、`plugins/`（puzzle / web / render）、`smoke.mjs`（端到端冒烟）、`browser_e2e.mjs`（真浏览器端到端）
- `public/`：浏览器客户端（`index.html` + `client/`）
- `content/packs/`：按语言分开的内容包（`core-zh`、`core-en`）
- `shared/`：共用层——`font_utils.py`（跨平台 CJK 字体）、`paths.py`（项目根发现与导入引导）、`ui_boot.py`、`cli.py`
- `scripts/`：环境重建、无头冒烟、内容包生成与校验、客户端一致性检查、卡片渲染
- `tests/`：Python 测试（无显示器、不依赖 pygame 窗口）
- `docs/`：文档枢纽——`spec/`（长期规范，如 [平台化路线图](docs/spec/SPEC-101-platform-roadmap.md)）、`records/`（实测记录与[调研卷](docs/records/platform-research-2026-10/README.md)）

## 内容包（谜题内容与代码分离）

谜题内容不再写死在 Python 模块里：5 种**内容型**谜题（谜语、猜单词、单词接龙、字母重排、填字）
从 `content/packs/core-zh/` 读取，**没有包时自动回退到模块内置题库**，所以缺包也能玩。

```powershell
# 从谜题模块派生内容包（改了题库后重新生成）
.\.venv\Scripts\python.exe scripts\build_content_pack.py

# 校验包与题库是否一致（CI 用：改了题库却忘记重新生成，这里会红）
.\.venv\Scripts\python.exe scripts\build_content_pack.py --check
```

- 包的 `manifest.json` 带**双版本字段**：`format_version`（包自身格式）与 `min_engine_version`
  （能读它的最老引擎）。包比引擎新则**拒绝加载**而不是半读。
- **加载即校验**：选项下标越界、重复条目、单词长度不符、填字格无人覆盖或坐标越界、
  包内出现 `eval(`/`exec(`/`__import__`/`lambda` 等，都会带着**文件名与条目下标**报错。
- 包是**纯数据**，不含可执行代码；坏包会**响亮报错**（写到 stderr）并退回内置题库——降级可以，静默降级不行。
- 换包目录：设环境变量 `TEXT_ADVENTURE_CONTENT_PACK` 指向你自己的包目录。
- 语种变体：条目 id 加 `@<lang>` 后缀（如 `riddle-001@en`）表示该语言的专用版本，无后缀为共享条目。

## 一份实现，多种语言（M5 已完成）
谜题逻辑**只有一份**：`gameplay_pool/`（项目根）。语言是构造参数，不是第二份副本：

```python
MathPuzzle(difficulty="easy", lang="zh").puzzle_name   # '数学题'
MathPuzzle(difficulty="easy", lang="en").puzzle_name   # 'Math Puzzle'
```

- 全部用户可见文案集中在 [`gameplay_pool/messages.py`](gameplay_pool/messages.py)（谜题名、提示、规则描述）；
  缺一条翻译会**响亮报错**（`KeyError` 指出键与语言），不会静默退回另一种语言。
- 内容（谜语/填字线索/词库）按语言分属不同内容包：`content/packs/core-zh`、`content/packs/core-en`。
- 注册表按 `(语言, 种类)` 建键，所以同一个进程里可以同时存在两种语言的服务
  （这正是合并时暴露的缺陷：原先按种类名建键，先注册的语言会赢下之后所有请求）。
- `text_adventure/` 与 `text_adventure_zh/` 现在只剩 **pygame 客户端**
  （`engine`/`ui`/`events`/`domain`/`main`），它们各自的 `gameplay_pool` 副本已删除——
  两份同名包会让「导入到哪一份」取决于 `sys.path` 顺序，那正是 M5 要消除的东西。

合并的正确性不是靠「看着差不多」，而是逐项比对：同一随机种子下，
统一实现与两版旧实现在**数据、提示、种类元数据**上一致（差异只有两处，且都记录在案：
填字的提示策略中英本来就不同，谜语提示把「answer」改成「option」）。
证据见 [`docs/records/m5-unification_2026-10-16.md`](docs/records/m5-unification_2026-10-16.md)。

## 测试状态（2026-10-16 复核）
- `pytest tests -q`：**159 passed**——注册表（含**按语言建键**与「未注册语言不回退」）、视图（谜底不泄漏、label 键契约）、服务（14 种全部可解、动作驱动不重复计分）、桥（真子进程）、宿主跨语言契约、内容包（双包 + 11 种坏包失败路径）、命令行（真子进程 + 管道 stdin）、每日一题（14 种逐一验证同种子可复现）、进度/连续天数/存档/历史/图形卡片、客户端一致性。
- `npm test`：**CLIENT CHECK PASSED / SMOKE PASSED（11 项）/ BROWSER E2E PASSED（18 项）**——最后一项是**真浏览器**（Playwright + Chromium）跑出来的：加载与控制台零错误、SSE、14 种可选、开局渲染中文标签、错答、提示、点击格子、键盘 `f` 插旗、右键插旗、方向键操作 2048、颜色不单独承载信息、答题结果、每日一题、分享卡片、进度显示、图形卡片以 `image/svg+xml` 提供、历史新在前、**axe-core 可访问性审计四个画面零 serious/critical**。
- `python scripts/smoke_headless.py`：**SMOKE PASSED**——两版 pygame 客户端各遍历 **14 种**谜题画面（含一次真实点击）＋ 菜单 ＋ 结果画面，无头运行。
- `python scripts/_audit_parity.py`：**两版各 0 problem**——统一实现与两版旧实现在数据、提示、种类元数据上逐项一致（只允许两类已登记差异）。
- `python scripts/check_build_consistency.py`：**CLIENT CONSISTENCY PASSED**——两客户端解析到同一个谜题池、暴露同样的 14 种、引擎与界面接口一致（已用负向对照验证会红）。
- `python scripts/build_content_pack.py [--language en] --check`：**up to date（两个包各 6 文件 / 154 条）**。
- 环境：Python 3.14.7 / pygame-ce 2.5.8 / Node 26.10.0 / cordis 4.0.0-rc.11 / playwright-core 1.64.1（复用本机已有的 Chromium，未下载）/ axe-core 4.14.0。
- 修复前两个版本**都无法启动**（`ui.py` 从一个从未存在的模块 `shared.font_utils` 导入字体），
  详见 [记录](docs/records/text-adventure-boot-crash-fix_2026-10-16.md)。
- 已知行为（既有，非本轮引入）：`MathPuzzle`、`RiddlePuzzle`、`GuessNumberPuzzle`、`PatternPuzzle` 的
  `check_answer` 对类型不对的入参抛 `ValueError`/`TypeError`；服务边界把它转成结构化错误，不计分。

## 依赖
- Python：`pygame-ce >= 2.5`（导入名仍是 `pygame`），声明在 `pyproject.toml`；`dev` 额外装 `pytest`。
- Node：`cordis`、`@cordisjs/plugin-loader`、`@cordisjs/plugin-logger-console`，声明在 `package.json`。
  Cordis 仍是 RC 线，版本在此显式钉住（调研见 [调研卷](docs/records/platform-research-2026-10/01-plugin-kernel.md)）。
- 虚拟环境 `.venv/` 与 `node_modules/` 都不入库。仓库里曾提交过一个**在别的机器/路径下建的** `.venv`
  （`pyvenv.cfg` 指向已不存在的解释器），已改为用 `scripts/rebuild_venv.ps1` 在本地重建。

## 治理
- 规则来自治理仓（分发版落地见 DSH 检出的 `governance/`），本仓自有文档按四分类放在 [`docs/`](docs/README.md)。
- 本仓**没有** Node 治理运行时，因此不假装跑过 `check:governance`：相关规则按条目人工机械核对并在提交信息里记账。

## 规则内核接入判定（R2 · 2026-08-27，2026-10-16 复核不变）

勘查结论：本作为谜题引擎（计分/连击/时间奖励，无骰子与角色属性），alloy.trpg
（D&D 三宝书 + GURPS Basic Set）无同构原语可接——按「只接同构原语、绝不破坏行为
契约」原则**不接入**（记账声明）。将来若引入检定/角色成长：
`from alloy.trpg import Character, roll_3d6`（接入模式参照 running-group-simulator
的 `core/dice.py`）。
