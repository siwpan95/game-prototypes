"""
Diablo: Cataclysm Era - 图形界面版
基于 pygame_ce/tkinter 的暗黑破坏神风格 RPG 游戏

各功能模块拆分：
    paths.py  - 路径解析
    models.py - 数据模型（装备/玩家/敌人）
    i18n.py   - 国际化文本与名称翻译
    data.py   - 预设游戏数据（武器/护甲/敌人/区域）
    storage.py- 存档/读档/设置/随机装备
    gui.py    - 主界面应用（GameGUI）
"""
from gui import GameGUI

# ---------------------------- Main Entry Point ----------------------------
if __name__ == "__main__":
    app = GameGUI()
