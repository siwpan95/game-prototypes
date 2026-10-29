"""
斯金纳箱 · 表情版 — 统一入口
- 签到模式：空格键签到，表情根据结果自动切换
- 表情浏览：按 E 切换浏览模式，数字键 0-9 切换表情
- 历史记录：按 H 查看签到历史
- 风扇背景：两个风扇在背景持续旋转
- ESC 退出
"""
import sys
import os

# 确保 smile 包可导入
smile_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, smile_dir)

from app import SkinnerFaceApp

if __name__ == "__main__":
    app = SkinnerFaceApp()
    app.run()
