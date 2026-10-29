# Cordis 化与 Web 层落地（第三、四项指令的实测记录）

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** 引入 Cordis（宿主 + 桥）与浏览器可玩层的落地过程
> **证据** 全部为当轮实测输出；复现命令见文末

## 一、做了什么

三层职责切开，谜题逻辑仍然是 Python 唯一真相源：

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 领域层 | `puzzle_service/` + `python/rpc_server.py` | 状态、规则、计分、视图模型 |
| 编排层 | `src/`（Cordis 宿主 + 插件） | 插件装载、生命周期、HTTP 与 SSE |
| 渲染层 | `public/`（浏览器）、`text_adventure*_zh/ui.py`（pygame，保留） | 把视图模型映射成界面 |

桥：JSON-RPC 2.0 over stdio，Python 侧零第三方依赖。宿主侧 `src/core/bridge.mjs`。

## 二、构建过程中被**实测**抓到的问题（不是推测）

这些问题全部在开发过程中真实出现并被修掉，这也是为什么冒烟测试用真子进程、真 HTTP：

| # | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| 1 | `bootHost` 后 `ctx.web` 不存在，宿主却在日志里报「ready」 | 插件是被 `loader.create` 装载了，但我在插件里写的 `start()` **永远不会被 Cordis 调用**：`Service` 的初始化钩子是构造期执行、`[Service.init]` 返回清理函数，没有异步 `start()` 这一步 | 改成构造期启动 + `ready` promise；`bootHost` 等 `ctx.puzzles.ready` 与 `ctx.web.ready` 都就绪才返回；不再有 `ctx.web` 时**响亮失败** |
| 2 | 接口全 500：`cannot get property "puzzles" without inject` | Cordis 在运行期强制依赖声明——读别的服务必须先 `static inject` | `WebService` 加 `static inject = ['puzzles']`；契约测试断言这行存在 |
| 3 | `stopHost` 报 `entry.options` 未定义 | 该版本 loader 的 `tree.entries()` 迭代出的不是 `[key, value]` 对，而是条目对象 | 按对象处理并跳过无 `fiber` 的条目；关停日志改为打印「disposed N entries」 |
| 4 | 两个版本在同一进程里互相遮蔽 | `text_adventure/` 与 `text_adventure_zh/` 各自导出同名顶层模块 `gameplay_pool`/`engine` | `bootstrap_import_path(build)` 一次只放行一个版本；冒烟测试**分进程**跑两版 |
| 5 | 字体「加载成功」但可能是方块 | `SysFont` 会静默回退到默认字体（pygame issue #3025） | 新增 `supports_cjk()`：用渲染度量证实字形真的存在，验证不了就红并在 stderr 出声 |
| 6 | 14 种谜题里有 6 种 `check_answer` 忽略入参 | 它们的状态自己就是判据（棋盘/配对数/win 标志/字母全亮/阶段标志） | 注册表新增 `answered_by="action"`；这类谜题在动作达成时计分，且**同一局只计一次**（测试守着） |

## 三、验证（当轮实测）

```
.venv/Scripts/python.exe -m pytest tests -q     -> 58 passed
node src/smoke.mjs                              -> SMOKE PASSED（11 项）
```

宿主冒烟测试的 11 项包含：14 种谜题的视图**全部通过原语白名单校验**、未知原语被拒、
坏答案返回结构化错误、中文提示跨进程不损坏、SSE 能收到快照、关停后端口真的释放。

## 四、未做（有意）

- **没有**把 pygame 版删掉或改写成 Web：两版共存，pygame 版仍是可玩的桌面客户端。
- **没有**引入 Python 插件框架：调研结论是 `pluggy`/`stevedore`/entry-points 只解决发现与钩子，
  不解决依赖声明与回滚，自己造等于重造 Cordis 的回滚正确性；生命周期放在协议层更划算。
- **没有**做内容包、编辑器、每日一题：属于 SPEC-101 的 M2–M4，需要单独排期。

## 五、复现

```
.venv/Scripts/python.exe -m pytest tests -q
node src/smoke.mjs
node src/boot.mjs          # 打开它打印的地址即可在浏览器里玩
```
