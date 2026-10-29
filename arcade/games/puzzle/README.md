# pintu

拼图游戏：MVVM 三层架构，pygame-ce 负责滤镜预览渲染、tkinter Canvas 负责拖拽拼合交互。

## 语言/类型
Python 3（pygame-ce + Pillow + tkinter），桌面 GUI 游戏。

## 目录要点
- `main.py`：入口（组装 MVVM 并启动视图）
- `viewmodels.py`：ViewModel 层；`views.py`：View 层（tkinter 交互 + pygame 预览）
- `models.py`：Model 层；`pic.py` / `fix_script.py` / `fix_script2.py`：图片处理与修复脚本
- `test_kid_a_walker.py`：测试脚本；`build/` `dist/`：打包产物；`docs/`：文档；`ARCHITECTURE.md` / `PRD.md`：架构与需求文档

## 运行方式与依赖
```
F:\Python314\python.exe main.py
```
依赖：`pygame-ce`、`Pillow`、tkinter（标准库）。GUI 窗口游戏，运行后会阻塞等待交互。

## 测试状态
`py_compile` 语法检查 8 个 `.py` 全部通过；GUI（pygame+tkinter）未做自动运行。
