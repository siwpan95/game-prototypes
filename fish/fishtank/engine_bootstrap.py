"""allin_engine 唯一接入点。任何其他模块都不得直接 import allin_engine。

🔴 本文件禁止 `from __future__ import annotations`（E6：会破坏引擎 Serializable 的嵌套反序列化）。

三条硬约束（见 ARCHITECTURE §3.1）：
1. `ALLIN_USER_DATA` 必须在 `import allin_engine` **之前**设置（E3：paths.py 在模块导入期求值）。
2. `allin_engine` 不是 pip 包，优先使用项目内置的 `<root>/tools/allin_engine`，实现零外部依赖。
3. 全项目只有本文件 `import allin_engine.*`，其余模块一律从这里取符号。
"""

import os
import sys
from pathlib import Path

APP_NAME = "LazyFishTank"
"""用户数据目录名（%APPDATA%\\LazyFishTank）。"""

_ENGINE_PROBE = ("core", "ecs.py")
"""用于判定某目录是否为引擎根的探针文件。"""

_ready = False
_user_data_dir = ""
_engine_home = ""


def _engine_candidates():
    """引擎根目录多级定位候选表（顺序即优先级）。

    ① 环境变量 ALLIN_ENGINE_HOME（显式覆盖）
    ② 项目内置 <项目根>/tools/allin_engine（零外部依赖，复制后即用）
    ③ PyInstaller 冻结环境 sys._MEIPASS 下的内置引擎
    """
    here = Path(__file__).resolve()
    # parents[0]=fishtank/, parents[1]=项目根/, parents[2]=项目父目录/
    candidates = [
        os.environ.get("ALLIN_ENGINE_HOME", ""),
        str(here.parents[1] / "tools" / "allin_engine"),
    ]
    # PyInstaller frozen: sys._MEIPASS 才是真实文件所在位置
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidates.append(str(Path(meipass) / "tools" / "allin_engine"))
    return candidates


def default_user_data_dir():
    """返回默认用户数据目录：%APPDATA%\\LazyFishTank（非 Windows 回退 ~）。"""
    base = os.environ.get("APPDATA") or str(Path.home())
    return str(Path(base) / APP_NAME)


def bootstrap(user_data_dir=""):
    """必须在任何引擎符号被使用前调用一次；幂等。

    :param user_data_dir: 显式指定用户数据目录（对应 CLI ``--data-dir``）。
                          留空则沿用已存在的 ALLIN_USER_DATA，再回退到默认目录。
    :raises RuntimeError: 三级定位均未找到引擎时抛出（信息中给出修复指引）。
    """
    global _ready, _user_data_dir, _engine_home
    if _ready:
        return

    # —— 步骤 1：先设环境变量（E3：paths.py 在导入期读取 ALLIN_USER_DATA）——
    if not user_data_dir:
        user_data_dir = os.environ.get("ALLIN_USER_DATA", "") or default_user_data_dir()
    os.environ["ALLIN_USER_DATA"] = user_data_dir
    try:
        Path(user_data_dir, "saves").mkdir(parents=True, exist_ok=True)
        Path(user_data_dir, "logs").mkdir(parents=True, exist_ok=True)
    except OSError:
        # 目录不可创建时不阻断启动，后续存档会走降级路径并记日志
        pass
    _user_data_dir = user_data_dir

    # —— 步骤 2：再挂 sys.path（插入引擎的父目录，因为包名是 allin_engine）——
    found = ""
    for cand in _engine_candidates():
        if cand and Path(cand, *_ENGINE_PROBE).is_file():
            found = cand
            break
    if not found:
        tried = "\n  ".join(c for c in _engine_candidates() if c)
        raise RuntimeError(
            "未找到 allin_engine 引擎目录。已尝试以下路径：\n  "
            + tried
            + "\n请设置环境变量 ALLIN_ENGINE_HOME 指向 allin_engine 目录"
            "（该目录下应存在 core/ecs.py）。"
        )
    parent = str(Path(found).parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    _engine_home = found
    _ready = True


bootstrap()  # 模块被 import 时立即执行，保证顺序正确


# —— 步骤 3：统一再导出（换引擎版本只改这里）——
from allin_engine.core.ecs import World, Entity, Component, System            # noqa: E402
from allin_engine.core.game_loop import FixedTimestepLoop                     # noqa: E402
from allin_engine.core.event_bus import EventBus                              # noqa: E402
from allin_engine.core.data_library import DataLibrary                        # noqa: E402
from allin_engine.core.serializable import Serializable                       # noqa: E402
from allin_engine.core import deps                                            # noqa: E402
from allin_engine.core import paths as engine_paths                           # noqa: E402
from allin_engine.systems.save_load import SaveLoadManager                    # noqa: E402
from allin_engine.ai.decision.behavior_tree import (                          # noqa: E402
    Status, Blackboard, Node, Selector, Sequence, Condition, Action, BehaviorTree)
from allin_engine.ai.decision.brain import (                                  # noqa: E402
    BlackboardComponent, BrainComponent, BrainSystem)
from allin_engine.ai.decision.difference_engine import ReactiveTracker         # noqa: E402
from allin_engine.fx.particle import (                                        # noqa: E402
    Particle, ForceField, Emitter, ParticleSystem)
from allin_engine.utils.json_loader import JSONLoader                         # noqa: E402
from allin_engine.utils.logger import Logger                                  # noqa: E402

_LOGGERS = {}


def get_logger(name="fishtank", level="INFO", console=True):
    """返回一个按名字缓存的引擎 Logger。

    ⚠️ 实读结论：`allin_engine.utils.logger` **没有** `get_logger` 工厂
    （ARCHITECTURE §3.1 的示例代码在这一行有误），只有 `Logger` 类。
    这里补一个等价工厂，日志落到 <user_data>/logs/<name>.log。

    :param name: 日志器名（同时作为文件名）
    :param level: DEBUG / INFO / WARNING / ERROR
    :param console: 是否同步输出到控制台
    :returns: Logger 实例（同名复用）
    """
    key = (name, level, console)
    if key in _LOGGERS:
        return _LOGGERS[key]
    log_dir = str(Path(_user_data_dir) / "logs") if _user_data_dir else ""
    try:
        lg = Logger(log_dir=log_dir, level=level, filename=name + ".log", console=console)
    except OSError:
        lg = Logger(log_dir="", level=level, filename=name + ".log", console=console)
    _LOGGERS[key] = lg
    return lg


def user_data_dir():
    """返回当前生效的用户数据目录。"""
    return _user_data_dir


def engine_home():
    """返回定位到的引擎根目录。"""
    return _engine_home


def save_dir():
    """返回存档目录（经 ALLIN_USER_DATA 重定向后的引擎存档目录）。"""
    return str(engine_paths.get_save_dir())


def gui_symbols():
    """延迟导入 GUI 相关符号。

    🔴 E9：`Styles` 会构造 tkfont.Font，**必须在 tk.Tk() 之后**才能实例化，
    所以绝不能在模块顶层导入并实例化。

    :returns: (Styles, StatusPanel, TkUtil, hsv_to_rgb)
    """
    from allin_engine.render.gui_base import Styles, StatusPanel, TkUtil
    from allin_engine.render.color_system import hsv_to_rgb
    return Styles, StatusPanel, TkUtil, hsv_to_rgb


def engine_font_candidates():
    """中文字体回退链（1.9）：引擎自带 TTF → Microsoft YaHei → TkDefaultFont。

    :returns: 字体名候选列表，调用方按序探测第一个可用项。
    """
    names = []
    try:
        fonts_dir = engine_paths.get_fonts_dir()
        if fonts_dir and Path(fonts_dir).is_dir():
            for ttf in sorted(Path(fonts_dir).glob("*.ttf")):
                names.append(ttf.stem)
    except OSError:
        pass
    names.extend(["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "TkDefaultFont"])
    return names
