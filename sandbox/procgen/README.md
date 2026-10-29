# procgen 程序化生成库（本仓内嵌副本）

供各游戏项目 `import` 复用的程序化生成工具包（纯 Python + numpy）。

> **溯源注记（2026-10-20）**：本目录是 [siwpan/procgen](https://gitee.com/siwpan/procgen) 的**内嵌冻结副本**，
> 按「自包含、零跨项目耦合」原则随 sandbox 一起版本化（`game.py` 即按此设计）。
> 上游包已于同日更名为 **`worldbuilder`**（PyPI：`pip install worldbuilder`），
> 因此**本副本的包名 `procgen` 与上游发行名已不一致**——这是刻意保留：
> 改名会波及 `world_gen.py` / `game.py` / `run.py` 三处导入与本仓既有产物，收益不抵成本。
> 代码内容与上游 `worldbuilder/` 逐模块相同（截至 2026-10-20 比对，7 个模块中 6 个 md5 一致，
> 仅 `__init__.py` 因包名字符串而不同）。后续如需跟进上游改动，请以 `worldbuilder` 为基准。

## 模块
- `noise`：`value_noise` / `perlin_noise` / `fractal_noise` / `fbm`（可调 lacunarity/gain）/ `simplex_noise`（方向伪影更少的改进版）
- `dungeon`：`generate_dungeon`（随机房间）/ `generate_dungeon_bsp`（二叉空间分割，保证连通）/ `generate_cave`（元胞自动机洞穴）/ `to_ascii(grid)` 打印
- `namegen`：`NameGenerator(style, method)`，风格 fantasy/sci/eastern，方法 syllable（音节拼接）/ markov（字符级转移学习）
- `loot`：`LootTable(entries).roll(n, unique=...)` 加权随机掉落，`unique=True` 无重复
- `terrain`：`generate_heightmap`（支持 `falloff` 岛屿）/ `classify` / `generate_terrain` / `generate_moisture` / `classify_biomes`（Whittaker 生物群系，8 类可达）/ `generate_world`
- `town`：`generate_town(seed, n_wards, walled)` —— 从零移植自 watabou 中世纪奇幻城市生成器：Voronoi 划区 + 城墙(塔楼/城门) + 图寻路路网 + ward 加权分配 + 建筑递归分割。返回 {bounds, center, wall, streets, wards, ...}，坐标为抽象单位

## 用法
```python
import sys; sys.path.insert(0, r"<仓库根>")
import procgen as pg

hm = pg.generate_heightmap(64, 64, seed=1)
d  = pg.generate_dungeon(48, 32, rooms=8, seed=2)
bsp = pg.generate_dungeon_bsp(60, 40, seed=5)          # BSP 地牢
cave = pg.generate_cave(56, 40, seed=7)                # 洞穴
names = pg.NameGenerator(style='fantasy').generate(10)
mkv = pg.NameGenerator(style='sci', method='markov').generate(10)
drops = pg.LootTable([("金币",50,(1,10)),("传说剑",1,(1,1))]).roll(5)
uniq = pg.LootTable([("a",50,(1,2)),("b",30,(1,2))]).roll(3, unique=True)
wld = pg.generate_world(80, 80, seed=11, falloff=0.3)  # 含生物群系
sx = pg.simplex_noise(xs, ys, seed=1)                  # 2D simplex
```

## 命令行演示
```bat
cd <仓库根>\procgen
python cli.py terrain --size 64 --seed 1 --out terrain.png
python cli.py dungeon --w 48 --h 32 --rooms 8
python cli.py name --style fantasy --n 10
python cli.py loot --n 5
```

## 说明
- 本库是独立包，**不依赖 tools 组其他项目**，可直接复制到任意游戏工程内使用（复制优于共享）。
- 所有随机均带 seed，可复现。
- 网格约定：`1`=可走/地板，`0`=墙（dungeon 与 cave 一致）。
