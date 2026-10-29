# TwelveLabors

> 仓库：<https://gitee.com/siwpan/god-hand-> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）

十二试炼：神话重构。

## 简介
希腊神话十二试炼题材的文字冒险 / roguelite 游戏，支持三种界面：Tkinter（默认）、pygame、控制台；数据（角色、遗物、结局、随机事件、章节）以 JSON + Excel 管理，含解锁系统与存档。

## 语言 / 类型
- 语言：Python
- 类型：桌面 GUI 游戏（tkinter / pygame / 控制台多 UI）

## 目录要点
- `main.py`：主入口（`--ui tkinter|console|pygame`、`--import-excel`、`--gen-template` 等参数）
- `src/`：`game_engine.py`（引擎）、`ui_tkinter.py`、`ui_pygame.py`、`ui_console.py`、`unlock_manager.py`、`validate_data.py`
- `data/`：角色、结局、遗物、随机事件、章节等 JSON；`saves/`：存档
- `excel_importer.py`、`generate_template.py`、`TwelveLabors.xlsx`：Excel 导入/模板生成
- `docs/`：设计文档；`dist/`：打包 exe；`run.bat` / `run.sh`：启动脚本

## 运行方式与依赖
```
python main.py                 # 默认 tkinter 界面
python main.py --console       # 控制台界面
python main.py --ui=pygame     # pygame 界面
python main.py --import-excel --check   # 校验 Excel 数据
```
- 依赖：tkinter（默认，随 Python 提供）；pygame（可选）；Excel 导入/模板需 `openpyxl`（当前环境未安装）。

## 测试状态
- `py_compile` 语法检查：通过（10 个 .py）。
- 运行：默认 GUI，未实际启动；Excel 导入功能依赖未安装的 openpyxl。
