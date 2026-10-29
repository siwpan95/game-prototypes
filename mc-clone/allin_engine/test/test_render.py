"""
test/test_render.py — render 层单元测试

测试 ConsoleRenderer (MapData 数据模型 / ANSI 工具 / 缓冲操作)、
Color 系统、FormulaEngine (纯 Python 模式)。

运行：
    cd <仓库根> && python -m allin_engine.test.test_render
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.render.console_renderer import (
    ConsoleRenderer, ANSI_FOREGROUND, ANSI_BACKGROUND,
    ANSI_RESET, CHAR_COLOR_MAP,
)
from allin_engine.world.map_data import MapData
from allin_engine.render.color_system import (
    SolidColor, HSVFlowColor, EnergyColor, RainbowColor,
)


# ══════════════════════════════════════════════════════════
# MapData 测试
# ══════════════════════════════════════════════════════════

def test_map_data_from_string():
    """测试从字符串创建 MapData"""
    md = MapData.from_string("""
#####
#@..#
#####
""")
    assert md.width == 5
    assert md.height == 3
    assert md.get(0, 0) == "#"
    assert md.get(1, 1) == "@"


def test_map_data_empty():
    """测试创建空白地图"""
    md = MapData.empty(10, 5, fill=".")
    assert md.width == 10
    assert md.height == 5
    assert md.get(0, 0) == "."
    assert md.get(9, 4) == "."


def test_map_data_get_set():
    """测试 get/set"""
    md = MapData.empty(5, 5)
    md.set(2, 2, "@")
    assert md.get(2, 2) == "@"
    # 越界返回空格
    assert md.get(999, 999) == " "


def test_map_data_empty_string():
    """测试空字符串"""
    md = MapData.from_string("")
    assert md.width == 0
    # .strip().split('\n') → [''] → 1 行
    assert md.height == 1


def test_map_data_uneven_lines():
    """测试不等宽行"""
    md = MapData.from_string("short\nvery long line\nok")
    assert md.width == 14  # 最长行
    assert md.height == 3
    assert md.get(13, 0) == " "  # short 的行被补空格


# ══════════════════════════════════════════════════════════
# ConsoleRenderer 缓冲操作测试
# ══════════════════════════════════════════════════════════

def test_renderer_init():
    """测试渲染器初始化"""
    cr = ConsoleRenderer(cols=40, rows=20)
    assert cr.size == (40, 20)
    assert cr.size[0] == 40
    assert cr.size[1] == 20


def test_renderer_draw_text():
    """测试绘制文字"""
    cr = ConsoleRenderer(cols=20, rows=5)
    cr.draw_text(0, 0, "Hello", color="red")
    # 缓冲中应有数据
    buf = cr._buf
    assert buf[0][0][0] == "H"
    assert buf[0][4][0] == "o"
    # 验证超出文本范围的格子仍是空格
    assert buf[0][5][0] == " "


def test_renderer_draw_centered_text():
    """测试居中绘制"""
    cr = ConsoleRenderer(cols=20, rows=5)
    cr.draw_centered_text(2, "Hi")
    # "Hi" len=2, 居中 x=(20-2)//2=9
    buf = cr._buf
    assert buf[2][9][0] == "H"
    assert buf[2][10][0] == "i"


def test_renderer_draw_grid():
    """测试绘制网格地图"""
    cr = ConsoleRenderer(cols=20, rows=10)
    md = MapData.from_string("##\n@E")
    cr.draw_grid(md, offset_x=1, offset_y=1)

    buf = cr._buf
    # offset (1,1): 地图行0 "##" 在 buf[1]，行1 "@E" 在 buf[2]
    assert buf[1][1][0] == "#"
    assert buf[1][2][0] == "#"
    assert buf[2][1][0] == "@"
    assert buf[2][2][0] == "E"


def test_renderer_draw_rect():
    """测试绘制矩形"""
    cr = ConsoleRenderer(cols=10, rows=10)
    # 3x3 rect有内部区域，2x2全边框
    cr.draw_rect(1, 1, 3, 3, char="X", border=True, border_char="+")

    buf = cr._buf
    # 边框
    assert buf[1][1][0] == "+"  # 左上角
    assert buf[1][3][0] == "+"  # 右上角
    # 内部 (dx=1, dy=1) 不在边框
    assert buf[2][2][0] == "X"


def test_renderer_draw_progress_bar():
    """测试绘制进度条"""
    cr = ConsoleRenderer(cols=30, rows=5)
    cr.draw_progress_bar(0, 0, current=50, total=100, width=10)
    buf = cr._buf
    # 应该有填充字符
    assert buf[0][1][0] != " "


def test_renderer_draw_progress_bar_zero_total():
    """测试进度条 total=0 的情况"""
    cr = ConsoleRenderer(cols=30, rows=5)
    cr.draw_progress_bar(0, 0, current=0, total=0, width=10)
    # 应该不崩溃，ratio 为 0
    assert cr._buf[0][0][0] != ""


def test_renderer_hline():
    """测试水平线"""
    cr = ConsoleRenderer(cols=10, rows=5)
    cr.draw_hline(0, 1, width=5, char="-")
    buf = cr._buf
    assert buf[1][0][0] == "-"
    assert buf[1][4][0] == "-"


def test_renderer_vline():
    """测试竖直线"""
    cr = ConsoleRenderer(cols=10, rows=10)
    cr.draw_vline(3, 2, height=3, char="|")
    buf = cr._buf
    assert buf[2][3][0] == "|"
    assert buf[4][3][0] == "|"


def test_renderer_clear():
    """测试清空缓冲"""
    cr = ConsoleRenderer(cols=10, rows=5)
    cr.draw_text(0, 0, "Test")
    cr.clear()
    # 清空后第一个格子应为空格
    assert cr._buf[0][0][0] == " "


def test_renderer_resize():
    """测试调整尺寸"""
    cr = ConsoleRenderer(cols=20, rows=10)
    cr.resize(30, 15)
    assert cr.size == (30, 15)


# ══════════════════════════════════════════════════════════
# ANSI 静态方法 测试
# ══════════════════════════════════════════════════════════

def test_colorize():
    """测试 colorize 静态方法"""
    result = ConsoleRenderer.colorize("Hello", "red", bold=True)
    assert "Hello" in result
    assert ANSI_RESET in result
    # 应该有红色前景码
    assert ANSI_FOREGROUND["red"] in result


def test_colorize_no_color():
    """测试无颜色时返回原文本"""
    result = ConsoleRenderer.colorize("Hello", "nonexistent_color")
    assert result == "Hello"


def test_colorize_bold():
    """测试加粗"""
    result = ConsoleRenderer.colorize("Bold", "green", bold=True)
    assert "Bold" in result
    assert ANSI_RESET in result


def test_strip_ansi():
    """测试去除 ANSI 转义序列"""
    colored = ConsoleRenderer.colorize("Hello", "red")
    assert "Hello" in colored
    stripped = ConsoleRenderer.strip_ansi(colored)
    assert stripped == "Hello"


def test_strip_ansi_plain_text():
    """测试纯文本 strip_ansi"""
    assert ConsoleRenderer.strip_ansi("plain text") == "plain text"


# ══════════════════════════════════════════════════════════
# ANSI 颜色映射表测试
# ══════════════════════════════════════════════════════════

def test_ansi_foreground_map():
    """测试前景色映射表"""
    assert ANSI_FOREGROUND["red"] == "\033[31m"
    assert ANSI_FOREGROUND["green"] == "\033[32m"
    assert ANSI_FOREGROUND["blue"] == "\033[34m"
    assert len(ANSI_FOREGROUND) >= 16


def test_ansi_background_map():
    """测试背景色映射表"""
    assert ANSI_BACKGROUND["red"] == "\033[41m"
    assert ANSI_BACKGROUND["black"] == "\033[40m"


def test_char_color_map():
    """测试字符颜色映射"""
    assert CHAR_COLOR_MAP["@"] == "bright_yellow"
    assert CHAR_COLOR_MAP["E"] == "red"
    assert CHAR_COLOR_MAP["#"] == "bright_black"
    assert CHAR_COLOR_MAP[" "] is None


# ══════════════════════════════════════════════════════════
# Color 系统测试
# ══════════════════════════════════════════════════════════

def test_solid_color():
    """测试固定颜色"""
    sc = SolidColor({"value": "#ff8000"})
    color = sc.get_color()
    assert color[0] == 255
    assert color[1] == 128
    assert color[2] == 0


def test_solid_color_tuple():
    """测试 rgb 元组配置"""
    sc = SolidColor({"value": [100, 200, 50]})
    assert sc.color == (100, 200, 50)


def test_hsv_flow_color():
    """测试 HSV 流动颜色"""
    fc = HSVFlowColor({"hue": [0.0, 0.7], "speed": 0.01, "sat": 0.8})
    rgb1 = fc.get_color(index=0, total=1, time=0.0)
    assert len(rgb1) == 3
    assert all(0 <= c <= 255 for c in rgb1)

    rgb2 = fc.get_color(index=0, total=1, time=0.1)
    # 时间变化后颜色应不同
    assert rgb1 != rgb2


def test_hsv_flow_color_custom():
    """测试自定义 HSVFlowColor"""
    fc = HSVFlowColor({"hue_range": [0.3, 0.9], "speed": 0.05, "saturation": 1.0, "value": 0.9})
    rgb = fc.get_color(index=5, total=10, time=0.0)
    assert len(rgb) == 3
    assert all(0 <= c <= 255 for c in rgb)


def test_energy_color():
    """测试能量颜色"""
    ec = EnergyColor({"hue_offset": 0.0})
    # 能量 0 → 偏冷色
    rgb_low = ec.get_color(energy=0.0)
    assert len(rgb_low) == 3
    # 能量 1 → 偏暖色
    rgb_high = ec.get_color(energy=1.0)
    assert rgb_low != rgb_high


def test_rainbow_color():
    """测试彩虹颜色流"""
    rc = RainbowColor({"speed": 0.05})
    hex1 = rc.get_color(index=0, total=5, time=0.0)
    hex2 = rc.get_color(index=0, total=5, time=0.3)
    assert len(hex1) == 3
    assert len(hex2) == 3
    assert hex1 != hex2


def test_rainbow_color_reset():
    """测试彩虹颜色重置"""
    rc = RainbowColor({"speed": 0.02})
    c1 = rc.get_color(time=0.1)
    c2 = rc.get_color(time=0.2)
    # 颜色应该在变化
    assert c1 != c2


# ══════════════════════════════════════════════════════════
# FormulaEngine 纯 Python 回退测试
# ══════════════════════════════════════════════════════════

def test_formula_engine_import():
    """测试公式引擎可导入（纯 Python 回退模式）"""
    from allin_engine.render.formula_engine import FormulaEngine
    fe = FormulaEngine()
    assert fe is not None
