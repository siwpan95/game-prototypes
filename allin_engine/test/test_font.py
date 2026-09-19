"""
test/test_font.py — 本地字体加载单元测试

覆盖：
  - 本地字体目录发现（discover_local_fonts）
  - 从本地加载 pygame 字体（load_local_font，按名 / 默认 / 缓存）
  - 从本地加载 tkinter 字体（load_local_tk_font，环境可用时）
  - load_cjk_font 的 local_first / name 参数
  - 别名注册、列出、清空缓存

运行：
    cd D:/allin && python -m allin_engine.test.test_font
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.utils.font import (
    discover_local_fonts,
    register_local_font,
    get_local_fonts_dir,
    get_default_local_font_name,
    list_local_fonts,
    load_local_font,
    load_local_tk_font,
    load_cjk_font,
    load_cjk_tk_font,
    list_available_cjk_fonts,
    clear_font_cache,
)


# 依赖可用性探测（runner 无 skip 机制，缺失时测试直接 pass）
try:
    import pygame  # noqa: F401
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

try:
    import tkinter  # noqa: F401
    TK_OK = True
except Exception:
    TK_OK = False


# ══════════════════════════════════════════════════════════
# 本地字体目录 / 发现
# ══════════════════════════════════════════════════════════

def test_get_local_fonts_dir():
    """get_local_fonts_dir 返回 Path。"""
    d = get_local_fonts_dir()
    assert isinstance(d, object) and hasattr(d, "exists")
    assert str(d).replace("\\", "/").endswith("fonts")


def test_discover_local_fonts_finds_bundled():
    """扫描 fonts/ 目录能发现随包分发的字体。"""
    found = discover_local_fonts()
    assert isinstance(found, list)
    # 包内应至少包含一个本地字体（打包的手写体）
    assert len(found) >= 1
    aliases = [a for a, _ in found]
    assert any("baocanmou" in a.lower() for a in aliases)


def test_list_local_fonts_nonempty():
    """list_local_fonts 返回已注册字体。"""
    fonts = list_local_fonts()
    assert len(fonts) >= 1
    for alias, path in fonts:
        assert isinstance(alias, str)
        assert os.path.exists(path)


def test_get_default_local_font_name():
    """默认本地字体别名存在。"""
    name = get_default_local_font_name()
    assert name is not None
    assert "baocanmou" in name.lower()


def test_default_font_stable_with_extra_registered_fonts():
    """项目添加自己的字体后，默认字体仍是引擎自带手写体（稳定）。"""
    clear_font_cache()
    try:
        register_local_font("arial", "C:/fake/arial.ttf")
        register_local_font("baocanmouhui", "C:/fake/bao.ttf")
        name = get_default_local_font_name()
        assert name is not None
        assert "baocanmou" in name.lower()
    finally:
        clear_font_cache()


# ══════════════════════════════════════════════════════════
# Pygame 本地字体加载
# ══════════════════════════════════════════════════════════

def test_load_local_font_returns_pygame_font():
    """load_local_font 返回 pygame.font.Font（默认本地字体）。"""
    if not PYGAME_OK:
        return
    f = load_local_font(32)
    assert f is not None
    assert hasattr(f, "render")


def test_load_local_font_by_name():
    """按别名加载本地字体。"""
    if not PYGAME_OK:
        return
    name = get_default_local_font_name()
    f = load_local_font(24, name=name)
    assert f is not None


def test_load_local_font_renders_cjk():
    """本地字体能渲染中文（CJK 支持）。"""
    if not PYGAME_OK:
        return
    f = load_local_font(28)
    assert f is not None
    surf = f.render("中文测试", True, (255, 255, 255))
    assert surf.get_width() > 0 and surf.get_height() > 0


def test_load_local_font_cache():
    """相同参数返回同一缓存对象。"""
    if not PYGAME_OK:
        return
    f1 = load_local_font(40)
    f2 = load_local_font(40)
    assert f1 is f2


def test_load_local_font_missing_name_none():
    """指定不存在的字体名返回 None。"""
    if not PYGAME_OK:
        return
    f = load_local_font(16, name="__no_such_font__")
    assert f is None


def test_load_cjk_font_local_first():
    """load_cjk_font(local_first=True) 能加载到本地字体。"""
    if not PYGAME_OK:
        return
    f = load_cjk_font(16, local_first=True)
    assert f is not None
    assert hasattr(f, "render")


def test_load_cjk_font_by_name():
    """load_cjk_font(name=...) 命中本地字体。"""
    if not PYGAME_OK:
        return
    name = get_default_local_font_name()
    f = load_cjk_font(20, name=name)
    assert f is not None


def test_load_cjk_font_env_var(tmp_path=None):
    """ALLIN_FONT_PATH 环境变量生效（无该变量时跳过断言）。"""
    if not PYGAME_OK:
        return
    # 仅验证在设置了环境变量时不会崩溃并返回字体
    import os as _os
    name = get_default_local_font_name()
    path = dict(list_local_fonts())[name]
    _os.environ["ALLIN_FONT_PATH"] = path
    try:
        f = load_cjk_font(18)
        assert f is not None
    finally:
        _os.environ.pop("ALLIN_FONT_PATH", None)


# ══════════════════════════════════════════════════════════
# Tkinter 本地字体加载（有 Tk 环境时）
# ══════════════════════════════════════════════════════════

def test_load_local_tk_font_returns_or_none():
    """load_local_tk_font 在 Tk 可用时返回字体，否则返回 None（不崩溃）。"""
    if not TK_OK:
        return
    f = load_local_tk_font(16)
    # 无 Tk 根窗口环境下可能返回 None，但绝不能抛异常
    assert f is None or hasattr(f, "actual")


def test_load_cjk_tk_font_local_first():
    """load_cjk_tk_font(local_first=True) 不崩溃。"""
    if not TK_OK:
        return
    f = load_cjk_tk_font(12, local_first=True)
    assert hasattr(f, "actual")


# ══════════════════════════════════════════════════════════
# 别名注册 / 列出 / 缓存管理
# ══════════════════════════════════════════════════════════

def test_register_local_font_adds_alias():
    """register_local_font 能新增别名到注册表。"""
    name = get_default_local_font_name()
    path = dict(list_local_fonts())[name]
    register_local_font("__test_alias__", path)
    fonts = dict(list_local_fonts())
    assert "__test_alias__" in fonts
    assert fonts["__test_alias__"] == path


def test_list_available_cjk_fonts_includes_local():
    """list_available_cjk_fonts 包含本地字体条目。"""
    results = list_available_cjk_fonts()
    assert isinstance(results, list)
    assert len(results) >= 1
    # 至少有一条本地字体记录（含别名前缀）
    assert any("baocanmou" in label.lower() for label, _ in results)


def test_clear_font_cache_resets():
    """clear_font_cache 清空缓存后重新加载产生新对象（非缓存命中）。"""
    if not PYGAME_OK:
        return
    f1 = load_local_font(30)
    assert f1 is not None
    clear_font_cache()
    f2 = load_local_font(30)
    assert f2 is not None
    # 清空缓存后重新加载应创建新对象（而非命中旧缓存）
    assert f1 is not f2
