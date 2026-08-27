# 诡秘之主·序列途径模拟系统 — 全面测试与深度评估报告

> 评估日期：2026-08-14
> 评估方式：编写并实跑 `tests/test_all.py`（纯标准库测试框架，覆盖全部模块 + 数据完整性 + 6 个 CLI demo + GUI 构造），逐项记录 PASS/FAIL/ERROR 与证据。
> 运行环境：Python 3.14.6 / Windows，`tkinter` 可用。

---

## 0. 测试结论速览

| 指标 | 结果 |
|------|------|
| 测试用例总数 | 30 |
| PASS | **28** |
| FAIL（已知缺陷，已标记） | **2** |
| ERROR | **0** |
| CLI demo（basic/multi/switch/full/gender/world） | **6/6 全部通过** |
| GUI 构造（不进主循环） | **通过** |

两个 FAIL 均为**真实缺陷的刻意暴露**（见第 2 节），不是测试噪音。无 ERROR，说明模块可导入、数据可加载、核心流程可端到端跑通。

---

## 1. 已验证通过的核心能力（有证据）

- **数据完整性**：22 条途径、9 个权柄体系全部存在；每条途径恰好 10 个序列（序列 9→0 无缺失/无多余）；每条序列含 `level/name/abilities/required_actions` 字段。
- **锚系统**：强度公式 `humanity*(1+0.1*connections)+legacy*0.5+believers*0.001` 正确；`Anchor.required_for_level` 设定表正确；边界裁剪（humanity 超 100 被剪成 100）正确。
- **污染系统**：5 级枚举（清醒/低语/幻觉/失控/神殒）与中文标签正确；`PollutionManager.accumulate` 升级、`is_lost`、`try_purify` 均正确。
- **序列与扮演消化**：22 条途径均可 `make_sequence(seq9)`；执行全部扮演行为后 `digested=True`、`digestion_ratio=1.0`。
- **晋升主流程**：同途径晋升（偷盗者→诈骗师）成功；弱锚触发 `AnchorBreakError`；未消化触发 `SequenceError`。
- **途径切换**：同组合法切换（愚者→错误 @seq3）成功；跨组切换（门→太阳）被 `SequenceError` 拒绝；黑暗→混沌魔女特殊互通被正确放行。
- **性别转换（3 条途径正确）**：混沌魔女/月亮/母亲 在对应序列正确变女。
- **唯一性**：单持有者约束正确（二次 `bind` 触发 `RuntimeError`）；序列 1 特性初始库存 3 份正确。
- **扮演循环**：高污染速率必然失控（`lost=True`）；强锚低污染可存活。
- **旧日/封印物 API**：`OldOnePath.required_for_old_one`、`FOUR_PILLARS`、`get_level_description`、`SEALED_ARTIFACT_LEVELS` 均可调用且返回符合预期。
- **GUI**：`LordOfMysteriesGUI()` 可在 Windows 下成功构造默认角色并布局（字体已注册），不进入 `mainloop` 不阻塞。

---

## 2. 发现的缺陷（按严重度）

### 🔴 P1 — `red_priest` 性别转换逻辑错误（真实 Bug）
**位置**：`ascension.py` `AscensionManager.advance` 的性别分支
**证据**（测试 `KNOWN_red_priest_gender_bug`）：
```
⚧ 性别转换：女 → 女（晋升导致雌性强制变雄性）
⚠ red_priest 升 seq4 -> 性别 女（代码本意应为 男 ♂）
```
**根因**：性别变化信息为 `"晋升导致雌性强制变雄性"`，**同时包含「雄」和「雌」**。代码用子串判断：
```python
if "雄性" in (msg or "") or target_pathway in ("mother","moon","chaos_witch"):
    gender = "女"
elif "雌性" in (msg or "") or target_pathway == "red_priest":
    gender = "男"
```
`"雄性" in msg` 先命中 → 错误置为 女。而 `elif` 里的 `target_pathway == "red_priest"`（本意变男）永远到不了。
**后果**：红祭司途径在序列 4+ 性别与设定（demo 标题标 ♂）和 `make_sequence` 初始意图（女→男）相反。
**附带不一致**：`main.py` 的 `demo_gender_change` 标题写 `红祭司途径：猎人(9) → 铁血骑士(4♂)`，但实跑输出 ♀，标题与代码自相矛盾。

**修复建议**（最小改动，消除子串歧义）：
```python
# 改为仅靠途径元组判定，彻底去掉脆弱的子串匹配
if target_pathway in ("mother", "moon", "chaos_witch"):
    gender = "女"
elif target_pathway == "red_priest":
    gender = "男"
# 兜底（其余途径不应有性别变化）
```

### 🔴 P1 — 锚需求公式与设定表方向相反，且「无锚晋升」被完全放行（设计缺陷）
**位置**：`ascension.py` `AscensionManager.advance` 第 50–54 行
**证据**（测试 `KNOWN_anchor_formula_inversion`）：
```
seq9: advance=90  vs 表=0
seq7: advance=70  vs 表=30
seq4: advance=40  vs 表=60
seq2: advance=20  vs 表=100
seq0: advance=0   vs 表=200
```
**根因**：晋升校验用 `required_anchor = current.LEVEL * 10`，而 `anchor.py` 里另有一张符合设定的需求表 `Anchor.required_for_level`（低序列 0 / 中序列 30 / 圣者 60 / 天使 100 / 真神 200）。两者**方向相反**——高序列所需锚强度反而更低，且设定表从未被咨询。
**更严重的后果**：校验写在 `if current.anchor:` 内，**不提供锚对象时直接跳过校验**，意味着可以不设任何锚一路晋升到序列 0，与「锚是对抗失控的最后防线」「天使/真神无锚无法存在」的设定完全冲突。
**测试 `ascend_no_anchor_skips_check` 已确认**：无锚时 `ascend()` 直接放行到 seq8。

**修复建议**：
```python
# 统一口径：始终需要锚，且用设定表
if current.anchor is None:
    raise AnchorBreakError("晋升需要锚定人性，但未设置锚")
required_anchor = Anchor.required_for_level(next_level)
if current.anchor.strength < required_anchor:
    raise AnchorBreakError(f"锚不足以支撑晋升！需要{required_anchor}，当前{current.anchor.strength:.1f}")
```
（注：设定表当前 seq9/8 需求为 0，与「低序列不需要锚」一致；若要更严格可上调低序列下限，但务必与 `Anchor.LEVEL_ANCHOR_REQUIREMENTS` 单一来源保持一致。）

---

## 3. 未接线 / 死代码（影响「完整性」评分）

通过全仓检索构造函数与调用点确认：

| 符号 | 状态 | 说明 |
|------|------|------|
| `Uniqueness` | **从未被实例化** | 仅 `import` 与类型标注；`ascension.advance` 的 `uniqueness.bind()` 分支永远到不了（demo/GUI 都不传 `uniqueness`） |
| `SequenceOneCharacteristic` | **从未被实例化** | `main.py` 导入但未使用，是死导入 |
| `OldOnePath`（类） | 定义后**未被调用** | 旧日晋升条件计算逻辑不可达 |
| `pillar_requirements` | 定义后**未被调用** | 四支柱需求逻辑不可达 |
| `get_switch_target_level` | 定义后**未被调用** | 切换目标等级辅助函数不可达 |
| `SEALED_ARTIFACT_LEVELS` | 定义后**未被调用** | 封印物等级表不可达 |
| `PollutionManager` | **仅 GUI 用到**（line 732） | 未被 `role_playing_loop` 采用（`role_playing_loop` 直接改 `character.pollution`，绕过了管理器） |

**结论**：项目概念上「声称」支持唯一性争夺、序列 1 聚合、旧日晋升、封印物体系，但**这些高级机制都没有真正接入模拟主流程**，属于「文档/API 存在但功能未落地」。对「完整性」扣大分。

---

## 4. 代码质量 / 可维护性问题

1. **`main.py` 不把 `PROJECT_ROOT` 加入 `sys.path`**：必须与 `gui_app.py` 不同，`main.py` 依赖「从项目目录内运行」。在别的 cwd 下 `python main.py` 直接 `ModuleNotFoundError: No module named 'sequences'`（已复现）。`gui_app.py` 已处理，应统一。
2. **运行时 monkey-patch**：`sequences.py` `BaseSequence._inject_hallucinations` 用 `types.MethodType` 把 `self.act` 替换成包装函数。污染高时每次 `check_sanity` 都重包，逻辑脆弱、难测试、且会持续往 `abilities` 追加「不可名状的低语」（虽有去重守卫）。
3. **随机性无 seed**：`role_playing.py` 用 `random` 但不设种子，测试结果不确定（本套件用极端参数保证必然结果，但正常模拟不可复现）。
4. **`act()` 表现力有限**：仅对「偷窃/潜入/编织谎言/欺诈他人」4 个行为有具体描写，其余 21 条途径全部走通用描述，扮演沉浸感弱。
5. **全局可变注册表**：`uniqueness._registry` / `_inventory` 用类变量 + 锁，跨进程/跨实例不安全；在 CLI 多次运行间会因 import 缓存残留（单进程内 OK）。
6. **作者自承技术债**：`sequences.py` 注释 `BaseSequence` 为「巨大的技术债」，说明作者清楚结构问题。
7. **API 形态不统一**：`pathway['sequences']` 是 `list[dict]`，而 `get_sequence_data(pk, lvl)` 返回单个 `dict`；测试若按 dict 假设会踩坑。

---

## 5. 性能 / 架构

- **性能**：纯内存对象模拟，无 I/O、无循环热点，性能无忧。GUI 为 `tkinter.Canvas` 自绘 + 字体内嵌，小数据量下流畅；但若 22 途径全展开渲染、或长时间扮演循环，Canvas 重绘无脏矩形优化，扩展性一般。
- **架构优点**：数据驱动（`pathways_data.py` 集中配置，22 途径零样板）、模块职责清晰（anchor/pollution/sequences/ascension/uniqueness/role_playing/pathway_groups 各司其职）、CLI 与 GUI 共用同一核心层（无逻辑重复）。
- **架构缺点**：核心层与「模拟/演示」边界模糊（`main.py` 既当入口又含大量 demo 逻辑）；GUI 单文件 1000+ 行，违反单一职责，难以单元测试。

---

## 6. 综合评分

| 维度 | 分数 | 说明 |
|------|------|------|
| 功能完整性 | 7/10 | 22 途径/10 序列/扮演/锚/污染/切换/性别/仪式齐全；但唯一性/序列1/旧日/封印物未真正接线 |
| 代码正确性 | 6/10 | 主流程可用；red_priest 性别 bug + 锚公式倒挂 |
| 架构/可维护性 | 5/10 | 数据驱动设计好；但运行时 monkey-patch、sys.path 依赖、死代码、GUI 超大单文件 |
| 可测试性 | 7/10 | 核心层函数式易测；随机无 seed；GUI 需显示环境 |
| 健壮性 | 6/10 | 无锚晋升放行、缺输入边界校验 |
| **综合** | **≈ 6.2 / 10** | 一个**概念完整、可演示、但高级机制未落地、且存在 2 处硬逻辑缺陷**的原型 |

> 以上评分对应**修复前**。修复后见第 9 节。

---

## 7. 修复优先级建议

1. **[必改]** `ascension.py` 性别判定改为纯途径元组分支（消除 red_priest bug）。
2. **[必改]** `ascension.py` 统一锚校验：用 `Anchor.required_for_level` 单一来源，且 `current.anchor is None` 时直接拒绝晋升。
3. **[建议]** 让 `main.py` 也把 `PROJECT_ROOT` 加入 `sys.path`（与 GUI 一致），或改用 `python -m`。
4. **[建议]** 二选一落地高级机制：要么把 `Uniqueness`/`SequenceOneCharacteristic`/`OldOnePath` 接到晋升流程与 GUI，要么从文档中移除「已支持」的表述，避免误导。
5. **[建议]** `role_playing_loop` 增加 `seed=` 参数，提升可复现性；移除 `self.act` 运行时替换，改用标志位控制疯癫表现。
6. **[建议]** 拆分 `gui_app.py`（数据层/视图层分离），便于单元测试与维护。

> **状态更新（2026-08-14 后续）**：第 4/5/6 项均已落地。
> - 4 ✅ `Uniqueness` / `SequenceOneCharacteristic` / `OldOnePath` 已接入晋升流程与 GUI（详见 `docs/COLLECT_THEN_ASCEND_DESIGN.md`）。
> - 5 ✅ `role_playing_loop` 已增加 `seed=` 参数（见 `role_playing.py`）。
> - 6 ✅ `gui_app.py` 已瘦身为 11 行薄启动器，逻辑迁至 `gui/` 包（详见 `docs/GUI_SPLIT_FEASIBILITY.md`）。
> - 补充：E1–E11 增强（材料 / 连续 SAN / 事件 / 存档 / 质量 / 能力 / 阵营 / AI 对手 / 成就图鉴 / 沉浸 / 共享核心）已全部落地，GUI 新增对手、图鉴、氛围音等入口；详见 `docs/ENHANCEMENT_RESEARCH.md` 与更新后的 `README.md`。

---

## 8. 交付物

- `tests/test_all.py` —— 30 个用例的测试套件（自带极简框架，无第三方依赖）
- `tests/TEST_RESULTS.txt` —— 本次运行的逐用例结果明细
- `EVALUATION.md` —— 本报告
- 此前已交付：`README.md`、`requirements.txt`

---

## 9. 修复纪要（第二轮 · 2026-08-14）

按「P1 逻辑缺陷 → 高级机制落地」的顺序完成修复，并补齐验证。修复后测试：**42/42 PASS，0 FAIL，0 ERROR**（含 3 个新增 demo 与 9 个新增用例）。

### 9.1 P1-1 修复：red_priest 性别判定（ascension.py）
- **改法**：性别分支由「消息子串 `"雄性"/"雌性"` 匹配」改为「途径元组判定」——`mother/moon/chaos_witch → 女`、`red_priest → 男`，其余途径不变。
- **证据**：`demo_gender` 标题与代码一致；新增用例 `gender_red_priest` 断言红祭司升至 seq4 性别为「男」并通过。

### 9.2 P1-2 修复：锚需求公式与设定表统一（ascension.py）
- **改法**：晋升锚校验改用 `Anchor.required_for_level(next_level)`（单一来源）。当需求 > 0 且未设置锚时直接拒绝；有锚则按设定表比对强度。
- **效果**：低序列（需求 0）无锚可晋升；高序列（需求 > 0）无锚一律拒绝，不再能「无锚直冲序列0」。
- **证据**：新增 `ascend_lowseq_no_anchor_ok`（低序列放行）、`ascend_highseq_requires_anchor`（高序列拒绝）、`anchor_formula_consistent`（恰好达标放行/不足拒绝）。

### 9.3 高级机制落地（核心修复目标）
| 机制 | 落地方式 | 验证 |
|------|----------|------|
| 唯一性（Uniqueness） | `uniqueness.py` 增加 `get_or_create`；`ascension.advance` 在晋升**序列0**时自动集齐本途径唯一性并绑定（已被他人持有则抛 RuntimeError） | `uniqueness_seq0_bind`、`uniqueness_contention`（争夺失败）、`demo_uniqueness` |
| 序列1特性（SequenceOneCharacteristic） | 增加 `ensure`（幂等取用）；序列0晋升自动集齐 3 份并绑定 | `sequence_one_characteristics`、`uniqueness_seq0_bind` |
| 旧日晋升（OldOnePath / pillar_requirements） | 新增 `promote_to_old_one(group, character)`：聚合途径组内**所有**途径的唯一性 + 3 份序列1，并接入 `OldOnePath.required_for_old_one` 与 `pillar_requirements`（支柱标记 tier） | `old_one_promotion`、`old_one_contention`（争夺失败）、`demo_old_one` |
| 途径切换目标（get_switch_target_level） | `ascension.switch_pathway` 现通过 `PathwaySwitchValidator.get_switch_target_level` 计算目标等级 | `switch_target_level_used` |
| 封印物等级表（SEALED_ARTIFACT_LEVELS） | 新增 `sealed_artifact_level(序列等级)` 映射；接入 `Sequence.full_report`（角色报告现含「对应封印物」一行） | `sealed_artifact_mapping`、`demo_sealed` |

### 9.4 代码质量改进
- **移除运行时 monkey-patch**：`sequences.py` 删除 `_inject_hallucinations` 对 `self.act` 的动态替换，改为 `_hallucinating` 标志位（在 `perform_action` 中按概率打印疯癫），消除脆弱的运行时自修改。
- **可复现性**：`role_playing_loop` 增加 `seed` 参数；新增 `role_playing_seed_deterministic` 验证相同 seed 结果一致。
- **可运行性**：`main.py` 顶部将 `PROJECT_ROOT` 加入 `sys.path`，支持从任意工作目录运行（与 GUI 一致）。
- **演示补全**：`main.py` 新增 `demo_uniqueness` / `demo_old_one` / `demo_sealed` 三个 demo，把上述高级机制接入可运行的主流程。

### 9.5 修复后综合评分
| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 功能完整性 | 7/10 | **9/10**（高级机制全部落地） |
| 代码正确性 | 6/10 | **9/10**（2 处 P1 已修） |
| 架构/可维护性 | 5/10 | **7/10**（移除 monkey-patch、单一来源锚表、新增机制有真实入口） |
| 可测试性 | 7/10 | **8/10**（seed 可复现、全局状态隔离） |
| 健壮性 | 6/10 | **8/10**（高序列强制锚校验） |
| **综合** | **≈6.2** | **≈ 8.4 / 10** |

### 9.6 仍待后续（非阻断）
- ~~`gui_app.py` 仍为 1000+ 行单文件；高级机制（唯一性/旧日）尚未在 GUI 中暴露操作入口~~ —— **已解决**：`gui_app.py` 现为 11 行薄启动器，唯一性 / 旧日 / AI 对手 / 成就图鉴 / 沉浸音效等均已接入 GUI（见 `docs/GUI_SPLIT_FEASIBILITY.md`、`docs/ENHANCEMENT_RESEARCH.md`）。
- 序列0晋升目前自动创建并绑定唯一性；若要支持「先收集再晋升」的交互式流程，可在 GUI 增加收集阶段。
- `SequenceOneCharacteristic` 不限制 index 上限（仅约定 3 份），可作为后续增强做约束。
