# DOOM 风格伪 3D 光线投射游戏

一个用 Python + **pygame-ce** 实现的 Wolfenstein / DOOM 风格伪 3D 光线投射（raycasting）游戏。核心是一条 DDA 网格光线投射管线，墙体由程序化噪声纹理渲染，并增量加入了**敌人 / 拾取物**、**surfarray 提速的纹理生成**、**关卡编辑器**与本项目说明文档。

---

## 简介

- 经典 Lodev 式 DDA 光线投射，单列四种 `RenderMode`：`WIREFRAME` / `SOLID` / `TEXTURED` / `DOOM_STYLE`。
- 伪 3D 音效：用「物理声呐（PhysicsRaySonar）」把玩家位移映射为多普勒 / 运动模糊调制（`DISABLE_AUDIO=1` 时安全降级，无声卡也不崩）。
- 增量功能：简单追逐 AI 敌人、生命 / 分数拾取物、HUD 生命条与分数、游戏内 GUI 关卡编辑器、JSON + ASCII 双格式关卡。

---

## 环境依赖与安装

需要 Python 3.10+。推荐依赖：

```bash
pip install pygame-ce numpy sounddevice
```

| 依赖 | 用途 |
|---|---|
| `pygame-ce` | 渲染与输入（主理人环境已装；代码回退 `import pygame` 兼容旧版 `pygame`） |
| `numpy` | 纹理噪声向量化（`surfarray` 提速） |
| `sounddevice` | 伪 3D 音频（缺失 / `DISABLE_AUDIO=1` 时自动降级） |

> 注：代码统一用
> ```python
> try:
>     import pygame_ce as pygame
> except ImportError:
>     import pygame
> ```
> 以便 `pygame-ce` 与旧版 `pygame` 均可运行。

---

## 运行方式

```bash
# 正常游玩
python main.py

# CI / 沙箱无显示自测：跑 N 帧后干净退出
python main.py --headless 30

# 指定关卡文件启动（JSON 或 ASCII）
python main.py --map maps/level_01.json --headless 20
python main.py --map maps/level_01.json

# 关闭音频（无声音设备环境 / 静默测试）
DISABLE_AUDIO=1 python main.py --headless 30

# 环境变量组合（Windows 示例）
set SDL_VIDEODRIVER=dummy
set DISABLE_AUDIO=1
python main.py --headless 30
```

- `--headless N`：无窗口运行 `N` 帧后退出，并跑 `_headless_validate`（覆盖 4 种渲染模式、实体渲染路径、声呐物理校验）。返回码 0 表示通过；校验失败返回码 1。
- `DISABLE_AUDIO=1`：跳过音频线程，适合服务器 / CI。
- `--map <path>`：从关卡文件重建网格与实体；缺省则走随机迷宫（`generate_maze`）。文件缺失时保留迷宫并打印 warning，不崩溃。

---

## 操作说明

| 按键 | 作用 |
|---|---|
| `W` / `S` | 前进 / 后退 |
| `A` / `D` | 左移 / 右移（strafe） |
| `←` / `→` | 左转 / 右转 |
| `空格` | 攻击：沿视线方向即时射线（hitscan），限射程、打墙即止、带冷却 |
| `1`–`4` | 切换 `RenderMode`（WIREFRAME / SOLID / TEXTURED / DOOM_STYLE） |
| `E` | 进入 / 退出游戏内关卡编辑器（游玩 ↔ 编辑；headless 下不触发） |
| `R` | 重开**当前关**（hp 回满、score 回退到进本关时的值；胜利画面按 `R` 从第 1 关重开） |
| `任意键` | "LEVEL CLEAR" 过场中：跳过过场立即进入下一关 |
| `ESC` | 游玩模式：退出程序；编辑模式：返回游玩并按当前编辑重建世界 |
| `Ctrl+S` / `Ctrl+O` | 编辑器内：保存 / 加载关卡（JSON） |
| `Ctrl+Z` | 编辑器内：撤销上一步编辑（多步，最多 50 步） |

**编辑器内（按 `E` 进入后）：**

| 输入 | 作用 |
|---|---|
| 数字键 `1`–`9` | 选择笔刷：砖墙 / 石墙 / 金属墙 / 木墙 / 玩家起点 / 敌人 / 生命 / 分数 / 橡皮 |
| 鼠标左键 | 用当前笔刷在格子上放置 |
| 鼠标右键 | 擦除该格（墙 + 实体） |
| `Ctrl+Z` | 撤销（无效操作不占撤销步；加载新文件后撤销栈清空） |

---

## 游戏特性

- **四种渲染模式**：线框、纯色距离色、纹理、DOOM 风格（含速度与多普勒混合的运动模糊）。
- **敌人 AI（追逐 + 远程）**：玩家进入「视线无遮挡 + 距离 ≤ 感知范围」时追击；逐轴网格碰撞滑动，不穿墙；接触造成伤害且带冷却。追击中且距离 ≤ 攻击射程、LOS 通、冷却就绪时朝玩家发射**直线能量弹**（亮橙色，命中扣血、打墙 / 超程消失，可侧移躲避）。
- **玩家攻击**：空格键沿视线即时射线攻击（hitscan），隔墙无效、带 0.4s 冷却——用它清空敌人推进关卡。
- **多关卡递进**：`LEVEL_SEQUENCE` 三关顺序推进（level_01 → 02 → 03，难度递增）；清空当前关全部敌人即过关，屏幕显示 "LEVEL CLEAR"（1.5s，任意键跳过）；通过最后一关显示 **YOU WIN**。score 跨关累计；hp 带入下一关但进关时至少回到 50%。`--map` 指定单关时清空敌人即直接胜利。
- **拾取物**：生命（回血）/ 分数（加分）两类，靠近即拾取后消失。
- **HUD**：小地图 + 信息面板 + `LEVEL n/total` 关卡横幅；实体在 3D 视图以色块（敌人红 / 生命绿 / 分数黄 / 弹体橙）叠加显示，小地图同步显示弹体橙点。
- **伪 3D 音频**：基于玩家速度的物理声呐，无设备安全降级。
- **关卡编辑器**：游戏内 GUI 编辑墙与实体，保存为与 `--map` 相同的 JSON 格式（闭环）；支持 `Ctrl+Z` 多步撤销（栈深 50，超限丢最旧）。
- **surfarray 提速**：墙体纹理由逐像素 `set_at` 改为 numpy + `pygame.surfarray` 向量化，确定性不变、输出仍为 64×64、仍为 4 张。

---

## 关卡文件格式

关卡有 **JSON（权威、无损）** 与 **ASCII（人类可读中间格式）** 两种表示，二者可互转（`json_to_ascii` / `ascii_to_json`）。

### JSON（权威格式）

```json
{
  "version": 1,
  "width": 24,
  "height": 24,
  "cells": [[0, 1, 2, 3, 4, 0], ["..."]],
  "player_start": { "x": 1.5, "y": 1.5, "angle": 0.0 },
  "enemies": [
    { "x": 5.5, "y": 5.5, "hp": 30, "damage": 10, "speed": 0.06, "type": "basic" }
  ],
  "pickups": [
    { "x": 8.5, "y": 8.5, "kind": "health", "amount": 25 },
    { "x": 12.5, "y": 12.5, "kind": "score", "amount": 100 }
  ]
}
```

- 整数 ↔ `TextureType`：`{0: 空, 1: BRICK, 2: STONE, 3: METAL, 4: WOOD}`。
- `cells[gy][gx]` 为整数纹理编号；`player_start.x/y` 为格中心浮点（如 `gx + 0.5`）。
- `enemies[].hp/damage/speed/type` 缺省用 `config` 常量；`pickups[].kind` 为 `health` / `score`，`amount` 缺省用常量。

### ASCII（可读中间格式）

| 字符 | 含义 | 映射到 JSON |
|---|---|---|
| ` ` 或 `.` | 空地 | `cells=0` |
| `#` | 墙（默认 STONE） | `cells=2` |
| `B` / `S` / `M` / `W` | 砖 / 石 / 金属 / 木墙 | `1` / `2` / `3` / `4` |
| `P` | 玩家起点 | `player_start`（取该格中心） |
| `E` | 敌人出生点 | `enemies`（hp / type 用默认） |
| `H` / `$` | 生命 / 分数拾取 | `pickups{kind: health|score}` |

> ASCII 为单字符 / 格，无法表达敌人 hp / 拾取 amount 等元数据；导出为 ASCII 时这些字段用 `config` 默认值补全。**JSON 为往返无损的权威格式**，ASCII 仅保证结构（墙 / 实体位置）稳定。

---

## 架构概览（各模块职责）

| 模块 | 职责 |
|---|---|
| `doom_game/__init__.py` | 包入口，版本号 |
| `doom_game/config.py` | 所有屏幕 / 玩法 / 音频可调常量（含敌人、拾取、地图路径） |
| `doom_game/core/types.py` | 基础共享类型：`TextureType` / `RenderMode` / `Vector2` / `Wall`（全项目唯一来源） |
| `doom_game/core/entities.py` | 基础实体 `Enemy` / `Pickup` / `PickupType` / `EnemyType`（只依赖 `core`） |
| `doom_game/core/player.py` | 玩家实体（位置 / 朝向 / 速度 / 生命 / 分数） |
| `doom_game/core/world_map.py` | 网格地图，O(1) 碰撞与 `line_of_sight` |
| `doom_game/render/renderer.py` | DDA 光线投射渲染器 + 敌人 / 拾取 billboard 叠加（`render_sprites`） |
| `doom_game/render/noise.py` | 程序化墙体纹理（numpy + surfarray 向量化） |
| `doom_game/render/doppler.py` | 距离 → 颜色 / 多普勒混合 |
| `doom_game/audio/audio_system.py` | 动态音频系统（headless 安全，可禁用） |
| `doom_game/audio/sonar.py` | 物理声呐：位移 → 信号，用于伪 3D 音效 |
| `doom_game/audio/karplus_strong.py` | 弦合成（拨弦音） |
| `doom_game/world/game_world.py` | 顶层编排：地图 / 玩家 / 渲染 / 音频 / HUD / 实体；`update` / `render` 契约 |
| `doom_game/world/hud.py` | HUD：小地图、信息面板、音频诊断 |
| `doom_game/world/level_io.py` | 关卡 I/O：`LevelData` + `load_map` / `save_map` / `ascii_to_json` / `json_to_ascii` + `build_enemies` / `build_pickups` |
| `doom_game/editor/level_editor.py` | 游戏内关卡编辑器（GUI，读写同格式） |
| `main.py` | 入口：参数解析、`--map` / `E` / `ESC` / `R`、事件路由、headless 自测 |

---

## 测试方式

```bash
# 全量 pytest（基础 53 例 + 增量 test_entities / test_level_io / test_noise / test_game_world_entities）
pytest

# 仅 headless 自测（不依赖显示 / 声卡）
SDL_VIDEODRIVER=dummy DISABLE_AUDIO=1 python main.py --headless 30

# 指定关卡 headless 加载
SDL_VIDEODRIVER=dummy DISABLE_AUDIO=1 python main.py --map maps/level_01.json --headless 20
```

`--headless N` 会遍历全部 `RenderMode`、跑移动 / 静止帧、执行声呐物理校验，并构造「带敌人 + 拾取」的场景渲染一帧，验证 `render_sprites` 与 HUD 标记路径不崩。

---

## F.A.Q

**Q：headless 模式为什么没有窗口？**
A：自测时设置 `SDL_VIDEODRIVER=dummy`，pygame 使用虚拟显示驱动，无需真实屏幕；`--headless N` 跑 `N` 帧后干净退出并跑校验。

**Q：没有声卡 / 不想出声？**
A：设置 `DISABLE_AUDIO=1`（或运行 `python main.py --headless ...`，自测默认关闭音频）。音频子系统会安全降级，不影响游戏逻辑。

**Q：怎么进入关卡编辑器？**
A：游玩中按 `E` 进入；编辑完成后按 `ESC`（或再按 `E`）返回游玩，世界按当前编辑重建。`Ctrl+S` 保存到 JSON，`Ctrl+O` 读取。headless 模式不会进入编辑器。

**Q：自定义的关卡怎么让游戏加载？**
A：保存为 JSON，然后 `python main.py --map your_level.json`。也可用 ASCII 文件（`.txt` / `.asc`），加载时会先转成 JSON。

**Q：为什么 JSON → ASCII → JSON 后敌人血量变了？**
A：这是预期行为。ASCII 单字符无法表达敌人 hp / 拾取 amount 等元数据，回转会补 `config` 默认值；JSON 才是权威无损格式。

**Q：迷宫模式为什么没有敌人 / 拾取？**
A：按设计，随机迷宫（`generate_maze`）不生成实体，敌人 / 拾取只来自 `--map` 或编辑器，以保证迷宫确定性与既有测试不变。

---

## 许可证

本项目为演示 / 教学用途。
