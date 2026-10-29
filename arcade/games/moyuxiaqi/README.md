# moyuxiaqi

摸鱼下棋：一个单文件的 pygame 棋类小游戏（含对 Python 3.14 下 pygame 系统字体的兼容性补丁）。

## 语言/类型
Python 3（pygame），桌面 GUI 游戏，单文件程序。

## 目录要点
- `moyuxiaqi.py`：唯一源文件（pygame 渲染，随机/计时等逻辑内聚，内含 `pygame.sysfont` 在 Python 3.14 的兼容补丁）

## 运行方式与依赖
```
/Python314/python.exe moyuxiaqi.py
```
依赖：`pygame`。GUI 窗口游戏，运行后会阻塞等待交互。

## 测试状态
`py_compile` 语法检查通过（1 个 `.py`）；GUI（pygame）未做自动运行。
