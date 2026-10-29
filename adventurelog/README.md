# 探险日志（log）— Auto Exploration Idle RPG

> 仓库：<https://gitee.com/siwpan/adventurelog> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）

tkinter 挂机放置 RPG：数据驱动（职业 / 技能 / 装备 / 怪物 / 地下城），支持 Excel / JSON 数据加载与自动挂机。

## 语言 / 类型
Python 3 / tkinter GUI 游戏

## 目录要点
- `main.py` —— 游戏入口（GUI）
- `core/` —— 游戏引擎（战斗、状态机、自动挂机等）
- `gui/` —— 界面（多标签页：酒馆 / 商店 / 仓库 / 野外）
- `data/`、`config/` —— 游戏数据与配置
- `gen_excel.py` —— 从 JSON 生成 Excel 配置模板（需 `openpyxl`）
- `demo_capture.py` —— 自动截图脚本（GUI）
- `promo_video_gen_v6.py` —— 宣传视频生成脚本
- `探险日志_宣传视频.mp4`、`探险日志_项目评估.md`、`log.txt`、`探险日志.spec`

## 运行方式
```bash
python main.py
```
依赖：tkinter（标准库）；`Pillow`（部分脚本）；`openpyxl`（仅 `gen_excel.py`）。

## 测试状态
- `py_compile` 语法检查：通过（27 个 .py 文件）
- GUI 类，未运行（避免弹窗）
