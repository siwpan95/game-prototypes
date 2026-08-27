# tests/_panel_harness.py
# 面板单元测试共享脚手架（无头、不依赖真实 Tk）。
#
# 设计目标：让 gui/panels/* 下的自由函数 draw_*(canvas, state, callbacks)
# 能在完全独立、无需显示环境的前提下被覆盖：
#   - FakeCanvas       记录 create_*/tag_bind/configure 调用，不真正绘制
#   - CallbackRecorder 记录某回调是否被触发、被触发的参数
#   - StubFont         替身 tk.font.Font，使 draw_log 的换行逻辑可在无头下运行
#   - make_callbacks / fired_callback_names 用来断言「面板绑定了正确的回调」
#
# 本文件同时提供极简测试框架（test / expect / run_all），与 tests/test_all.py
# 同构但相互独立，便于面板测试单独运行。
import sys
import os
import io
import contextlib
import traceback
import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

RESULTS = []  # (name, status, detail)
TESTS = []


def test(name):
    """装饰器：把函数注册为测试用例（自动隔离全局唯一性/序列1 注册表）"""
    def deco(fn):
        def wrapper():
            buf = io.StringIO()
            try:
                _reset_global_state()
                with contextlib.redirect_stdout(buf):
                    fn()
                RESULTS.append((name, "PASS", buf.getvalue().strip()[-600:]))
                print(f"[PASS] {name}")
            except AssertionError as e:
                detail = f"{buf.getvalue().strip()[-400:]}\n断言失败: {e}"
                RESULTS.append((name, "FAIL", detail))
                print(f"[FAIL] {name}: {e}")
            except Exception as e:
                detail = f"{buf.getvalue().strip()[-400:]}\n异常: {type(e).__name__}: {e}\n" + \
                         "".join(traceback.format_tb(e.__traceback__)[-3:])
                RESULTS.append((name, "ERROR", detail))
                print(f"[ERROR] {name}: {type(e).__name__}: {e}")
        wrapper.__name__ = name
        TESTS.append(wrapper)
        return wrapper
    return deco


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _reset_global_state():
    """每个用例前清空全局注册表，保证隔离（唯一性/序列1 是模块级单例）"""
    try:
        from uniqueness import Uniqueness, SequenceOneCharacteristic
        Uniqueness._reset_state()
        SequenceOneCharacteristic._reset_state()
    except Exception:
        pass


# ───────────────────────── 无头替身：字体 ─────────────────────────
# 注意：tkinter 在无显示环境下（如托管 Python）可能缺失。这里用 try 包裹，
# 缺失时跳过 StubFont 替身——纯逻辑测试（test_e1_core 等）无需字体替身即可运行。
try:
    import tkinter
    import tkinter.font as tkfont

    class StubFont:
        """tkinter.font.Font 在无显示环境下创建需要 Tk 实例；用按字符数估算的
        measure 替身，使 draw_log 的像素换行逻辑可在无头下运行。"""
        def __init__(self, *args, **kwargs):
            self._spec = kwargs.get("font")
        def measure(self, text):
            return len(text) * 7

    tkfont.Font = StubFont
except Exception:
    # 无 tkinter 环境：保持 headless-friendly，仅跳过字体替身。
    pass


# ───────────────────────── 无头替身：Canvas ─────────────────────────
class FakeCanvas:
    """兼容 tkinter.Canvas 关键接口的记录型替身。

    记录所有 create_*/tag_bind/configure 调用，便于断言：
      - 面板确实渲染了内容（items 非空）
      - 面板把正确的回调绑定到了正确的 tag
    """
    def __init__(self, width=580, height=600):
        self._w = width
        self._h = height
        self._id = 0
        self.items = []            # [("text"|"line"|"oval"|"arc"|"poly", kwargs), ...]
        self.tag_bind_calls = []    # [(tag_or_id, event, handler), ...]
        self.configs = []           # [kwargs, ...]

    def _new_id(self):
        self._id += 1
        return self._id

    def delete(self, *args):
        pass

    def create_text(self, *a, **k):
        self.items.append(("text", k))
        return self._new_id()

    def create_line(self, *a, **k):
        self.items.append(("line", k))
        return self._new_id()

    def create_oval(self, *a, **k):
        self.items.append(("oval", k))
        return self._new_id()

    def create_arc(self, *a, **k):
        self.items.append(("arc", k))
        return self._new_id()

    def create_polygon(self, *a, **k):
        self.items.append(("poly", k))
        return self._new_id()

    def tag_bind(self, tag, event, handler):
        self.tag_bind_calls.append((tag, event, handler))

    def configure(self, **k):
        self.configs.append(k)

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h

    def canvasy(self, y):
        return y


# ───────────────────────── 回调记录与触发 ─────────────────────────
class CallbackRecorder:
    """记录某个命名的回调是否被调用、被调用时传入的参数。"""
    def __init__(self, name):
        self.name = name
        self.called = False
        self.calls = []   # [(args, kwargs), ...]

    def __call__(self, *args, **kwargs):
        self.called = True
        self.calls.append((args, kwargs))
        return None


def make_callbacks(*names):
    """构造 {name: CallbackRecorder(name)} 字典。"""
    return {n: CallbackRecorder(n) for n in names}


def fired_callback_names(canvas, callbacks):
    """触发 canvas 上所有已绑定的 handler，返回「被调用的回调 recorder 名」集合。"""
    for tag, event, handler in canvas.tag_bind_calls:
        handler(None)
    return {name for name, rec in callbacks.items() if rec.called}


# ───────────────────────── 状态 / 角色构造辅助 ─────────────────────────
def make_fonts():
    return {
        "tiny":  ("Arial", 9),
        "small": ("Arial", 10),
        "body":  ("Arial", 12),
        "title": ("Arial", 16),
        "h1":    ("Arial", 24),
        "h2":    ("Arial", 20),
        "mono":  ("Consolas", 10),
    }


from gui.state import GUIState


def make_state(character=None, old_one_info=None, fonts=None,
              view_mode="character", event_log=None):
    st = GUIState()
    st.character = character
    st.old_one_info = old_one_info
    st.fonts = fonts or make_fonts()
    st.view_mode = view_mode
    st.event_log = event_log if event_log is not None else []
    return st


from sequences import make_sequence


def char_seq9():
    return make_sequence("error", 9)


def char_seq1():
    return make_sequence("error", 1)


def char_seq0():
    return make_sequence("error", 0)


# 面板回调全集（用于测试时构造 callbacks 字典）
PANEL_CALLBACK_KEYS = [
    "do_action", "do_ascend", "do_switch", "do_random_event",
    "do_collect_seq1", "do_collect_uniqueness", "do_promote_old_one",
    "do_faction_action", "do_rival_tick", "do_add_rival", "do_toggle_ambient",
    "select_pathway", "select_pathway_from_view", "on_group_click",
]


# ───────────────────────── 运行器 ─────────────────────────
def run_all():
    print("=" * 70)
    print("  诡秘之主 · 面板单元测试（自由函数 · 无头）")
    print(f"  时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    for t in TESTS:
        t()
    n_pass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    n_fail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    n_err = sum(1 for _, s, _ in RESULTS if s == "ERROR")
    print("\n" + "=" * 70)
    print(f"  汇总: PASS={n_pass}  FAIL={n_fail}  ERROR={n_err}")
    print("=" * 70)
    if n_fail or n_err:
        for name, status, detail in RESULTS:
            if status in ("FAIL", "ERROR"):
                print(f"\n--- {name} [{status}] ---")
                print(detail)
        raise SystemExit(1)
