# Web 平台形态（含关卡编辑器）调研

- **主题**：把桌面 Python + pygame 文字解谜游戏搬到浏览器可玩（无 pygame 依赖），并支持以后在网页内编辑谜题/内容包。
- **检索日期**：2026-10-16（下文所有来源均为当日联网检索；二手文章与官方文档已分别标注）。
- **调研边界**：只覆盖「Web 平台形态 + 关卡编辑器」；不覆盖 Python 侧重构方案、计分规则、美术。
- **术语**：**视图模型**＝Python 谜题进程输出的、渲染无关的 JSON 描述；**原语（primitive）**＝网格 / 列表 / 文本输入 / 选项等最小渲染单元。
- **项目上下文（仅用仓库相对路径）**：`puzzle_service/`（`registry.py` 谜题注册表、`service.py` 会话与计分、规划中的 `views.py` 视图模型适配层）、`text_adventure_zh/gameplay_pool/`（14 种谜题，含 `color_sequence.py`）、`text_adventure_zh/ui.py`（现 pygame 渲染层）、`docs/_research/`。

## 结论摘要

1. **「服务端产出声明式视图描述 + 前端少量通用控件渲染」是被验证过的模式，但只在「固定控件集」内成熟**。JSON Forms 用「数据 schema（JSON Schema）+ UI schema（布局）」双 schema 分离，并提供 renderer 注册表与自定义 renderer 扩展点（[jsonforms.io/docs/uischema](https://jsonforms.io/docs/uischema)、[Custom Renderers](https://jsonforms.io/docs/tutorial/custom-renderers)）。一旦需要 schema 未暴露的精细布局或交互，官方路径是写 React 组件（[C3 AI 的 JSON vs React 对照表](https://docs.c3.ai/docs/uiComponentLibraryReact/8.10/topic/json-component-limitations)）——即**通用渲染器负责 80%，剩余 20% 必须显式自定义**，这不是缺陷而是该模式的固有边界。
2. **产业界（Lyft / Airbnb）采用 server-driven UI 的动机是「绕开客户端发版」与「实验速度」，代价是测试成本、版本兼容与可访问性**；Lyft 明确提到「客户端越来越不知道自己渲染的是什么，可访问性支持变难」（[MobileNativeFoundation 讨论 #47](https://github.com/MobileNativeFoundation/discussions/discussions/47)、[SDUI 综述](https://medium.com/@aubreyhaskett/server-driven-ui-what-airbnb-netflix-and-lyft-learned-building-dynamic-mobile-experiences-20e346265305)）。对本项目的含义：视图模型必须有**原语白名单 + 未知原语 fail loud**，否则会退化成「每个谜题一条特例分支」。
3. **回合制解谜的传输首选 SSE，不是 WebSocket**。SSE 天然带自动重连、`retry` 与 `Last-Event-ID` 断点续传语义（[javascript.info: Server Sent Events](https://fa.javascript.info/server-sent-events)）；WebSocket 是双向且最重，且**协议本身不含重连/恢复**（[Ably: WebSockets vs SSE](https://ably.com/blog/websockets-vs-sse)、[designgurus](https://designgurus.substack.com/p/websockets-vs-server-sent-events)），要用恢复能力得引入 Socket.IO 的 `connectionStateRecovery`（v4.6.0 起，[官方文档](https://socket.io/docs/v4/connection-state-recovery)）。本项目服务端本来就持有会话快照（`puzzle_service/service.py`），「重连＝重发全量快照」是最省事的恢复契约。
4. **Node 侧边界要记清**：内置 `WebSocket` **客户端**自 v22.4.0 起标记为 stable；Node **没有**内置 WebSocket 服务端，要当服务端仍得用 `ws` 或 socket.io（[Node.js 官方 learn 页](https://nodejs.org/learn/getting-started/websocket)、[RisingStack](https://blog.risingstack.com/nodejs-22)）。
5. **网页关卡编辑器有可直接借鉴的开源实现，但没有一个能直接吃「文字解谜」的数据**：Tiled（JSON map format、`--export-map` CLI）、LDtk（MIT、文档化 JSON、崩溃备份）、`blurymind/tilemap-editor`（零依赖、自带 PWA `manifest.webmanifest` + `sw.js`）、Konva/react-konva（canvas 交互 + 拖拽/吸附）。**未找到**文字解谜 / 文本冒险类的开源关卡编辑器案例（来源见 §3）。
6. **「编辑态 / 游玩态」双模式的可核查证据是「只读开关」而非「双编辑器」**：Excalidraw 用 `viewModeEnabled` 布尔 prop 在同一组件内切只读；JSON Forms 用 `readonly` 整表禁用 + rule 做元素级启用/禁用。游戏引擎侧（Unity）的既有约定是「Play Mode 的改动不写回场景」（[Cinemachine 文档](https://docs.unity3d.com/Packages/com.unity.cinemachine@2.3/manual/CinemachineSavingDuringPlay.html)）。**未找到**针对网页关卡编辑器双模式的权威工程规范文章。
7. **撤销/重做的现实取舍**：快照（memento）实现简单、易把已有状态升级为可撤销；命令模式支持宏录制但更难（[实践文章](https://www.npbee.me/posts/command-based-undo)、[Unity 讨论](https://discussions.unity.com/t/approach-to-creating-an-undo-redo-system/946942)）。内容包是纯数据且体积小 → **快照栈足够**；Yjs `UndoManager` 只在真要做协同编辑时才值得（[Yjs 文档](https://docs.yjs.dev/getting-started/a-collaborative-editor)）。
8. **内容包分发 = 静态 JSON + 指纹缓存 + Schema 校验 + 显式版本门**。缓存用「新 URL 代替失效」+ `Cache-Control: max-age=31536000, immutable`（[MDN Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control)）；离线用 Service Worker（stale-while-revalidate 等策略的定义与利弊见 [web.dev](https://web.dev/articles/service-worker-caching-and-http-caching)）+ IndexedDB（[MDN](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)）；校验用 JSON Schema（**当前版本 2020-12**，[json-schema.org/specification](https://json-schema.org/specification)）+ Ajv（支持 draft-04/06/07/2019-09/2020-12 与 JTD，[ajv.js.org](https://ajv.js.org)）。版本门的最佳现实先例是 Minecraft 数据包的 `pack.mcmeta`：用 `min_format`/`max_format` 表达兼容区间，而不是单一版本号（[Minecraft Wiki: Pack format](https://minecraft.wiki/w/Pack_format)）。
9. **可访问性有硬约束，且「颜色序列」这类纯颜色玩法天然违反 WCAG**：WCAG 2.2 于 2023-10-05 成为 W3C Recommendation，新增 9 条 SC、移除 4.1.1 Parsing（[W3C What's New in WCAG 2.2，本次直接抓取](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)）。SC 1.4.1（Level A）禁止颜色作为唯一视觉手段（[W3C Understanding 1.4.1](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html)）。对策是把每个颜色**重复编码**为符号/形状/文字（游戏业界的通行做法，[Can I Play That 色盲指南](https://caniplaythat.com/2020/01/29/color-blindness-accessibility-guide)、[forallwe](https://www.forallwe.com/en/post/color-blindness-video-games-accessibility-filters)）。
10. **Windows 单机双进程（Node + Python）可行的最省事形态是：只暴露 Node 一个端口，Python 作为子进程由 `spawn` 拉起并守护**。Windows 上杀子进程树要用 `taskkill /PID <pid> /T /F`（Node 不支持按名字杀进程，[nodejs/help#4050](https://github.com/nodejs/help/issues/4050)）；守护用 NSSM 或 WinSW，**不要指望 PM2**——PM2 官方 `pm2 startup` 支持的 init 系统列表里没有 Windows（[PM2 官方文档](https://pm2.keymetrics.io/docs/usage/startup)），Windows 方案要么依赖登录态（`pm2-windows-startup`，2015 年后未更新），要么另装服务包装器（[二手文章](https://medium.com/@gzthomasliang/run-pm2-as-service-on-windows-server-in-modern-way-286b9f4b8228)）。

## 逐项调研

> 本节所有链接的检索日期均为 **2026-10-16**；标「二手」的是博客/教程/问答，标「官方」的是项目文档或规范。

### 1. 服务端渲染「视图模型」的通用 UI 模式

**1.1 模式家族与成熟度**

| 方案 | 核心机制 | 成熟度信号 | 适配本项目？ |
| --- | --- | --- | --- |
| JSON Forms | JSON Schema（数据）+ UI Schema（`VerticalLayout`/`Control` 等元素）双 schema，renderer 注册表 | 官方文档完整、支持 React/Angular/Vue，官方提供 custom renderer 教程（[uischema](https://jsonforms.io/docs/uischema)、[custom renderers](https://jsonforms.io/docs/tutorial/custom-renderers)） | 可借鉴「双 schema + renderer 注册表」结构，但不必引入库 |
| RJSF | 直接由 JSON Schema 映射到 UI 组件，附带主题包 | 二手对比文章称其为 React 生态采用最广（[SurveyJS 对比](https://surveyjs.io/stay-updated/blog/best-json-form-editor)、[DEV 对比](https://dev.to/yanggmtl/schema-driven-forms-in-react-comparing-rjsf-json-forms-uniforms-formio-and-formitiva-2fg2)） | 仅作参考 |
| Uniforms / Form.io | 前者做 schema 适配器；后者是「表单即基础设施」（API/权限/白标） | 二手对比（[Form.io 对比文](https://form.io/json-schema-forms-formio-rjsf-jsonforms-surveyjs-compared)） | 明确过重 |
| server-driven UI（SDUI） | 后端直接下发界面描述 | Lyft/Airbnb 生产实践（官方工程讨论 [discussion #47](https://github.com/MobileNativeFoundation/discussions/discussions/47)） | 结构同构，可直接借用其教训清单 |

**1.2 能力边界（有明确文档证据）**

- C3 AI 的官方文档给了可直接照抄的判据表：**基础布局与展示逻辑 → 用 JSON 组件（前提是组件开箱支持该用例）；需要 schema 未暴露的自定义结构/布局/交互 → 用代码写组件**；并直说「JSON UI 组件不是为复刻代码的表达力而设计的」，条件渲染只有有限的 `ConditionalRenderer`/`SwitchRenderer`（[C3 AI: Limitations of JSON UI components](https://docs.c3.ai/docs/uiComponentLibraryReact/8.10/topic/json-component-limitations)）。
- JSON Forms 的自定义 renderer 机制说明「扩展点」是常规路径：写自定义 renderer 时要自己处理 dispatch、并注意 `ResolvedJsonFormsDispatch` 与 `JsonFormsDispatch` 的性能差异（[官方教程](https://jsonforms.io/docs/tutorial/custom-renderers)）。→ 对本项目：**每种谜题不该有专属渲染器；只有「无法用既有原语表达」时才新增原语**。
- 产业界的代价清单（Lyft/Just Eat 口径）：测试复杂度显著上升、需跨多设备验证、组件版本兼容问题、以及**可访问性支持变难**（客户端不清楚自己渲染的是什么）（[discussion #47](https://github.com/MobileNativeFoundation/discussions/discussions/47)、[综述](https://medium.com/@aubreyhaskett/server-driven-ui-what-airbnb-netflix-and-lyft-learned-building-dynamic-mobile-experiences-20e346265305)）。

**1.3 对本项目的映射建议（建议，非来源结论）**

- 把 14 种谜题收敛成原语闭包：`grid`（数独/数织/扫雷/2048/填字）、`list`（记忆/列表选择）、`text-input`（数学/猜数字/字谜/填字答案）、`choice`（选项/随机抽取）、`color-sequence`（颜色序列，见 §5 的无障碍替代）、`status`（计分/计时/提示）。
- 视图模型带 `viewModelVersion` 与 `kind`；前端遇到未知原语或未知版本**直接报错并提示刷新**，不静默降级（与仓库既有的 fail-loud 纪律一致）。
- 原语 → 语义 HTML 的映射必须是固定表（`grid` → 表格语义或 ARIA grid、`choice` → radio/checkbox 组），禁止渲染成裸 `<div>`；每个原语必须带可访问名称（label）。这是对 §5 可访问性的结构性保障。

### 2. 实时交互的传输选型

**2.1 三种传输在「回合制解谜」下的取舍**

| 维度 | HTTP 轮询 / 长轮询 | SSE | WebSocket |
| --- | --- | --- | --- |
| 方向 | 客户端拉 | 单向（服务端→客户端） | 双向 |
| 实现/运维成本 | 最低，任何代理都过 | 低，走普通 HTTP，不易被防火墙拦（[Ably](https://ably.com/blog/websockets-vs-sse)） | 最高，需要握手升级、可能被企业代理拦（[Ably](https://ably.com/blog/websockets-vs-sse)、[designgurus](https://designgurus.substack.com/p/websockets-vs-server-sent-events)） |
| 断线恢复 | 无内建，靠客户端重放 | **内建**：自动重连 + 可调 `retry` + `Last-Event-ID` 续传（[javascript.info](https://fa.javascript.info/server-sent-events)） | **协议层无**，需 Socket.IO `connectionStateRecovery`（[官方](https://socket.io/docs/v4/connection-state-recovery)）或自建 |
| 连接数限制 | — | HTTP/1.1 下每域约 6 条并发流（跨标签页共享），HTTP/2 多路复用后基本消失（二手：[portalZINE](https://portalzine.de/sses-glorious-comeback-why-2025-is-the-year-of-server-sent-events)、[DEV](https://dev.to/abhivyaktii/understanding-server-sent-events-sse-and-why-http2-matters-1cj7)） | 无此限制 |
| 其他限制 | 延迟 | 仅文本（UTF-8）、单向 | 需自行定义消息语义与心跳 |

- 二手综述强调「不要默认上 WebSocket」：简单负载用简单模式，否则白背运维负担（[designgurus](https://designgurus.substack.com/p/websockets-vs-server-sent-events)、[RxDB 对比](https://rxdb.info/articles/websockets-sse-polling-webrtc-webtransport.html)）。

**2.2 Node 侧现状（官方口径）**

- 内置 `WebSocket` **客户端**：自 Node.js v21 起基于 Undici 提供，**v22.4.0 标记为 stable**；示例 `new WebSocket('wss://…')`（[nodejs.org/learn](https://nodejs.org/learn/getting-started/websocket)、[RisingStack](https://blog.risingstack.com/nodejs-22)、[NodeSource](http://nodesource.com/blog/nodejs-22-features)）。
- **Node 依然没有内置 WebSocket 服务端**，要接受来连仍需 `ws` / socket.io 之类的库（[nodejs.org/learn](https://nodejs.org/learn/getting-started/websocket)；`ws` 用法见二手 [Ably 库综述](https://ably.com/blog/websocket-libraries-for-node)、[Honeybadger 教程](https://www.honeybadger.io/blog/websocket-node)）。

**2.3 建议（本项目）**

- 主链路：`POST /rpc`（提交动作/答案）+ `GET /events`（SSE 推送视图模型快照）。理由：回合制对延迟不敏感；`puzzle_service` 已是「无传输、可快照」的设计（见 `puzzle_service/service.py` 文件头说明）；SSE 原生重连省掉一整套自建协议。
- 状态恢复契约：每会话维护递增 `seq`；客户端重连带 `Last-Event-ID`（SSE 原生）或 `?since=<seq>`；服务端**能补增量就补，否则直接重发全量快照**（全量更简单，且视图模型不大）。避免让前端做状态合并。
- WebSocket 只在出现「需要 <100ms 双向」或「多人实时同屏」需求时再引入；届时优先 socket.io 的 `connectionStateRecovery` 而不是自造恢复层。

### 3. 谜题 / 关卡编辑器

**3.1 可借鉴的既有实现（官方优先）**

- **Tiled**：JSON 导出支持全部 Tiled 特性、比 TMX 更适合在 JS 环境加载，且可用命令行 `--export-map` 自动化导出；CSV 导出只支持图块层（官方文档：[JSON Map Format](https://doc.mapeditor.org/en/stable/reference/json-map-format)、[Generic File Formats](https://doc.mapeditor.org/en/stable/manual/export-generic)）。→ 可借鉴「图层 + 对象层 + 自定义属性」的数据组织与「CLI 导出」的自动化习惯。
- **LDtk**：开源（MIT）2D 关卡编辑器，输出「文档化 JSON，任何引擎都易解析」，并有强备份/崩溃恢复（[ldtk.io 官方站](https://ldtk.io)）。→ 可借鉴「编辑器崩溃不能丢草稿」这一需求（对网页版＝自动存草稿到 IndexedDB/localStorage）。
- **`blurymind/tilemap-editor`**：零依赖、移动端友好的瓦片地图编辑器，仓库内自带 `manifest.webmanifest` 与 `sw.js`（[GitHub](https://github.com/blurymind/tilemap-editor)）。→ 证明「单页 + PWA + 导入器」的网页编辑器形态可行，且可离线。
- **Konva / react-konva**：2D canvas 框架，支持拖拽、吸附（snap）、序列化、多框架绑定，MIT（[官方 About](https://konvajs.org/docs/about.html)；第三方网格库综述提到其拖拽/吸附能力与 React 绑定，[Max Zsol](https://maxzsol.com/top-5-open-source-draggable-grid-layout-ui-libraries-for-the-web)）。→ 只在需要自由拖拽布局时才引入。
- **Excalidraw**：开源白板，`.excalidraw` 为纯 JSON、可脱离应用读取（二手：[DEV 对比文](https://dev.to/nologintools/excalidraw-free-online-whiteboard-no-login-required-25j5)、[Meetrix 综述](https://meetrix.io/blogs/open-source-whiteboard-tools)）；官方提供 `viewModeEnabled` 只读开关（[官方 Quick Start](https://excalidraw-excalidraw.mintlify.app/quickstart)、[npm 包 README](https://www.npmjs.com/package/@excalidraw/excalidraw-next)）。
- 商业/闭源参考（非开源，仅交互参考）：PixLab 浏览器瓦片地图编辑器，支持图层、导出结构化数据（[官网](https://pixlab.io/tilemap-2d-level-editor)）。
- **文字解谜 / 文本冒险类的开源关卡编辑器：未找到可核查来源。** 检索到的网页关卡编辑器全部属于 2D 瓦片/平台类。

**3.2 编辑态 / 游玩态双模式**

- 可核查的相邻证据：
  - Excalidraw：`viewModeEnabled` 布尔 prop 切换只读视图（官方）。
  - JSON Forms：`readonly` 整表禁用；单个元素用 rule 的 `ENABLE`/`DISABLE` 动态控制；**注意其把 JSON Schema 的 `readOnly: true` 当作 disabled 处理**，语义上不区分 readonly 与 disabled（[官方 ReadOnly 文档](https://jsonforms.io/docs/readonly)）。
  - Unity：官方文档明确「正常情况下退出 Play Mode 时不会保存你对场景的修改」，第三方包才提供「保留 Play 期间调整」的特例（[Cinemachine: Saving in Play Mode](https://docs.unity3d.com/Packages/com.unity.cinemachine@2.3/manual/CinemachineSavingDuringPlay.html)）。
  - Godot：编辑器运行场景用 F5/F8（[官方文档](https://docs.godotengine.org/en/stable/getting_started/step_by_step/nodes_and_scenes.html)）；社区提案讨论「在编辑器内直接运行」时必须先保存原场景状态以便停止后还原（[godot-proposals#9142](https://github.com/godotengine/godot-proposals/issues/9142)）。
- **未找到**面向网页关卡编辑器的「编辑态/游玩态」权威工程文章；`iframe` 隔离预览也未检索到可核查的工程规范来源（检索命中的 `IFRAME` 结果是 Google Apps Script 的沙箱迁移文档，与本主题无关）。
- 建议（非来源结论）：**一份内容包 JSON，两个渲染器**——`render(viewModel, {mode: 'edit' | 'play'})`；play 模式对内容包只读，运行时的改动只进会话快照、不回写内容包；编辑态改动即时重算视图模型做预览（不需要 iframe；若后续要隔离第三方内容包脚本，再考虑 iframe + `sandbox`）。

**3.3 撤销 / 重做**

- 快照 vs 命令：实践文章给出取舍——快照（memento）容易把既有状态升级为可撤销、且不污染架构；命令模式更灵活、支持宏录制，但实现更难（[npbee.me](https://www.npbee.me/posts/command-based-undo)、[Unity 讨论帖](https://discussions.unity.com/t/approach-to-creating-an-undo-redo-system/946942)）。
- 协同编辑场景：Yjs 的 `UndoManager` 提供选择性撤销、可用 `trackedOrigins` 限定「只撤销本地/某来源的变更」（[Yjs 官方文档](https://docs.yjs.dev/getting-started/a-collaborative-editor)；ProseMirror 集成示例见 [discuss.prosemirror.net](https://discuss.prosemirror.net/t/offline-peer-to-peer-collaborative-editing-using-yjs/2488)）。
- 建议（非来源结论）：首版用**快照栈**（上限 100 步、结构共享或 JSON 深拷贝二选一），快捷键 `Ctrl+Z` / `Ctrl+Shift+Z`，撤销栈按「一次编辑会话」作用域；不要提前引入 CRDT。

**3.4 导入 / 导出**

- 导出：常规做法是生成 Blob + `<a download>`；桌面 Chrome/Edge/Opera 可用 File System Access API 的 `showSaveFilePicker()` 直接写盘，**Firefox/Safari 只支持 OPFS 沙箱、不支持本地磁盘选择器**（[MDN showSaveFilePicker](https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker)、二手支持矩阵 [testmuai](https://www.testmuai.com/learning-hub/file-system-access-api-browser-support)）→ 必须保留下载兜底。
- 导入：文件选择后先过 schema 校验再入库，错误要能定位到「哪个字段、期望什么」（见 §4）。
- 编辑器数据建议：`{ packFormat, id, title, levels: [...] }`，每个级别带 `kind` 与 `params`；导出前校验 + 规范化（键顺序稳定，便于 diff 与快照测试）。

### 4. 内容包分发格式与标准

- **静态 JSON + CDN**：现代做法是给静态资源加内容指纹，用「新 URL 代替缓存失效」，对不变资源加长缓存 `Cache-Control: max-age=31536000, immutable`（[MDN Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control)；二手深入解释 [CSS Wizardry](https://csswizardry.com/2019/03/cache-control-for-civilians)）。同源部署（Node 直接托管静态文件）可顺带绕开 CORS；跨源则必须由服务端给出 CORS 头（通用 fetch 语义；本项未见针对 JSON 的专项规范，标注为工程常识）。
- **完整性**：SRI 要求 `integrity` 与 `crossorigin` 同时具备，浏览器才会校验跨源资源；另有 `Integrity-Policy` 响应头可强制文档加载的脚本必须带完整性（[MDN Subresource Integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Subresource_Integrity)）。→ 本项目内容包是数据、不是脚本，SRI 主要用于前端 bundle 与第三方库。
- **离线缓存**：Service Worker 的 `stale-while-revalidate`（先给缓存再后台更新，适合非关键新鲜度的内容）、cache-first、cache-only 的适用场景与利弊在 web.dev 有明确说明（[web.dev: Service worker caching and HTTP caching](https://web.dev/articles/service-worker-caching-and-http-caching)）；IndexedDB 适合存结构化大数据（含 File/Blob），且遵守同源策略（[MDN IndexedDB API](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)）。
- **PWA 可安装性**（若想「像 App 一样」打开）：必须 HTTPS 或 localhost/127.0.0.1；Chromium 系要求 manifest 含 `name` 或 `short_name`、192px 与 512px 图标、`start_url`、`display`（或 `display_override`）、`prefer_related_applications` 为 false 或缺省；Service Worker 对可安装性**不是必需**（[MDN: Making PWAs installable](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)、[MDN: What is a PWA](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/What_is_a_progressive_web_app)）。
- **Schema 校验**：JSON Schema 当前版本为 **2020-12**（上一版 2019-09），元 schema 亦为 2020-12（[json-schema.org/specification](https://json-schema.org/specification)、[draft 2020-12](https://json-schema.org/draft/2020-12)）；Ajv 支持 draft-04/06/07/2019-09/2020-12 与 JSON Type Definition（RFC 8927），并被官方描述为编译 schema 为 JS 校验代码（[ajv.js.org](https://ajv.js.org)、[GitHub](https://github.com/ajv-validator/ajv)）。→ Node 侧用 Ajv 做「内容包入库前 + 启动时」双重校验；Python 侧的校验器选型**本轮未核查**（标注：未找到可核查来源）。
- **版本与迁移**：最贴近的现实先例是 Minecraft 数据包 —— 包根目录 `pack.mcmeta` 用 `min_format`/`max_format` 声明兼容区间，格式号随游戏版本变化（例如 1.21.9 推荐 88；数据包与资源包格式号互相独立），格式号不匹配只给兼容性警告但仍加载（[Minecraft Wiki: Pack format](https://minecraft.wiki/w/Pack_format)；二手工具站 [minecraftmaps](https://www.minecraftmaps.com/tools/pack-mcmeta)）。→ 借鉴为 `packFormat: { min, max }`，由宿主判断「本内容包是否需要迁移」。
- **迁移机制**：未找到权威的通用「内容包迁移」规范；可核查的只有「显式版本字段 + 迁移函数链」这一工程惯例（**标注：未见标准来源，属工程共识**）。建议 `migrations: { "1→2": fn, "2→3": fn }` 顺序执行，迁移后回写并保留原文件备份。

### 5. 可访问性与规范化

**5.1 WCAG 2.2 要点（以 W3C 页面为准，本次直接抓取）**

- WCAG 2.2 于 **2023-10-05** 成为 W3C Recommendation；相比 2.1 新增 **9 条** SC，并移除 4.1.1 Parsing（[W3C What's New in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)）。新增条目与等级：2.4.11 Focus Not Obscured (Minimum) **AA**、2.4.12 (Enhanced) **AAA**、2.4.13 Focus Appearance **AAA**、2.5.7 Dragging Movements **AA**、2.5.8 Target Size (Minimum) **AA**、3.2.6 Consistent Help **A**、3.3.7 Redundant Entry **A**、3.3.8 Accessible Authentication (Minimum) **AA**、3.3.9 (Enhanced) **AAA**。
- **纠正一处常见误传**：多篇二手博客把 2.4.13 Focus Appearance 写成 AA，W3C 页面标注为 AAA；以 W3C 为准。
- 本项目最相关的三条：
  - **2.5.7 拖拽替代（AA）**：任何拖拽操作都必须能用不拖拽的单指操作完成 → 编辑器拖拽摆放格子必须配「点击选中 + 方向键/上下按钮移动」。
  - **2.5.8 目标尺寸（AA）**：指针目标至少 24×24 CSS px，或与相邻目标保持足够间距（另有 Inline / Equivalent / Essential 等例外）→ 网格单元格与按钮尺寸即为设计硬约束（[W3C 页面原文](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)）。
  - **3.3.7 冗余录入（A）**：同一流程内已提供的信息不得要求再次输入 → 会话恢复后表单要自动回填。
- 3.3.8/3.3.9 约束的是**认证步骤**（不得强制记忆/解谜类认知测试）。本项目本身是解谜游戏，这两条不约束玩法，但意味着**不能拿谜题当登录验证**（例如「答对谜题才能登录」），否则违规。

**5.2 键盘与屏幕阅读器**

- 键盘可达（SC 2.1.1 Keyboard）是基础：所有玩法必须可不用鼠标完成。
- 网格用 ARIA grid 模式：`grid` 是二维导航的复合控件，方向键在单元格间移动焦点（[MDN grid role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/grid_role)、[APG Grid 模式](https://www.w3.org/WAI/ARIA/apg/patterns/grid)）。**注意争议**：APG 建议的 PageUp/PageDown/Home/End 会劫持浏览器翻页导航，社区 issue 建议改用修饰键（[w3c/aria-practices#3409](https://github.com/w3c/aria-practices/issues/3409)）→ 本项目只用方向键 + Enter/Space 足够。
- 表格/网格语义：若用 `display: table/grid` 等 CSS 覆盖原生语义，必须显式补齐 ARIA table/grid 角色，否则屏幕阅读器读不出行列关系（[Sarah Higley: Grids Part 2](https://sarahmhigley.com/writing/grids-part2)）。
- 动态更新：用 live region 播报。`aria-live="polite"` 为常态（用户空闲时朗读），`assertive` 只用于时间敏感的紧急信息且会打断当前朗读；**容器必须先存在于 DOM 再更新内容**，否则不会被播报（[MDN Live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions)、[MDN alert role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/alert_role)）→ 答题判定结果、计时提醒、动作被拒绝的提示都走 polite live region。
- 参考实现：屏幕阅读器可玩的文字冒险确有先例 —— Upheaval 提供 TTS、键盘导航与暗色模式（[实况录像](https://www.youtube.com/watch?v=pdjtJHbQHUo)）；AI Dungeon 被无障碍游戏列表收录为屏幕阅读器可玩（[Knights of the Braille](https://knightsofthebraille.com/accessibility)）。→ 文本类玩法天然适配，但需要显式设计键盘映射与朗读时机。

**5.3 颜色与对比度（含「颜色序列」替代方案）**

- 硬约束：**SC 1.4.1 Use of Color（Level A）**——颜色不得作为传达信息、指示动作、提示响应或区分元素的**唯一**视觉手段；若信息用颜色差异表达，必须同时用另一种视觉手段提供（[W3C Understanding 1.4.1](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html)）。当前 `text_adventure_zh/gameplay_pool/color_sequence.py` 的纯颜色玩法直接命中此条。
- 对比度：正文 4.5:1、大文本 3:1（SC 1.4.3 AA）；UI 组件与有意义图形 3:1（SC 1.4.11 AA）（二手解释 [Stark](https://www.getstark.co/wcag-explained/perceivable/distinguishable/contrast-minimum)、[AllAccessible](https://www.allaccessible.org/blog/color-contrast-accessibility-wcag-guide-2025)；本轮未直接抓取 W3C 对应 Understanding 页，**数字口径以二手来源为准**）。
- 游戏业界通行对策（二手，但两家独立来源一致）：不要只用颜色；用图标/符号/文字/图案重复编码状态；为色盲提供可调色板或 protan/deutan/tritan 预设；地图标记用不同形状；重要元素用边框/星数/图案区分（[Can I Play That](https://caniplaythat.com/2020/01/29/color-blindness-accessibility-guide)、[forallwe](https://www.forallwe.com/en/post/color-blindness-video-games-accessibility-filters)）。
- **颜色序列的可访问性替代方案（以下为建议，非来源结论）**：
  1. 每个颜色同时绑定一个**符号 + 中文色名**（如「红 ▲」「蓝 ●」），序列直接渲染成「▲●■▲」这样的符号串，颜色只是强化；
  2. 提供「高对比 / 色盲友好调色板」开关（预设 + 强度），并把选择存进会话；
  3. 允许用键盘输入色名或序号作答，作为点选颜色的等价路径（对应 SC 2.5.8 的 Equivalent 思路）；
  4. 目标序列与已输入序列都要有非颜色的位置/数量提示（例如「第 3 位：■」），并同步到 live region；
  5. 若难度依赖颜色识别本身，则需要在设计侧确认替代方案是否等价，避免变成「可访问但换了一个题」。

**5.4 动效**

- 必须尊重 `prefers-reduced-motion`：该媒体特性用于检测用户是否要求减少非必要动效，值为 `no-preference` / `reduce`（[MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion)；二手实践 [Smashing Magazine](https://www.smashingmagazine.com/2021/10/respecting-users-motion-preferences)）→ 2048 滑动、记忆翻牌等动画在 reduce 下改为瞬时切换。

### 6. 部署与运维（Windows 单机，Node + Python 双进程）

**6.1 进程模型**

- Node 官方 `child_process.spawn` 支持 `stdio` 重定向（把 stdout/stderr 写入文件）与 `detached`/`unref` 语义（[Node 官方文档](https://nodejs.org/api/child_process.html)）。→ Python 进程的 stdout 建议直接落到 `logs/python.log`，Node 不解析人类可读输出，只解析协议行。
- Windows 杀进程树：Node 不支持按名字杀进程，需要拿到 PID 后用 `taskkill /pid <pid> /f /t`（[nodejs/help#4050](https://github.com/nodejs/help/issues/4050)；二手经验 [Adobe 社区帖](https://community.adobe.com/questions-729/killing-child-process-in-cep-node-js-1379943)）。→ 关闭/重启时必须清树，否则会留下孤儿 Python 进程占住资源。
- **建议（非来源结论）**：Python 不额外监听 TCP 端口，而由 Node 通过 stdin/stdout 的 JSON 行协议驱动（与 `puzzle_service/service.py` 文件头「the Cordis host talks to over JSON-RPC」一致，只是换成 stdio 通道）。这样对外只暴露 Node 一个端口，端口冲突面最小、也便于把 Python 进程当纯计算服务重启。

**6.2 守护与自启（Windows）**

| 方案 | 状态（可核查） | 结论 |
| --- | --- | --- |
| WinSW | MIT，包装任意可执行文件为 Windows 服务；3.x 在 `v3` 分支开发，2.x 稳定版在 Releases；支持日志滚动等（[GitHub](https://github.com/winsw/winsw)、[NuGet 2.11.0](https://www.nuget.org/packages/WinSW)） | 推荐备选 |
| NSSM | 把 `python.exe + 脚本` 装成服务、可监控执行状态并把输出记入 Windows 事件日志（二手教程 [MSSQLTips](https://www.mssqltips.com/sqlservertip/7325/how-to-run-a-python-script-windows-service-nssm)、[Medium 指南](https://joe-thomas.medium.com/running-a-python-script-as-a-windows-service-a-guide-a32abbc90172)） | **推荐**：命令行最简 |
| PM2 | 官方 `pm2 startup` 支持的 init 系统为 systemd/upstart/launchd/openrc/rcd/systemv 等，**不含 Windows**（[PM2 官方](https://pm2.keymetrics.io/docs/usage/startup)）；Windows 需 `pm2-windows-startup`（注册表，依赖用户登录，2015 年后未更新）或 `pm2-service-installer` / `jessety/pm2-installer`（二手 [Medium](https://medium.com/@gzthomasliang/run-pm2-as-service-on-windows-server-in-modern-way-286b9f4b8228)） | 不作为首选 |
| 任务计划程序 | 未核查官方文档 | 未找到可核查来源 |
| node-windows | 未核查到官方文档状态 | 未找到可核查来源 |

**6.3 端口冲突**

- Node 绑定失败抛 `EADDRINUSE`，应在 `server.on('error')` 捕获并给出可读提示（非 0 退出码），而不是打一堆栈（二手 [OpenReplay](https://blog.openreplay.com/fix-error-eaddrinuse-nodejs)、[DEV](https://dev.to/antonrosh/address-already-in-use-a-simple-guide-to-freeing-up-ports-54g5)）。
- Windows 排查：`Get-NetTCPConnection -LocalPort <port>` 取 `OwningProcess`，再 `Get-Process -Id <pid>`（[Stack Overflow 高票答案](https://stackoverflow.com/questions/48198/how-do-i-find-out-which-process-is-listening-on-a-tcp-or-udp-port-on-windows)、[Windows OS Hub](https://woshub.com/get-nettcpconnection-windows-powershell)）。`netstat -ano` 是传统等价手段（同源）。
- → 端口走环境变量（如 `PORT`），启动前探测占用给出明确提示；Python 侧不占端口。

**6.4 日志**

- Node 侧：pino 输出 JSON、把格式化放到 worker thread，二手指南称其在官方 benchmark 中显著快于同类（[SigNoz 指南](https://signoz.io/guides/pino-logger)）。→ 选择 pino 的现实理由是**结构化 JSON 日志**（便于按 session 过滤），而非性能。
- Python 侧：标准库 `logging` + `RotatingFileHandler`（**本轮未专门抓取官方页面，标注为待核查**）。
- 统一约定（建议）：两进程都用 UTC ISO-8601 时间戳 + `session_id` / `request_id` 字段；Node 把子进程 stdout/stderr 原样落 `logs/python.log`；日志目录按天轮转、保留 N 天。

**6.5 崩溃恢复**

- 健康检查：`GET /healthz` 返回 `{ ok, pythonAlive, lastHeartbeat, packVersion, uptime }`；Node 侧记录 Python 最近一次心跳时间，超时即判定死亡。
- 重启策略：指数退避（1s → 2s → 4s，封顶 30s），连续失败 N 次后停止并写日志（避免无限重启刷屏）。
- 会话恢复：Node 持有权威会话快照（`puzzle_service` 已有 snapshot 概念），Python 重启后由 Node 重建会话；要想「重启不丢当前谜题」，需把快照落到磁盘（`data/sessions/*.json` 或 SQLite）并在恢复时校验 `seq`；否则必须在界面上明确告知「服务已重启，当前谜题重开」。

## 落地建议（含最小可行清单）

**分阶段（建议）**

- **M1 浏览器可玩（只读玩法，不做编辑器）**：定义视图模型 v1（原语白名单 + `viewModelVersion`）；Node 起 `POST /rpc` + `GET /events`(SSE) + `/healthz`；前端用原生控件渲染；键盘全可达；颜色玩法上线「符号 + 色名」替代；`prefers-reduced-motion` 生效。
- **M2 内容包**：`packs/<packId>/manifest.json`（含 `packFormat: {min,max}`）+ `levels/*.json` + `schema/*.json`；Ajv 在入库前与启动时双校验；Service Worker 缓存 + IndexedDB 存已解析内容包与编辑器草稿；导出/导入走下载兜底。
- **M3 网页编辑器**：`/editor` 路由，表格/网格 + 原生表单；快照撤销栈；预览复用同一渲染器的 play 模式；拖拽只作为增强并配键盘替代。

**最小可行部署清单（Windows 单机，10 条）**

1. **只开一个对外端口**：Node 的 HTTP 端口；Python 走 stdio，不监听。
2. **端口可配置 + 可诊断**：`PORT` 环境变量；启动前探测占用；`EADDRINUSE` 时给出可读提示并非 0 退出。
3. **进程守护**：用 NSSM（或 WinSW）把「启动 Node」装成 Windows 服务，配置开机自启与失败自动重启。
4. **子进程生命周期**：`spawn` + `stdio` 重定向到 `logs/python.log`；退出事件触发指数退避重启；关闭/重启前用 `taskkill /pid <pid> /t /f` 清树。
5. **健康检查**：`/healthz` 汇总 Node、Python 心跳、内容包版本；外部可直接 curl。
6. **日志**：Node 用 pino 写 `logs/node.log`（JSON 行）；Python 用 `logging` 轮转写 `logs/python.log`；统一 UTC 时间戳与 `session_id`。
7. **配置外置**：端口、内容包目录、日志级别、数据目录全部走环境变量或 `config.json`；不写死盘符（沿用仓库既有纪律）。
8. **状态持久化**：会话快照写 `data/sessions/`，重启按 `seq` 校验；若暂不持久化，必须在 UI 上明说「重启会重开当前谜题」。
9. **内容包校验 fail loud**：启动时校验 `packs/*`，失败即拒绝启动或明确标记该包不可用，绝不静默跳过。
10. **备份与回滚**：代码与内容包分别版本化；保留上一版本的包目录，支持按版本号回滚。

## 风险

1. **原语收敛不住**：SDUI 的经典失败模式是「每个业务需求都变成一个新组件」，最终平台退化成「远程写 UI」。缓解：原语白名单 + 未知原语 fail loud + 新原语需评审并补语义映射。
2. **测试成本上升**：Lyft / Just Eat 的经验是 SDUI 变体多、跨设备回归成本显著上升。缓解：Python 侧对每种 kind 生成视图模型并做黄金文件（golden file）快照比对。
3. **版本漂移**：旧缓存的前端遇到新原语、或旧内容包遇到新宿主。缓解：视图模型带 `viewModelVersion`、内容包带 `packFormat{min,max}`，双向判兼容，不兼容时给出明确提示。
4. **可访问性倒退**：SDUI 让客户端「不知道自己渲染的是什么」（Lyft 原话），语义标签最容易被丢。缓解：原语 → 语义 HTML 的固定映射表写进规范；颜色玩法按 §5.3 改造；把键盘/对比度/live region 纳入验收项。
5. **「颜色序列」改造可能改变难度**：符号化后题目性质可能变化，需要设计侧确认等价性，否则只是把不可访问换成了不好玩。
6. **Windows 双进程脆弱**：孤儿进程、端口占用、服务方案分散且第三方维护状态不一致（`pm2-windows-startup` 长期未更新）。缓解：单端口 + stdio 协议 + `taskkill /t` 清树 + 健康检查。
7. **离线缓存不一致**：Service Worker 可能把旧前端与新内容包混搭。缓解：内容包与前端各自的版本门，必要时按版本切换缓存名。
8. **编辑器范围膨胀**：拖拽、多选、复制粘贴、图层、撤销粒度都很吃工时。缓解：首版只做「表单 + 表格 + 快照撤销」，canvas 拖拽列为后续增强。
9. **双份真相**：编辑器与运行时各维护一套数据模型会分叉。缓解：只认一份内容包 schema，编辑器是它的另一种视图。
10. **本轮未核查项**（写报告时如实标注）：Python 侧 JSON Schema 校验器选型、axe 类自动化无障碍测试工具、Windows 任务计划程序/node-windows 的官方状态、`RotatingFileHandler` 官方页面、iframe 预览的工程规范来源 —— 均**未找到可核查来源或未核查**，落地前需补查。

## 来源清单

| 编号 | URL | 检索日期 | 支撑的结论 |
| --- | --- | --- | --- |
| S01 | https://jsonforms.io/docs/uischema | 2026-10-16 | §1 数据 schema 与 UI schema 分离、Control/Layout 元素 |
| S02 | https://jsonforms.io/docs/tutorial/custom-renderers | 2026-10-16 | §1 自定义 renderer 是官方扩展路径；dispatch 性能差异 |
| S03 | https://jsonforms.io/docs/readonly | 2026-10-16 | §3.2 `readonly` / rule ENABLE-DISABLE；`readOnly` 被当作 disabled |
| S04 | https://docs.c3.ai/docs/uiComponentLibraryReact/8.10/topic/json-component-limitations | 2026-10-16 | §1 JSON vs React 判据表；JSON 组件不追求复刻代码表达力 |
| S05 | https://github.com/MobileNativeFoundation/discussions/discussions/47 | 2026-10-16 | §1 Lyft 动机（运维灵活性/复杂度收敛）；测试成本、版本兼容、a11y 变难 |
| S06 | https://medium.com/@aubreyhaskett/server-driven-ui-what-airbnb-netflix-and-lyft-learned-building-dynamic-mobile-experiences-20e346265305 | 2026-10-16 | §1 Airbnb 的部署速度/实验收益与 payload/离线处理（二手） |
| S07 | https://dev.to/yanggmtl/schema-driven-forms-in-react-comparing-rjsf-json-forms-uniforms-formio-and-formitiva-2fg2 | 2026-10-16 | §1 各 schema 驱动表单库定位对比（二手） |
| S08 | https://form.io/json-schema-forms-formio-rjsf-jsonforms-surveyjs-compared | 2026-10-16 | §1 「渲染用轻库 / 表单即基础设施」的取舍（二手，厂商视角） |
| S09 | https://surveyjs.io/stay-updated/blog/best-json-form-editor | 2026-10-16 | §1 RJSF 为 React 生态最广泛采用（二手，厂商视角） |
| S10 | https://nodejs.org/learn/getting-started/websocket | 2026-10-16 | §2 内置 WS 客户端 v22.4.0 stable；无内置 WS 服务端 |
| S11 | https://blog.risingstack.com/nodejs-22<br>http://nodesource.com/blog/nodejs-22-features | 2026-10-16 | §2 Node 22 内置 WebSocket 稳定（二手）；§2 Node 22 特性（二手） |
| S12 | https://fa.javascript.info/server-sent-events | 2026-10-16 | §2 SSE 自动重连、`retry`、`Last-Event-ID`、`readyState` |
| S13 | https://socket.io/docs/v4/connection-state-recovery<br>https://socket.io/docs/v4/server-options | 2026-10-16 | §2 v4.6.0 连接状态恢复；`maxDisconnectionDuration`；§2 `connectionStateRecovery` 选项细节 |
| S14 | https://ably.com/blog/websockets-vs-sse | 2026-10-16 | §2 SSE 走 HTTP 不易被拦；WS 需预算回退路径（二手，厂商） |
| S15 | https://designgurus.substack.com/p/websockets-vs-server-sent-events<br>https://rxdb.info/articles/websockets-sse-polling-webrtc-webtransport.html | 2026-10-16 | §2 「不要默认上 WebSocket」的取舍框架（二手）；§2 三种传输对比；SSE 与 WS 都依赖在线连接（二手） |
| S16 | https://portalzine.de/sses-glorious-comeback-why-2025-is-the-year-of-server-sent-events | 2026-10-16 | §2 HTTP/1.1 每域 6 连接限制、HTTP/2 缓解（二手） |
| S17 | https://dev.to/abhivyaktii/understanding-server-sent-events-sse-and-why-http2-matters-1cj7 | 2026-10-16 | §2 SSE 连接数限制与 HTTP/2 多路复用（二手） |
| S18 | https://ably.com/blog/websocket-libraries-for-node | 2026-10-16 | §2 `ws` 库用法与定位（二手） |
| S19 | https://doc.mapeditor.org/en/stable/reference/json-map-format | 2026-10-16 | §3.1 Tiled JSON 格式与字段（官方） |
| S20 | https://doc.mapeditor.org/en/stable/manual/export-generic | 2026-10-16 | §3.1 JSON/CSV/Lua 导出与 `--export-map` CLI（官方） |
| S21 | https://ldtk.io | 2026-10-16 | §3.1 LDtk：MIT、文档化 JSON、崩溃备份（官方站） |
| S22 | https://github.com/blurymind/tilemap-editor | 2026-10-16 | §3.1 零依赖网页瓦片地图编辑器、自带 manifest 与 sw.js |
| S23 | https://konvajs.org/docs/about.html | 2026-10-16 | §3.1 Konva 能力与 MIT 许可（官方） |
| S24 | https://maxzsol.com/top-5-open-source-draggable-grid-layout-ui-libraries-for-the-web | 2026-10-16 | §3.1 拖拽/吸附网格库综述（二手） |
| S25 | https://excalidraw-excalidraw.mintlify.app/quickstart<br>https://www.npmjs.com/package/@excalidraw/excalidraw-next | 2026-10-16 | §3.2 `viewModeEnabled` 只读开关（官方文档镜像）；§3.2 `viewModeEnabled` prop 定义 |
| S26 | https://dev.to/nologintools/excalidraw-free-online-whiteboard-no-login-required-25j5<br>https://meetrix.io/blogs/open-source-whiteboard-tools | 2026-10-16 | §3.1 `.excalidraw` 为纯 JSON（二手）；§3.1 白板工具开放格式与许可现状（二手） |
| S27 | https://pixlab.io/tilemap-2d-level-editor | 2026-10-16 | §3.1 浏览器瓦片编辑器的交互参考（商业工具） |
| S28 | https://docs.unity3d.com/Packages/com.unity.cinemachine@2.3/manual/CinemachineSavingDuringPlay.html | 2026-10-16 | §3.2 Unity 默认不保存 Play Mode 场景改动（官方） |
| S29 | https://docs.godotengine.org/en/stable/getting_started/step_by_step/nodes_and_scenes.html | 2026-10-16 | §3.2 Godot 编辑器内运行场景（F5/F8）（官方） |
| S30 | https://github.com/godotengine/godot-proposals/issues/9142 | 2026-10-16 | §3.2 编辑器内运行需先保存原状态 |
| S31 | https://www.npbee.me/posts/command-based-undo | 2026-10-16 | §3.3 命令模式 vs 快照（memento）取舍（二手） |
| S32 | https://discussions.unity.com/t/approach-to-creating-an-undo-redo-system/946942 | 2026-10-16 | §3.3 快照法易实现、命令法支持宏录制（社区讨论） |
| S33 | https://docs.yjs.dev/getting-started/a-collaborative-editor<br>https://discuss.prosemirror.net/t/offline-peer-to-peer-collaborative-editing-using-yjs/2488 | 2026-10-16 | §3.3 Yjs UndoManager、`trackedOrigins`（官方）；§3.3 y-prosemirror 撤销/重做插件用法（社区） |
| S34 | https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker | 2026-10-16 | §3.4 保存文件选择器 API（官方文档） |
| S35 | https://www.testmuai.com/learning-hub/file-system-access-api-browser-support | 2026-10-16 | §3.4 Firefox/Safari 不支持本地磁盘选择器（二手） |
| S36 | https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control<br>https://csswizardry.com/2019/03/cache-control-for-civilians | 2026-10-16 | §4 指纹 URL + `max-age=31536000, immutable`；§4 指纹优于查询串的缓存破坏（二手） |
| S37 | https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Subresource_Integrity | 2026-10-16 | §4 SRI 的 `integrity`+`crossorigin`、`Integrity-Policy` |
| S38 | https://web.dev/articles/service-worker-caching-and-http-caching | 2026-10-16 | §4 stale-while-revalidate / cache-first / cache-only 适用场景（官方） |
| S39 | https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API | 2026-10-16 | §4 IndexedDB 存结构化大数据、同源限制 |
| S40 | https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable | 2026-10-16 | §4 PWA 可安装条件与 manifest 必需成员 |
| S41 | https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/What_is_a_progressive_web_app | 2026-10-16 | §4 PWA 组成与 Service Worker 可选性 |
| S42 | https://json-schema.org/specification<br>https://json-schema.org/draft/2020-12 | 2026-10-16 | §4 当前版本 2020-12、上一版 2019-09；§4 2020-12 变更要点 |
| S43 | https://ajv.js.org<br>https://github.com/ajv-validator/ajv | 2026-10-16 | §4 Ajv 支持的 draft 范围与 JTD；§4 Ajv 仓库与文档入口 |
| S44 | https://minecraft.wiki/w/Pack_format<br>https://www.minecraftmaps.com/tools/pack-mcmeta | 2026-10-16 | §4 `pack.mcmeta` 的 `min_format`/`max_format` 版本门先例；§4 格式号不匹配仅警告、数据包/资源包格式号独立（二手） |
| S45 | https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ | 2026-10-16 | §5.1 WCAG 2.2 成为 Recommendation 的日期、9 条新 SC 与等级、移除 4.1.1（**本次直接抓取**） |
| S46 | https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html | 2026-10-16 | §5.3 SC 1.4.1 不以颜色为唯一手段 |
| S47 | https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions | 2026-10-16 | §5.2 polite/assertive 用法与滥用警告 |
| S48 | https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/alert_role | 2026-10-16 | §5.2 先渲染容器再更新内容才会播报 |
| S49 | https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/grid_role | 2026-10-16 | §5.2 grid 角色与方向键导航 |
| S50 | https://www.w3.org/WAI/ARIA/apg/patterns/grid | 2026-10-16 | §5.2 APG Grid 模式的键盘交互与数据/布局网格差异 |
| S51 | https://github.com/w3c/aria-practices/issues/3409 | 2026-10-16 | §5.2 PageUp/PageDown/Home/End 劫持浏览器导航的争议 |
| S52 | https://sarahmhigley.com/writing/grids-part2 | 2026-10-16 | §5.2 CSS 覆盖表格语义后必须显式补 ARIA 角色 |
| S53 | https://caniplaythat.com/2020/01/29/color-blindness-accessibility-guide | 2026-10-16 | §5.3 用图标/形状/动画辅助颜色信息、色盲模式（二手） |
| S54 | https://www.forallwe.com/en/post/color-blindness-video-games-accessibility-filters | 2026-10-16 | §5.3 状态/稀有度/地图标记的非颜色重复编码（二手） |
| S55 | https://www.getstark.co/wcag-explained/perceivable/distinguishable/contrast-minimum<br>https://www.allaccessible.org/blog/color-contrast-accessibility-wcag-guide-2025 | 2026-10-16 | §5.3 1.4.3 / 1.4.6 / 1.4.11 对比度数字（二手）；§5.3 对比度与「不以颜色为唯一手段」清单（二手） |
| S56 | https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion | 2026-10-16 | §5.4 `prefers-reduced-motion` 语义与系统设置入口 |
| S57 | https://www.smashingmagazine.com/2021/10/respecting-users-motion-preferences | 2026-10-16 | §5.4 尊重动效偏好（二手） |
| S58 | https://www.youtube.com/watch?v=pdjtJHbQHUo | 2026-10-16 | §5.2 Upheaval：键盘导航 + TTS 的可访问文字冒险实例 |
| S59 | https://knightsofthebraille.com/accessibility | 2026-10-16 | §5.2 屏幕阅读器可玩游戏清单（含 AI Dungeon） |
| S60 | https://nodejs.org/api/child_process.html | 2026-10-16 | §6.1 `spawn` / `stdio` / `detached` 官方语义 |
| S61 | https://github.com/nodejs/help/issues/4050 | 2026-10-16 | §6.1 Node 不支持按名杀进程；`taskkill /T` 杀树 |
| S62 | https://community.adobe.com/questions-729/killing-child-process-in-cep-node-js-1379943 | 2026-10-16 | §6.1 Windows 上杀子进程树的实操（二手） |
| S63 | https://github.com/winsw/winsw<br>https://www.nuget.org/packages/WinSW | 2026-10-16 | §6.2 WinSW 3.x/2.x 状态、MIT、日志与配置（官方仓库）；§6.2 WinSW 功能与包信息 |
| S64 | https://www.mssqltips.com/sqlservertip/7325/how-to-run-a-python-script-windows-service-nssm<br>https://joe-thomas.medium.com/running-a-python-script-as-a-windows-service-a-guide-a32abbc90172 | 2026-10-16 | §6.2 NSSM 把 Python 脚本装成服务、日志入事件日志（二手）；§6.2 NSSM 安装步骤（二手） |
| S65 | https://pm2.keymetrics.io/docs/usage/startup | 2026-10-16 | §6.2 PM2 `startup` 支持的 init 系统不含 Windows（官方） |
| S66 | https://medium.com/@gzthomasliang/run-pm2-as-service-on-windows-server-in-modern-way-286b9f4b8228 | 2026-10-16 | §6.2 `pm2-windows-startup` 依赖登录、2015 年后未更新（二手） |
| S67 | https://blog.openreplay.com/fix-error-eaddrinuse-nodejs<br>https://dev.to/antonrosh/address-already-in-use-a-simple-guide-to-freeing-up-ports-54g5 | 2026-10-16 | §6.3 `EADDRINUSE` 捕获与处理（二手）；§6.3 端口占用的定位思路（二手） |
| S68 | https://stackoverflow.com/questions/48198/how-do-i-find-out-which-process-is-listening-on-a-tcp-or-udp-port-on-windows | 2026-10-16 | §6.3 `Get-NetTCPConnection` + `Get-Process` 排查 |
| S69 | https://woshub.com/get-nettcpconnection-windows-powershell | 2026-10-16 | §6.3 `Get-NetTCPConnection` / `Get-NetUDPEndpoint` 用法（二手） |
| S70 | https://signoz.io/guides/pino-logger | 2026-10-16 | §6.4 pino 的结构化日志与 worker thread（二手，含官方 benchmark 转述） |
