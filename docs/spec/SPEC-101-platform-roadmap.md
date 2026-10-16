# 平台化路线图（谜题即插件 → 内容平台）

> **编号** SPEC-101 ｜ **效力** 规范 ｜ **状态** 生效
> **生效** 2026-10-16 ｜ **最后修订** 2026-10-16 ｜ **适用面** 本仓的架构演进、插件边界、内容与渲染分层
> **时点** 结论与来源检索于 2026-10-16 ｜ **承载体** 无机械门禁（路线图是判断，不是可判定的规则）；其中已实现的部分由 `tests/` 与 `npm run smoke` 守着
> **引用格式** SPEC-101 §阶段 M1

本规范把「朝更平台化的方向延伸」写成可执行的分阶段计划。每条判断都给出依据：
要么是本仓的**实测**（标注「实测」），要么是**联网调研**（在
[调研卷](../records/platform-research-2026-10/README.md) 有带 URL 与检索日期的完整报告）。
凡未找到可核查来源的，写「未找到可核查来源」，不编造。

---

## 一、现状（实测 2026-10-16）

| 事实 | 证据 |
| --- | --- |
| 14 种谜题种类，逻辑与 pygame 界面原先耦合在 1584 行 `ui.py` 里：事件与绘制两条硬编码 14 路 `isinstance` 链，注册表两份 | `goto` 之前的代码；现由 `puzzle_service/registry.py` 取代 |
| 两个版本各自导出同名顶层模块（`engine`/`gameplay_pool`/...），同进程只能加载一个 | `shared/paths.py` 的注释与 `bootstrap_import_path(build)` 的单版本约束 |
| 6 种谜题的 `check_answer` 忽略入参、只读自身状态 | `puzzle_service/registry.py` 的 `answered_by="action"` 与 `tests/test_service.py` 的断言 |
| 4 种谜题对类型不对的入参抛 `ValueError`/`TypeError` | `docs/records/text-adventure-boot-crash-fix_2026-10-16.md` 的输入健壮性表 |
| 谜底不会进入视图模型 | `tests/test_views.py::test_views_never_contain_the_solution` |

## 二、目标架构（已落地部分）

```
浏览器 (public/)                     渲染层：把视图模型映射到语义 HTML，一个客户端渲染全部 14 种
   │  POST 动作 + SSE 快照
Node Cordis 宿主 (src/)              编排层：插件装载、生命周期、HTTP/SSE；不含谜题逻辑
   │  JSON-RPC 2.0 over stdio (src/core/bridge.mjs ↔ python/rpc_server.py)
Python 谜题进程 (puzzle_service/)    领域层：状态、规则、计分、视图模型——唯一真相源
   └─ pygame 客户端 (text_adventure*_zh/ui.py)  共存的旧渲染层，未删除
```

三层职责的判据来自调研结论：**被多个消费者共享且必须一致的东西才进内核**，
其余一律做成插件或数据（见 `records/platform-research-2026-10/02-platform-architecture.md`）。

## 三、分阶段路线

### 阶段 M0 · 可玩性修复（已完成 2026-10-16）
修掉两个版本都启动失败的问题，补上共享层、无头冒烟测试、可复现的环境重建脚本。

### 阶段 M1 · 浏览器可玩（已完成 2026-10-16）
- 视图模型 + 原语白名单（10 个原语：`text/field/options/list/clues/grid/sequence/keyboard/colors/board`），
  未知原语**响亮失败**而不是渲染空白页（实测：`npm run smoke` 的「unknown primitive」一项）。
- 传输选 **POST 动作 + SSE 快照**：回合制不需要长连接；SSE 自带断线重连与 `Last-Event-ID`，
  而 WebSocket 协议层不含恢复，Node 内置 WebSocket 只有客户端、没有服务端。
  来源：[Node.js WebSocket 现状](https://nodejs.org/learn/getting-started/websocket)（检索 2026-10-16）。
- 可访问性：纯颜色玩法同时给符号与文字（WCAG 2.2 **SC 1.4.1** 要求不能只靠颜色传达信息），
  每个鼠标操作都有键盘通路。来源：[What's New in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)（检索 2026-10-16）。
  注：二手博客常把 2.4.13 Focus Appearance 误标为 AA，实为 AAA ——按 W3C 原文核对。

### 阶段 M2 · 内容包（下一步）
把谜题内容从代码里抽出来，才能谈「内容供给」和「难度标定」。
- 数据格式：`manifest.json` 带**双版本字段**（`format_version` + `min_engine_version`），
  先例是 Minecraft 的 `pack.mcmeta`；正文用 JSON Schema（2020-12）校验，迁移用幂等注册表。
- 内容包**不得包含可执行代码**（不引入 Python 表达式、不引入 `eval`），这与「进程边界才是唯一真边界」的
  调研结论一致：`node:vm` 官方明确不是安全机制，
  来源：[Node.js VM](https://nodejs.org/api/vm.html)、[Node.js Permissions](https://nodejs.org/api/permissions.html)（检索 2026-10-16）。
- 首发范围建议：先把 5 种**纯内容型**谜题（谜语、填字、单词阶梯、字母重排、图案规律）数据化，
  它们是「内容质量决定体验」的那一类，也是社区投稿最可能接得住的形态。

### 阶段 M3 · 网页编辑器
编辑态用**只读开关**而不是第二套编辑器（可核查先例：Excalidraw 的 `viewModeEnabled`、
JSON Forms 的 `readonly`）；撤销重做用快照栈即可，协同编辑（Yjs/CRDT）在这一阶段是过度设计。
调研结论标注：**未找到**文字解谜类开源关卡编辑器可作直接参照。

### 阶段 M4 · 每日节奏与分享（留存优先于变现）
竞品扫描的结论是平台卖的是「每日节奏 + streak + 无剧透分享 + 档案」，不是谜题种类数量。
- 每日一题**不需要后端**：按本地日期从预打乱列表取题（可核查先例：Wordle 的做法，
  来源：[Hacker News 讨论](https://news.ycombinator.com/item?id=30435522)，检索 2026-10-16）。
- 分享卡片只输出**结构信息**（猜测图样，不含答案），剪贴板即可，无需账号。
- 变现排在留存验证之后；调研**未找到**可核查的 ARPDAU/eCPM 数据，不要据此编数字。

### 阶段 M5 · 双实现收敛（结构债）
`text_adventure/` 与 `text_adventure_zh/` 是两份并行实现，同构模块已经漂移。
收敛为「一份实现 + 语言资源」是内容包、快照、多语言的前置条件；迁移时用
`puzzle_service` 的 kind 清单做对照，确保两侧种类集合一致（当前各 14 种，实测）。

## 四、红线

1. **不可信插件绝不同进程**：进程边界是唯一可信边界。
2. **内容包不含可执行代码**；归档条目名不可信（防 Zip Slip），解压前校验路径。
3. **跨进程调用必须带超时与字节上限**（桥已实现：每请求超时、请求体上限 1 MB）。
4. **谜底不进视图模型**（已有测试守着）。
5. **谜题 id 唯一**；同名不同类必须拒绝注册（已有测试守着）。
6. **不假绿**：视图原语未登记、插件未装载、服务未 ready，都必须看得见地失败。

## 五、修订记录

| 日期 | 变更 | 依据 |
| --- | --- | --- |
| 2026-10-16 | 建立本规范：M0–M1 标为已完成，M2–M5 定方向与红线 | 用户三项指令（修复 / 引入 Cordis / 平台化调研）；四份联网调研报告 |
