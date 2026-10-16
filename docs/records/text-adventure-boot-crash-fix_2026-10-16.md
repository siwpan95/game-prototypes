# text-adventure：启动崩溃修复与 Cordis 化改造起点

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** `Gitee siwpan/text-adventure` 仓内
> **证据** 全部为当轮实测命令输出；命令在文末「复现」节逐条列出。
> **注意** 记录只陈述这一次发生的事，不作为长期要求；长期要求见 `docs/spec/`。

## 一、修复前的实际状态（三个缺陷，两个致命）

| # | 缺陷 | 证据 | 影响 |
| --- | --- | --- | --- |
| 1 | `shared.font_utils` 不存在 | `ModuleNotFoundError: No module named 'shared'`，抛在 `UI.__init__` 第 117 行 `self.font_lg = _load_font(32)` | **两个版本都打不开**：窗口还没画第一帧就崩。README 当时只声明 `py_compile` 通过，所以这个缺陷从未暴露 |
| 2 | `.venv` 是死环境 | `pyvenv.cfg` 记录 `home = F:\Python314`、`command = F:\Python314\python.exe -m venv G:\games\text_adventure\.venv`；本机解释器实际在 `G:\Python314\python.exe`，且该盘符下的路径不存在 | 任何 `.venv\Scripts\python.exe` 调用都失败；同时它记录的是**另一台机器/另一个路径**（`G:\games\...`），仓被搬动过 |
| 3 | 两个版本导出同名顶层模块 | `text_adventure/` 与 `text_adventure_zh/` 各自含 `gameplay_pool/`、`engine.py`、`events.py`、`domain.py`，导入走扁平写法（`from engine import Engine`） | 谁先进入 `sys.path` 谁生效：同一进程内先导入的版本会**静默遮蔽**另一个。冒烟测试最初正是抓到这一点（中文版报 `cannot import name 'COLOR_CN' from 'gameplay_pool.color_sequence'`，实际拿到的是英文版的文件） |

## 二、输入健壮性实测（供服务边界设计用）

对 14 个谜题种类分别用三种探测值调用 `check_answer`：

| 种类 | `data` 中的答案字段 | `check_answer("文本")` | `check_answer(999999)` | `check_answer([])` |
| --- | --- | --- | --- | --- |
| MathPuzzle | `answer: int` | 抛 `ValueError` | `False` | 抛 `TypeError` |
| RiddlePuzzle | `answer: int`（选项下标） | 抛 `ValueError` | `False` | 抛 `TypeError` |
| GuessNumberPuzzle | `target: int` | 抛 `ValueError` | `False` | 抛 `TypeError` |
| PatternPuzzle | `answer: int` | 抛 `ValueError` | `False` | 抛 `TypeError` |
| 其余 10 种 | `answer: int` 或 `word/target: str` | `False` | `False` | `False` |

结论：4 种走 `int()` 强转的种类**不规范化输入**，类型不对就抛异常。这不是本轮引入的，而是既有行为。
处置决定：**不改谜题类**（英文/中文两份副本都改会制造漂移），改为在 JSON-RPC 边界把异常转成结构化错误响应，
并让服务按答案类型规范化入参；探针 `scripts/smoke_headless.py::_check_puzzles` 保留这条检查，
一旦某种类连类型正确的错答都判对，立即变红。

另外实测确认：`MathPuzzle` 接受**数字字符串**（`check_answer("22")` 对 `answer=22` 返回 `True`），
说明 Web 端表单提交字符串是可行的。

## 三、本轮修了什么

- 新增 `shared/font_utils.py`：用 `pygame.font.SysFont` 按**字体族名**解析 CJK 字体（Windows/macOS/Linux 候选族名列表），
  不写死任何字体文件路径；找不到 CJK 族时退回 pygame 内置字体并**在 stderr 出声**，不静默渲染豆腐块。
- 新增 `shared/paths.py`：从自身位置向上找到含 `pyproject.toml` **且**含 `shared/` 的目录作为项目根（两个判据同时满足，
  避免误认父目录）；`bootstrap_import_path(build)` 一次只放行**一个**版本目录，杜绝上面第 3 条遮蔽。
- `text_adventure/ui.py`、`text_adventure_zh/ui.py`：导入 `shared` 前先 `ensure_importable()`，不再依赖 `main.py` 的
  `sys.path` 前导；`_load_font` 继续作为薄封装保留（英文版 `load_font`、中文版 `load_cjk_font`）。
- 新增 `pyproject.toml`：`packages` 显式列出导入根，`pip install -e .` 让 `shared` 在任何启动方式下可导入。
- 新增 `scripts/rebuild_venv.ps1`：运行期探测解释器（`$env:TEXT_ADVENTURE_PYTHON` → `python3` → `python`），
  每一步输出 `PASS/FAIL/SKIP`，**SKIP 不算通过**，失败即非零退出。
- 新增 `scripts/smoke_headless.py`：无头（dummy SDL）驱动两个版本各走完 菜单→答题→结果 三个画面，
  并在**独立子进程**里分别运行两个版本（第 3 条缺陷的必然要求）。
- `.gitignore` 补 `*.egg-info/`（可编辑安装产物）。

## 四、复现（当轮实际执行的命令）

```
python scripts\smoke_headless.py                      # 修复前：UI() 抛 ModuleNotFoundError
pwsh -NoProfile -File scripts\rebuild_venv.ps1 -Force # 重建 .venv 并以冒烟测试收尾
```

修复后输出：`SMOKE PASSED`（谜题注册表、CJK 字体、中文版启动、英文版启动 4 项全过）。

## 五、遗留（下一轮处理，已记录不遗忘）

1. `docs/` 枢纽尚未建立（本轮只落这一份记录）；`README.md` 已同步更新运行方式。
2. Cordis 化（Node 宿主 + Python JSON-RPC 桥）尚未动工；本轮只完成「让游戏能打开 + 建立共享层」。
3. 中文字符串经 PowerShell 管道输出会因控制台代码页显示为乱码（测试内部比较不受影响，
   受影响的只是**人眼可读性**）；后续 CLI 输出统一显式 UTF-8。
