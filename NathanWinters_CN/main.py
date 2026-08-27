"""
NathanWinters_CN — 薄壳入口（纯 Tkinter GUI）
所有引擎逻辑由 shared_core 提供，本文件仅注入配置并启动。
"""
import sys
import os

# 确保项目根目录在 sys.path（shared_core 可被导入）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_core.base_engine import ConcreteGameEngine
import config


def main():
    engine = ConcreteGameEngine(config)
    engine.run()
    engine.ui.root.mainloop()


if __name__ == "__main__":
    main()
