# smile

斯金纳箱 · 表情版 v2。

## 简介
基于 pygame 的签到抽卡式游戏：空格键签到触发开奖动画，数字键切换表情，H 查看历史，S 查看统计/成就；含软硬保底、连胜冻结卡、里程碑成就、屏幕震动与彩带庆祝等「game juice」，并有背景风扇与恶搞音效。

## 语言 / 类型
- 语言：Python
- 类型：桌面 GUI 游戏（pygame）

## 目录要点
- `main.py`：统一入口（调用 `app.py` 的 `SkinnerFaceApp`）
- `app.py`：应用主类与游戏循环
- `core/`：表情引擎、风扇引擎、签到、成就、音效、juice 等
- `ui/`：签到、浏览、历史、统计面板
- `sounds/`、`fan_sounds/`：音效资源；`expressions.json`：表情数据
- `gen_sounds.py`、`gen_fan_sounds.py`：音效生成脚本

## 运行方式与依赖
```
python main.py
```
- 依赖：`pygame`（当前环境已安装）。

## 测试状态
- `py_compile` 语法检查：通过（19 个 .py）。
- 运行：GUI 窗口游戏，未实际启动（避免卡住）。
