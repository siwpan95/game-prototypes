# -*- coding: utf-8 -*-
"""KID-A WALKER  —  伪3D步行模拟器  v3.0  INFINITE MAP
风格：暗色赛博 / 深蓝荧光走廊
音乐：saw wave 降调(-8半音)+混响 无限循环
特性：《遗迹2》风格模块化随机拼接伪无限地图
      - 21×21 房间模块预置库（走廊/交叉口/大厅/迷宫/暗室等）
      - 玩家靠近区块边缘时自动生成相邻区块
      - 玩家附近 3×3 模块动态加载，离开后模块被重置
      - v3.0: 多线程预加载，异步渲染，开始/游戏状态完全分离

入口文件。实现已拆分到同目录的 `kaw/` 包，这里只做启动。
注意：文件名不可改 —— arcade 合集的 main.py 按 games/kid-a-walker/kid_a_walker.py 拉起。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from kaw.game import Game  # noqa: E402


def main():
    """入口函数"""
    Game().run()


if __name__ == "__main__":
    main()
