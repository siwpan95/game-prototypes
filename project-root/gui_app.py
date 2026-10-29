# gui_app.py
# 诡秘之主 序列途径模拟系统 —— Canvas 图形界面（薄启动器）
#
# 实际实现已拆分到 gui/ 包（见 gui/app.py 与 gui/panels、gui/controllers 等）。
# 本文件仅作向后兼容入口，供 run_gui.bat 与既有文档继续工作；
# 同时把 LordOfMysteriesGUI 暴露为模块级符号，便于 `from gui_app import LordOfMysteriesGUI`。

from gui.app import LordOfMysteriesGUI

if __name__ == "__main__":
    LordOfMysteriesGUI().run()
