# M5 群系/洞穴/存档/打包 · 架构文档（mc_clone_gui / <仓库根>/MC2）

## 一句话总结
在 M1–M4 基础上完成 M5「世界深度」：确定性**群系**（5 种生物群系 + 海洋）、**洞穴**雕刻（不破地表与岩浆湖）、完整**存档/读档**（world/daynight/player/survival/creatures 经 PUBLIC 接口还原）、以及 **PyInstaller 一键打包**。全量 **250 测试通过 / 0 失败**（M1–M4 无退化 + 25 个 M5 新测试）。

## 范围（overview.md 第 31 行定义）
> 续做 M4（生物/精灵/刷怪）、M5（群系/洞穴/存档/PyInstaller 打包）。

| 主题 | 交付 | 关键约束 |
|---|---|---|
| 群系 | `worldgen/biomes.py` | terrain.py 禁改；确定性（PerlinNoise+random.Random） |
| 洞穴 | `worldgen/caves.py` | 仅挖 z∈[1,depth-2]，绝不破 z=0 地表与 z=depth-1 岩浆湖 |
| 存档 | `savegame.py` | 地基零改动：经 PUBLIC 构造器/属性还原，不新增 to_dict |
| 打包 | `build.spec`/`build.py`/`requirements.txt` | allin_engine 外部依赖经 pathex 注入捆绑 |

## 任务清单（T-M5-01~12）
- T-M5-01 `Biome(Enum)` + `BiomeMap`（列→群系确定性映射，归一化分阶段保证 5 种齐备）
- T-M5-02 `BiomeTerrainGenerator`：组合复用 `MultiLayerGenerator` 填 z>=1，再用群系逻辑重写 z=0（PLAINS/FOREST/TAIGA→GRASS，DESERT→SAND；OCEAN 注水）
- T-M5-03 `CaveCarver`：噪声阈值 + 虫洞随机游走雕刻空腔（按群系调密度）
- T-M5-04 边界保护：z=0 与 z=depth-1 净快照对比，测试断言未被破坏
- T-M5-05 `SaveGame(Serializable)` 数据容器 + 各子系统↔dict 快照辅助
- T-M5-06 `save_game()`：world.to_dict() 完整网格 + daynight/player/survival/creatures 序列化
- T-M5-07 `load_game()`：经 PUBLIC 接口重建（Player 写 _fx/_fy/_sync_aabb；SurvivalSystem.set_spawn；CreatureSystem.spawn + 还原 hp/state）
- T-M5-08 事件总线新增 `SAVE_GAME`/`LOAD_GAME` 并订阅日志
- T-M5-09 `GameLoop` 接入：`request_save`/`request_load`/`save_on_exit`，F5/F9 键位，`--load`/`--save` 参数，读档分支重建 spawn 指向新世界
- T-M5-10 输入层 `GUIInputManager.save_pressed`/`load_pressed`（F5/F9）
- T-M5-11 PyInstaller：`build.spec`（pathex 注入 allin_engine + datas 收集 data/ + hiddenimports）+ `build.py` + `requirements.txt`
- T-M5-12 测试：`test_m5_worldgen.py`(12) / `test_m5_save.py`(13) / `test_m5_integration.py`(5)；全量回归无退化

## 关键设计
### 群系（worldgen/biomes.py）
- `BiomeMap.__init__` 用低频 `PerlinNoise(seed)` 采样全宽，归一化到 [0,1] 后按 5 段阈值映射到 Biome——**无论噪声分布如何，最小/最大列必落入 OCEAN/DESERT 尾部**，稳定产出全部 5 种。
- `BiomeTerrainGenerator.generate(world, registry, seed)`：先 `MultiLayerGenerator`（M3）填好 z>=1（含底部岩浆湖），再逐列用群系高度偏移 + 细节噪声重写 z=0；OCEAN 列自海底到水位填 WATER、海底覆 SAND。

### 洞穴（worldgen/caves.py）
- 两种机制结合：① 噪声阈值雕刻（密度按 `BiomeMap.cave_density` 调整阈值）；② `random.Random(seed)` 虫洞随机游走生成连通隧道。
- 严格夹紧在 `z∈[1, D-2]`，z=0 与 z=D-1 层**完全不触碰**。

### 存档（savegame.py）
- `SaveGame` 继承 `allin_engine.core.serializable.Serializable`（dataclass），字段为原生 dict/list 容器；`to_dict/from_dict` 自动基于字段完成。
- **不重新生成世界**：直接保存 `world.to_dict()` 完整网格（含所有 z 层），读档 `BlockWorld.from_dict` 还原，字节一致。
- 地基零改动：所有状态仅经 PUBLIC 构造器 + 运行时属性赋值重建（含 `p._fx/_fy` + `_sync_aabb()`、直接赋值 `player.inventory._items` 等运行时操作，不修改任何源文件）。
- 容错：文件缺失→`FileNotFoundError`；JSON 损坏→`ValueError`；缺可选字段用默认值兜底。

### 集成闸口（main_gui.py / event_bus.py / mouse_input.py）
- `_build_world` 重构为 `_build_registry()` + `_build_world()`（注册表逻辑集中，供生成与读档复用）。
- `GameLoop` 新增 `save_path` 参数 + `request_save/request_load/save_on_exit`；`_update` 末尾经 `_input_action("save_pressed"/"load_pressed")` 触发（鸭子类型，headless 桩安全返回 False）。
- `run()` 退出前 `save_on_exit()` 自动存档到 `DEFAULT_SAVE_PATH`（`save/` 目录，自动建父目录）。
- `--load PATH`：从存档还原世界/玩家/系统（不重新生成）；`--save PATH`：指定存档路径。
- 读档后 `request_load` 重建 `SpawnSystem` 指向新世界/生物，避免写入旧列表。

### 打包（build.spec）
- `pathex=[ROOT, ENGINE]`（`ROOT`=<仓库根>/MC2、`ENGINE`=<仓库根>）：让分析器找到本地模块与 allin_engine。
- `datas=[(data, "data")]`：data/*.json 随包收集，运行时由 `main_gui._THIS_DIR` 定位（与开发期一致）。
- `hiddenimports`：显式列出 allin_engine 各子包，避免动态导入漏收集。
- `excludes=["tkinter", ...]`：GUI 走 pygame，tkinter 仅 headless 测试用，不进包。
- 产物 `dist/mc_clone_gui.exe`（console=False，图形界面无控制台窗口）。

## 风险与对策（R1~R5）
- **R1 确定性**：群系/洞穴仅用 `PerlinNoise(seed)` + `random.Random(seed)`，禁用全局随机/时间；同 seed 两次生成逐格一致（测试覆盖）。
- **R2 洞穴边界**：雕刻夹紧 `z∈[1,D-2]`，测试断言 z=0 地表与 z=D-1 岩浆湖净快照不变。
- **R3 地基零改动**：群系/洞穴/存档均不修改 terrain.py/block_world.py/player.py/survival.py/inventory.py/daynight.py/creatures/*；存档经 PUBLIC 接口还原。
- **R4 读档一致性**：world 存完整网格，读档字节一致；玩家/生物数值经断言还原。
- **R5 外部引擎打包**：allin_engine 经 pathex + hiddenimports 捆绑，data 经 datas 收集；开发期 PYTHONPATH 注入保持一致。

## 质量与验证
- 全量 **250 passed / 0 failed**（M1–M4 225 + M5 25）。
- M5 新测试：worldgen 12（确定性/群系覆盖/洞穴边界/海洋/往返）、save 13（往返/容错/缺字段）、integration 5（事件常量/输入键位/存档读档往返/_build_world 群系+洞穴）。
- PyInstaller 构建产物验证：见 `build.py` 与 `docs/build_m5.md`。

## 运行方式
```bash
# 开发运行
cd <仓库根>/MC2
set PYTHONPATH=<仓库根>;<仓库根>/MC2
python -m pytest tests -q            # 全量测试
python main_gui.py --seed 12345      # 启动 GUI（F5 存档 / F9 读档 / 退出自动存档）
python main_gui.py --load save/quicksave.json   # 从存档启动

# 打包
python build.py                      # 产出 dist/mc_clone_gui.exe
```
