# 平台化架构模式调研（Puzzle-as-Plugin / 内容平台）

- 调研主题：平台化架构模式（微内核插件、内容与逻辑分离、分发治理、安全、i18n、演化路径）
- 面向项目：`siwpan/text-adventure`（Python + pygame 桌面解谜游戏，14 种谜题种类，正在改造为「Cordis 宿主 + Python 谜题进程（JSON-RPC over stdio）+ Web 渲染」）
- 核查方式：全部结论经联网检索复核；每条来源标注 **URL + 检索日期**，检索日期均为 **2026-10-16**
- 本文档使用的项目内路径均为**仓库相对路径**（如 `text_adventure/`、`text_adventure_zh/`、`shared/`、`docs/records/`），不含机器绝对路径

---

## 结论摘要

1. **微内核的成败几乎完全取决于「契约」而非「插件」**：内核只应保留托管、发现/注册、生命周期、以及不可协商的平台策略；插件承载可选行为，并通过内核契约通信。契约版本化、插件粒度、内部注册表、连接方式是这类架构的四大复杂度来源。（来源 S1、S2、S3）
2. **「什么进内核」的判据应是「多个消费者共享且必须一致」**：跨插件一致性规则、全局不变量进内核；某一玩法的判定规则、可替换的呈现、可替换的内容必须留插件。IDEA/浏览器/产品平台的既有做法是「内核 + 扩展点」，插件之间不允许互相访问内部实现，只允许消费事件或稳定接口。（来源 S2、S3）
3. **事件总线与直接依赖注入不是二选一，而是分层**：事件总线带来拓扑解耦（新增订阅方无需改动发布方），但会引入隐式耦合、可观测性下降、时序与幂等问题；请求/响应（含 JSON-RPC）延迟可预测、易调试但耦合紧。建议「通知/广播走事件，判定/胜负/存档走直接调用 + 稳定契约」。（来源 S4、S5、S6）
4. **内容与逻辑分离有成熟的工程骨架**：`schemaVersion` 内嵌于每份文档 + 有序的 up/down 迁移函数注册表 + 兼容性模式（backward / forward / full）；Minecraft Bedrock 的 `manifest.json` 提供了「`format_version`（文档格式）+ `min_engine_version`（运行环境下限）双版本字段」这一被广泛复制的先例。（来源 S7、S8、S9、S10）
5. **完整性优先于签名**：先在 manifest 中固化内容哈希（逐文件 SHA-256）与内容包版本；签名（Sigstore keyless / cosign / 平台密钥）是可选的下一跳，其价值在于「可追溯 + 防篡改 + 透明度日志」，而不仅是「校验通过」。（来源 S11、S12）
6. **插件市场的治理没有便宜方案**：VS Code Marketplace 多引擎杀毒 + 沙箱动态行为检测 + 密钥扫描，发现恶意即移除并封禁发布者、并在客户端强制卸载；Obsidian 转向「每个版本自动审查」，并承认「无法对插件提供安全保证」，要求 `SECURITY.md` 披露能力；Steam Workshop 对新增与更新走审核队列。三者共同点是**能力披露 + 每版本复查 + 事后可撤回**，而不是一次性入口审核。（来源 S13、S14、S15、S16）
7. **npm/PyPI 的教训是「扫描不等于安全」**：`npm audit` / `pip-audit` 只覆盖已知 CVE，设计上无法判断新发布包是否恶意；安装即继承开发者/CI 的权限与凭据。若本项目要开放插件分发，**必须默认无信任**，不能把生态级扫描当作防线。（来源 S17、S18）
8. **沙箱要分层，不要把同进程限制当安全边界**：Node 官方明确 `node:vm` **不是**安全机制，不得用于运行不可信代码；Node Permission Model（`--permission`）自称「安全带」而非安全保证，且**不继承到子进程**、符号链接会被跟随、存在已知绕过（如通过既有 fd 访问文件系统）。（来源 S19、S20）
9. **Python 侧的高危面很具体**：`pickle` 反序列化可执行任意代码（官方警告，建议改用 JSON、必要时用 `hmac` 签名）；`eval()` 不得用于不可信输入（改用 `ast.literal_eval`）；`subprocess` 应传参数序列并保持 `shell=False`，可执行文件用**全限定路径**（且 `--permission`-style 的进程级权限不会自动约束子进程）；解压内容包须防 Zip Slip（`../`、Windows 反斜杠与绝对路径变体）与压缩炸弹。（来源 S21、S22、S23、S24、S25）
10. **双语并行实现是本项目当前最大的架构债**：`text_adventure/` 与 `text_adventure_zh/` 两套包共享同一批模块名（`domain.py`/`engine.py`/`events.py`/`ui.py`/`gameplay_pool/`），这正是「同一内容两份实现必然漂移」的教科书形态。行业做法是单一主语言 + 翻译层（Ren'Py 的 None language 模型、Godot 的 gettext/CSV 流程），而「key 化」与「工程化复数」由 ICU MessageFormat/CLDR 或 Fluent 提供。（来源 S26、S27、S28、S29、S30）
11. **CJK 渲染是具体可解的环境问题，不应被当成"以后再说"**：pygame 的 `SysFont()` 会在找不到可用字体时**静默回退到默认字体**（中文显示为方块且不报错），必须直接指定字体文件的 `pygame.font.Font(path, size)`，并显式检查字形覆盖。（来源 S31、S32）
12. **演化路径的关键，是让每个阶段都有"可独立交付的消费者"**：平台化的常见死法是先建市场后建内容（鸡生蛋问题），或在只有一个消费者时先做抽象层。可验证里程碑应写成「能被端到端跑通的用例」。平台化的起点建议是「内容包 + 双消费者（桌面 + Web）共用同一协议」，而不是「先做插件市场」。（来源 S33、S34、S35）

---

## 逐项调研

### 1. 微内核 / 插件架构

**架构共性（内核与插件的边界）**

- 微内核（别名插件架构）只有两类组件：内核系统与插件组件。内核负责插件注册管理、生命周期管理、插件间通信与动态替换；插件是可独立增删替换的可选行为单元。（来源 S1）
- 内核的必备职责被概括为四类：托管（hosting）、发现/注册、生命周期管理、**不可协商的平台策略**；并对外暴露扩展点与稳定 API/事件。一致性是两级的：系统级不变量在内核，插件专属规则在插件自身的有界上下文内。（来源 S2）
- 代价必须预先承认：契约治理（契约版本化、插件粒度、内部插件注册表、多种连接方式）是主要开发复杂度；该模式更适合中小规模产品，可扩展性一般；插件间不直接通信、消息由内核转发的做法带来透明性，也带来路由与协议理解成本。（来源 S1、S2）

**边界怎么切（什么进内核 / 什么必须留插件）**

- 进内核：跨插件的全局一致性规则、生命周期与调度、共享服务（存档格式、资源加载、权限判定）、以及「所有插件都依赖且改动会造成系统性破坏」的最小能力面。（来源 S2）
- 留插件：某一玩法的判定逻辑、可替换的呈现层、可替换的内容与本地化、租户/区域专属规则。既有先例中，插件**只消费内核契约（例如事件）**，绝不访问其他插件的内部实现或数据表；规则变化只更新对应插件并可热重载。（来源 S2、S3）
- 反例警戒：内核如果开始承载「某类谜题的特例判定」或「某个 UI 的具体布局」，插件化收益立即被内核的发布节奏吞掉；插件若开始直接读写内核内部状态，则失去了独立替换能力。这与本项目「谜题 = 插件」的诉求直接冲突，需在契约层显式禁止。

**插件间通信：事件总线 vs 直接依赖注入**

- 事件总线/事件驱动：生产者与消费者互不知晓，可用异步消息提升容错与横向扩展；代价是可观测性差（异步追踪困难）、失败延迟或分散、可能产生多个事实源与数据结构耦合。（来源 S4、S5）
- 直接依赖注入/请求-响应：延迟低且可预测、调试简单；代价是耦合紧，行为迁移需改动所有调用方。（来源 S4、S6）
- 关键的第三方判据：EDA 的多数解耦收益**来自 Publish-Subscribe 通道本身**，而不是「事件语义」；过度使用「可任意增加接收方」的维度，会在另一个维度上加深耦合，系统随规模增长而变乱——这是「demo 很好看、长期很痛」的典型。（来源 S5）
- 对本项目的映射：**广播型通知**（谜题进度变化、成就、遥测、UI 刷新）适合事件总线；**判定型交互**（提交答案、请求提示、结算、存档写入）必须是显式请求-响应（现有 JSON-RPC over stdio 就是这条路径），否则胜负判定会退化为「等待某个事件是否到达」的隐式时序依赖。

### 2. 内容与逻辑分离

**既有模式**

- 数据驱动设计（Data-Driven Design）的内核表述：行为由外部数据支配，代码只提供处理这些数据的通用机制；「什么/怎么做」放在可独立于源码变更的数据文件中。警戒线也很明确——不要为几个 YAML 就能表达的规则发明 DSL；且「删掉该文件程序就跑不起来」的东西**不是配置，是内容**。（来源 S7）
- 内容包 / 资产包 / 关卡包的先例字段：Minecraft Bedrock `manifest.json` 用 `format_version` 声明 manifest 文档格式版本，用 `min_engine_version` 声明可运行的最低引擎版本，用 `version` 声明包自身版本；升级须改 `version` 否则会触发重复包检测。（来源 S9、S10）

**数据格式与版本化**

- 推荐骨架：每份内容文档内嵌数值型 `schemaVersion`，配套「有序的 up/down 迁移函数注册表」（迁移函数需幂等）；以兼容性模式约束演进——backward（新 schema 能读旧数据）/ forward / full。JSON Schema 的向后兼容演进有两条可操作规则：新增属性时，新属性 schema 必须与旧版本的 `additionalProperties` 兼容；删除属性时，新版本的 `additionalProperties` 必须与被删属性的 schema 兼容。（来源 S8、S36）
- 破坏性变更的处理惯例：SemVer 主版本号是「破坏性变更」的第一信号；先废弃后移除，并配套迁移指南与 CLI 迁移工具。（来源 S37、S38）
- SemVer 硬规则：**已发布版本的内容 MUST NOT 被修改**，任何修改都必须作为新版本发布；`0.y.z` 为初始开发期，公共 API 不稳定。（来源 S37）
- 校验落地：Python 侧可用 `jsonschema` 的版本化验证器（支持 Draft 2020-12 等）做内容包入口校验；注意 JSON Schema 各 Draft 的关键字差异（如 Draft 2020-12 用 `prefixItems` 替代旧的 `additionalItems` 语义）。（来源 S39、S40）

**内容包的签名与完整性**

- 第一步是哈希清单：为内容包生成逐文件 SHA-256 清单，随包发布并纳入加载前置校验（这也让「同一内容多语言」的漂移可被机械检测）。
- 第二步才是签名：Sigstore 的 keyless 签名（Fulcio 颁发证书 + Rekor 透明度日志）与 cosign 的 `sign/verify` 流程，提供了「可验证来源 + 可公开审计 + 记录签名事件」的组合；其价值被明确表述为完整性（防篡改）、真实性（来源可追溯）、防止未授权修改。（来源 S11、S12）
- 现实取舍：面向本项目当前阶段，**哈希清单 + 版本 + 引擎版本下限**已能覆盖「内容损坏/被替换/不兼容」三类主要问题；引入签名体系应等到「存在第三方内容作者」这一条件成立之后。

### 3. 插件市场与分发治理

**发现与安装**

- 集中式目录 + 客户端内搜索是主流（Obsidian 的 directory、VS Code 的 Marketplace）；Obsidian 明确「新插件必须通过自动审查才会进入目录并可被搜索，每个新版本都会被扫描，未通过则在 24 小时内从搜索中移除」。（来源 S14）
- 版本约束与依赖求解：npm 的 `package.json` 定义了一整套范围语法（`^version`、`~version`、`1.2.x`、`a - b`、`r1 || r2` 等），并针对宿主给出实践建议——若宿主遵循 semver，则只有主版本变更才会破坏插件，因此依赖应写成 `"^1.0"` / `"1.x"`，用到 1.5.2 引入的特性则写 `"^1.5.2"`。（来源 S41）
- 语义化版本与锁文件的分工：范围表达「可接受的演进」，锁文件保证「可复现的安装」。（来源 S42）

**审核流程的先例对比**

| 生态 | 审核/治理机制 | 可借鉴点 | 来源 |
| --- | --- | --- | --- |
| VS Code Marketplace | 每个提交/更新多引擎杀毒扫描；沙箱内动态行为检测；自动扫描密钥/凭据；发现恶意即移除，必要时封禁发布者，并**在客户端阻止该扩展、强制卸载已安装实例** | 「事后可撤回」必须下沉到客户端，而不只是从市场下架 | S13、S43 |
| Obsidian | 转向「每个版本自动审查」（安全 + 代码质量 + 开发者政策合规）；要求根目录 `SECURITY.md` 披露行为与数据访问；对热门/精选/被举报插件保留人工审查；官方明确「无法提供安全保证」，敏感数据场景建议自行审计 | 能力披露文件（机器可读 + 人可读）+ 自动审查 + 人工兜底的三层结构 | S14、S15、S16 |
| Steam Workshop | 新增与更新均进入审核队列，审核通过前其他玩家不可见（旧版本仍对已订阅用户可用）；首次提交需邮箱验证；多数条目数小时内处理 | 「更新也需审核」+「旧版本保持可用」是内容平台的实用折中 | S44 |
| npm / PyPI | 生态级扫描与 2FA 等治理手段；但恶意包通常没有 CVE/公告，`npm audit`、`pip-audit` **设计上不判断「新发布包是否恶意」**；安装脚本继承开发者/CI 权限与凭据 | 分发即执行权限的授予，治理必须默认不信任 | S17、S18 |

### 4. 安全

**沙箱与权限：进程隔离 vs 同进程 capability 限制**

- 能力（capability）模型的要点：能力是「不可伪造的令牌」，同时**指定资源并授予权限**，由持有者出示；它按最小权限原则支持细粒度分区与受控分享，天然缓解 ambient authority 与 confused deputy 问题。（来源 S45）
- Node 侧的官方态度决定了方案选型：`node:vm` **不是安全机制，不得用于运行不可信代码**（V8 context 只是不同的全局对象，无法阻断经由原型链/错误对象逃逸）。（来源 S19）
- Node Permission Model（`--permission`，v20 引入，v23.5/v22.13 起非实验性）把 fs/网络/子进程/worker/native addon/WASI/FFI/Inspector 收进统一权限面，支持 `--allow-fs-read` / `--allow-fs-write` / `--allow-child-process` / `--allow-worker` / `--allow-net` 等；并提供 `process.permission.has()/drop()` 运行时 API（drop 不可逆）与 audit 模式（不拒绝，只经 diagnostics channel 记录）。（来源 S20）
- 但官方同时给出**明确的边界声明**：该模型是「安全带」，用于防止**可信代码**误改文件或误用资源，**不为恶意代码提供安全保证**；恶意代码可以绕过。文档还列出具体约束：模型不继承到子进程；不继承到 worker thread（除非在 `execArgv` 中重新列明）；使用既有 fd 访问文件系统可绕过；符号链接会被跟随（即使指向未授权路径）；`node:sqlite` 等其他途径访问文件系统不受保证。（来源 S20）
- 结论：**跨语言（Node 宿主 ↔ Python 谜题进程）已经天然是进程隔离，这应当被当作唯一的安全边界**；同进程内的一切「限制」只用于防止 bug 与误用，不能用于承载不可信第三方插件。Worker 线程虽有 `resourceLimits`（`maxOldGenerationSizeMb`、`stackSizeMb` 等，触限即终止 worker）与 `postMessage` 通道，但共享进程内存、且资源限额只约束 JS 引擎、不含 `ArrayBuffer` 等外部数据；跨线程消息必须视为不可信输入。（来源 S46）

**资源耗尽与注入**

- 无界循环/无限输出的防护应落在**进程边界**：对每次 JSON-RPC 调用设置超时（进程级 + 调用级），限制单条消息与累计输出字节数，限制谜题进程的内存与 CPU，进程被杀后按「该谜题会话失败」而非「整个游戏崩溃」处理。
- 协议层加固：JSON-RPC 2.0 规定了错误码区间（-32700 解析错误、-32600 无效请求、-32601 方法不存在、-32602 参数无效、-32603 内部错误，-32000..-32099 供实现自定义的服务端错误）；批量请求可返回逐条错误。LSP 的 stdio 帧格式（`Content-Length` 头 + `\r\n\r\n` + JSON）是跨语言 stdio 通信的成熟范式，可作为本项目消息封帧的参照；MCP 的经验可直接借用：请求 id 必须是字符串或整数且**不得为 null**、同一会话内不得复用，响应必须且只能设置 `result` 或 `error` 之一，通知不得带 id。（来源 S47、S48、S49）

**Python 侧具体手段**

- 反序列化：`pickle` 官方警告「不安全，只反序列化你信任的数据」，恶意 pickle 可在反序列化期间执行任意代码；如需防篡改应使用 `hmac` 签名；处理不可信数据应改用 JSON（JSON 反序列化本身不构成任意代码执行漏洞）。同时 `pickle` 官方文档也指出：长期存活对象**应在对象内放版本号**，由 `__setstate__` 做转换——这与内容包 `schemaVersion` 的思路一致。（来源 S21）
- 表达式求值：不可对不可信输入使用 `eval()`；仅需字面量时用 `ast.literal_eval`（只解析字面量，不执行代码）；内容包中的「条件/表达式」字段应设计成受限表达形式，而非 Python 表达式。（来源 S22、S50）
- 子进程：`subprocess` 文档强调**为最大可靠性使用全限定可执行文件路径**（`sys.executable` + `-m` 是启动当前解释器的推荐方式），传参用序列而非字符串，`shell=True` 前须阅读其安全注意事项（并提供 `shlex.split()` 作为拆词参照）；`timeout` 到期会杀掉子进程并抛 `TimeoutExpired`；`close_fds` 默认为真，`pass_fds` 用于显式保留 fd。（来源 S23）
- 路径穿越与压缩炸弹：Zip Slip 的根因是归档条目名带有 `../` 等目录穿越序列，导致写入目标目录之外、进而任意文件覆盖甚至代码执行；防御要点是**规范化后校验目标路径仍在允许根目录内**，并注意 Windows 变体（反斜杠、盘符绝对路径、ADS 冒号）；同类风险还包括压缩炸弹/嵌套目录造成的资源耗尽。（来源 S24、S25）

### 5. 多语言 i18n

**消息层：key 化、复数、变体**

- ICU MessageFormat 用 CLDR 复数规则选择分支：`{count, plural, =0 {zero} one {singular} other {plural}}`，`#` 替换为格式化后的数字，精确匹配（`=0`）优先于类别，`other` 分支为必需回退；`select` 用于按字符串变量选分支（性别、状态等）。（来源 S28）
- CLDR 定义最多六类复数（zero/one/two/few/many/other），各语言只用其子集：英语 one/other，波兰语 one/few/many/other，阿拉伯语六类全用，**中文/日文只有 other**；因此 `count == 1` 这种硬编码只对英语成立。（来源 S29、S51）
- gettext 与 Fluent 的分野：gettext 用「源字符串（通常英文）作为 msgid」，优点是少一层间接，缺点是同一源串需要不同译文时必须靠 `msgctxt` 消歧、且复数支持是「特例式加装」的；Fluent 使用稳定消息标识符 + 通用「字符串变体 + 选择器」模型（复数只是其中一种选择器），并把 gettext 的三件套（.po/.pot/.mo，含提取与编译步骤）压缩为单一 .ftl 文件。（来源 S26、S27）
- key 化取舍的实践结论：key 化对大规模团队与外部翻译服务更稳健；以源字符串为 key 在 gettext 生态内是正常做法（Poedit 等工具可用已完成的 en.po 自动带出英文）；无论哪种，都必须为译者提供上下文。（来源 S52、S53）

**字体与渲染（CJK / RTL）**

- pygame 具体坑：`pygame.font.SysFont("simhei", 60)` 在字体已安装、`get_fonts()` 也列出的情况下，中文仍全部显示为方块且**不报错**（疑似静默回退到默认字体），而用 `pygame.font.Font("/path/simhei.ttf", 60)` 直接加载字体文件则正常；同一问题也出现在 `pygame.freetype.SysFont()`。（来源 S31）
- 因此工程结论是：**自带字体文件、用 `Font(path, size)` 加载**，并把「字体打包」纳入内容/资源治理；同时提示 pygame 2.0.3 起支持 UCS-4 渲染（`hasattr(pygame.font, "UCS4")` 可探测），`render()` 只渲染单行、`\n` 不换行，且字体渲染非线程安全。（来源 S32）
- 整形与回退的边界：HarfBuzz 是整形库（字符序列 → 字形序列），**它本身不做字体回退**，回退由应用/引擎负责；缺失字形会落到 `.notdef`（俗称 tofu 方块），回退还可能导致同一词内字形来自不同字体、粗细与大小不一致。复杂文本与双向文本需要「按字体/样式切分成段 → 逐段整形 → 断行」的流水线，Unity 也是在 2024 年才通过 HarfBuzz+ICU 补上复杂文本与双向渲染。（来源 S54、S55、S56）

**同一内容多语言的工程做法（直接对应本项目痛点）**

- Ren'Py 的模型：每个游戏有且只有一个**主语言（None language）**，其他语言放在 `translation/<lang>/` 目录下，由框架从主脚本自动生成待翻译条目；可翻译对话、字符串、图片甚至样式（图片按 `game/tl/<lang>/xxx.png` 优先替换）。已知限制：多路径方案下**不能跨语言读取存档**（需存 `game_lang` 并在 `after_load` 校验）。（来源 S30、S57）
- Godot 的模型：CSV/PO 两种流程，key 化时用 `tr()`/`tr_n()`；官方文档提示使用**翻译键**时复数形式支持不完整，建议改用 gettext PO；CSV 可指定翻译上下文（Godot 4.6 起）以消歧同形异义源串。第三方评述亦指出 Ren'Py 式「每种语言 1:1」缺少主翻译文档会让本地化更费力。（来源 S58、S59、S60）
- 共同教训：**并行双实现会把「翻译」问题升级为「两份产品」问题**——每修一个 bug 要修两次，每加一个谜题要写两遍，且没有任何机制保证两版语义一致。正确形态是「一份主实现 + 语言资源 + 自动提取 + 覆盖率/对齐校验」。

### 6. 演化路径

**可借鉴的通用规律**

- 平台化的经典障碍是鸡生蛋（两侧都要先有量），可行战术包括：先给一侧创造独立价值（「单机模式市场」）、优先吸引能同时充当供需两侧的用户、以及提供在另一侧不活跃时仍具价值的种子供给。（来源 S33、S34）
- 平台往往不是一开始设计出来的：iPhone 首发时并没有 App Store，产品先流行、平台化机会随后才被识别出来；这意味着「平台化」应与「当前已有消费者的真实需求」对齐，而不是反向让需求迁就架构。（来源 S33）
- 破坏性变更的惯例流程：先用 SemVer 主版本号宣告 → 发布迁移指南（含前后对比）→ 提供 CLI 迁移工具 → 在 schema/文档中把旧字段标记为 deprecated 并把报错信息指向迁移指南。（来源 S38）

**本项目分阶段建议（见下一节）+ 常见失败模式**

- 失败模式 A：**先建市场、后建内容**。没有足量内容时开放分发，目录空空，首发用户流失且很少回来。（来源 S34）
- 失败模式 B：**内核膨胀**。为了「通用」把具体谜题判定塞进内核，之后每次改玩法都要动内核，插件化名存实亡。（来源 S1、S2）
- 失败模式 C：**事件总线滥用**。用事件替代显式调用，短期解耦、长期隐式耦合与不可调试；EDA 的教训是「demo 好、规模化后乱」。（来源 S5）
- 失败模式 D：**内容格式频繁破坏性变更**。旧内容包/旧存档无法加载，玩家侧表现为「更新后进度损坏」，且缺少迁移函数注册表时无处修补。（来源 S8、S36）
- 失败模式 E：**双实现持续分叉**。两版内容并行维护，最终只能冻结一版。（来源 S30、S57）

---

## 对本项目的建议（分阶段）

> 阶段划分遵循「每个阶段产出可被端到端验证的消费者」原则；仓库内涉及路径均用相对路径表述。

**阶段 0（现状收敛，最小改动）**
- 目标：把「两份实现」变成「一份实现 + 语言资源」，先把最大的结构性债务止住。
- 动作：确定主语言实现（推荐以 `text_adventure_zh/` 为准或以 `text_adventure/` 为骨架），另一份降级为语言资源；在 `shared/` 下建立 i18n 装载层（key → 文案），文案采用 key 化 + ICU 风格的复数/选择语义（CLDR 类别由库提供，不要自写 `count == 1`）。
- 可验证里程碑：`scripts/smoke_headless.py` 在两种 locale 下都跑通；CI 校验两种语言 key 集合完全一致（缺 key/多 key 即红）。

**阶段 1（内容与逻辑分离）**
- 目标：谜题内容成为数据，加载器成为唯一入口。
- 动作：定义内容包目录与 manifest（建议字段：`pack_id`、`version`（SemVer）、`format_version`、`min_engine_version`、`schema_version`、逐文件 `sha256`、`requires`、`locales`）；在 `shared/paths.py` 同级建立内容根解析；用 `jsonschema` 做入口校验；建立迁移函数注册表（up/down，幂等）。
- 可验证里程碑：至少 5 个既有谜题改为「纯内容 + 通用加载器」驱动；删掉一个内容包后游戏能明确报错而不是崩溃；篡改内容包内任一文件后加载失败并指认具体文件。

**阶段 2（协议与进程边界）**
- 目标：谜题逻辑作为独立进程运行，安全边界落到进程级。
- 动作：把谜题进程能力面收敛为一组 JSON-RPC 方法（如 `puzzle.describe` / `puzzle.start` / `puzzle.submit` / `puzzle.hint`）；沿用 `Content-Length` 帧 + `id` 非 null、响应只含 `result` 或 `error` 之一、通知不带 `id` 的规范；为每次调用设超时与输出上限；谜题进程崩溃映射为单个谜题会话失败。
- 可验证里程碑：杀掉谜题进程后宿主仍可交互并给出可读提示；一次恶意/缺陷谜题（死循环 + 巨量输出）不会挂起宿主；调用超时有明确错误码。

**阶段 3（内容包生态内部化）**
- 目标：内容包成为一等公民，具备版本矩阵与兼容性保证。
- 动作：发布 `format_version` 与 `min_engine_version` 的兼容性矩阵；`requires` 做范围求解（参照 `^1.0` 形式的实践建议）；内容更新一律新版本、不原地改（对齐 SemVer 第 3 条）。
- 可验证里程碑：用旧版本内容包在新引擎上跑通（backward），并给出「不兼容」时指向迁移指南的报错；至少一次真实的 schema 迁移被自动化测试覆盖。

**阶段 4（Web 渲染作为第二消费者）**
- 目标：让协议「位置无关」被证明。
- 动作：Web 端只消费同一组 JSON-RPC 方法，不复制玩法逻辑；如果 Web 端必须改协议，说明协议抽象错了，先改协议。
- 可验证里程碑：桌面与 Web 在**同一内容包、同一谜题进程**下得到一致的判定结果（同一组输入的结算序列一致）。
- 备注：这也是本阶段最大的收益——一个消费者时做抽象极易过度设计，两个消费者时才第一次获得真实反馈。

**阶段 5（开放分发，条件触发）**
- 目标：允许第三方内容/插件，但默认不信任。
- 动作：本地目录安装 → 校验 manifest/哈希/签名 → 内容包默认**无逻辑执行权**（纯数据 + 声明式能力）；含逻辑执行的插件必须走进程隔离，并显式声明所需能力（文件/网络/子进程）；建立能力披露文件（对齐 Obsidian 的 `SECURITY.md` 思路）与「每版本复查 + 可撤回」机制。
- 可验证里程碑：装一个故意恶意的内容包，只能造成「该包被拒绝/该谜题进程被杀」，不能读宿主文件、不能联网、不能拉起额外进程。

---

## 风险与红线

1. **红线：不可信插件不与宿主同进程、不共享解释器能力面**。Node 官方明确 `node:vm` 不是安全机制、Permission Model 只是「安全带」，两者都不能作为对恶意代码的承诺。跨 Node/Python 的进程边界才是真边界。
2. **红线：内容包里不出现可执行代码与 Python 表达式**。禁止 `pickle`、禁止 `eval`；字面量解析用 `ast.literal_eval`，条件用受限 DSL 或声明式条件表。
3. **红线：不信任归档条目名**。解压必须做规范化 + 前缀校验，覆盖 `../`、`..\`、绝对路径、盘符与 ADS 变体；同时限制解压体积与嵌套深度（防压缩炸弹）。
4. **红线：无超时、无输出上限的跨进程调用等于把宿主交给插件**。每次调用都应有超时、字节上限、并发上限。
5. **红线：`--permission` 不继承、fd 可绕过、符号链接会被跟随**；不要基于「Node 侧已加权限」推断子进程或未来新增的读写路径也安全。
6. **风险：语义化版本的「不可修改已发布版本」一旦违反，缓存与内容寻址全部失真**。内容包与插件都必须遵守「改动 = 新版本」。
7. **风险：内核膨胀与事件总线滥用是渐进式的**，不会在某次提交里爆发。建议在评审中固定两问：这条规则是否被多个消费者共享？（否则进插件）这次交互需要结果还是只需要通知？（需要结果就不要用事件）。
8. **风险：CJK/复杂文本渲染被低估**。`SysFont` 静默回退、HarfBuzz 不做回退、`.notdef` 方块不报错——都必须有自动化的「字形覆盖 + 渲染非空」检查，否则问题只在玩家截图中暴露。
9. **风险：Web 端与桌面端复制玩法逻辑**。这是双实现债务的二次发作，比第一次更贵；一旦发现 Web 端要重写判定，应停下来改协议。
10. **风险：在没有第二个内容作者之前就建市场**。鸡生蛋问题的对策是先给一侧独立价值；本项目的「一侧」就是内容包本身的可用性与工具链质量。

---

## 来源清单（URL + 检索日期 + 支撑的结论）

> 检索日期均为 **2026-10-16**（本次会话联网核查日期）。标注为「未找到可核查来源」的条目表示检索未能取得可引用的权威来源。

| 编号 | 来源 | 支撑结论 |
| --- | --- | --- |
| S1 | [Microkernel Architecture Pattern – GeeksforGeeks](https://www.geeksforgeeks.org/system-design/microkernel-architecture-pattern-system-design) | 微内核=内核+插件，内核负责注册/生命周期/插件间通信/动态替换；优缺点 |
| S2 | [Microkernel Monolith – Software Architecture Guild](https://software-architecture-guild.com/guide/architecture/styles/microkernel-monolith) | 内核职责四分类（托管/发现注册/生命周期/平台策略）；两级一致性模型；插件不访问他插件内部 |
| S3 | [Microkernel Architecture: How It Works – Adaptive Engineer](https://newsletter.adaptiveengineer.com/p/microkernel-architecture-how-it-works-and-what-it-offers) | 契约治理（版本化、粒度、注册表、连接方式）是主要复杂度来源 |
| S4 | [Request-Response vs Event-Driven: Key Tradeoffs](https://medium.com/@andycrossman712/request-response-vs-event-driven-communication-key-tradeoffs-6084ab7a78c0) | 事件驱动可观测性差、请求响应延迟可预测 |
| S5 | [Event-driven = Loosely coupled? Not so fast! – Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/ramblings/eventdriven_coupling.html) | 解耦主要来自 pub/sub 通道；过度解耦在另一维度加深耦合；EDA 规模化后变乱 |
| S6 | [What Is an Event Bus? – Akamai](https://www.akamai.com/glossary/what-is-an-event-bus) | 事件总线的无依赖通信与横向扩展收益 |
| S7 | [Data-Driven Design – DEV Community](https://dev.to/methodox/data-driven-design-leveraging-lessons-from-game-development-in-everyday-software-5512) | 数据驱动设计的定义与两条警戒线（勿造 DSL；「删掉就坏」的是内容不是配置） |
| S8 | [Schema Versioning Strategy: A Practical Guide](https://www.jundago.com/blog/schema-versioning-strategy) | `schemaVersion` 内嵌 + 迁移函数注册表 + 兼容性模式（Avro/Protobuf/JSON Schema 对照） |
| S9 | [Project Setup – Bedrock Wiki](https://wiki.bedrock.dev/guide/project-setup) | `format_version` / `min_engine_version` / `version` 与「升级须改版本」 |
| S10 | [Minecraft Bedrock manifest.json 模板](https://convertmcpack.net/pages/manifest_template.html) | manifest 字段语义与 `min_engine_version` 取值约束 |
| S11 | [Signing Other Types – Sigstore 文档](https://docs.sigstore.dev/cosign/signing/other_types) | cosign 对非容器制品的签名与验证流程 |
| S12 | [Model authenticity and transparency with Sigstore – Red Hat](https://next.redhat.com/2025/04/10/model-authenticity-and-transparency-with-sigstore) | keyless 签名（Fulcio 证书 + Rekor 透明度日志）带来的完整性/真实性/可审计 |
| S13 | [Security and Trust in Visual Studio Marketplace – Microsoft for Developers](https://developer.microsoft.com/blog/security-and-trust-in-visual-studio-marketplace) | 多引擎杀毒 + 沙箱动态检测 + 密钥扫描；恶意即移除并可封禁发布者；客户端强制卸载 |
| S14 | [The future of Obsidian plugins – Obsidian](https://obsidian.md/blog/future-of-plugins) | 每版本自动审查；未通过 24 小时内从搜索移除；新插件须过审才入目录 |
| S15 | [Plugin security – obsidian-help（GitHub）](https://github.com/obsidianmd/obsidian-help/blob/master/en/Extending%20Obsidian/Plugin%20security.md) | 插件可访问文件/联网/安装程序；自动扫描 + 人工复核；建议自行审计 |
| S16 | [Security Guide – Obsidian Plugin Observer](https://plugin.observer/security-guide) | `SECURITY.md` 能力披露（含"不确定就写 None"与随版本更新要求） |
| S17 | [npm & PyPI Supply Chain Attacks Explained – Loginsoft](https://www.loginsoft.com/post/npm-and-pypi-supply-chain-attacks-how-malicious-packages-bypass-security-controls) | `npm audit`/`pip-audit` 只覆盖已知 CVE，无法判断新包是否恶意；安装继承开发者/CI 权限 |
| S18 | [Killing Two Birds with One Stone: Malicious Package Detection in NPM and PyPI (arXiv 2309.02637)](https://arxiv.org/html/2309.02637v2) | 恶意包数据集有限、生态规模差异导致检测难度不同 |
| S19 | [VM (executing JavaScript) – Node.js 文档](https://nodejs.org/api/vm.html) | 「`node:vm` 不是安全机制，不得用于运行不可信代码」 |
| S20 | [Permissions – Node.js 文档](https://nodejs.org/api/permissions.html) | Permission Model 为「安全带」不防恶意代码；不继承到子进程/worker；fd 绕过；符号链接被跟随；audit 模式与 `drop()` |
| S21 | [pickle – Python 文档](https://docs.python.org/3/library/pickle.html) | pickle 不安全、可执行任意代码、建议 JSON 与 `hmac`；长期对象应在对象内放版本号 |
| S22 | [Safe and Secure Python Code: don't use eval() – Codiga](https://www.codiga.io/blog/python-eval) | 不得对不可信输入使用 `eval()`，改用 `ast.literal_eval` |
| S23 | [subprocess – Python 文档](https://docs.python.org/3/library/subprocess.html) | 可执行文件用全限定路径（`sys.executable` + `-m`）；`shell=True` 安全注意；timeout/close_fds/pass_fds |
| S24 | [Zip Path Traversal – Android Developers](https://developer.android.com/privacy-and-security/risks/zip-path-traversal) | Zip Slip 成因、任意文件覆盖、可致代码执行、规范化校验缓解 |
| S25 | [Zip Slip Vulnerability – Sourcery](https://www.sourcery.ai/vulnerabilities/zip-slip-vulnerability-java) | Windows 变体（反斜杠/绝对路径/ADS）与压缩炸弹导致的资源耗尽 |
| S26 | [Fluent vs gettext – projectfluent wiki](https://github.com/projectfluent/fluent/wiki/Fluent-vs-gettext) | gettext 三格式与复数特例化；Fluent 单一 .ftl 与通用字符串变体 |
| S27 | [Fluent – A localization system（Hacker News 讨论，含项目方表述）](https://news.ycombinator.com/item?id=36276791) | 消息标识符 vs 源字符串标识符的取舍 |
| S28 | [A Practical Guide to the ICU Message Format – Phrase](https://phrase.com/blog/posts/guide-to-the-icu-message-format) | `plural`/`select` 语法、`#`、`=0` 优先级、`other` 必需；序数复数 |
| S29 | [i18n Pluralization: CLDR Plural Rules – Lokalise](https://www.locize.com/blog/i18n-pluralization) | 六类复数与各语言子集（中文仅 other）；`count === 1` 只对英语成立 |
| S30 | [Translation – Ren'Py 文档](https://www.renpy.org/doc/html/translation.html) | 单一主语言（None language）模型；可翻译图片/样式；资源按语言目录优先 |
| S31 | [pygame Issue #3025: SysFont 静默回退默认字体](https://github.com/pygame/pygame/issues/3025) | `SysFont` 中文显示方块且不报错；`Font(path)` 正常 |
| S32 | [pygame.font – pygame 文档](https://www.pygame.org/docs/ref/font.html) | UCS-4 支持与 `UCS4` 探测；单行渲染；字体渲染非线程安全 |
| S33 | [The chicken-and-egg problem of marketplaces – Platform Chronicles](https://platformchronicles.substack.com/p/the-chicken-and-egg-problem-of-marketplaces) | 平台常是事后识别；先服务可同时充当两侧的用户；iPhone 无 App Store 先例 |
| S34 | [How to Solve the Chicken and Egg Problem for Marketplace Founders](https://www.journeyh.io/blog/chicken-and-egg-problem) | 种子供给与「单机模式市场」；早期用户信任决策快 |
| S35 | [Tactics to solve the Chicken and Egg Paradox – Politecnico di Milano](https://re.public.polimi.it/bitstream/11311/1132412/1/PostPrint.pdf) | 双边平台鸡生蛋问题的学术表述与策略综述 |
| S36 | [Understanding JSON Schema Compatibility – Robert Yokota](https://yokota.blog/2021/03/29/understanding-json-schema-compatibility) | backward/forward/full 定义与 JSON Schema 增删属性的两条兼容规则 |
| S37 | [Semantic Versioning 2.0.0](https://semver.org) | 已发布版本 MUST NOT 修改；0.y.z 不稳定；主版本=破坏性信号 |
| S38 | [Breaking Change: Definition, Examples & Best Practices](https://www.docsie.io/blog/glossary/breaking-change) | 迁移指南 + deprecated 报错指向 + CLI 迁移工具的惯例流程 |
| S39 | [jsonschema 文档](https://python-jsonschema.readthedocs.io) | Python 侧多 Draft 校验支持（Draft 2020-12 等）与 CLI 工具 |
| S40 | [JSON Schema 2020-12 关键字参考](https://www.learnjsonschema.com/2020-12) | Draft 差异（`prefixItems`/`items` 语义） |
| S41 | [package.json – npm Docs](https://docs.npmjs.com/cli/v11/configuring-npm/package-json) | semver 范围语法；插件依赖宿主的实践建议（`^1.0` / `1.x` / `^1.5.2`） |
| S42 | [Semantic Versioning Explained – OpenReplay](https://blog.openreplay.com/semantic-versioning-explained) | `^`/`~`/精确版本语义与锁文件保证可复现安装 |
| S43 | [Developers Are Victims Too: VS Code Extension Ecosystem (arXiv 2411.07479)](https://arxiv.org/html/2411.07479v1) | 发布者验证、每个提交/更新扫描、命名抢注防护 |
| S44 | [Steam Support – User-Generated Content Approval](https://help.steampowered.com/en/wizard/HelpWithUGCSubmission) | 新增与更新进审核队列、旧版本对已订阅用户仍可用、多数数小时内处理 |
| S45 | [Capability-based security – Wikipedia](https://en.wikipedia.org/wiki/Capability-based_security) | 能力=不可伪造令牌、同时指定资源与权限；最小权限与受控分享 |
| S46 | [Worker threads – Node.js 文档](https://nodejs.org/api/worker_threads.html) | `resourceLimits` 语义与「触限终止 worker」；限制只作用于 JS 引擎 |
| S47 | [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification) | 错误码区间与预定义错误码；批量请求 |
| S48 | [Language Server Protocol – Wikipedia](https://en.wikipedia.org/wiki/Language_Server_Protocol) | 基于 JSON-RPC、带类似 HTTP 头的 stdio 消息帧 |
| S49 | [Messages – Model Context Protocol](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) | id 非 null 且会话内不复用；响应只含 result 或 error；通知不带 id |
| S50 | [ast – Python 文档](https://docs.python.org/3/library/ast.html) | AST 模块定位（供 `ast.literal_eval` 字面量解析路径引用） |
| S51 | [Unicode CLDR Plural Rules 完整指南](https://intlpull.com/blog/cldr-plural-rules-complete-guide-2026) | 六类复数、各语言子集、用 ICU 而非硬编码判断 |
| S52 | [Localization Keys vs. Direct Text Keys – DEV Community](https://dev.to/spyke/localization-keys-vs-direct-text-keys-5i) | key 化在大型团队/外部翻译服务下更稳健；源串为 key 的适用条件与上下文要求 |
| S53 | [Godot 论坛：localization 策略与边界情形](https://forum.godotengine.org/t/understanding-localization-strategies-and-edge-cases/119719) | 长文本（设定集/手册）用 gettext 的别扭之处；Poedit 用 en.po 带出英文的实际体验 |
| S54 | [Fallback for harfbuzz fonts – TeX StackExchange](https://tex.stackexchange.com/questions/520034/fallback-for-harfbuzz-fonts) | HarfBuzz 只做整形、回退由应用负责 |
| S55 | [Litherum: End-To-End Tour of Text Layout/Rendering](http://litherum.blogspot.com/2015/02/end-to-end-tour-of-text-rendering.html) | 缺字形落到 `.notdef`（tofu）；回退导致同词混排不同字体 |
| S56 | [State of Text Rendering 2024 – Behdad](https://behdad.org/doc/text2024) | 复杂文本/双向渲染需整形驱动回退；Unity 2024 年才经 HarfBuzz+ICU 支持 |
| S57 | [Multiple Language Support – Ren'Py Wiki](https://www.renpy.org/wiki/renpy/doc/cookbook/Multiple_Language_Support) | 多路径翻译方案与「不能跨语言读档」的限制 |
| S58 | [Localization using spreadsheets – Godot 文档](https://docs.godotengine.org/en/latest/tutorials/i18n/localization_using_spreadsheets.html) | CSV/PO 流程；key 化时复数支持不完整、建议 gettext；翻译上下文（4.6+） |
| S59 | [Complete Godot Localization Guide – GodotAwesome](https://godotawesome.com/godot_localization) | `.pot` 提取 → `.po` → `.mo`/`.translation` 工作流与 RTL 支持 |
| S60 | [Producing and Localizing a Visual Novel in Ren'Py – Medium](https://medium.com/@william.hanwei.dan/producing-and-localizing-a-visual-novel-in-renpy-73a0c1f7c708) | Ren'Py「无主翻译文档、语言两两 1:1」导致本地化更费力 |

**未找到可核查来源的条目**（不作为结论依据）
- 「微内核 + 事件总线」在**游戏行业**的具体量化收益对比：检索未取得权威一手来源。
- 游戏内容包（level pack / content pack）**签名校验**的标准做法：检索到的是引擎运行日志与工具文档层面的零散证据，未见统一规范，故本文只给出「哈希清单 → 可选签名」的工程建议而非标准引用。
- 「何时应该为游戏开放 mod 支持」的可操作判据：检索到的多为行业评论，未取得可核查的方法论来源。
