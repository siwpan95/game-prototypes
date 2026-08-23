# Minecraft 复刻版（2D 文字向）· MC Clone

一个 **2D 文字向「我的世界」复刻成品**：确定性噪声生成侧视地形与世界，GUI 下可移动、挖掘、
建造、生存（饥饿/昼夜）、作业模拟、生物 AI 与战斗、群系/洞穴、存档读档，并可一键打包为
可分发 exe。

> 引擎地基（`alloy` 里的 MC 专属模块）已整体迁出；本目录 `D:\allin\example` 是**完全自包含**的独立成品。
> 原 `alloy` 的三个通用能力（`Serializable` / `JSONLoader` / `InputManager`）已内联到 `mcclone/_engine/`，
> 无需额外 PYTHONPATH，克隆即可运行。

## 里程碑

| 里程碑 | 主题 | 状态 |
|---|---|---|
| M1 | 基础引擎（世界/渲染/输入/事件） | ✅ |
| M2 | 生存基底（玩家/饥饿/昼夜/合成） | ✅ |
| M3 | 模拟层 / 作业系统（挖掘/建造） | ✅ |
| M4 | 生物与世界（AI/刷怪/战斗/掉落） | ✅ |
| M5 | 群系 / 洞穴 / 存档 / PyInstaller 打包 | ✅ |

## 目录结构

D:\allin\example
├── main.py              # 命令行入口：生成地形并 ANSI 渲染（--no-gui 降级路径）
├── mcclone/             # 方案 B 深度分层包（单一命名空间 mcclone）
│   ├── main_gui.py      # GUI 主入口（--seed / --load / --save；F5 存档 / F9 读档）
│   ├── paths.py         # 项目路径常量（PROJECT_ROOT / DATA_DIR / SAVE_DIR）
│   ├── _engine/          # 内联引擎（Serializable / JSONLoader / InputManager）
│   ├── core/            # 引擎无关核心
│   │   ├── event_bus.py  # 事件总线（M1）
│   │   ├── geometry.py   # Vec2i / AABB2D / clamp / lerp
│   │   ├── camera.py     # 相机（视口跟随 / Z 层切换）
│   │   ├── block_registry.py  # BlockDef / BlockRegistry
│   │   ├── block_world.py     # BlockWorld（稀疏方块世界 + 序列化）
│   │   ├── noise.py      # PerlinNoise（确定性 fbm）
│   │   ├── terrain.py    # TerrainGenerator（确定性侧视地形）
│   │   └── daynight.py   # DayNight（昼夜循环 + 序列化）
│   ├── player/           # 玩家与物品
│   │   ├── player.py     # Player（AABB 物理 / 状态）
│   │   ├── inventory.py  # Inventory（物品栏）
│   │   └── crafting.py   # Crafting（合成表）
│   ├── render/           # 渲染层
│   │   ├── text_world_renderer.py  # TextWorldRenderer（ANSI）
│   │   ├── tile_world_renderer.py  # TileWorldRenderer（GUI 瓦片）
│   │   ├── hud.py        # HUD（快捷栏 / 状态条 / 生物计数）
│   │   ├── fx_tiles.py   # M6 程序化像素瓦片纹理
│   │   └── particles.py  # M6 粒子系统
│   ├── audio/            # M6 音效
│   │   └── audio_fx.py   # SoundEngine（可插拔后端）
│   ├── input/            # 输入层
│   │   ├── input_realtime.py  # 实时输入
│   │   └── mouse_input.py     # 鼠标输入
│   ├── world/            # 世界 / 存档 / 世界生成
│   │   ├── savegame.py   # M5 存档/读档
│   │   └── worldgen/     # M3/M5 世界生成（multilayer/biomes/caves）
│   ├── systems/          # M2 生存系统（survival）
│   ├── simulation/       # M3 模拟/作业（world_sim/jobs）
│   └── creatures/        # M4 生物系统（entity/physics/ai/drops/system/spawn/render）
├── data/                # 方块/合成 JSON
├── docs/                # 架构文档（architecture_m1..m6、build_m5）
├── tests/               # 全量 pytest
├── packaging/           # M5 PyInstaller 打包
├── dist/                # 打包产物（mc_clone_gui.exe）
├── pytest.ini           # pytest 配置（保留在根目录）
└── README.md

## 运行

Python 3.14+ 即可，无需额外依赖或 PYTHONPATH——项目已完全自包含。

```bash
cd D:\allin\example
python -m mcclone.main_gui --seed 12345
```

GUI 操作：
- 移动 `A/D` 或 `←/→`，跳跃 `W`/`Space`，下蹲 `S`
- 左键：攻击优先（范围内有生物则攻击，否则挖掘）；右键：建造作业 / 取消
- 快捷栏 `1-6` 切换方块
- `F5` 存档 / `F9` 读档；退出时自动存档到 `save/quicksave.json`
- 从存档启动：`python -m mcclone.main_gui --load save/quicksave.json`

## 测试

`conftest.py` 基于文件实际位置自动注入路径，无需手动设置 `PYTHONPATH`：

```bash
cd D:\allin\example
python -m pytest -q
# 或零依赖运行器：python tests/run_tests.py
```

## 打包（M5）

详见 [docs/build_m5.md](docs/build_m5.md)。

```bash
cd D:\allin\example
python packaging/build.py        # 产物：dist/mc_clone_gui/mc_clone_gui.exe
```

## 设计要点

- **确定性**：`(seed, width, height)` 固定则世界逐格一致；群系/洞穴/生物/存档均基于 `random.Random(seed)`。
- **扁平本地引用**：模块内部互引用均用扁平本地 import（如 `from block_world import BlockWorld`）。
  引擎通用能力已内联到 `mcclone/_engine/`，不再依赖外部 `alloy`。
- **坐标约定**：x 向右、y 向上；屏幕行 r ↔ world y = `max_y - r`，列 c ↔ world x = `min_x + c`。
- **方块 id**：0=air 1=stone 2=dirt 3=grass 4=water 5=sand 6=stone_brick 7=glass 8=lava
  9=beef 10=pork 11=rotten_flesh。
- **地基零改动**：`terrain.py`/`player.py`/`block_world.py`/`geometry.py` 等禁改地基，M2–M5 均以
  新模块/新包叠加，向后兼容。

详见 [docs/architecture_m5.md](docs/architecture_m5.md)。
