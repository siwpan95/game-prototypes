# 命令行客户端：把终端变成主力交互面

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** 浏览器实测暂缓期间的终端可玩路径
> **证据** 全部为当轮实测；复现命令见文末

## 一、为什么做这个

浏览器端只做到了「HTTP 正确、SSE 正确、客户端语法与 DOM 绑定正确」，**没有真正在浏览器里点过一局**。
在那种状态下把浏览器当主力交互面，等于把"没验证过的东西"当成验证过的东西。
命令行客户端能在**没有任何图形环境**的机器上完整玩一局，而且是可脚本驱动、可断言的形态。

顺带它验证了视图模型契约的另一半：**第三个客户端不需要改服务端任何代码**。
终端把同一份视图模型渲染成文字（`text`/`field`/`options`/`grid`/`sequence`/`keyboard`/`colors`/`board`），
和网页端渲染成语义 HTML 是同一件事的两种投影。

## 二、形态

- `puzzle_service/cli.py`：既是一行命令（`new math easy`），也是交互式会话（REPL）。
- `scripts/play.ps1`：Windows 包装脚本，只解决两件事——找一个**能跑的解释器**
  （`$env:TEXT_ADVENTURE_PYTHON` → 项目 `.venv` → `python3`/`python`/`py`，不写死路径），
  以及把子进程编码设成 UTF-8（默认代码页会把中文变乱码）。
- **stdin 是管道时不打印提示符**：提示符只给真人看。所以同一套代码既能手玩也能被测试驱动。
- 一条命令出错 → 非零退出码，脚本可分支判断；错误信息是中文，与界面语言一致。
- `;` 分隔多条命令，使一次调用内可共用同一局（`new sudoku ';' hint`）。

## 三、开发过程中被测试抓到的问题（都是真实缺陷）

| # | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| 1 | `python -m puzzle_service.cli` 毫无输出、退出码 0 | 文件里**没有 `__main__` 守卫**，模块被导入后什么都不做 | 补 `if __name__ == "__main__"` |
| 2 | 退出码靠"输出是否以 × 开头"判断 | 用文本当控制信号，改一次文案就失效 | 改为显式返回 `(keep_going, ok, output)` |
| 3 | 一次调用无法完成"开局 → 提示" | 每次调用都是新进程，状态不跨进程 | 新增 `;` 分隔多命令 |
| 4 | `new no-such-kind` 直接抛 `UnknownKind`（英文、带完整列表） | 客户端边界没接住注册表的查找失败 | 在客户端转成一行中文并列出可选种类 |
| 5 | 中文界面里输入框标签显示英文 `Answer` | 视图模型里的 label 由服务端写死为英文，而服务端并不知道谁在渲染 | 终端客户端做展示层翻译，并在 SPEC-101 记下更干净的修法（服务端发 label **键**而不是 label 文本） |
| 6 | 测试之间互相污染：某模块把 kind 注册成"无内容包" | 注册表是进程级全局，谁先发现谁定调 | 测试夹具统一走 `PuzzleService`（与真实入口一致） |

## 四、验证

```
.venv/Scripts/python.exe -m pytest tests -q                 -> 102 passed
.venv/Scripts/python.exe -m pytest tests/test_cli.py -q     -> 20 passed（真子进程 + 管道 stdin）
pwsh -NoProfile -File scripts/play.ps1 kinds                -> 14 种（中文表头，制表符分隔）
"new math easy`nhint`nstate`nquit" | ... scripts/play.ps1   -> 完整一局，中文不乱码
```

测试刻意跑**真子进程**并用**管道**喂 stdin：编码问题、提示符泄漏到管道、模块没有入口——
这些在进程内单测里都看不见。

## 五、复现

```
pwsh -NoProfile -File scripts/play.ps1
pwsh -NoProfile -File scripts/play.ps1 new minesweeper ';' act reveal row=0 col=0
.venv/Scripts/python.exe -m pytest tests/test_cli.py -q
```

## 六、未做

- 没有做每日一题（date-seeded 题序）与分享卡片：那是 SPEC-101 §阶段 M4，
  命令行形态下分享卡片的意义有限，建议与 Web 端一起做。
- 没有做终端 UI 的动态刷新（无光标重绘/翻页）：当前是"输出追加"式，管道友好、实现简单；
  真要终端全屏体验，需要引入 curses/rich 之类的依赖，与"零依赖"取向冲突，暂不做。
