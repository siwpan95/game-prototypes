# mcclone3d —— 《我的世界》风格 3D 体素沙盒（基于 3dworld 引擎）

`mcclone3d` 是 [`mc-clone`](https://gitee.com/siwpan/mc-clone)（MC1 文字冒险 + MC2 2D 侧视）
的 **3D 重做版**：把方块世界的玩法搬到真三维体素场景里，引擎用
[`siwpan/3dworld`](https://gitee.com/siwpan/3dworld) 的 `world3d`。

> **三仓关系**：`3dworld` 是**引擎与渲染能力本体**；`mcclone3d` 是**消费方**
> （玩法 + 贴图规则）；`mc-clone` 是**旧版**（2D / 文字形态），**原样保留、不再改动**。

## 状态：Phase 0 可用

| 能做 | 说明 |
| --- | --- |
| 确定性体素世界 | 种子决定地形/水/沙岸/雪线/矿脉/树；同种子两次生成**逐格相同** |
| 面剔除 + 图集 UV | 只画可见面；UV 走引擎 **世界级投影**（`texproj`），跨方块花纹连续 |
| 第一人称 | WASD/空格/飞行、重力与跳跃（跳高 1.19 格，与解析解对拍）、贴墙滑行 |
| 挖与放 | DDA 体素拾取（薄墙不穿）、左键挖/右键放、不许把自己封死、基岩挖不动 |
| hotbar 与库存 | 1–9 换方块；生存模式挖到进库存、放置消耗 |
| 存档 | **种子 + 编辑增量 + 玩家状态**（JSON，UTF-8）；参数不符**响亮报错** |
| 区块局部重建 | 改一块只重扫本块 + 贴边邻块 |
| headless 验收 | 自动机脚本（与帧率无关）+ 7 条检查，**零 GL** |

路线图见 [`docs/阶段计划.md`](docs/阶段计划.md)（Phase 1 生存循环 → 2 生物与昼夜 → 3 红石级机制）。

![Phase 0 地貌](shots/phase0_vista.png)

## 引擎从哪来（**必读**）

本项目**不自带引擎副本**，运行时从 `3dworld` 检出导入：

```bat
:: 方式一（推荐）：把 3dworld 检出加进 PYTHONPATH
set PYTHONPATH=G:\repos\3dworld          :: 本机示例；换机请换成你的检出目录
python examples\mcclone3d.py

:: 方式二：设 MC3D_ENGINE_ROOT
set MC3D_ENGINE_ROOT=G:\repos\3dworld

:: 方式三：装成可编辑包（一次性）
python -m pip install -e G:\repos\3dworld
```

找不到引擎时 `mcclone3d/_engine.py` 会抛一条**点名说清三条通路**的错误，不会静默降级。

## 运行

```bat
python examples\mcclone3d.py                 :: 交互：漫步 / 挖 / 放
python examples\mcclone3d.py --smoke 3       :: 3 秒后自动退出（冒烟）
python examples\mcclone3d.py --flag auto,verbose   :: 自动机 + 每秒心跳
python examples\shot_vista.py                :: 截图到 shots/（目视验证）
python -m mcclone3d.cli                      :: headless 验收（不需要窗口）
python -m tests.run_all                      :: 全部单测（86 项，零 GL）
```

**操作**：`WASD` 移动 ｜ `Space` 跳 ｜ 鼠标左键拖动转向 ｜ **左键挖 / 右键放** ｜
`1`–`9` 选 hotbar ｜ `F` 切飞行 ｜ `R` 重生 ｜ `Ctrl+S` 存档 ｜ `Esc` 退出。

## 与引擎的接法（不改 3dworld 一行）

只用引擎的三个**公开扩展点**（见 [`docs/阶段计划.md` §二](docs/阶段计划.md)）：

| 扩展点 | 用途 |
| --- | --- |
| `world3d.host.registry.SERVICES`（可写封闭表） | 登记服务短名 `mcclone` → `mcclone3d.kernel:McCloneKernel` |
| `WORLD3D_CONFIGS` 环境变量 | 让引擎来**本项目**的 `configs/` 读配置树 |
| `world3d.host.tree.mount_tree(path, want=...)` | 挂载配置树（demo 与 headless 验收**共用同一份接线**） |

## 贴图：走引擎的 UV 投影与贴图规则

* 像素材质**程序化生成**（16×16，逐字节确定性）⇒ 仓里没有二进制素材、无授权问题；
* 每个面的 UV 由 `u = (p · u_dir) * scale + offset` 算出（与 Source `texinfo` 同构），
  密度 `1/(图集列数 × tile_size)` ⇒ **一格方块面恰好跨一格图集格**，且跨方块连续；
* 图集映射、平铺回绕（`TexWrap.REPEAT`）、密度体检（`texproj.density_report`）都用引擎那一套。

三个实测踩过的坑（面的手性 / 图集 v 轴翻转 / 绕序）都写在
[`mcclone3d/mesh.py`](mcclone3d/mesh.py) 的模块说明里，并各有单测钉住。

## 目录

```
mcclone3d/
  _engine.py        引擎接入层（定位 world3d / 登记服务 / 指配置目录）
  blocks.py         方块表：id / 名称 / 固体 / 贴图（按面）/ 面剔除规则
  textures.py       程序化 16×16 像素材质 + 图集几何（零 GL 生成）
  world.py          区块化体素世界（确定性生成 + 编辑增量 + 跨区块邻块查询）
  mesh.py           区块网格：面剔除 + 逐面 UV 投影 → 图集 UV
  kernel.py         玩法内核（Service）：物理 / 拾取 / 挖放 / hotbar / 存档 / 自动机
  cli.py            headless 验收（7 条，零 GL）
configs/
  cordis.mcclone.yml   配置树（demo 与验收共用）
examples/
  mcclone3d.py      交互 demo（第一人称 + 挖/放 + 选中框 + 准星）
  shot_vista.py     截图脚本（地貌 / 材质 / 选中框的目视验证）
tests/              86 项纯逻辑单测（零 GL）
docs/阶段计划.md     架构、阶段路线、验收口径
shots/             截图（gitignore，可随时重生成）
```

## 测试与验收

```
python -m tests.run_all     # 模块 7/7、用例 86 项：方块表/贴图/世界/网格/物理/拾取/内核
python -m mcclone3d.cli     # world / mesh / physics / raycast / digplace / save / auto
```

判据是**可量化的比较**，不是"看起来对"：同种子逐格相同、面数与逐格统计相符、
跳高与解析解对拍、自动机三种帧率结果一致、存档往返逐字段相等。

## 已知边界

* 世界是**有限箱体**（默认 256×256×64 ≈ 220 万方块）；无限地形要区块流式加载，属 Phase 2。
* 不含任何 Minecraft 官方素材；本项目是**机制致敬**，与原作无隶属关系、不声称任何商标。
* 引擎侧已知差异（`MeshData.triangle_count` 对索引网格按 `//9` 少算 3 倍）只在本仓
  **记录 + 断言 + 回避**，不就地改 3dworld。

## 许可

MIT（见 [LICENSE](LICENSE)）。方块贴图为程序化生成。
