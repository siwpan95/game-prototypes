"""pytest 公共夹具。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 测试**不写用户目录**：`ALLIN_USER_DATA` 在 import 任何 fishtank 模块之前
   就被指向 tmp 目录，避免污染 %APPDATA%\\LazyFishTank（E3 同理）。
"""

import os
import sys
import tempfile

# —— 必须先于任何 fishtank / allin_engine import ——
_TEST_HOME = os.path.join(tempfile.gettempdir(), "lazyfishtank_pytest")
os.makedirs(_TEST_HOME, exist_ok=True)
os.environ.setdefault("ALLIN_USER_DATA", _TEST_HOME)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest  # noqa: E402

from fishtank.data_defs import load_all  # noqa: E402
from fishtank.state import GameState  # noqa: E402

DATA_DIR = os.path.join(_ROOT, "data")
GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")

T0 = 1700000000
"""所有测试共用的固定时间锚点（2023-11-14 22:13:20 UTC）。

🔴 测试里**绝不调用 time.time()** —— 时间必须显式注入，否则结果不可复现。
"""


@pytest.fixture(scope="session")
def data_bundle():
    """(BalanceTable, FishLibrary, DecorLibrary, UIText) —— 全测试会话共享。"""
    return load_all(DATA_DIR)


@pytest.fixture(scope="session")
def bal(data_bundle):
    """平衡表。"""
    return data_bundle[0]


@pytest.fixture(scope="session")
def species(data_bundle):
    """鱼种库。"""
    return data_bundle[1]


@pytest.fixture(scope="session")
def decor(data_bundle):
    """装饰库。"""
    return data_bundle[2]


@pytest.fixture(scope="session")
def uitext(data_bundle):
    """UI 文案。"""
    return data_bundle[3]


@pytest.fixture()
def new_state(bal, species):
    """一份全新的初始存档（时间锚点 = T0）。"""
    return GameState.new_game(bal, species, when=T0)


@pytest.fixture()
def tmp_save_dir():
    """一次性存档目录。

    ⚠️ 刻意**不用** pytest 的 `tmp_path`：某些受限运行环境会拦截
    `shutil.rmtree`（回收站不可用时 fail-closed），导致 `tmp_path` 的
    清理阶段抛 OSError 把测试污染成 ERROR。这里自己用 `mkdtemp` +
    逐文件 `os.remove` 收尾，只依赖最基础的文件 API。
    """
    d = tempfile.mkdtemp(prefix="lft_saves_", dir=_TEST_HOME)
    try:
        yield d
    finally:
        try:
            for name in os.listdir(d):
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    os.remove(p)
            os.rmdir(d)
        except OSError:
            pass  # 清理失败不影响测试结论
