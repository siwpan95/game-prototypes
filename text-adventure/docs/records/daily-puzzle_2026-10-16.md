# 每日一题：种子驱动的确定性选题（M4 第一步）

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** 「按日期固定出题」的落地与它暴露的三个陷阱
> **证据** 全部为当轮实测；复现命令见文末

## 一、要解决的问题

「每日一题」的全部价值在于**同一天对所有人生效、同一天重开浏览器还是那一题**。
它不需要服务端排期、不需要预生成列表：日期 → 种子 → （种类，内容）即可。
听起来是一行 `random.seed(...)` 的事，实际上踩了三个坑，每个都让「确定性」名存实亡。

## 二、三个陷阱（都是实测抓到并修掉的）

### 1. 用 `hash()` 当种子 → 每次重启换题

Python 的 `hash()` 对字符串按进程加盐（`PYTHONHASHSEED`），
所以 `hash("2026-10-16")` 在两次运行里不同 → 同一台机器重启一次就换题。
改用 SHA-256 取前 16 位十六进制转整数，跨进程、跨机器一致；
`tests/test_daily.py::test_the_seed_is_stable_across_processes` 用子进程实测这一点。

### 2. `random.seed()` 会污染同进程的其它会话

最省事的写法是 `random.seed(seed)`，但那是**进程级全局状态**：
如果同一个服务进程里还有别的会话在玩，它们也会被钉到同一个序列上。
改为给谜题实例挂一个独立的 `random.Random(seed)`，并让所有内置题库的抽取都走
`self._rng()`；`tests/test_daily.py` 里有一条断言专门守着「不重播全局生成器」。

### 3. 静态方法没有 `self`，于是悄悄退回全局随机

把 `random.choice` 机械替换成 `self._rng().choice` 时，
`SudokuPuzzle._generate_solution` 是 `@staticmethod`——它没有 `self`。
第一次迁移脚本把 `self._rng()` 写进了静态方法体，直接 `NameError`；
AST 感知后改为给静态方法加 `rng=None` 参数，但**调用处**忘了传：
`self._generate_solution(size, box_h, box_w)` 依然用模块级随机数。
表现是「14 种里 13 种可复现，只有数独每次都不同」——
`tests/test_daily.py` 逐一验证全部种类才把它逼出来。

## 三、顺带发现的两件事

- **`strptime` 太宽容**：它接受 `2026-2-3`。同一个日期的两种写法会变成两道不同的题。
  现在要求往返格式化后字符串不变（严格 `YYYY-MM-DD`）。
- **两个版本的 base 类漂移**：`_rng()` 只加到了中文版，英文版仍是模块级随机数，
  直到英文版被真正跑起来才暴露。为此新增 `scripts/check_build_consistency.py`
  （独立冒烟脚本 + 一条 pytest），逐一比对 14 个类的结构；
  它已用**注入漂移**验证过真的会红，不是只会报绿。

## 四、测试里同样重要的一条

`test_different_days_eventually_give_different_puzzles` 最初比较的是**视图**，
结果 4 种谜题（猜单词、颜色序列、记忆翻牌、猜数字）全被判为「日期无影响」——
因为它们的视图**故意不暴露状态**（猜单词的视图里永远没有那个词）。
这不是缺陷，是设计。断言改为比较**生成数据的身份**，同时另加一条
「隐藏状态的视图仍然可复现」。教训：比较错层次会把正确行为报成缺陷。

## 五、验证

```
.venv/Scripts/python.exe -m pytest tests -q                        -> 114 passed
.venv/Scripts/python.exe -m pytest tests/test_daily.py -q          -> 11 passed（14 种逐一验证）
.venv/Scripts/python.exe scripts/check_build_consistency.py        -> BUILD CONSISTENCY PASSED
.venv/Scripts/python.exe -m puzzle_service.cli daily 2026-10-16    -> 每日一题（2026-10-16）：guess_number
node -e "...bridge.call('puzzle.daily', {day:'2026-10-16'})"       -> 经桥返回同一题
```

## 六、复现

```
pwsh -NoProfile -File scripts/play.ps1 daily
pwsh -NoProfile -File scripts/play.ps1 daily 2026-10-16
.venv/Scripts/python.exe -m pytest tests/test_daily.py -q
```

## 七、未做（下一步）

- 连续记录（streak）跨日持久化、无剧透分享卡片、按题号回放历史每日题：
  这三件是 SPEC-101 §阶段 M4 的剩余部分。
