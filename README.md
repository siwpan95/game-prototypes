# qiandao（签到 · 斯金纳箱）

基于 tkinter 的签到奖励强化（斯金纳箱）演示工具，使用有界指数增长公式模拟签到触发概率与奖励选择。

## 语言 / 类型
- 类型：Python 桌面 GUI 程序（tkinter，入口为 `.pyw`，无控制台窗口）
- 语言：Python 3

## 目录要点
- `qiandao.pyw` —— 主程序（GUI 入口，`python qiandao.pyw`）
- `init_data.py` —— 数据初始化脚本（生成 rewards.xlsx / qiandao_history.json / backups）
- `import_excel.py` —— 命令行导入 Excel 奖励配置（`--show` / `--backup` / `<excel>`）
- `rewards.json` / `rewards.xlsx` —— 奖励配置
- `qiandao_history.json` / `qiandao_state.json` —— 历史与状态数据
- `backups/` —— 备份目录

## 运行方式与依赖
- GUI：`F:\Python314\python.exe qiandao.pyw`（或 `pythonw qiandao.pyw`）
- 数据脚本：`python init_data.py`；`python import_excel.py --show`
- 依赖：标准库 tkinter；Excel 读写需 `pandas` + `openpyxl`（可选）

## 测试状态
- py_compile 语法检查通过（3/3 文件）；GUI 程序按规范未运行。
