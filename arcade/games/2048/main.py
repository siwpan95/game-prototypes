#!/usr/bin/env python3
"""项目唯一入口。

    python main.py                      # 默认 greedy 策略，终端动画
    python main.py -s fixed             # 复现原始版本的行为
    python main.py -g 30 --compare      # 相同牌运下横向对比全部策略
"""

import sys

from game2048.cli import main

if __name__ == "__main__":
    sys.exit(main())
