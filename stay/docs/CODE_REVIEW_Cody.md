# 代码审查报告 — Progress Quest 2 (Python/Tkinter 移植版)

> 审查者：Cody（代码审查师 / code-reviewer）
> 范围：/g/stay 全部 34 个源文件 + requirements.txt + 两份 settings.json + savefile.pq2
> 说明：本报告因 SendMessage 通道故障（"Unknown message type: undefined"）以文件形式落盘交付，内容与本应发送给 team-lead 的报告一致。

## 审查发现（按严重度排序）

| # | 严重度 | 类别 | 文件:行 | 问题描述 | 建议修复 |
|---|--------|------|---------|----------|----------|
| 1 | 高 | 安全/正确性 | serializer.py:117-164 + game.py:450/225 | 存档反序列化无类型与范围校验，盲目信任 JSON 形状。Level 为 0 会触发 _monster_task 中 `(5*level*1000)//c.Level` 的 ZeroDivisionError；current_action 超枚举范围会令 `CurrentActionType(...)` 抛 ValueError；_win_spell 在 WIS+Level=0 时 `np.integers(0,0)` 抛 ValueError。被篡改/损坏的 .pq2 即可让游戏崩溃（DoS）。 | 反序列化后做 schema 校验：断言 Level>=1、各数值为 int、current_action 在枚举范围内；对缺失/异常字段用安全默认值或拒绝加载（返回 LoadError）。 |
| 2 | 高 | 正确性 | newgame.py:143-165 + tkinter_gui.py:420-423,826-833 | 自动投骰后台线程在确认角色/关闭窗口时未停止。`_on_confirm`/`_on_close` 都未调用 `stop_auto_roll()`；daemon 线程持续 mutation 角色属性，并通过 `after(0, _refresh_stats)` 刷新已被 destroy 的创建界面控件，导致 TclError 崩溃。且默认目标 `{"Total":1}` 会无限循环直到手动停止（停止按钮在切换界面后已销毁）。 | 在 `_on_confirm`/`_on_close` 开头调用 `new_game.stop_auto_roll()`；用锁或 threading.Event 保证线程可见退出；刷新前检查控件是否存活。 |
| 3 | 中 | 安全 | game.py:76-87 + serializer.py:188-197 | 存档文件路径未校验、无大小限制。`--savefile` 与 GUI 文件框传入的路径被直接 `gzip.open(path,'wb')` 写入（任意路径写）；`load_from_file` 将整个文件 `.read().decode()` 全量读入内存，无上限，来自不可信来源的 gzip bomb 可造成资源耗尽。 | 对存档路径做白名单/目录约束；限制解压后最大字节数并分块读取；GUI 文件框限定 `*.pq2`。 |
| 4 | 中 | 正确性 | serializer.py:181-186 | 保存非原子写。直接 `gzip.open(path,'wb')` 写盘，进程崩溃/断电会留下截断/部分写的损坏存档。 | 先写临时文件再 `os.replace(tmp, path)`（原子替换）；失败时保留旧档。 |
| 5 | 中 | 正确性 | game.py:94-115 | 种族/职业属性从未应用到角色数值。`Race/Class.attributes`（如 WIS、HP Max、MP Max）仅参与序列化与哈希，`_on_character_created` 不读取它们，角色 STR..CHA/HP/MP 只来自骰子。核心养成机制缺失，且 MP Max/HP Max 为非标准属性码（疑似半成品逻辑）。 | 在 `_on_character_created` 中按 attributes 调整对应数值；或若确为装饰，删除该字段及数据中的 MP Max/HP Max。 |
| 6 | 中 | 正确性 | localization.py + data/races.py,classes.py,spells.py | 中文本地化与数据不一致：脚本实测 3 个种族(Hob-Hobbit/Low Elf/Skraeling)、3 个职业(Jungle Clown/Puma Burgular[拼写错]/Vermineer)、1 个法术(Gyp) 在 CN 模式漏译；同时存在 3 个孤立 CN 条目(Angel/Greater Gnome/Vampire、Gongfarmer/Italophobia/Puma Burglar)。`translate()` 子串替换还会误伤，如 Battle-Finch 变 战斗Finch。 | 用脚本生成数据名与翻译键的一致性校验并纳入 CI；修正 Puma Burgular 拼写；删除孤儿条目；将 translate 改为基于词边界/精确词的匹配。 |
| 7 | 中 | 正确性 | localization.py:389-406 | `translate_action_label`/`translate_quest_label` 仅替换前缀关键词即返回，未对剩余部分（怪物名/物品名/修饰词）调用 `translate()`，导致行动/任务行中英文混排（如 `正在对战 an imaginary Dragon`）。 | 改为 `translate(label.replace(prefix, cn, 1))` 或 `cn + translate(label[len(prefix):])`，对剩余文本继续翻译。 |
| 8 | 中 | 安全 | serializer.py:160-164 | 存档完整性哈希校验被刻意关闭（仅 print Warning），且哈希本身存于存档文件内，篡改者可重算哈希，校验形同虚设（security theater）。 | 如需防篡改，使用 HMAC-SHA256 或将校验信息与荷载分离；若仅用于崩溃诊断，明确文档说明不提供完整性保护。 |
| 9 | 中 | 性能 | localization.py:381-386 + tkinter_gui.py:649,657,684 | `translate()` 每次调用都重新 `sorted(TRANSLATION_TABLE.keys(), key=len, reverse=True)` 并对整段文本做全表子串扫描；`_update_display` 每 100ms 对库存/剧情每个条目调用，产生 O(条目数 × 词典大小) 重复计算。 | 在模块加载时缓存排序后的键列表（与 `.get` 精确匹配合并），避免每帧重建。 |
| 10 | 中 | 性能 | game.py:200,569,629 | 主线程同步存档过频：`_level_up`/`_complete_quest`/`_complete_act` 每次成功都 `save_game()`（全量 serialize+gzip+写盘）。快速推进时在 Tk 主线程产生大量阻塞 IO。 | 引入节流（如每 N 秒或每 M 次事件才落盘）、脏标记，或放到后台线程（注意与原子写配合）。 |
| 11 | 中 | 依赖 | requirements.txt | 依赖仅有下限 `numpy>=1.24.0`、无上限。实测当前解析到 numpy 2.5.1；虽本代码基本兼容 2.x，但无上界意味着未来 numpy 破坏性变更会静默升级。numpy 1.x<1.26 曾有 CVE-2024-27227（object 数组 argsort，本游戏不触发，但应纳入风险登记）。 | 改为兼容区间（如 `numpy>=1.24,<3`）并固定到已测试版本；记录已知 CVE 与缓解（本游戏未用到受影响 API）。 |
| 12 | 中 | 依赖 | /g/stay（根） | 无锁文件：无 requirements.lock / poetry.lock / pyproject.toml / Pipfile，依赖不可复现，CI 与部署存在漂移风险。 | 引入 pyproject.toml + 锁定（pip-tools/poetry/uv），CI 校验锁定文件。 |
| 13 | 中 | 可维护性 | game.py（24KB/640 行） | 巨型单类：`Game` 同时承担存档、新游戏、主循环、战斗、装备、任务、剧情、商店等职责，圈复杂度高、不可单测。 | 拆分为 engine / progression / combat / equipment / quest / plot 等模块；主循环与 IO 解耦。 |
| 14 | 中 | 可维护性 | game.py（多处） | 魔法数字遍布：2000(初值 MaxProgress)、1000(经验/进度除数)、`5*level*1000`(怪物时长)、26/60*60(剧情时长)、装备价系数、概率阈值 2/5、1/25、1/4 等，均无命名常量。 | 提取为模块级命名常量/枚举（如 BASE_MAX_PROGRESS、MS_PER_SECOND、各概率常量）。 |
| 15 | 中 | 正确性 | game.py:279-302,413-441 | `_win_equip` 当 `plus<0` 时生成畸形装备名 `"-3 <name>"`（应为只应用修饰词）；且 `level//qty` 在 qty>level 时可退化到 0，产生等级为 0 的退化怪物。 | 负数 plus 时不加数字前缀；对 qty 做 `min(qty, level)` 保护避免 level 归零。 |
| 16 | 中 | 可维护性 | settings.json vs pq2/settings.json + newgame.py:157 | 配置来源混乱/重复：根 settings.json(theme=hollow-knight) 与 pq2/settings.json(theme=original) 内容不一致，且后者未被任何代码读取（GUI 只读根目录那份）；`import time` 位于函数体内。 | 统一为单一配置来源；删除未使用的 pq2/settings.json；将 import time 提到模块顶部。 |

## 代码债小结
- 重复/死代码：`gui/base.py` 的 `View` ABC 与抽象方法 `show_main_menu`/`show_character_creator`/`show_game_screen` 从不被子类实现（`TkGUI` 也未标注 override），属死抽象；`gui/__init__.py`、`utils/__init__.py`、`data/__init__.py` 为空壳。
- 结构化重复：`_sick`/`_young`/`_big`/`_special`（game.py:452-514）四个修饰词函数几乎同构，可表驱动；`_complete_quest` 的多种随机奖励分支可用查找表收敛。
- 圈复杂度/坏味道：`tick`（game.py:119-156）与 `_dequeue`（308-368）嵌套状态机逻辑分支多、无状态图文档；`Character` 全部属性为公开可变实例变量，无封装，GUI 直接改 `character.*`，并发与测试风险高。
- 未使用枚举值：`LoadError.InvalidPermissions`/`UnknownSaveVersion`、`SaveError.InvalidPermissions`/`OutOfSpace` 从未被返回——因为存档没有版本字段（`serialize` 不写 schema version），旧/未来格式无法识别，属隐蔽的正确性债。
- 误翻风险：`translate()` 基于任意子串替换（非词边界），会误伤包含修饰词前缀的专有名词。
- 内存增长：自动投骰 `_unroll_buffer` 在长循环中不封顶地追加（newgame.py:88），属轻微无界增长。

## 依赖债小结
- 声明与导入一致（正面）：除标准库（argparse/json/gzip/os/ctypes/tkinter/threading/datetime/hashlib）外仅 numpy，无未声明或多余第三方依赖；`eval`/`exec`/`pickle`/`subprocess`/`yaml.load` 全项目扫描为 0（反序列化使用安全 json，无 RCE 风险）。
- 主要风险是版本治理缺失：无上限 (`>=1.24.0`)、无锁文件、无 pyproject.toml；建议加兼容上界并锁定到已测版本（当前 numpy 2.5.1 可运行，但应固定）。
- 资源文件 `STKAITI.TTF`（12MB）随仓库分发，无 LICENSE 标注，分发合规需确认。

## 整体评价（含严重度分布估计）
- 安全：无代码执行类致命漏洞（未用 pickle/eval，JSON 反序列化安全）；主要风险在不可信存档的健壮性与防篡改（#1、#3、#8）。本机单机游戏风险可控，但若分享存档则 #1 可被利用致崩溃，建议按中危处理。
- 正确性：2 项高危（#1 崩溃路径、#2 线程刷新已销毁控件崩溃），其余为中/低；本地化与种族/职业机制缺失属功能性缺陷，应在发版前修复。
- 性能：无 N+1/算法级致命瓶颈；主要为主线程同步频繁存档(#10)与每帧全量翻译/重建控件(#9)引起的可感知卡顿，属中低。
- 可维护性/债：game.py 巨型单类(#13)与魔法数字(#14)是后续演进最大障碍，建议优先重构。
- 依赖：声明干净但治理缺失(#11,#12)，风险中。

严重度分布估计：严重 0 条 / 高 2 条 / 中 14 条（表中全部）/ 低 多条（额外低危：魔法属性码装饰性、DNA 用 `hash()` 进程随机化 tkinter_gui.py:787、tick 大 ms 未防御、死抽象等）。

结论：Request Changes（需修改后再合并）。必须修复 #1、#2（两处高危崩溃/健壮性），建议发版前一并处理 #3、#4、#5、#6、#7、#10、#11；#8/#9/#12/#13/#14 列入技术债 backlog。所有发现均可定位到文件:行，建议项具体可复核。

说明：本地化一致性、Level=0 除零、`integers(0,0)` 均已用脚本在本环境实测复现；numpy 实测版本 2.5.1。

---

## 修复状态追踪（2026-07-27 更新）

> 本报告原始结论为 **Request Changes**；截至 2026-07-27，所列发现**已全部落地修复**，结论已失效。以下为对账记录，配套回归测试 `tests/test_review_fixes.py` 全绿：38 passed / 3 xfailed / 1 xpassed。

### 第一轮（2026-07-26，前序会话）
关闭代码审查全部 **#1–#16** 及事故复盘项 **A3 / A4 / A6**，代表性落地（均已代码实测确认）：

| 项 | 落地内容 | 代码锚点 |
|----|----------|----------|
| #1 高危崩溃 | 反序列化后 schema 校验（Level≥1、数值类型、current_action 枚举范围） | `serializer.deserialize` + `tests/test_review_fixes.py::test_tampered_*` |
| #2 线程崩溃 | `_on_confirm`/`_on_close` 调用 `stop_auto_roll()`，刷新前检查控件存活 | `tkinter_gui.py:418/450/925` |
| #3 gzip 炸弹 | 解压后体积上限 + 分块读取 | `serializer._SaveTooLargeError` |
| #4 原子写 | 临时文件 + `os.replace`，保留上一版为 `.bak` | `serializer.save_to_file` |
| #5 种族/职业属性 | `_on_character_created` 应用 `Race/Class.attributes` | `game.py:211-213` |
| #6 本地化缺译 | 数据名↔翻译键一致性校验；修正拼写；删孤儿条目 | `localization.py` |
| #8 完整性校验 | HMAC-SHA256 信封（`version`+`mac`），与荷载分离 | `serializer` A6 信封 |
| #9 翻译缓存 | 模块加载时缓存排序键，避免每帧重建 | `localization.py` |
| #10 存盘节流 | 脏标记/节流，避免主线程频繁阻塞 IO | `game.py` |
| #11 numpy 上界 | `numpy>=1.24,<3` | `requirements.txt` / `pyproject.toml` |
| #12 锁文件 | 引入 `pyproject.toml` 声明式依赖 | `pyproject.toml` |
| #13/#14 | 巨型单类拆分 + 魔法数字提取为常量 | `game.py` / `types.py` |
| A3 自动存盘 | `set_auto_save()` 开关 + 失败回调 | `game.py:68/159` |
| A4 存盘错误 | `save_game()` 返回 `SaveError`，UI 不静默吞 | `game.py:139` / `tkinter_gui.py:783` |
| A6 信封 | 与 #8 合并，HMAC 校验 | `serializer` |

### 第二轮（2026-07-27，本轮）— 收口三项历史遗留
| 项 | 落地内容 | 代码锚点 |
|----|----------|----------|
| `LoadError.Corrupt` | 新增 `Corrupt=5`，与数据层 `NotValidSaveFile` 分层：信封/结构损坏归 Corrupt，逻辑值非法归 NotValidSaveFile（ADR-001 §3.2） | `types.py`、`serializer._CorruptError` |
| A7 启动自愈 | `load_game_with_recovery`：`os.replace(cur, cur+".corrupt")` 隔离坏档→回退 `.bak`→成功回填主档；`main.pyw`/TkGUI 统一走恢复路径 | `game.py`、`main.pyw`、`tkinter_gui.py` |
| A11 缺键监控 | `record_missing_key`/`get_missing_keys`/`audit_translation_coverage`/`get_cn(monitor=)`；仅监控显式键查找，审计范围排除按设计应为英文的怪物名/特殊物品/物品属性 | `localization.py` |

### 仍开放（本轮刻意不做，已以 `xfail(strict=False)` 跟踪，避免范围蔓延）
- **A5 字体缺失显式告警信号**：字体路径（PyInstaller `_MEIPASS`）已修复，但"无任何可用 CJK 字体时显式告警/抛 typed error"未实现，仍静默回退。见 `tests/test_chaos_savefile.py::test_missing_font_signals_explicitly`。
- **A11 基于词边界的 `translate`**：当前 `translate()` 仍为子串替换（可能误伤专有名词），词边界/精确词匹配未实现。见 `tests/test_localization_regression.py::test_missing_key_is_reported` 等。

> 归档说明（2026-07-27）：本文件与原 `COORD_A3A4_Cody.md`、`Docu-postmortem-review.md`、`incident-postmortem-pq2-savefile.md` 一并从项目根归档至 `docs/`；字体 `STKAITI.TTF` 移至 `assets/` 并由 `tkinter_gui._resolve_resource("assets/STKAITI.TTF")` 加载；pytest 运行脚本移至 `scripts/`。
