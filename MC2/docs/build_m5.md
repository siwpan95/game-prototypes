# M5 打包说明（PyInstaller）

将 `<仓库根>/MC2` 的 2D 我的世界复刻版打包为可分发 exe。

## 前置
- Python 3.14（开发/测试用 managed 运行时；打包用已装 pyinstaller 的解释器）
- `pygame-ce`（运行时依赖，已随项目环境安装）
- `PyInstaller >= 6.0`
- `allin_engine`：外部引擎，位于 `<仓库根>/allin_engine`，**无需 pip 安装**，由 `build.spec` 的 `pathex` 注入

## 一键打包
```bash
cd <仓库根>/MC2
python packaging/build.py
# 等价：pyinstaller --clean --noconfirm packaging/build.spec
```
产物：`dist/mc_clone_gui/mc_clone_gui.exe`（One-Folder 形态，含全部依赖与 data/）。

## 设计要点
- **入口** `main_gui.py`，支持 `--no-gui / --seed / --load / --save`。
- **外部引擎**：`build.spec` 的 `pathex=[ROOT, ENGINE]`（`ROOT`=<仓库根>/MC2、`ENGINE`=<仓库根>）让分析器找到 allin_engine；`hiddenimports` 显式列出其各子包，避免动态导入漏收集。
- **数据文件**：`datas=[(data, "data")]` 收集 `data/*.json`，运行时由 `main_gui._THIS_DIR` 定位（与开发期一致）。
- **裁剪**：`excludes=["tkinter", ...]` —— GUI 走 pygame，tkinter 仅 headless 测试用，不进包。
- **窗口**：`console=False`，图形界面不弹控制台。

## 验证清单
- [ ] `python packaging/build.py` 退出码 0
- [ ] `dist/mc_clone_gui/mc_clone_gui.exe` 存在
- [ ] 运行 exe 可进入 GUI（需显示环境），F5 存档生成 `save/quicksave.json`
- [ ] `--load save/quicksave.json` 可从存档启动

## 已知限制
- 本环境（无显示）仅能验证**构建成功**，无法 headless 验证 GUI 实际渲染；GUI 观感需真机目检。
- UPX 压缩个别二进制可能告警但不影响产物可用性。
