# 街机合集 arcade

> 仓库：<https://gitee.com/siwpan/arcade> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

> 独立仓 siwpan/arcade（一仓一目录，2026-08-27 起）。单文件玩具整合项目（2026-08-25 用户拍板）：10 个小游戏收进一个选单壳，每玩法保留一个现行版，重复重做版已删除。

## 纪律

- 壳只做「展示 + 启动」；每个游戏**独立子进程 + 独立 cwd**（子进程隔离，崩一个不影响其他）；
- 游戏文件原样保留在 `games/<name>/`（复制优于共享，不融合代码）；
- 平台登记：`platform.yaml`（game 分类，入口 `python main.py`）。

## 收录

| 名称 | 目录 | 入口 |
|---|---|---|
| 俄罗斯方块 | games/tetris | main.py |
| 井字棋 | games/tictactoe | 井字棋8.py |
| 摸鱼下棋 | games/moyuxiaqi | moyuxiaqi.py |
| KID-A 步行模拟器（ModernGL 真 3D） | games/kid-a-walker | kid_a_walker.py |
| ASCII 滑雪 | games/ski | main.py |
| 拼图 | games/puzzle | main.py |
| 2048（终端自动对弈） | games/2048 | main.py |
| Calculator ∞ Alchemia 解密终端 | games/calculator | main.py |
| Line Rider Pro 画线骑行 | games/rider | main.py |
| 六一零食大闯关 | games/sixone | main.py |

## 运行

```bash
cd <PATH>
python main.py
```

## 发行版

| 版本 | 内容 |
|---|---|
| [v1.0.0-arcade](https://gitee.com/siwpan/arcade/releases/tag/v1.0.0-arcade) | 首版 10 游戏（伪 3D 步行模拟器） |
| [v1.1.0](https://gitee.com/siwpan/arcade/releases/tag/v1.1.0) | KID-A WALKER 真 3D 升级（ModernGL + EEVEE 式 bloom；其余 9 游戏沿用 v1.0.0 包） |

## 打包（2026-08-25 · 方案①逐游戏分体，已跑通）

```bash
pip install pyinstaller pywin32 pywin32-ctypes   # pywin32-ctypes>=0.2.3（0.2.0 在 Py3.14 坏）
python build_all.py                 # 全量：菜单 onefile + 10 游戏 onedir
python build_all.py --only tetris   # 只重打一个游戏（独立更新！）
python make_release.py              # 每游戏 zip + 全量 zip（v1.0.0 命名）
python make_release.py --only kid-a-walker --ver v1.1.0   # 单游戏 + 自定义版本号
```

> 游戏目录若存在同名 `<sub>.spec`（如 kid-a-walker），build_all 优先使用它——
> 复杂游戏的 hiddenimports / 动态库收集由游戏自己的 spec 维护。

产物：

- `dist/arcade.exe`（菜单 onefile，2.1MB，仅 tkinter）
- `dist/games/<sub>/<sub>.exe`（各游戏 onedir 平铺：exe+dll+数据同目录，cwd/__file__ 相对都成立；菜单以独立子进程启动）
- `release/arcade-<游戏>-<版本>-win64.zip`（可逐个上 gitee Release；sixone 超 100MB 仅入全量包）
- `release/arcade-collection-<版本>-win64-full.zip`（全量分发）

关键决策：**发行版保持子进程隔离**（每游戏一个 exe = 每游戏独立更新，插件化纪律的物理化）；sixone 因 pandas 依赖较大（259.6MB 目录），已排除 sqlalchemy/torch/cv2/numba/scipy 等非必要依赖。

## 整合背景

详见《单文件玩具整合方案_2026-08-25》：吸血鬼幸存者/公路驾驶/俄罗斯轮盘/贪吃蛇/文字传奇/挂机族等玩法重复重做已收敛（重复版删除，保留版独立成项目并登记平台）。
