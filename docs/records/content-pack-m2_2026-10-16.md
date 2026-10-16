# 内容包落地与两个实测缺陷（M2）

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** 把 5 种内容型谜题的题库迁出代码
> **证据** 全部为当轮实测；复现命令见文末

## 一、做了什么

`content/packs/core-zh/`（154 条）由 `scripts/build_content_pack.py` 从谜题模块**派生**，
不是手抄——手抄几百个单词必然漂移，而且没人知道哪一份是对的。5 种内容是：
谜语 12、猜单词 90、字母重排 40、单词接龙 9、填字 3。

运行期读取顺序：**内容包 → 模块内置题库**（`BasePuzzle.pick_content()`）。
所以没有包时游戏照常运行，迁移是增量的而不是一刀切；坏包则**响亮报错并写明原因**，
同时退回内置题库——降级是允许的，静默降级不允许。

## 二、过程中被抓到的两个**实测**缺陷

### 1. 模块里就有脏数据：4 字母单词池混进两个 5 字母单词

`WORD_POOLS[4]` 里含 `knife`、`flame`（5 个字母）。这让「4 字母梯子」的池子与梯子长度不一致。
处置：导出器按梯子长度过滤，并把被丢弃的词记进 `sourcePoolDropped` 字段（有据可查，不是悄悄删掉）；
`puzzles_service/content.py` 的校验器对每个梯子断言「池中所有词与起点等长」，
这类错误以后在**加载时**就红，不必等人玩到那一题。

### 2. 英文版填字界面：`UnboundLocalError`（潜在崩溃）

`text_adventure/ui.py` 的 `_handle_crossword` 把「检查」按钮的循环写在了事件循环**外面**，
却引用循环变量 `ev`。中文版写对了（循环内），英文版只是**碰巧**没被测到——
原来的无头冒烟测试每轮只随机玩一题，抽不到填字就永远发现不了。

处置：把该循环移回事件循环内，与中文版一致；并把冒烟测试改成**确定性遍历全部 14 种**
（每种都画一遍、并送一次真实点击事件），不再依赖随机抽题。

## 三、顺带修正的判断

原计划把「图案规律（pattern）」一起数据化。实测其 `puzzle_type = "generated"`：
它的题目由算式（等差/等比/平方/斐波那契/幂）生成，**没有题库可迁**。
真正需要的是难度参数化而不是内容包。已把这一条修正写进
[SPEC-101 §阶段 M2](../spec/SPEC-101-platform-roadmap.md)，并把 5 种首发范围改为
谜语 / 猜单词 / 单词接龙 / 字母重排 / 填字。

## 四、校验器覆盖（加载即校验）

选项下标越界、重复条目、难度枚举、单词只含字母、梯子两端等长且池内词等长、
填字格坐标越界与「既非阻断格又无单词覆盖」的格子、块列表格式、
`format_version` 比引擎新则**拒绝而不是半读**、`min_engine_version` 高于引擎则拒绝、
内容文件里出现 `eval(` / `exec(` / `__import__` / `lambda` 一律判为不合格（包是数据，不是代码）。

## 五、验证

```
.venv/Scripts/python.exe -m pytest tests -q                  -> 82 passed
.venv/Scripts/python.exe scripts/build_content_pack.py --check -> up to date (6 files, 154 items)
.venv/Scripts/python.exe scripts/smoke_headless.py           -> SMOKE PASSED（两版 × 14 种，含点击）
npm test                                                     -> CLIENT CHECK PASSED / SMOKE PASSED
```

## 六、未做

- 内容包还没有**社区投稿/审核**流程，也没有签名（调研结论：签名留到有第三方作者之后，先用哈希清单）。
- 难度分级仍是**派生**的（谜语按题干长度、字母重排按词长），真正的编辑分级需要人来定，
  包格式已经能表达（每条自带 `difficulty`），改的是数据不是代码。
- 英文版仍在使用中文包内容（`content_kind` 已对齐，包本身未做语言变体）；
  按 `id@en` 后缀的变体机制已在加载器里预留，见 SPEC-101 §阶段 M5。

## 七、复现

```
.venv/Scripts/python.exe scripts/build_content_pack.py
.venv/Scripts/python.exe scripts/build_content_pack.py --check
.venv/Scripts/python.exe -m pytest tests/test_content_pack.py -q
```
