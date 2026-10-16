# M5 第二步：两个 pygame 客户端合并为一份（像素级等价证据）

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** `text_adventure/` 与 `text_adventure_zh/` 两个桌面客户端
> **证据** 全部为当轮实测；复现命令见文末

## 一、先量后动

| 文件 | 行数 | 差异 |
| --- | --- | --- |
| `domain.py` | 19 | **0** |
| `events.py` | 24 | **0** |
| `main.py` | 22 | **0** |
| `engine.py` | 108 | 4 行（两条「没有活动中的谜题」文案） |
| `ui.py` | 1582 | 226 行（95 个差异块） |

即：三个文件**逐字相同**，一个只差文案，只有 `ui.py` 有实质差异——而 95 个差异块里，
除两处布局选择外全是界面文案。所以合并 = 把文案抽成表 + 把两处布局变成按语言的分支。

## 二、两处**不是文案**的差异（保留，不统一）

1. **模式选项**：英文客户端给 4 个模式（默认「均衡」），中文客户端只给「随机」。
2. **提示条位置**：中文放在页脚之上（不遮住谜题），英文画在屏幕中部。

统一它们等于**悄悄改掉一版的行为**，所以两者都按语言保留（`client/translations.py` 的
`MODE_OPTIONS` / `HINT_BAR_AT_BOTTOM`，各有注释说明来源）。

## 三、等价性的证明方式：像素比对

文案抽取靠人眼核对 226 行差异块是不可靠的，所以用**渲染结果**判定：
把同一份谜题数据分别喂给旧客户端与合并后的客户端，逐像素比对同一画面。

```
两版各 44 个画面：菜单 + 14 种谜题 × 3 难度 + 结果页
中文：44/44 完全一致
英文：44/44 完全一致
```

**它抓到三处真实差异**，每一处都是人眼扫 diff 不会发现、但用户看得见的：

| # | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| 1 | 颜色卡片顺序不同（红绿蓝黄 vs 红蓝绿黄） | 旧界面写死显示顺序，而 `color_sequence.COLORS` 是另一个顺序（红蓝绿黄）；我误用了数据顺序 | 显示顺序进表（`SWATCH_ORDER`），注释写明它与数据顺序不同 |
| 2 | 英文卡片大小写不同（`red` vs `Red`） | 旧英文界面直接用颜色键（小写），旧中文用中文词；我照英文习惯首字母大写 | 表里英文用**小写**，与旧界面一致 |
| 3 | 英文界面字体不同 | 旧英文用拉丁字体族，旧中文用 CJK 字体族；我统一用了 CJK | 字体族跟随语言（`_load_font(..., prefer_cjk=...)`），英文界面不再无端换字体 |

第 1、2 条尤其说明问题：**「看起来对」和「和以前一样」是两件事**。

## 四、过程中我自己的三个错误（都被工具链抓住）

1. 用**多层脚本接力**改文件：一次替换把标签表达式写进了颜色参数、把每个数字键都标成「删除」。
   表现是 `invalid color name` 与「按任意数字都会删输入」。
   处置：改为**一趟生成**（`scripts/oneoff/build_unified_client.py`），输入是旧文件、输出是新文件，
   每条替换要么命中要么报错，不再叠加补丁。
2. 翻译函数叫 `t`，而绘制方法里 `t` 是文本 surface 的局部变量 → `TypeError: 'pygame.surface.Surface' object is not callable`。
   处置：界面侧导入为 `tr`，并在表里注明为什么有两个名字。
3. 变量遮蔽之外，还有一次**顺序错误**：先做文案替换会把 `if btn.text == "检查"` 变成
   `if btn.text == tr(...)`（恒真且永不触发的比较）。处置：先做基于「按键标识」的分发替换，再做文案替换。

## 五、删除的正当性（功能面 × 接任者）

| 被删的功能面 | 接任者 | 验证 |
| --- | --- | --- |
| `text_adventure/ui.py`（英文界面，1582 行） | `client/ui.py` + `client/translations.py`（`lang="en"`） | 44/44 画面像素一致 |
| `text_adventure_zh/ui.py`（中文界面） | 同上（`lang="zh"`） | 44/44 画面像素一致 |
| `text_adventure/engine.py`、`text_adventure_zh/engine.py` | `client/engine.py`（`lang` 参数） | 无头冒烟把 14 种画面各驱动一遍；错误文案按语言 |
| 两份 `domain.py`、`events.py`、`main.py` | `client/domain.py`、`client/events.py`、`client/main.py` | 两文件逐字相同，直接搬运 |
| `shared.paths.bootstrap_import_path(build=...)` | `bootstrap_import_path()`（无参数） | 目录已删，参数失去意义；留着会误导 |
| `scripts/migrate_rng_calls.py` | 无（其目标目录已删） | 删掉以免留下指向不存在文件的工具 |

## 六、基线已固化

像素证据不再是一次性输出：`scripts/client_screens.py` 记录/校验两种语言各 44 个画面的
像素哈希（`tests/client_screens.json`），并由 `tests/test_host_contract.py` 在每次测试中校验。
`--record` 可重录，但改动会被显式看见。

## 七、验证

```
.venv/Scripts/python.exe -m pytest tests -q                       -> 160 passed
.venv/Scripts/python.exe scripts/client_screens.py --language zh   -> MATCH THE BASELINE
.venv/Scripts/python.exe scripts/client_screens.py --language en   -> MATCH THE BASELINE
.venv/Scripts/python.exe scripts/check_build_consistency.py        -> CLIENT CONSISTENCY PASSED
.venv/Scripts/python.exe scripts/smoke_headless.py                 -> SMOKE PASSED（两语言 × 14 种）
npm test                                                           -> CLIENT CHECK / SMOKE / BROWSER E2E
```

## 八、复现

```
.venv/Scripts/python.exe scripts/client_screens.py --language zh
.venv/Scripts/python.exe scripts/client_screens.py --record --language zh   # 有意改动后重录
.venv/Scripts/python.exe -m client.main --lang en        # 手动开英文桌面版
.venv/Scripts/python.exe -m client.main --lang zh        # 手动开中文桌面版
```

## 九、未做

- 桌面客户端未接入进度/每日一题（那是服务端与网页/终端已有的能力）：桌面版仍是"单机随机出题"。
  接进来是独立任务，价值明确但不在本次合并范围。
- `scripts/oneoff/` 保留了两个只跑一次的工具（生成合并后客户端、按钮调用形状检查），
  留作证据而不是日常工具；它们指向的旧文件已不存在，重跑需要先 `git show` 取回。
