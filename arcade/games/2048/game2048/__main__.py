"""支持 ``python -m game2048``。"""

import sys

from game2048.cli import main

if __name__ == "__main__":
    sys.exit(main())
