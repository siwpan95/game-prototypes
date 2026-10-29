# 01 · 插件化内核选型调研

> **检索日期** 2026-10-16（全部 URL 均为该日实测可访问）
> **范围** 只回答一个问题：把「谜题 = 插件」的平台化做实，内核该选谁、Python 侧该怎么落地。
> **证据等级** ① 官方仓库/官方文档/规范原文 ② 官方托管 API（npm registry、GitHub API、PyPI JSON）③ 第三方分析与新闻（仅作背景，不作判据）。文中每条结论后标注来源编号，编号对应文末《来源清单》。
> **本项目代码事实** 只引用仓库相对路径（`pyproject.toml`、`text_adventure/gameplay_pool/base_puzzle.py` 等），不含任何机器绝对路径。

## 结论摘要

1. **Cordis 活着且维护密集，但仍未发布正式版**：npm 上 `cordis` 的 `latest` 已是 `4.0.0-rc.11`（2026-10-14 发布），GitHub 同日打 `v4.0.0-rc.11` 标签，仓库 2026-10-15 仍有提交、未归档、MIT 许可；README 明确写着「API 尚不稳定，可能在不通知的情况下变更」。**[S01][S02][S03]**
2. **Cordis 的强项正好是「谜题装载」需要的那部分**：`inject` 声明依赖、服务依赖决定加载顺序、注册即「可逆副作用」（reload/teardown 自动撤销）。这几条有官方概念文档背书（DSH 的 cordis-primer 与论文摘要）。**[S05][S04]**
3. **Python 侧没有 Cordis 等价物**：cordis 本体是 TS/JS；社区确有 `python-cordis`（0.1.x，2026-08 发布）与 `fshoocn/cordis-port` 这类第三方移植，但均为 0 star 的实验件，**不可作为依赖**。Python 生态能提供的只有「发现 + 钩子」，没有「依赖解析 + 回滚」。**[S08][S09][S10]**
4. **Python 侧推荐：不引入插件框架**。14 种谜题同仓维护、接口已经被 `BasePuzzle` 收敛，真正缺的不是插件发现，而是**生命周期与回滚的显式化**——那应该做在 JSON-RPC 协议层（`puzzle.create`/`puzzle.dispose`），而不是在 Python 进程内再造一套 IOC。`pluggy`/`stevedore` 解决的是另一个问题。**[S11][S12][S13][S14]**
5. **「谜题 = 插件」有可查的同类实践**：KTaNE 的炸弹模块（模块可独立开发/装载 + 独立说明书）、shapez 的 Puzzle DLC（题目包 + 编辑器 + 分享）、H5P/Moodle 的题型内容包。它们共同点是「**题目/模块是内容单位，宿主只认统一接口**」，与本项目方向一致。**[S16][S17][S18]**
6. **风险红线**：RC 依赖 + 双运行时 + 跨语言边界，三者叠加会把「调试成本」变成主要成本；建议设定三条明确的退回纯 Python 的触发线（见《风险与红线》），并把退回成本压到「删掉 Node 目录 + 换一个入口脚本」。**[S01][S05][S06]**

## 逐项调研

### 1. Cordis 现状

**版本线与维护状态**（均为 2026-10-16 实测）

| 事实 | 值 | 来源 |
| --- | --- | --- |
| npm `cordis` `dist-tags` | `latest = 4.0.0-rc.11`，`next = 4.0.0-beta.5` | [S01] |
| 最近版本节奏（rc 线） | rc.0(2026-03-28) → rc.7(07-14) → rc.8(08-10) → rc.9(08-29) → rc.10(09-08) → rc.11(10-14) | [S01] |
| 包元数据 | MIT；`main: lib/index.js`；依赖仅 `cosmokit@^1.8.1`、`@standard-schema/spec@^1.1.0`；仓库 `github.com/cordiverse/cordis` 的 `packages/core` | [S01] |
| 官方插件包（同仓 monorepo） | `@cordisjs/plugin-loader@1.0.0-rc.8`、`plugin-hmr@1.1.1`、`plugin-include@1.1.1`、`plugin-timer@1.1.4`（均 2026-10-14）、`plugin-group@1.0.0`（2026-03-24） | [S01b] |
| GitHub 仓库 | 9,208 star / 586 fork / 49 open issues；`created 2022-05-17`；`pushed_at 2026-10-15`；`archived=false`；License `MIT`；`homepage` 指向 DSH 的 cordis-primer | [S02] |
| 最近提交（2026-10-14/15） | `fix(core): settle disposed fibers to DISPOSED (#133)`、`fix(core): stop service lookup at isolation boundaries (#209)`、`refactor(core): move ctx.root to ctx[Context.root] (#207)` | [S02] |
| GitHub Release | `v4.0.0-rc.11`（2026-10-14T04:22Z，标记为非 prerelease 的普通 release） | [S03] |
| 稳定性声明（原文） | 「**Cordis is under active development. The API is not yet stable and may change without notice.**」 | [S01readme] |

**官方文档与论文**

- README 列的两个入口：论文 arXiv 2608.25512 与论文仓库 `cordiverse/paper`；文档指向 DSH 托管的 cordis-primer，并注明「official documentation is still under construction」。**[S01readme]**
- 论文《A Programming Paradigm for Spatiotemporal Composability》：arXiv:2608.25512 [cs.PL]，2026-08-26 提交 v1，92 页 1 图 2 表；作者 Yifan Shi（1,2）、Wei Zhang（1）、Tianyi Cui（2），机构为 (1) Peking University、(2) DeepSeek-AI；DOI 10.48550/arXiv.2608.25512。**[S04]**
- 论文要点（摘要原文可核）：把动态组合拆成两个正交维度——**temporal composability**（组件移除时能完全撤销其副作用）与 **spatial composability**（声明并反应式管理组件间依赖）；做法是把经典的 effect / coeffect 提升为运行时机制，形式化为 **revertible effects**（每个上下文变换带有运行时保存的逆）与 **reactive coeffects**（每次上下文变更按组件的 coeffect 规格分类，驱动其激活/停用），统一为单一 context 类型，称为 **context paradigm**；实现即 Cordis：核心库做 effect 追踪与 coeffect 解析，声明式 loader 做配置对账与 hot module replacement。**[S04]**
- 论文仓库 `cordiverse/paper`：3,015 star，2026-08-13 建仓，最后推送 2026-08-28；**仓库未声明 License**（GitHub API `license: null`）——若要引用论文文字需另行确认授权。**[S04b]**

**Cordis ↔ Koishi ↔ DeepSeek Harness 的关系（逐条核过，不靠转述）**

- **Koishi 仍跑 Cordis v3**：`koishijs/koishi` 的 `packages/core/package.json`（版本 4.18.11）依赖写的是 `cordis: ^3.18.1`；npm 上 `@cordisjs/core` 的 `latest` 也停在 `3.18.1`（2025-06-01），而 `cordis` 本体已是 4.0.0-rc.11——**v3 与 v4 是两条并行的包线**。**[S07a][S07b]** 第三方分析称「Koishi 用了 Cordis 四年、其 Web 控制台本身也是 Cordis 应用」，与论文摘要中 Koishi 的表述方向一致，但属背景而非判据。**[S19]**
- **DSH 把 Cordis 源码 vendored 进来**：`vendor/README.md` 记录 8 个 Cordis 家族包全部改为 `@deepseek-ai` 作用域（`cordis` → `@deepseek-ai/cordis`），当前 vendor 版本 **4.0.0-rc.10**，上游 `cordiverse/cordis` 的 `main@f8ea3cd`（2026-09-08），并附「本地改动日志」。**[S06]** 该 vendor 记录的同步过程本身有仓库内的记录文档（`governance/docs/records/cordis-upstream-sync_2026-10-08.md`）。**注意**：本仓记录与在线检索缓存里出现的 `4.0.0-rc.7` 是同步前的旧快照，**当前状态以 vendor 清单的 rc.10 为准**。
- **Cordis 是 DSH 的框架层，不是 DSH 的产物**：Cordis 仓库建于 2022-05-17，Koishi 依赖 v3 线，DSH 仓库 2026-08-13 才建；三者是「元框架（Cordis）→ 长期使用者（Koishi v3）→ 新旗舰使用者（DSH v4 vendored）」的关系。**[S02][S07a][S03b]**
- 概念文档：DSH 官方站点的《Cordis 入门》给出五个核心概念（插件=实现 Service 的对象；上下文是服务容器 `ctx.<key>`；**通过 `inject` 声明依赖，加载顺序由服务依赖表达而非手工编排**；类型化事件 `emit/waterfall/parallel/serial/bail`；**注册是可逆副作用，用 `ctx.effect()`/`ctx.on()` 安装，reload 与 teardown 时撤销**），并给出实践规则「每个注册都要有对应 disposer，需要顺序就放进同一个 effect」。**[S05]** 该文档是 DSH 对其 vendored 版本的描述，**不是 Cordis 官方文档**（官方文档自述仍在建设中）。**[S01readme]**

### 2. Cordis 在「游戏/内容型应用」中的适用性

**强项（对谜题装载是正面命中）**

| 能力 | Cordis 的机制 | 对「谜题即插件」意味着什么 | 来源 |
| --- | --- | --- | --- |
| 动态组合 | 插件即实现 Service 的对象，由 `inject` 声明依赖，加载顺序由依赖图推出 | 新增谜题不必改宿主的启动序列；谜题依赖「计分服务」「题库服务」时可声明而非约定顺序 | [S05] |
| 热插拔 / 回滚 | 注册是可逆副作用（`ctx.effect()`），reload 与 teardown 撤销；论文形式化为 revertible effects | 谜题卸载/重载时，它注册的题目、按钮、监听器不会残留——这正是 14 种谜题并行时最容易出 bug 的地方 | [S05][S04] |
| 依赖注入 | 上下文是服务容器，按 key 查找而非 import 实现 | 谜题与「渲染/状态/存档」解耦，符合 `text_adventure/engine.py` 已有的事件总线方向 | [S05] |
| 生态与治理 | MIT、单仓 monorepo、loader/hmr/include/group/timer 官方件齐全、维护密集 | 许可与 DSH 一致（MIT），便于本项目保持 MIT | [S01][S01b] |

**弱项（必须在设计里提前吃掉）**

1. **生态规模有限**：官方件只有 loader/hmr/include/group/timer/logger 这一小组（见上表版本清单），没有「游戏/内容」方向的官方扩展；npm 上 `cordis` 的 dependents 数远小于主流框架（包里自带 2 个运行期依赖）。**[S01][S01b]**
2. **TS 类型是事实上的接口层**：官方概念文档描述事件分发模式、`waterfall` 语义、`declare module` 声明合并都建立在 TypeScript 上。**[S05]** 若谜题语言是 Python，**Cordis 的类型系统一点忙也帮不上**——跨语言时接口只能靠协议约定与运行时校验兜住。
3. **Python 侧无等价物**：见第 3 节。
4. **API 不稳定**：README 自陈「可能不通知即变更」；rc 线在 6 个月里发了 12 个 rc。**[S01readme][S01]** DSH 的应对是**源码 vendor + 本地补丁**（8 个包 + 改动日志），这是「拥有框架层」的代价，也是它不跟随上游发布列车的方式。**[S06]**

### 3. Python 侧等价方案对比

| 方案 | 发现机制 | 依赖声明 / 顺序 | 生命周期钩子 | 卸载 / 回滚语义 | 代价 | 来源 |
| --- | --- | --- | --- | --- | --- | --- |
| **pluggy** 1.7.0 | 手动 `register()`，或按 entry point 组 `load_setuptools_entrypoints(group)` | **无**（只有 hook 名匹配与 `tryfirst/trylast` 优先级） | 无内建生命周期钩子；有 hook wrapper（生成器 `yield`）做「环绕」 | `unregister()` 只摘掉钩子实现；**文档明说 teardown 抛出的异常不被处理，可能导致后续 teardown 时序错乱或被跳过**（`PluggyTeardownRaisedWarning`） | 需要把谜题改写成 `@hookimpl` 风格；对「一个谜题对象带有自己状态」的模型是错配 | [S11][S12] |
| **`importlib.metadata` entry points** | 标准库：`entry_points(group=...)` + `.select()`，`EntryPoint.load()` 解析 | **无**（只有包元数据，依赖是「包依赖」不是「运行时服务依赖」） | 无 | 无（发现 ≠ 管理） | 零依赖、标准库自带（3.8+，3.12 起 `select` 语义定型，3.13 起 `EntryPoint` 不再是 tuple-like） | [S13] |
| **stevedore** 5.9.1 | 包装 entry points，提供 Driver / Hook / Extension / Dispatch 四类 Manager | **无**（`verify_requirements` 校验的是 entry point 的包依赖，不是运行时服务依赖） | 只有「加载时初始化」（`invoke_on_load` + 参数） | 无卸载语义 | 引入一层 Manager 抽象；要求 Python ≥3.11；官方定位是「避免各家自己写 entry point 代码」 | [S14][S14b][S15] |
| **`entrypoints`（旧库）** | 只为发现 entry points | 无 | 无 | 无 | **已进入维护模式，作者明示新代码应改用标准库 `importlib.metadata`** | [S16] |
| **自造注册表 + 生命周期协议** | 仓内注册（显式表 / 装饰器），外部谜题再叠加 entry points | 可按需实现（通常写成元数据字段 + 显式排序） | 可以按游戏需要定义（create/start/answer/hint/dispose） | **可以做成显式的**：每次注册返回 undo，宿主持有 | 需要自己写并自己测约 100–200 行 | 本文建议 |

**结论**：Python 生态的四个成熟方案都在解决「**如何发现并钩住**」，没有一家解决「**如何声明依赖并撤销副作用**」。Cordis 的差异化恰恰在后半段（论文的关键词就是 revertible effects / reactive coeffects）。**[S04]**

### 4. 「谜题即插件」的既有实践（有出处可查）

1. **Keep Talking and Nobody Explodes（KTaNE）——炸弹模块即插件**：官方支持用户自制模块并接入 Steam Workshop；社区模块以「一个模块一份独立说明书」的形式分发，甚至出现专门生成自订说明书的工具（MakeMyManual：为「modded modules」生成可导航说明书，并把原版/needy 模块分区）。这是最贴近「谜题 = 可装载单元 + 自带呈现契约」的工程化案例。**[S17][S17b]**
2. **shapez 的 Puzzle DLC——题目包 + 编辑器 + 分享**：DLC 新增 Puzzle 模式与 **Puzzle Editor**（自造题目并分享给社区），并在商店页列出 20 个入门题。它的形态是「题目是内容单位，玩家也能生产内容」。**[S18]**
3. **教育平台的题型内容包**：Moodle 的 `qformat_h5p` 把 H5P 的多种内容类型（Branching Scenario、Quiz(Question Set)、Interactive Video 等）导入为 Moodle 题型；`mod_hvp` 则是连到 h5p.org 下载 content type 库的插件。即「**题型/内容类型是可安装、可启停的插件**」，并且题库与应用分层。**[S19b]**
4. 行业通例是「内容单位随包发布、宿主只认统一接口」（DLC 题目包/关卡包在商业解谜游戏里极常见，例如 Timelie 的 Hell Loop 谜题包、Voxelgram 的 82 题包）。**[S18b]**
5. **未找到可核查来源**：没有找到「以 Cordis 为宿主的谜题插件规范」这类先例；本项目在 Cordis + Python 组合上属于自走，不能引用既有实践背书，只能靠自家先例项目（`cordis-table-app` 的 `src/core/bridge.mjs` + `python/rpc_server.py`）作内部证据。**[S20]**

### 5. 风险（RC、跨语言调试、双运行时）

- **RC 风险是可量化的**：rc 线 6 个月 12 个版本，官方自陈 API 可能不通知即变更；DSH 的对策是 vendor + 补丁日志。若直接依赖 npm 版本，**升级是「跟着上游改」，不升级是「带着已知漂移」**。**[S01][S01readme][S06]**
- **跨语言桥的调试成本**：JSON-RPC over stdio 在业界有稳定参照（LSP 的 base protocol：`Content-Length` 头 + 默认 `utf-8` 内容体，头部为 ASCII，`\r\n` 分隔；所有请求都必须有响应；取消走 `$/cancelRequest` 通知）。**协议本身不难，难的是两侧的错误栈无法合并**——Python 侧异常要序列化成 RPC error 才能到 Node 日志，Node 侧超时要能在 Python 侧被观察到。**[S21]** 本项目的内部先例已经踩过这条路（`cordis-table-app` 有独立的 `_smoke_bridge.mjs` 桥冒烟），建议直接沿用「桥必须有独立冒烟」的做法。**[S20]**
- **双运行时部署负担**：终端用户需要同时具备可用的 Node 与 Python；安装/启动脚本要处理两套依赖与两套版本钉。这属于 **SPEC-006** 与门禁 `g16-launcher-integrity`、`g17-skip-visibility` 的射程：不得写死机器路径或工具版本钉，验证步骤被跳过必须出声（SKIP 不是通过）。
- **本项目特有的一条**：中英双语是两个并行实现（`text_adventure/` 与 `text_adventure_zh/`，各自导出同名顶层模块，README 说明「同一进程里只能有一个版本生效」）。平台化后若两侧都注册谜题，**必须约定「同一谜题只注册一次、以包名区分」**，否则同进程内会互相遮蔽或重复装载。

## 推荐与理由

**推荐（按优先级）**

1. **宿主继续用 Node + Cordis；但把「谜题插件」的语义重心放在 RPC 协议层，而不是 Python 进程内的插件框架。** Python 进程内部用**一张显式注册表**（谜题 id → 类 + 元数据），外部第三方谜题将来再加 entry point 发现。
2. **RPC 协议显式化谜题生命周期**：至少区分「列举/创建实例/推进动作/请求提示/销毁实例」，每个 `create` 必须有对应的 `dispose`；Node 侧持有「我创建了哪些实例」的所有权，断连或超时时由宿主回收。这在语义上对齐 Cordis 的 revertible effects，但把「逆」放在协议里，**不要求 Python 侧长出一个 IOC 容器**。**[S04][S05]**
3. **登记式注册表（registry）落点为 `text_adventure/gameplay_pool/`**：现在 `__init__.py` 已经手工导出了 14 个类 + `PUZZLE_CLASSES`，把它升级为「带元数据的注册表」即可（类型、难度、是否需要 UI、是否需要生成器），不必新建框架层。`BasePuzzle` 现有契约（`_generate` / `check_answer` / `get_hint` / `reset`）已经足够当插件接口。**[S22]**
4. **跨语言契约只定义一次**：谜题清单以 Python 侧注册表为事实源，Node 侧只做投影/缓存；禁止两边各维护一份谜题列表。这直接对应治理里的「同一份工作只在一处落地」（调试铁律 64）。
5. **若将来确有「第三方谜题包」需求**，再引入标准库 entry points（`[project.entry-points."text_adventure.puzzles"]`），发现失败要响亮报错而不是静默跳过。**[S13]**

**为什么推荐「不自己造轮子」，也推荐「不引入 pluggy/stevedore」**

- 不引 `pluggy`：它是**钩子总线**，不是**组件生命周期**。缺依赖声明、缺回滚；其 teardown 语义文档自带告警。为 14 个自持状态的谜题套一层 hookimpl 只会把简单问题复杂化。**[S11][S12]**
- 不引 `stevedore`：它解决的是「别自己写 entry point 管理代码」，额外要求 Python ≥3.11；对本仓「谜题库就在仓内」的现状是纯开销。**[S14][S14b]**
- 不引 `entrypoints`：维护模式，官方劝退。**[S16]**
- **不自己造「插件框架」**（IOC/依赖图/热重载）：那才是重复造轮子，且要自己承担回滚正确性——Cordis 花了 4 年 + 一篇 92 页论文才把这件事形式化。**但「自己写一张注册表 + 一套 RPC 生命周期方法」不是造轮子**，是把业务事实写清楚，成本约百行量级。

**实施顺序建议**：先做一条竖切（挑一个谜题走通「Node 装载 → RPC create → 作答 → dispose」全链，并带上桥的独立冒烟），再批量迁移其余 13 种；迁移期间新旧路径并存，逐条替换而不是推倒重来。

## 风险与红线

**红线（违反即回退设计，不要靠加补丁绕过）**

1. **不 pin 不上线**：`cordis` 与官方插件包必须钉到确切 rc 版本，并记录「钉的是哪个 rc + 为什么」。升级 rc 必须走一次完整桥冒烟；不允许 `^4.0.0-rc.x` 这种浮动范围进用户可见的部署面（rc 的语义化版本规则下 `^` 行为不可依赖）。
2. **桥的错误必须双向可见**：Python 侧异常不得被吞成「空结果」；Node 侧超时必须能区分「Python 忙」与「Python 死」。对齐 `g10-failloud-probe`（坏输入必须响亮失败）与 `g17-skip-visibility`（跳过验证必须出声）。
3. **谜题注册单一事实源**：同一谜题在中英双语两侧只能注册一次；注册表出现重复 id 时**启动即失败**，不允许「后者覆盖前者」。
4. **每个 `create` 都有 `dispose`**：谜题实例的宿主所有权明确；宿主崩溃/断连后 Python 侧的残留状态必须可判定、可清理。
5. **退回成本可控**：Node 宿主的一切（loader 配置、RPC 服务端、谜题→插件的包装层）集中在少数几个文件/目录内；不得把「谜题逻辑」写进 Node 侧。这条是第 6 条的物理前提。

**「应当放弃 Node 宿主、退回纯 Python」的判断线（任一条成立即建议回退，先记录触发事实再动手）**

| 触发线 | 判据（可测） |
| --- | --- |
| ① 谜题侧增量压倒宿主侧 | 连续若干次迭代中，90% 以上的改动只落在 Python 侧，而 Node 侧每次都要跟着改样板 |
| ② 跨语言调试成为主要成本 | 出现「同一故障需要同时开两个运行时/两份日志才能定位」，且反复发生（例如每月 ≥3 次），或需要为 Cordis 的漂移单独写兼容层 |
| ③ 热插拔需求消失 | 实测「热插拔谜题」在开发/发布流程里没有被使用（都是整进程重启），Cordis 的核心卖点对本项目不再产生价值 |
| ④ 分发面不允许双运行时 | 面向最终用户分发时，无法接受「同时要求 Node 与 Python」（安装器、体积、企业环境限制任一条卡死） |
| ⑤ 稳定性要求高于可组合性 | 需要长期只吃 LTS/稳定版本的依赖（安全审计等），RC 线不再可接受 |

**回退的落地方式（现在就留好）**：Node 侧退化为一个薄启动器或直接删除；Python 侧保留「注册表 + 生命周期」不变，把 RPC 生命周期方法换成进程内直调。因为第 1–4 条已经把语义都放在协议层和注册表上，**回退的语义损失接近零**——这正是「不把 Cordis 语义模仿进 Python」的第二个理由。

## 来源清单

> 检索日期均为 **2026-10-16**；「支撑结论」列写明这条来源在本文中承担什么。

**Cordis 本体**

| 编号 | URL | 支撑结论 |
| --- | --- | --- |
| S01 | [npm registry: cordis](https://registry.npmjs.org/cordis)（含 dist-tags、版本时间线、许可、依赖、仓库目录） | 4.0.0-rc.11 / MIT / rc 线节奏 / 运行期依赖仅 2 个 |
| S01b | [npm registry: @cordisjs/plugin-loader](https://registry.npmjs.org/@cordisjs%2Fplugin-loader)、[hmr](https://registry.npmjs.org/@cordisjs%2Fplugin-hmr)、[include](https://registry.npmjs.org/@cordisjs%2Fplugin-include)、[group](https://registry.npmjs.org/@cordisjs%2Fplugin-group)、[timer](https://registry.npmjs.org/@cordisjs%2Fplugin-timer) | 官方插件包清单与版本；同属 `cordiverse/cordis` 仓库 |
| S01readme | [cordiverse/cordis README（GitHub API）](https://api.github.com/repos/cordiverse/cordis/readme) | 「API 不通知即变更」原文；论文与文档入口；「官方文档仍在建设中」 |
| S02 | [GitHub API: repos/cordiverse/cordis](https://api.github.com/repos/cordiverse/cordis) ＋ [commits](https://api.github.com/repos/cordiverse/cordis/commits) | star/fork/issues、创建与推送时间、未归档、MIT、近期提交主题 |
| S03 | [GitHub API: repos/cordiverse/cordis/releases](https://api.github.com/repos/cordiverse/cordis/releases) | `v4.0.0-rc.11` 发布时点与 tag 形态 |
| S04 | [arXiv:2608.25512 摘要页](https://arxiv.org/abs/2608.25512) | 论文标题/作者/机构/日期/页数；revertible effects、reactive coeffects、context paradigm、Cordis 实现 |
| S04b | [GitHub API: repos/cordiverse/paper](https://api.github.com/repos/cordiverse/paper) | 论文仓库存在与活跃度；**未声明 License** |
| S05 | [DSH 官方文档《Cordis 入门》](https://deepseek-harness.github.io/deepseek-harness/reference/cordis-primer) | 五核心概念（插件/上下文/`inject`/事件分发模式/可逆注册）、disposer 实践规则 |

**Koishi 与 DeepSeek Harness 的关系**

| 编号 | URL | 支撑结论 |
| --- | --- | --- |
| S06 | `vendor/README.md`（本机 DSH 检出内的 vendor 清单，非在线来源） | DSH 以 `@deepseek-ai` 作用域 vendored 8 个 Cordis 包，当前 `4.0.0-rc.10`、上游 `main@f8ea3cd`（2026-09-08），并附本地改动日志 |
| S07a | [GitHub API: koishijs/koishi `packages/core/package.json`](https://api.github.com/repos/koishijs/koishi/contents/packages/core/package.json) | 发布版 `@koishijs/core@4.18.11` 依赖 `cordis: ^3.18.1`——Koishi 仍在 v3 线 |
| S07b | [npm registry: @cordisjs/core](https://registry.npmjs.org/@cordisjs%2Fcore) | v3 线包停在 `3.18.1`（2025-06），与 v4 rc 线并行 |
| S03b | [GitHub API: repos/deepseek-ai/deepseek-harness](https://api.github.com/repos/deepseek-ai/deepseek-harness) | DSH 仓库建仓时点（2026-08-13）与 MIT 许可，用于厘清三者先后 |

**Python 侧方案**

| 编号 | URL | 支撑结论 |
| --- | --- | --- |
| S08 | [PyPI JSON: python-cordis](https://pypi.org/pypi/python-cordis/json) | 第三方 Python 移植 0.1.4（2026-08-15），依赖 pluggy + omegaconf——存在但非官方 |
| S09 | [GitHub API: fshoocn/cordis-port](https://api.github.com/repos/fshoocn/cordis-port) | 0 star / 0 fork；许可 `NOASSERTION`——不可作为依赖的判据 |
| S10 | [piwheels: python-cordis](https://www.piwheels.org/project/python-cordis) | 版本线与发布时间交叉验证 |
| S11 | [pluggy 文档首页](https://pluggy.readthedocs.io/en/stable/) | pluggy 定位（pytest 的插件内核、1400+ 插件）、hookspec/hookimpl 模型、`register`/`unregister`/`load_setuptools_entrypoints`、LIFO 调用顺序、wrapper 语义 |
| S12 | [pluggy API Reference](https://pluggy.readthedocs.io/en/stable/api_reference.html) | 无依赖声明/无生命周期钩子的判据；`PluggyTeardownRaisedWarning` 原文（teardown 异常不被处理） |
| S13 | [Python 文档 `importlib.metadata`](https://docs.python.org/3/library/importlib.metadata.html) | entry points 标准库 API；3.12 `select()` 定型、3.13 `EntryPoint` 非 tuple-like；自定义 `DistributionFinder` 提供者机制 |
| S14 | [stevedore User Guide](https://docs.openstack.org/stevedore/latest/user/index.html) | 四种 Manager、四类加载模式、`verify_requirements` 含义（校验包依赖而非服务依赖） |
| S14b | [stevedore 项目文档入口](https://docs.openstack.org/stevedore/latest/) | 版本/归属；文档版权为 CC-BY 3.0（代码许可见仓库） |
| S15 | [PyPI JSON: stevedore](https://pypi.org/pypi/stevedore/json) | 5.9.1（2026-08-20）、`requires_python >=3.11` |
| S16 | [GitHub: takluyver/entrypoints](https://github.com/takluyver/entrypoints) | 「维护模式，新代码请用 `importlib.metadata`」原文 |

**「谜题即插件」实践**

| 编号 | URL | 支撑结论 |
| --- | --- | --- |
| S17 | [Rock Paper Shotgun：KTaNE 支持自制模块](https://www.rockpapershotgun.com/keep-talking-and-nobody-explodes-mods) | 官方模块化 + Workshop 分发的报道 |
| S17b | [MakeMyManual（GitHub）](https://github.com/Burniel123/MakeMyManual) | 社区工具为「modded modules」生成独立说明书——模块自带呈现契约的证据 |
| S18 | [Steam：shapez - Puzzle DLC](https://store.steampowered.com/app/1625400/shapez__Puzzle_DLC) | 题目包 + Puzzle Editor + 分享机制 |
| S18b | [linuxgameconsortium：shapez Puzzle DLC 发布](https://linuxgameconsortium.com/puzzle-dlc-released-for-the-epic-game-shapez-io) | 价格/时间等背景交叉验证（第三方媒体，仅背景） |
| S19b | [Moodle Marketplace：H5P content types（qformat_h5p）](https://marketplace.moodle.com/plugins/qformat_h5p) | 题型/内容类型作为可安装插件的教育平台实践 |

**风险背景与规范参照（第三方，仅背景）**

| 编号 | URL | 支撑结论 |
| --- | --- | --- |
| S19 | [Floatboat：Cordis — The Plugin Kernel Behind DeepSeek Harness](https://floatboat.ai/blog/cordis-plugin-framework) | 「Koishi 四年 + DSH v4」叙事与 ctx.effect 三机制的第三方复述（**不作判据**） |
| S20 | `cordis-table-app` 的 `src/core/bridge.mjs`、`python/rpc_server.py`、`src/_smoke_bridge.mjs`（本机同级先例仓，非在线来源） | 本项目已有的「Cordis 宿主 + Python 桥」先例；桥需要独立冒烟的内部证据 |
| S21 | [LSP 3.17 规范（base protocol）](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/) | JSON-RPC over stdio 的框架约定：`Content-Length` + 默认 `utf-8`、头部 ASCII、请求必须应答、`$/cancelRequest` 取消、错误码区间 |
| S22 | 本仓 `pyproject.toml`、`text_adventure/gameplay_pool/base_puzzle.py`、`text_adventure/gameplay_pool/__init__.py`、`README.md` | 谜题契约与注册现状（14 个类 + `PUZZLE_CLASSES`）、双语包结构、`BasePuzzle` 方法集 |

**未找到可核查来源**：① Cordis 官方（非 DSH 托管）的完整文档站点；② Cordis 或 Koishi 的 Python 官方绑定；③ 以 Cordis 为宿主的谜题/教育内容插件先例；④ 论文仓库的许可声明（`license: null`）。
