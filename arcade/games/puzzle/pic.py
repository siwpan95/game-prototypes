"""
向后兼容入口 —— 仍可直接运行 python pic.py
实际逻辑已拆分至 models.py / viewmodels.py / views.py / main.py 。
"""

from main import main

if __name__ == "__main__":
    main()
