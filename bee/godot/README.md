# BeeIdleRPG — Godot 前端脚手架（M2 / Phase C）

> ⚠️ **未验证（UNVERIFIED）**：本目录为脚手架，编写时本机**未安装 Godot**，
> GDScript 代码未经实际运行。请在 Godot 4.x 中打开并实测后再并入主流程。

## 架构

```
┌──────────────┐   TCP JSON-line    ┌──────────────────────────┐
│  Godot 前端   │  (127.0.0.1:18765) │  sim_core 桥接服务 (Python) │
│  game.gd     │ ─── init/step/ ──▶ │  python -m               │
│  sim_bridge  │ ◀── state/quit ─── │    src.sim_core.bridge    │
└──────────────┘                    └──────────────────────────┘
                                            │ 驱动
                                            ▼
                                     SimCore（确定性模拟内核）
```

- 模拟内核 `SimCore` 完全在 Python 侧运行（headless，无 GUI 依赖）。
- Godot 仅作渲染/输入前端，通过 `sim_bridge.gd` 以子进程 IPC 驱动内核。
- 证明「UI 与模拟彻底解耦」：内核可在独立进程中复现黄金基准（见 `tests/test_sim_bridge.py`）。

## 运行步骤

1. 在 `bee/` 根目录启动桥接服务（保持运行）：
   ```bash
   python -m src.sim_core.bridge --port 18765
   ```
   启动后会向 stdout 打印 `READY 18765`。

2. 用 Godot 4.x 打开本目录 `godot/` 作为项目。

3. 按 F5 运行。UI 应显示 idle RPG 日志与状态（等级/金币/区域/时间/击杀/死亡），实时推进。

4. 退出 Godot 项目时，`game.gd._exit_tree` 会发送 `quit` 关闭桥接服务。

## 协议速查

| 客户端→服务端 | 说明 |
| --- | --- |
| `{"cmd":"init","seed":12345,"save_path":""}` | 固定种子确定性新建 |
| `{"cmd":"step","dt":0.05}` | 推进一帧 |
| `{"cmd":"state"}` | 取回 `{log_messages, fingerprint}` |
| `{"cmd":"new_game","name":..,"race":..,"char_class":..,"seed":?}` | 角色创建后重开 |
| `{"cmd":"quit"}` | 优雅退出 |

服务端响应：`{"ok":true,...}` 或 `{"ok":false,"error":"..."}`。
`race`/`char_class` 为字符串 ID（如 `"WARRIOR"`、`"HUMAN"`，大小写不敏感），由桥接服务解析为枚举。

## 注意

- `sim_bridge.gd` 的 `PORT` 必须与启动桥接服务时的 `--port` 一致（默认 18765）。
- 端口固定便于 Godot 连接；若需多开，改 `--port` 与 `PORT` 常量即可。
- 接入角色创建 UI：Godot 侧收集 name/race/class 后调用 `_bridge.new_game(...)`。

## Phase C 验收清单（怎样算打通）

> 本目录编写时本机**无 Godot**，下列为标准验收项。逐项满足即判 **PASS**，可进 Gate 2。

### 前置
- 本机安装 Godot 4.x（godotengine.org 下载单 exe 即可）。建议 4.3+；装更高版本（4.4/4.5…）打开本项目时编辑器会提示「项目配置来自旧版本」，点「升级」即可，`config_version=5` 向后兼容，无害。

### 步骤
1. 在 `bee/` 根目录启动桥接服务（**先起**，保持运行）：
   ```bash
   python -m src.sim_core.bridge --port 18765
   ```
2. 用 Godot 打开 `godot/` 作为项目，按 **F5** 运行 `game.tscn`。

### 预期（PASS 判定）
1. bridge 终端首行打印 `READY 18765`。
2. Godot 运行后 `Stats` 从「等待连接...」变为实时刷新：
   `Lv N | 金币 N | 区域 N | 时间 N.N | 击杀 N | 死亡 N`。
3. `LogView` 出现 idle RPG 日志文本并持续滚动（约每 0.05s 一帧）。
4. 退出 Godot 项目 → bridge 终端收到 `quit` 并退出（或手动 Ctrl-C 终止）。

### 设计预期澄清
- Godot 端**不要求**逐字节等于 `golden_baseline.json`：字节级黄金一致性由 `tests/test_sim_bridge.py`（子进程 Python 跑）守护。Godot 验收只验证「能连 / 能驱动 / 能渲染」。

### 排错
- **连接失败（err != OK）**：确认 bridge 先启动、端口 18765 一致、localhost 防火墙未拦截（127.0.0.1 通常免拦截）。
- **中文乱码**：bridge 以 `ensure_ascii=False` 发 UTF-8；Godot `StreamPeerTCP.get_string()` 默认按 UTF-8 解码。若乱码，检查 Godot 项目文本编码设置。
- **bridge 单连接**：`serve()` 仅 `listen(1)`，同一时刻只接一个 Godot 实例；重跑需先重启 bridge。
- **升级提示**：4.3+ 打开旧配置点「升级」无害，勿选「取消」。

