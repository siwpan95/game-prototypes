# 事故响应桌面演练（工作流 3）— Progress Quest2 启动崩溃 + 中文界面乱码

- 系统：Progress Quest 2 — The Progression（Python / Tkinter 桌面放置养成游戏）
- 演练主题：存档损坏导致启动即崩溃 + 中文界面乱码
- 演练日期（演练时钟）：D0
- 主持 / IC：team-lead　|　记录 / SRE：Rex（sre-engineer）　|　对外沟通：tech-writer

> 核实说明（已用 Read + 实跑验证，非臆测）：
> 1. `pq2/game.py::load_game` 对**截断(500B)、空文件、半写 JSON** 三类损坏档，实测均返回 `LoadError.NotValidSaveFile`，**未抛未捕获异常**。
> 2. 因此严格意义上，"启动即崩溃"的表象由「`except Exception` 吞错 + `.pyw` 无控制台使诊断不可见 + 无自愈/备份致永久卡死」共同构成；`except Exception` 是**唯一防崩溃屏障**，其本身即脆弱点（不捕获 `BaseException` 子类如 `MemoryError`/`SystemExit`；且吞掉全部错误导致不可观测、不可诊断、无法触发自愈）。
> 3. 中文乱码两条真实根因已实测：字体路径在冻结发布下解析错误导致 `STKAITI.TTF` 缺失；`localization.translate()` 子串替换制造中英混杂乱码。

---

## 一、事故时间线（演练时钟）

| 节点 | 时间 | 事件 / 动作 |
|------|------|-------------|
| D0 14:02 | 用户 A 报告 | 微博 / 玩家群反馈："双击 `main.exe` 没反应，进程一闪而过，进不去游戏"。无错误窗口。 |
| D0 14:05 | 用户 B、C 跟进 | 同样"启动即退出"；其中 B、C 为中文 Windows，额外报告"界面中文全变方块/中英混杂乱码"。 |
| D0 14:10 | 首次响应（Rex/SRE） | 建事故频道，拉起战情室；按"启动失败 + 区域化乱码"初步定性为潜在 SEV2，启动 15 分钟响应 SLA。 |
| D0 14:18 | 分诊确认 | 复现假设：损坏的 `savefile.pq2` 被启动器以 `--savefile savefile.pq2` 加载（与 `main.pyw` 文档用法一致）；中文用户另受字体回退影响。 |
| D0 14:35 | 证据收集（Rex） | 本地实测：截断/空/半写档均返回 `NotValidSaveFile`，`.pyw` `print()` 无控制台不可见；冻结发布下字体路径解析到 `_MEIxxxx` 临时目录，`STKAITI.TTF` 缺失。确认根因方向。 |
| D0 14:55 | 缓解（止血） | 临时方案：发布"存档自检 + 启动自愈"热修说明（坏档→提示并回退备份/新建游戏）；中文用户临时指引"安装微软雅黑/宋体或手动指定字体"。 |
| D0 15:30 | 沟通 | 群内/社区公告第一版（见第五节）；内部站会同步进展。 |
| D0 17:00 | 根治方案评审 | architect + code-reviewer 评审：原子写 + `.bak` 轮换、错误类型细分、字体资源定位改用 `sys._MEIPASS`、整词翻译。 |
| D0 18:00 | 恢复判定 | 热修灰度发布，坏档用户可正常进入（新建或恢复）；乱码用户经字体探测+告警后回退到可用中文字体。标记"缓解生效"，关闭战情室。 |
| D0+1 ~ D0+3 | 复盘与固化 | 落地原子写/备份/校验/混沌测试（见第七、八节），输出无责复盘。 |

---

## 二、影响范围

**受影响用户（量化估算依据）**
- 触发条件高度本地化：仅"本机异常关机 / 磁盘写满导致上次存档截断或半写"的用户会撞上启动失败。该条件与用户机器健康度相关，与版本无关。
- 估测受影响比例 **≈ 3%–8% 活跃用户**（依据：同类桌面放置游戏在"异常关机/掉电"场景下的存档损坏自发率经验区间；非全局故障）。
- 中文界面乱码：**中文 Windows 用户子集 ≈ 受影响用户的 40%–60%**，且集中出现在"冻结发布(.exe) + 系统缺少雅黑/宋体回退"的机器上（精简版/GHOST 版系统高发）。

**功能影响**
- 启动失败用户：**核心功能完全不可用**（无法进入主菜单/继续游戏），且因无备份/自愈而**每次启动反复复现** → 对个体等同"永久性宕机"。
- 乱码用户：功能可用，但**可理解性严重降级**（中文显示为方块/中英混杂），误操与差评风险高。
- 其余用户（存档完好 / 英文界面）：无影响。

**数据损坏风险**
- 损坏 `savefile.pq2` 本身**不可恢复**（截断/半写数据丢失）——受影响用户损失当前进度，属**不可逆数据丢失**。
- 无 `.bak` 轮换、无写后读回校验，意味着一次写失败即可"就地覆盖"唯一存档（见第四节根因 Why3）。
- 无跨用户扩散风险（纯本地文件，无服务端）。

---

## 三、SEV 评级

**最终定级：SEV2（主要功能降级）**

**定级理由**
- 符合 SEV2 定义"主要功能降级"：受影响用户**核心功能（进入游戏）完全不可用**，且伴随数据丢失与区域化严重体验降级。
- 触发面为**用户本地条件**（掉电/满盘），非系统性版本缺陷，故未达 SEV1"所有用户受影响 / 服务宕机"。
- 具备可行缓解路径（新建游戏 / 恢复备份），非完全无解，故高于 SEV3/SEV4。

**为何不是更高（SEV1）**
- 非全量用户受影响；无服务端，无"数据中心级宕机"；未影响新游戏玩家与存档完好用户；可通过发布热修+自愈在数小时内缓解。

**为何不是更低（SEV3/SEV4）**
- 不只是"次要功能问题"：对撞上该问题的用户是**启动即死、进度全失**，个体影响等同 SEV1 体验；且损失不可逆（无备份）。降级幅度与数据风险均超过 SEV3/SEV4 阈值。

**建议**：若后续发现"某次自动更新批量损坏存档"或"冻结发布普遍缺字体影响全体中文用户"，应立即上调至 **SEV1**。

---

## 四、角色分配

| 角色 | 担当 | 职责 |
|------|------|------|
| Incident Commander（事故指挥官） | team-lead | 全局指挥、定级拍板、升级决策、对外口径最终确认 |
| 沟通负责人（Comms） | tech-writer | 对外用户公告、社区/群话术、内部状态页更新 |
| 记录员（Scribe） | Rex（sre-engineer，本人） | 时间线、5 Why、行动项追踪、本演练文档 |
| 存档/序列化响应者 | code-reviewer | 原子写、备份轮换、错误类型细分、防御式解析修复 |
| 架构/自愈设计 | architect | 存档格式版本头、启动自愈、字体资源定位方案 |
| 测试/验证 | testing-expert | 回归用例、混沌与固化测试（截断/半写/满盘/缺字体） |
| i18n/文案 | tech-writer（协同） | 翻译整词化、缺键监控、用户提示文案 |

---

## 五、状态更新与沟通模板

### 5.1 对内——站会 / 事故群消息话术（一版）

> **【事故同步】PQ2 启动失败 + 中文乱码（SEV2）**
> 进展：已定位——损坏的 `savefile.pq2` 被启动器加载，当前 `load_game` 用 `except Exception` 把错误折成 `NotValidSaveFile` 后 `main.pyw` 仅 `print` 并返回 1；但 `.pyw` 无控制台，用户看不到任何提示，表现为"双击没反应"。且无备份/自愈，坏档每次启动反复复现。中文乱码另因冻结发布下字体路径解析到 `_MEIxxxx` 临时目录，`STKAITI.TTF` 缺失 + `translate()` 子串替换制造中英混杂。
> 已做：建战情室；实测复现三类损坏档；发布临时自愈说明与中文用户字体指引。
> 下一步：code-reviewer 出原子写+`.bak` 热修；architect 出字体资源定位(`sys._MEIPASS`)与启动自愈设计；testing-expert 补混沌测试。
> 需要：社区公告拟稿（tech-writer）；确认是否灰度热修通道可用。
> 下次更新：15:30。

### 5.2 对外——用户公告草稿（一版）

> **【已知问题·进度同步】关于部分玩家"启动后秒退"与"中文显示为方块"的说明**
>
> 我们已收到部分玩家反馈：游戏启动后立即退出、无法进入；部分中文界面显示为方块或中英混杂。
>
> **原因（简化版）**：当电脑异常关机或磁盘空间不足时，上一次自动存档可能被截断/半写。当前版本在检测到损坏存档后未能给出清晰提示，而是静默退出；同时中文版在部分系统上字体回退异常，导致显示错乱。**受影响的是"存档损坏"或"特定系统字体缺失"的玩家，并非所有人。**
>
> **临时解决办法**：
> 1. 启动失败：删除/改名游戏目录下的 `savefile.pq2`（会丢失当前进度，建议先备份），或等待我们推送的"存档自检+自动恢复备份"热修，届时坏档会提示你恢复备份或开新档。
> 2. 中文方块：安装"微软雅黑/宋体"等中文字体后重开；热修将自动检测并回退到可用中文字体。
>
> **我们将在 24 小时内推送热修**，并补充存档自动备份，避免再次丢失进度。给您带来不便，我们深表歉意。
> —— PQ2 团队

---

## 六、根因分析（5 Why）

### 6.1 主线：启动失败 / 存档损坏

- **Why1 — 为什么用户"启动即失败、进不去游戏"？**
  → 损坏的 `savefile.pq2` 在启动时被加载；`load_game` 返回 `NotValidSaveFile`，`main.pyw` 仅 `print(...)` 并 `return 1`；但 `.pyw` 无控制台，提示不可见，用户只见"进程一闪而过"。且无"新建游戏/恢复备份"回退，坏档每次启动反复触发同一失败。
- **Why2 — 为什么存档会损坏？**
  → 用户机器异常关机 / 磁盘写满，导致**最后一次自动存档被截断或半写**。
- **Why3 — 为什么存档会"就地截断/半写"且无可恢复副本？**
  → `save_game` 在游戏主循环（`_level_up` / `_complete_quest` / `_complete_act`）中被调用，但其**返回值被忽略**；序列化用 `gzip.open(...).write(...)` **单次覆盖写**，没有"临时文件 + 原子 rename"、没有 `.bak` 备份轮换、没有"写后读回校验"。一次写失败即覆盖唯一存档。
- **Why4 — 为什么错误被"吞掉"且不可观测？**
  → `load_game` 用 **`except Exception` 把一切异常折成单一 `NotValidSaveFile`**，丢失根因与可诊断信息；`main.pyw` 的诊断只走 `print()`（`.pyw` 无控制台）；系统**无任何崩溃上报/遥测**，导致只能通过用户口头反馈才发现。
- **Why5 — 为什么没有自愈 / 备份 / 可观测？**
  → 设计上**未把"存档损坏"作为一等事故**处理：缺少原子写、备份轮换、启动自愈（坏档→回退备份或新游戏）、字体/缺键健壮回退与告警。可观测性（崩溃/字体缺失/损坏计数）为零。

> 实测佐证：截断(500B)/空文件/半写 JSON 三类损坏档，`load_game` 均返回 `NotValidSaveFile`、游戏状态保持 `None_`——证明当前确有防护，但该防护即"唯一屏障"且不可见、不可恢复。

### 6.2 支线：中文界面乱码

- **Why1 — 为什么中文界面乱码/方块？**
  → 中文以方块显示，或中英混杂难以阅读。
- **Why2 — 为什么？**
  → `STKaiti` 字体未注册，回退字体缺少 CJK 字形；同时 `translate()` 子串替换制造中英混杂。
- **Why3 — 为什么 STKaiti 未注册？**
  → `_register_local_font` 依赖 `_PROJECT_ROOT`（由 `__file__` 三级 `dirname` 推导）。**冻结发布（PyInstaller）下 `__file__` 落在 `_MEIxxxx` 临时目录**，`STKAITI.TTF` 不在该路径 → 字体缺失（实测：`_PROJECT_ROOT` 误解析为 `C:\Users\...\Temp\_MEI12345`）。
- **Why4 — 为什么没有可靠兜底？**
  → `_get_font_family` 回退链假设系统存在 `Microsoft YaHei/SimSun`，但精简版/非中文 Windows 可能缺失；且 `translate()` 对复合串做**无词边界子串替换**（实测 `"Seek the Magic Orb" → "寻找 the Magic 法球"`），缺失键仅回退英文而非占位/告警。
- **Why5 — 为什么设计如此？**
  → 本地化未做"字体存在性探测 + 显式失败告警"；翻译采用朴素子串匹配而非整词/词边界匹配；i18n 缺键无监控。

---

## 七、行动项（表格）

类型：止血(Stopgap) / 根治(Root-cause) / 预防(Preventive)

| # | 行动 | Owner | 时限 | 类型 |
|---|------|-------|------|------|
| A1 | 发布热修：启动器加载存档前先做"损坏自检"，坏档弹窗提示并**回退 `.bak` 或新建游戏**，不再静默退出 | code-reviewer + Rex | D0+1（24h） | 止血 |
| A2 | 中文用户临时指引 + 字体探测：缺失 CJK 字体时显式告警并回退到可用中文字体 | tech-writer + code-reviewer | D0+1 | 止血 |
| A3 | `save_to_file` 改为**原子写**（写临时文件 + `os.replace`）+ **单份 `.bak` 轮换**（与 ADR-001 §3.3/§5 一致；多份备份为后续增强）；**先落地作为 A6/A7 的恢复底座**；写满盘须接线 `SaveError.OutOfSpace`（types.py 已定义，从未接线） | code-reviewer | D0+7（1 周） | 根治 |
| A4 | `load_game` **细分错误类型**、保留根因链（不再 blanket `except Exception` 吞错）；`main.pyw` 以 GUI 弹窗/日志替代 `print` | code-reviewer | D0+7 | 根治 |
| A5 | 字体资源定位**双路径**：优先 `getattr(sys, '_MEIPASS', None)`，缺失则回退现有 `_PROJECT_ROOT`（__file__ 推导）；平台化字体加载抽象（Win: `AddFontResourceExW` / 其他: 系统 CJK 字体探测）；清理 `tkinter_gui.py:18` 过期 `d:\allin\stay` 注释（债#14）；与 code-reviewer 约定资源路径接口边界 | architect + code-reviewer | D0+7（1 周） | 根治 |
| A6 | **存档信封 + 防御式解析（合并原 A8，按 ADR-001）**：版本信封(format/version/sha256) + 原子写 + .bak；`LoadError` 复用 `UnknownSaveVersion`（已定义未接线）并仅增补 `Corrupt`；**信封层严格、数据层宽容**（tolerant reader：未知键忽略、缺失键默认值、已知字段做类型/范围断言）；手写轻量校验（纯 stdlib，不引 pydantic）；写后读回仅对"dirty 节流落盘"点做，并与 A3 的 .bak 配对 | architect | D0+14（2 周） | 预防 |
| A7 | **启动自愈**：每次启动前校验 + 自动恢复最新完好 `.bak`；**依赖 A3 的 .bak 与 A6 的 `Corrupt` 检测**，排在 A3/A6 之后（设计草案见 §九） | Rex | D0+21（A3/A6 后，约 3 周） | 预防 |
| A8 | **监控/遥测**：崩溃上报、字体缺失上报、存档损坏计数（即便桌面端也做轻量埋点/本地日志） | Rex | D0+21（3 周） | 预防 |
| A9 | **混沌/固化测试**：CI 常驻注入"截断/半写/磁盘满/缺字体"用例，断言"不崩溃 + 可自愈" | testing-expert | D0+21 | 预防 |
| A10 | i18n：`translate()` 改为**整词/词边界**匹配，缺键上报监控而非仅回退英文 | tech-writer（i18n） | D0+14 | 预防 |

> **评审修订（architect 评审，D0）**：① A6 与 A8 合并为单条（见上），统一按 **ADR-001** 实施；复用 `LoadError.UnknownSaveVersion`、仅增补 `Corrupt`；信封层严格 / 数据层宽容；手写轻量校验（纯 stdlib，不引 pydantic）。② 自动存盘点（`_level_up`/`_complete_quest`/`_complete_act`）须**消费 `save_game` 返回值**，不得静默吞错（code-reviewer 契约修复）；A6 读后写/重试同样消费返回错误。③ A3 先行作为 A6/A7 恢复底座；A7 延至 A3/A6 之后（D0+21）。④ A5 双路径 + 平台化字体抽象，并清理 `tkinter_gui.py:18` 过期注释（债#14）。

---

## 八、预防措施

1. **监控告警**
   - 轻量崩溃/异常上报（桌面端可落本地日志 + 可选上报），覆盖 `load_game` 各错误码与字体缺失事件。
   - 关键指标：存档损坏计数、启动失败率、中文乱码相关支持工单量；设阈值告警。
   - 启动失败必须**可见**：用 GUI 弹窗/系统通知替代 `print()`（`.pyw` 无控制台）。

2. **存档完整性校验（ADR-001 信封）**
   - 存档写入**版本信封**（format/version/sha256 硬校验）；读取时先校验信封，再 JSON 解析；`LoadError` 复用 `UnknownSaveVersion`、增补 `Corrupt`。
   - 写后读回**仅对"dirty 节流落盘"点**做（与 A6 自动存盘节流配对），不一致即重试/告警，避免写放大。

3. **启动自愈 / 备份**
   - `save_to_file` **原子写**：写 `savefile.pq2.tmp` → `os.replace` 到 `savefile.pq2`，杜绝半写。
   - **`.bak` 轮换**：保留最近 1–2 份历史存档；启动检测到当前档损坏时自动回退到最近完好备份。
   - 损坏且无备份时，明确提示并允许"开新游戏"，绝不静默退出。

4. **序列化防御式解析（信封严格 / 数据宽容）**
   - 信封层严格校验 `format/version/checksum`；数据层 **tolerant reader**：未知键忽略、缺失键给安全默认值、已知字段做**类型/范围断言**（手写轻量校验，纯 stdlib，不引 pydantic；与 ADR-001 一致）。
   - `load_game` 区分 `FileNotFound / NotValidSaveFile / Corrupt / UnknownSaveVersion`，保留根因用于诊断与遥测。

5. **混沌 / 固化测试**
   - CI 常驻用例：注入**截断档、空档、半写 JSON、磁盘满（mock 写失败）、缺字体**环境，断言进程不崩溃且能自愈/提示。
   - 对 `translate()` 增加"复合串、缺键、子串冲突"回归用例，断言输出为完整中文而非中英混杂。

6. **本地化健壮性**
   - 字体：用 `sys._MEIPASS`（PyInstaller 资源目录）或显式资源路径定位 `STKAITI.TTF`；注册失败则**显式告警**并回退到探测到的首个可用 CJK 字体。
   - 翻译：`translate()` 改为基于词边界/整词表匹配，避免子串误替换；缺键上报监控、UI 占位而非裸英文。

---

## 九、A7 启动自愈恢复流程设计（草案，对齐 ADR-001 §5）

> 状态：草案。契约口径已锁定于 ADR-001 §5（信封 `format/version/checksum`、`.bak` 单份轮换、`Corrupt` 语义）。本节供 code-reviewer(A3/A6)、tech-writer(A4 弹窗)、testing-expert(A10) 对齐；最终以落地代码为准。

### 9.1 目标与边界
- 消费 A6 的 `LoadError.Corrupt` / `NotValidSaveFile` / `UnknownSaveVersion` 与 A3 的 `.bak` 恢复底座。
- **不崩溃、不静默**：任何损坏档必须以 GUI 弹窗呈现（A4），并提供"恢复备份 / 开新游戏"选项（A1 止血逻辑固化）。
- 依赖 ADR-001 §3.3 的 `.bak` 语义：每次成功落盘前 `savefile.pq2` 复制为 `savefile.pq2.bak`（单份）。

### 9.2 恢复决策树 —— `Game.load_with_recovery(filepath) -> (LoadError, recovered: bool)`
```python
def load_with_recovery(self, filepath: str):
    primary = self.load_game(filepath)          # ADR-001 §3.4 分类错误
    if primary == LoadError.None_:
        return (LoadError.None_, False)         # 正常
    if primary in (LoadError.Corrupt, LoadError.NotValidSaveFile, LoadError.UnknownSaveVersion):
        # 隔离损坏样本（不删除）：保留取证，对接 A9
        corrupt_path = filepath + ".corrupt"
        if os.path.exists(filepath):
            try: os.replace(filepath, corrupt_path)
            except OSError: pass
        bak = filepath + ".bak"
        if os.path.exists(bak):
            # 用临时 Character 探测备份，避免污染当前 character
            probe = Character()
            saved, self.character = self.character, probe
            bak_err = self.load_game(bak)
            self.character = saved if bak_err != LoadError.None_ else probe
            if bak_err == LoadError.None_:
                self.save_game()                 # 回填当前档（原子写；当前档已隔离故不再覆盖 .bak）
                return (LoadError.None_, True)   # 已恢复
        return (primary, False)                  # 无备份 / 备份也坏 → 交 UI 新游戏
    return (primary, False)
```
安全说明：损坏主档在信封/校验阶段即抛错（§3.2），`_apply_data_tolerant` 未执行，故 `self.character` 不会被半写入；对 `.bak` 用临时 `Character()` 探测，成功才交换，进一步隔离。恢复前先 `os.replace` 把损坏档隔离为 `.corrupt`（**不删除**），保留唯一取证样本。

### 9.3 启动接线（main.pyw / TkGUI）
- 启动器 `--savefile savefile.pq2` 加载；改 `main.pyw`：不再 `print+return 1`，改为
  `err, recovered = game.load_with_recovery(savefile)`；
  `err == None_` 正常进入（recovered 时轻提示"已从备份恢复"）；否则交由 TkGUI 错误弹窗（A4）。
- TkGUI `_on_load_game`（手动加载）同样走 `load_with_recovery`，统一决策路径。

### 9.4 边界与取舍（已对齐 architect）
- **B1 单份 `.bak`（已确认）**：ADR-001 §3.3/§5 单份；A3 已收敛单份（见 A3 行）。多份留作后续增强。
- **B2 新游戏兜底（已确认）**：`Corrupt` 后允许"直接开新游戏"（§5 最后兜底），与 A1 一致。
- **B3 弹窗 + 推荐恢复（已确认）**：不静默自动覆盖；保留损坏样本供排查；无 GUI 的 headless 回退日志 + 退出码。architect 已向 team-lead 推荐"弹窗 + 默认预选恢复备份"口径。
- **B4 回填当前档（已确认）**：恢复成功后回填当前档，下次启动走正常路径（备份 checksum 已过 load 验证，安全）。
- **B6 `.corrupt` 隔离（增强，已采纳）**：恢复前把损坏当前档 `os.replace(current, current+".corrupt")` 隔离，而非删除；`.corrupt`=坏样本（取证）、`.bak`=好备份，两文件职责不同、互不冲突。单份 `.corrupt` 每次覆盖即可，复杂度极低。对接 A9 遥测/本地日志（上报损坏模式，呼应 Why5"无遥测"）。architect 将把此动作补入 ADR-001 §5。
- **B5 遥测（A9）**：每次 `Corrupt` / 恢复成败 emitting 事件（损坏计数、恢复成功率）；`.corrupt` 样本可作离线分析输入。

### 9.5 测试（对接 A10）
- 当前损坏 + .bak 完好 → `(None_, True)`，并生成 `savefile.pq2.corrupt`（原坏样本被隔离、非删除），当前档被回填为备份内容，`.bak` 仍为好备份。
- 当前损坏 + 无 .bak → `(Corrupt/NotValidSaveFile, False)`，UI 提示新游戏。
- 当前损坏 + .bak 也损坏 → `(xxx, False)`，UI 提示新游戏。
- 用户选"新游戏" → 进入 NewGame，不加载损坏档。

---

*本演练基于 `/g/stay` 代码实读与本地复现（截断/空/半写档均返回 `NotValidSaveFile`；冻结发布字体路径误解析至 `_MEIxxxx`；`translate()` 子串替换实测产生中英混杂）。所有结论锚定真实代码路径，可作为后续根因修复与预防措施的输入。*

---

## 状态更新（2026-07-27）— §9 自愈方案已落地

本复盘 §7–§9 描述的修复方案**现已实现**，事故闭环：

- **信封/结构层损坏分类（ADR-001 §3.2）**：新增 `LoadError.Corrupt = 5`，将"信封/结构损坏"（解压失败、JSON 坏、mac 不匹配、缺 version）与"数据层 schema 非法"（`NotValidSaveFile`）明确分层；对应 `serializer._CorruptError` / `_InvalidDataError`。
- **A7 启动自愈（§9.1–§9.3）**：`Game.load_game_with_recovery` 已落地——
  1. 主档加载失败 → `os.replace(current, current+".corrupt")` **隔离**（保留唯一取证样本，不删除）；
  2. 回退最近 `.bak`；成功则 `save_game()` **回填主档**；
  3. `main.pyw` 与 TkGUI `_on_load_game` 统一走恢复路径，恢复时轻提示"已从备份恢复"。
- **A11 缺键监控（呼应 Why5 无遥测）**：`localization` 新增 `record_missing_key` / `get_missing_keys` / `audit_translation_coverage`，启动时审计翻译覆盖；范围刻意排除按设计应为英文的怪物名/特殊物品/物品属性，避免监控被噪声淹没。

**验证**：回归测试全绿（38 passed / 3 xfailed / 1 xpassed）；`tests/test_chaos_savefile.py`、`tests/test_review_fixes.py` 覆盖 Corrupt 分类与 A7 恢复矩阵。

**仍开放（非本次事故范围，已 xfail 跟踪）**：A5 字体缺失显式告警信号、A11 基于词边界的 `translate` 精确匹配。

> 归档说明（2026-07-27）：本文档与原 `CODE_REVIEW_Cody.md`、`COORD_A3A4_Cody.md`、`Docu-postmortem-review.md` 一并从项目根归档至 `docs/`；字体 `STKAITI.TTF` 移至 `assets/`；pytest 运行脚本移至 `scripts/`。
