# MCclone

MCclone：基于 alloy 的《我的世界》风格复刻合集，含 MC1（文字冒险，tkinter）与 MC2（2D 侧视复刻，pygame），由统一启动器管理。

## 语言/类型
Python 3（tkinter + pygame），桌面 GUI 游戏合集。

## 目录要点
- `launcher.py`：统一启动器（命令行菜单，支持 `--probes` 无头自检）
- `MC1/`：文字冒险游戏（tkinter 入口 `MC1/main.py`）
- `MC2/`：2D 侧视复刻（pygame 入口 `MC2/mcclone/main_gui.py`）
- `alloy/`：自研引擎（ECS、渲染、AI、音频、战斗、存档等，含自身 `pyproject.toml` 与 README）
- `product_core/` `saves/` `tests/` `.github/`：产品核心、存档、集成测试与 CI 配置

## 运行方式与依赖
```
F:\Python314\python.exe launcher.py
F:\Python314\python.exe launcher.py --probes   # 无头运行全部探针
```
依赖：Python 3.10+；MC1 需 tkinter，MC2 需 pygame（无显示设备时 GUI 无法启动，但探针可 headless 运行）。GUI 窗口游戏，运行后会阻塞等待交互。

## 测试状态
`py_compile` 语法检查 177 个 `.py` 全部通过；GUI（tkinter/pygame）未做自动运行。
