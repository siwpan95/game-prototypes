# M5：两套并行实现收敛为「一份实现 + 语言资源」

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** 结构债清理：`text_adventure/gameplay_pool` 与 `text_adventure_zh/gameplay_pool` 合并
> **证据** 全部为当轮实测；每一步都有脚本与比对，复现命令见文末

## 一、先量清楚，再动手

合并前先量了 17 对同名文件（各约 1580 行）：

| 事实 | 数值 |
| --- | --- |
| 文件对数 | 17 |
| 完全相同的文件 | 2（`__init__.py`、`random_pick.py`） |
| 差异总行数 | 约 200 行，且**几乎全是文案**（谜题名、提示、规则描述） |
| 差异最大的文件 | `riddle_puzzle.py` 56 行、`crossword_puzzle.py` 48 行（都是题库/线索数据） |

结论：**逻辑只有一份，文案有两份**。所以合并 = 把文案抽出来，而不是重写逻辑。

## 二、怎么做的

1. `gameplay_pool/messages.py`：全部用户可见文案按语言列表（`PUZZLE_NAMES` / `LABELS` / `TEMPLATES`）。
   缺翻译**响亮报错**（`KeyError` 指出键与语言），不静默退回另一语言。
2. `gameplay_pool/base_puzzle.py`：语言成为构造参数 `lang`；
   `puzzle_name` 仍是类属性（默认语言），实例属性按语言覆盖——因此**客户端代码一行未改**。
3. 14 个谜题类合并进 `gameplay_pool/`。两处**中英本来就不同**的行为**保留而不统一**：
   - 填字提示策略（英文给"最后一个字母"，中文报下一条未完成的线索）；
   - 颜色显示（中文用「红色」，英文用 `Red`）。
   统一它们等于偷偷改掉一版的行为，所以选择"按语言分支 + 注释说明"。
4. 内容按语言分包：新增 `content/packs/core-en`（154 条，从英文旧模块派生），
   `load_pack(language=...)` 按语言选择，`TEXT_ADVENTURE_CONTENT_PACK` 仍可覆盖。
5. 注册表改为按 **(语言, 种类)** 建键，删掉两份重复的 `gameplay_pool` 目录。

## 三、过程中被比对抓出来的四个真问题

| # | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| 1 | 英文内容的请求拿到中文题 | 注册表按**种类名**建键，进程里先注册的语言赢下之后所有请求 | 改为按 `(语言, 种类)` 建键；未注册的语言**报错**而不是回退 |
| 2 | 英文包已存在却仍出中文题 | 我的比对探针把旧构建目录留在 `sys.path`，`gameplay_pool` 解析到了**旧的中文包**——等于拿统一实现跟它自己比 | 探针显式断言导入到的是哪个包；这条断言本身抓住了问题 |
| 3 | 探针报"数据不一致" | 探针直接构造谜题却**没传内容包**，于是回退到内置题库（中文） | 探针按注册表的方式传入该语言的包 |
| 4 | 客户端解析到两份不同的池 | 同名包两份共存时，导入哪一份取决于 `sys.path` 顺序 | 删除两份副本（git 记录为 **rename**，历史未丢） |

第 2、3 条都是**探针自己的缺陷**：如果当时不追根因、直接"修代码"，就会把正确的行为改坏。
这与前一轮可访问性审计里那两次「断言写错而非产品有缺陷」是同一类教训。

## 四、删除的正当性（功能面 × 接任者）

| 被删的功能面 | 接任者 | 验证 |
| --- | --- | --- |
| `text_adventure/gameplay_pool/`（17 文件） | `gameplay_pool/`（项目根，同一实现） | 客户端一致性检查：两客户端解析到**同一个**池；pygame 无头冒烟两版各 14 种画面通过 |
| `text_adventure_zh/gameplay_pool/`（17 文件） | 同上 | 同上 |
| 英文内置题库（谜语/填字线索） | `content/packs/core-en/`（154 条，派生自它） | 集合比对：统一实现不会抽出旧版没有的条目 |
| 中文内置题库 | `content/packs/core-zh/`（既有的 154 条） | 同上 |
| 旧版 `puzzle_name` 类属性语义 | 同名类属性（默认语言）+ 实例属性按语言覆盖 | pygame 客户端显示名不变（冒烟未改一行客户端代码） |

**行为等价性证据**：同一随机种子下逐项比对统一实现与两版旧实现（`scripts/_audit_parity.py`），
比较数据、提示、`puzzle_type`/`content_kind`/`puzzle_name`。

```
compared unified(zh) with legacy-zh: 0 problem(s)
compared unified(en) with legacy-en: 0 problem(s)
```

只允许两类已登记差异：填字提示策略（中英本就不同）、谜语提示把「answer」改成「option」
（谜语给的是选项，用词更准）。后者作为**已知文案改动**写进比对脚本的 `ACCEPTED_HINT_REWORDS`，
而不是让脚本"宽容"掉。

脚本还会报告"抽样差异"：内容是从池子里抽的，同一种子不必然抽到同一条，
所以逐条比对会抽签差异当成缺陷——脚本用集合级检查（不会抽到旧版没有的条目）表达真正要守的性质。

## 五、验证

```
.venv/Scripts/python.exe -m pytest tests -q                      -> 159 passed
.venv/Scripts/python.exe scripts/_audit_parity.py                 -> 两版各 0 problem
.venv/Scripts/python.exe scripts/check_build_consistency.py       -> CLIENT CONSISTENCY PASSED
.venv/Scripts/python.exe scripts/smoke_headless.py                -> SMOKE PASSED（两版 × 14 种画面）
npm test                                                          -> CLIENT CHECK / SMOKE / BROWSER E2E 全过
.venv/Scripts/python.exe scripts/build_content_pack.py --check              -> up to date（zh，154 条）
.venv/Scripts/python.exe scripts/build_content_pack.py --language en --check -> up to date（en，154 条）
```

`check_build_consistency.py` 已改用**负向对照**验证过：删副本之前它报红（指出两份池并存），
删除之后通过——所以它不只是"会报绿"。

## 六、复现

```
.venv/Scripts/python.exe scripts/_audit_parity.py
.venv/Scripts/python.exe scripts/check_build_consistency.py
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'.'); from puzzle_service.registry import get, languages; from puzzle_service.service import PuzzleService; PuzzleService(language='zh'); PuzzleService(language='en'); print(languages(), get('riddle','en').title, get('riddle','zh').title)"
```

## 七、未做

- pygame 客户端（`engine`/`ui`/`events`/`domain`）仍是**两套**、各约 1600 行，未合并：
  合并它们要动 1584 行的绘制代码，而这条渲染路径已被 Web 与终端两个客户端取代。
  这一步的收益与风险比远低于谜题库那一步，留作独立任务（若做，走同样的"先比对、再合并、后删除"流程）。
- 尚未新增第三种语言：机制已就位（`messages.py` 加一列 + 一个内容包），但没有真实需求时不造数据。
