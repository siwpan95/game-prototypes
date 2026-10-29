"""★ `fish_painter.geometry()` 的双端一致性契约测试（对应子任务 4.6 / T05）。

🔴 禁止 `from __future__ import annotations`（E6）。

这份测试的定位与其它测试不同：它不是在"验证 Python 实现正确"，
而是在**把画鱼规范钉死成可执行的契约**。T05 要把这套几何逐条抄进
XJ380 的 C++ `fish_paint.cpp`，届时 C++ 端会用同一批输入产出同一批
数字来对拍。所以这里断言的每个数值，都是 C++ 端必须复现的。

导入约束
--------
本文件只 import `pyapp.fish_painter`，**不 import tkinter**。
`fish_painter` 的纯函数区必须能在无显示环境下独立工作 ——
这条由 `test_pure_region_does_not_need_tkinter` 显式守住。
"""

import ast
import math
import os

import pytest

from pyapp import fish_painter as fp

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 一条标准测试鱼：便于手算校验（rx = 1.0 * 100 * 1.0 / 2 = 50，ry = 50*0.4 = 20）
SHAPE = {"length": 1.0, "height_ratio": 0.4, "tail": "fork"}
BASE = 100.0
STAGE_SCALE = {"fry": 0.45, "juvenile": 0.7, "adult": 1.0, "mature": 1.1}

ALL_TAILS = ("fork", "fan", "round", "long")
ALL_STAGES = ("fry", "juvenile", "adult", "mature")
ALL_PATTERNS = ("none", "stripes", "spots")


# ---------------------------------------------------------------------------
# 1. body_size：尺寸公式
# ---------------------------------------------------------------------------

def test_body_size_formula_is_exact():
    """`rx = length * base_len * stage_scale / 2`，`ry = rx * height_ratio`。"""
    rx, ry = fp.body_size(SHAPE, "adult", BASE, STAGE_SCALE)
    assert rx == pytest.approx(50.0)
    assert ry == pytest.approx(20.0)

    rx2, ry2 = fp.body_size(SHAPE, "fry", BASE, STAGE_SCALE)
    assert rx2 == pytest.approx(50.0 * 0.45)
    assert ry2 == pytest.approx(20.0 * 0.45)


def test_body_size_scales_monotonically_with_stage():
    """成长阶段越靠后，鱼越大（L1：成长只增不减）。"""
    sizes = [fp.body_size(SHAPE, s, BASE, STAGE_SCALE)[0] for s in ALL_STAGES]
    assert sizes == sorted(sizes), "阶段缩放必须单调不减，实际 %r" % sizes
    assert sizes[0] < sizes[-1], "鱼苗与熟成必须有可见体型差"


def test_body_size_survives_garbage_input():
    """脏数据不得抛异常 —— 渲染层每帧都调它，抛一次就是满屏红。"""
    for bad_shape in ({}, None, {"length": None}, {"length": "x", "height_ratio": []}):
        rx, ry = fp.body_size(bad_shape, "adult", BASE, STAGE_SCALE)
        assert rx > 0.0 and ry > 0.0, "兜底尺寸必须为正，实际 %r" % ((rx, ry),)

    # 未知阶段名 -> 缩放兜底 1.0，不报错
    rx, _ = fp.body_size(SHAPE, "elder_god", BASE, STAGE_SCALE)
    assert rx == pytest.approx(50.0)

    # stage_scale 传 None -> 用内置兜底表
    rx, _ = fp.body_size(SHAPE, "adult", BASE, None)
    assert rx == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# 2. geometry：图元清单与绘制顺序
# ---------------------------------------------------------------------------

def test_geometry_draw_order_is_fixed():
    """绘制顺序必须是 尾→背→腹鳍→身体→腹部→花纹→眼睛→描边。

    顺序即 z-order。C++ 端逐条 blit，顺序错了鱼会"身体盖住眼睛"。
    """
    prims = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE,
                        pattern="stripes", outline=2)
    roles = [p.role for p in prims]

    # 身体一定在鳍之后（盖住鳍根），眼睛一定在身体之后
    i_fin = roles.index(fp.ROLE_FIN)
    i_body = roles.index(fp.ROLE_BODY)
    i_belly = roles.index(fp.ROLE_BELLY)
    i_accent = roles.index(fp.ROLE_ACCENT)
    i_eye = roles.index(fp.ROLE_EYE)
    i_outline = roles.index(fp.ROLE_OUTLINE)

    assert i_fin < i_body < i_belly < i_accent < i_eye < i_outline, (
        "绘制顺序被破坏：%r" % roles)


def test_geometry_covers_all_required_parts():
    """部件表（ARCHITECTURE §7.4）里的每个部件都必须真的产出图元。"""
    prims = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE,
                        pattern="stripes", outline=1)
    roles = set(p.role for p in prims)
    required = {fp.ROLE_BODY, fp.ROLE_BELLY, fp.ROLE_FIN,
                fp.ROLE_ACCENT, fp.ROLE_EYE, fp.ROLE_EYE_HL, fp.ROLE_OUTLINE}
    assert required <= roles, "缺失部件：%s" % sorted(required - roles)

    # 鳍至少三片：尾 + 背 + 腹
    fins = [p for p in prims if p.role == fp.ROLE_FIN]
    assert len(fins) >= 3, "鳍数量不足：%d" % len(fins)


def test_geometry_kinds_are_all_declared():
    """产出的 kind 必须都在 `KIND_*` 常量表内（C++ 端按此表实现分派）。"""
    known = {fp.KIND_ELLIPSE, fp.KIND_ELLIPSE_HALF, fp.KIND_POLYGON,
             fp.KIND_CIRCLE, fp.KIND_OUTLINE}
    for tail in ALL_TAILS:
        for pattern in ALL_PATTERNS:
            for outline in (0, 1, 2):
                shape = dict(SHAPE, tail=tail)
                prims = fp.geometry(shape, "adult", 0.3, BASE, STAGE_SCALE,
                                    pattern=pattern, outline=outline)
                for p in prims:
                    assert p.kind in known, "未声明的 kind=%r" % p.kind


def test_geometry_is_pure_and_deterministic():
    """同输入必同输出 —— 纯函数是双端一致的前提，绝不能引入随机或时钟。"""
    a = fp.geometry(SHAPE, "adult", 0.37, BASE, STAGE_SCALE, "spots", 2)
    b = fp.geometry(SHAPE, "adult", 0.37, BASE, STAGE_SCALE, "spots", 2)
    assert len(a) == len(b)
    for pa, pb in zip(a, b):
        assert (pa.kind, pa.role) == (pb.kind, pb.role)
        assert (pa.cx, pa.cy, pa.rx, pa.ry) == (pb.cx, pb.cy, pb.rx, pb.ry)
        assert pa.points == pb.points


def test_geometry_does_not_mutate_input():
    """不得就地改调用方的 shape 字典（渲染层每帧复用同一份 dict）。"""
    shape = {"length": 1.0, "height_ratio": 0.4, "tail": "fan"}
    snapshot = dict(shape)
    fp.geometry(shape, "adult", 0.5, BASE, STAGE_SCALE, "stripes", 2)
    assert shape == snapshot, "geometry() 污染了输入字典"


def test_zero_length_in_data_still_draws_a_fish():
    """数据表里 `length: 0` 视同"没填"，走默认值 1.0 —— 而不是画出一条隐形鱼。

    这是准则 L1（鱼永不消失）在渲染层的体现：**宁可尺寸不准，也不能让
    玩家的鱼凭空不见**。`body_size` 里的 `or 1.0` 就是干这个的，
    C++ 端必须保留同样的兜底。
    """
    prims = fp.geometry({"length": 0.0, "height_ratio": 0.4}, "adult",
                        0.0, BASE, STAGE_SCALE)
    assert prims, "length=0 把鱼画没了，违反 L1"
    body = [p for p in prims if p.role == fp.ROLE_BODY][0]
    assert body.rx == pytest.approx(50.0), "未回退到默认体长"


def test_geometry_returns_empty_on_degenerate_size():
    """基准体长为 0（窗口尚未布局）时返回空列表，而不是画畸形图元。"""
    assert fp.geometry(SHAPE, "adult", 0.0, 0.0, STAGE_SCALE) == []
    assert fp.geometry(SHAPE, "adult", 0.0, -5.0, STAGE_SCALE) == []


# ---------------------------------------------------------------------------
# 3. 尾鳍四型
# ---------------------------------------------------------------------------

def test_all_four_tail_types_produce_distinct_geometry():
    """fork / fan / round / long 四型必须真的长得不一样。

    这条防的是"C++ 端偷懒只实现一种尾巴"，也防 Python 端把某个分支
    写成了 fallthrough。
    """
    sigs = {}
    for tail in ALL_TAILS:
        prims = fp.geometry(dict(SHAPE, tail=tail), "adult", 0.0, BASE, STAGE_SCALE)
        fins = [p for p in prims if p.role == fp.ROLE_FIN]
        # 用（图元数, 各图元 kind, 包围盒）当指纹
        sigs[tail] = (len(fins), tuple(p.kind for p in fins),
                      tuple(round(v, 4) for v in fp.bounding_box(fins)))

    assert len(set(sigs.values())) == len(ALL_TAILS), (
        "尾鳍类型未区分：%r" % sigs)


def test_unknown_tail_falls_back_without_crash():
    """未知尾型必须兜底成某一种，而不是画不出尾巴。"""
    prims = fp.geometry(dict(SHAPE, tail="dragon"), "adult", 0.0, BASE, STAGE_SCALE)
    fins = [p for p in prims if p.role == fp.ROLE_FIN]
    assert len(fins) >= 3, "未知尾型没有兜底"


def test_long_tail_extends_further_than_fork():
    """long 尾必须比 fork 尾伸得更远（否则视觉分级无意义）。"""
    def tail_reach(tail):
        prims = fp.geometry(dict(SHAPE, tail=tail), "adult", 0.0, BASE, STAGE_SCALE)
        fins = [p for p in prims if p.role == fp.ROLE_FIN]
        return -fp.bounding_box(fins)[0]  # 向后（-x）伸出的距离

    assert tail_reach("long") > tail_reach("fork")


# ---------------------------------------------------------------------------
# 4. 摆尾相位
# ---------------------------------------------------------------------------

def test_tail_swing_follows_sine_spec():
    """尾尖 y 偏移 = `sin(2π·phase) * rx * TAIL_SWING`（§7.4 硬规范）。"""
    rx = 50.0
    for phase in (0.0, 0.125, 0.25, 0.5, 0.75, 0.9):
        expect = math.sin(2.0 * math.pi * phase) * rx * fp.TAIL_SWING
        assert fp._tail_tip_dy(rx, phase) == pytest.approx(expect), (
            "phase=%g 摆尾公式不符" % phase)


def _flat(points):
    """把 [(x,y),...] 摊平成 [x,y,...]，供 approx 比较。"""
    out = []
    for (x, y) in points:
        out.extend((x, y))
    return out


def test_tail_swing_is_periodic():
    """相位是周期量：phase 与 phase+1 必须给出完全相同的几何。

    渲染层的相位是累加的（`phase += dt * speed`），从不取模。
    若几何对 phase 不是严格周期，鱼游久了摆尾会漂移。
    """
    a = fp.geometry(SHAPE, "adult", 0.2, BASE, STAGE_SCALE)
    b = fp.geometry(SHAPE, "adult", 1.2, BASE, STAGE_SCALE)
    assert len(a) == len(b)
    for pa, pb in zip(a, b):
        assert pa.cy == pytest.approx(pb.cy, abs=1e-9)
        if pa.points:
            assert _flat(pa.points) == pytest.approx(_flat(pb.points), abs=1e-9)


def test_tail_is_at_rest_on_both_sine_zeros():
    """尾鳍与背鳍在 phase=0 与 phase=0.5 上都回到中线（sin 0 = sin π = 0）。

    只比尾/背：腹鳍是**故意错相 90°** 的，见下一条测试。
    """
    def tail_and_dorsal(phase):
        ps = fp.geometry(SHAPE, "adult", phase, BASE, STAGE_SCALE)
        return [p for p in ps if p.role == fp.ROLE_FIN][:-1]  # 末尾那片是腹鳍

    for pa, pb in zip(tail_and_dorsal(0.0), tail_and_dorsal(0.5)):
        assert _flat(pa.points) == pytest.approx(_flat(pb.points), abs=1e-9)


def test_pelvic_fin_is_in_quadrature_with_tail():
    """★ 腹鳍相位比尾鳍**超前 90°**（`sin(2πφ + π/2)`）—— C++ 端必须照抄。

    这不是笔误：所有鳍同相摆动会让鱼看起来像一块僵硬的板子，
    错开四分之一周期才有"游"的感觉。这条契约极易在移植时被"顺手对齐"掉，
    所以单独钉一条测试。
    """
    def pelvic_sway(phase):
        ps = fp.geometry(SHAPE, "adult", phase, BASE, STAGE_SCALE)
        return [p for p in ps if p.role == fp.ROLE_FIN][-1].points[1][1]

    ry = 20.0
    base_y = ry * 1.15
    # phase=0 -> sin(π/2)=+1 -> +ry*0.10；phase=0.5 -> sin(3π/2)=-1 -> -ry*0.10
    assert pelvic_sway(0.0) == pytest.approx(base_y + ry * 0.10, abs=1e-9)
    assert pelvic_sway(0.5) == pytest.approx(base_y - ry * 0.10, abs=1e-9)
    # phase=0.25 时尾鳍摆幅最大，腹鳍恰好归零
    assert pelvic_sway(0.25) == pytest.approx(base_y, abs=1e-9)


def test_swing_actually_moves_the_tail():
    """phase=0.25（sin=1，最大摆幅）时尾尖必须真的偏离中线。"""
    still = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE)
    swung = fp.geometry(SHAPE, "adult", 0.25, BASE, STAGE_SCALE)
    d = max(abs(a.cy - b.cy) for a, b in zip(still, swung))
    dp = 0.0
    for a, b in zip(still, swung):
        for (_, ya), (_, yb) in zip(a.points, b.points):
            dp = max(dp, abs(ya - yb))
    assert max(d, dp) > 1.0, "最大相位下尾巴纹丝不动，摆尾没接上"


# ---------------------------------------------------------------------------
# 5. 稀有度视觉分级（4.7）
# ---------------------------------------------------------------------------

def test_pattern_levels_add_geometry():
    """none < stripes/spots：花纹只加图元，不改身体本身。"""
    plain = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE, "none", 0)
    striped = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE, "stripes", 0)
    spotted = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE, "spots", 0)

    assert len(striped) > len(plain)
    assert len(spotted) > len(plain)

    # 身体图元本身不因花纹改变
    def body(ps):
        b = [p for p in ps if p.role == fp.ROLE_BODY][0]
        return (b.cx, b.cy, b.rx, b.ry)
    assert body(plain) == body(striped) == body(spotted)


def test_outline_levels_are_graded():
    """描边等级 0/1/2：0 无描边，2 比 1 粗（R5 双端渐变 + 2px 发光描边）。"""
    def outlines(level):
        ps = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE, "none", level)
        return [p for p in ps if p.role == fp.ROLE_OUTLINE]

    assert outlines(0) == []
    o1, o2 = outlines(1), outlines(2)
    assert o1 and o2, "描边等级 1/2 必须产出图元"
    assert max(p.width for p in o2) > max(p.width for p in o1), "描边未分级"


def test_unknown_pattern_is_ignored_safely():
    """未知花纹名当 none 处理，不抛异常。"""
    ps = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE, "plaid", 0)
    assert [p for p in ps if p.role == fp.ROLE_BODY], "未知花纹把鱼画没了"


# ---------------------------------------------------------------------------
# 6. 包围盒与坐标系约定
# ---------------------------------------------------------------------------

def test_bounding_box_of_empty_is_zeros():
    """空图元列表的包围盒是全 0（渲染层据此跳过绘制）。"""
    assert fp.bounding_box([]) == (0.0, 0.0, 0.0, 0.0)


def test_bounding_box_contains_every_primitive():
    """包围盒必须真的框住所有图元 —— 点击命中依赖它。"""
    prims = fp.geometry(SHAPE, "mature", 0.25, BASE, STAGE_SCALE, "spots", 2)
    x0, y0, x1, y1 = fp.bounding_box(prims)
    for p in prims:
        if p.points:
            for (px, py) in p.points:
                assert x0 - 1e-9 <= px <= x1 + 1e-9
                assert y0 - 1e-9 <= py <= y1 + 1e-9
        else:
            assert x0 - 1e-9 <= p.cx - p.rx and p.cx + p.rx <= x1 + 1e-9
            assert y0 - 1e-9 <= p.cy - p.ry and p.cy + p.ry <= y1 + 1e-9


def test_fish_faces_positive_x():
    """坐标系约定：鱼永远朝 +x 画，朝左由渲染层镜像（§7.4）。

    验证方式：眼睛必须在身体的前半段（cx > 0）。
    """
    prims = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE)
    eyes = [p for p in prims if p.role in (fp.ROLE_EYE, fp.ROLE_EYE_HL)]
    assert eyes, "没有眼睛"
    for e in eyes:
        assert e.cx > 0.0, "眼睛画到了鱼尾侧（cx=%.3f），朝向约定被破坏" % e.cx

    fins = [p for p in prims if p.role == fp.ROLE_FIN]
    assert fp.bounding_box(fins)[0] < 0.0, "尾鳍必须在 -x 侧"


def test_body_is_centered_at_origin():
    """身体椭圆的中心就是原点 —— 渲染层直接用鱼的屏幕坐标做平移。"""
    prims = fp.geometry(SHAPE, "adult", 0.0, BASE, STAGE_SCALE)
    body = [p for p in prims if p.role == fp.ROLE_BODY][0]
    assert body.cx == pytest.approx(0.0)
    assert body.cy == pytest.approx(0.0)
    assert body.rx == pytest.approx(50.0)
    assert body.ry == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# 7. 与真实鱼种数据对拍
# ---------------------------------------------------------------------------

def test_every_species_renders(species, bal):
    """fish_data.json 里**每一个**鱼种、每一个阶段都必须能画出来。

    这条是真正的回归网：新增鱼种时若 shape 字段写错，这里立刻炸。
    """
    scale = bal.get("growth.stage_scale", None)
    for sp in species.all_items.values():
        for stage in ALL_STAGES:
            prims = fp.geometry(sp.shape, stage, 0.3, 60.0, scale,
                                pattern="stripes", outline=1)
            assert prims, "%s @ %s 画不出图元" % (sp.id, stage)
            x0, y0, x1, y1 = fp.bounding_box(prims)
            assert x1 > x0 and y1 > y0, "%s @ %s 包围盒退化" % (sp.id, stage)
            # 尺寸必须落在合理区间，防止某条鱼把窗口撑爆
            assert (x1 - x0) < 60.0 * 6.0, "%s @ %s 体型异常巨大" % (sp.id, stage)


def test_every_species_tail_is_known(species):
    """所有鱼种的 tail 字段必须落在四型之内（否则悄悄走了兜底分支）。"""
    unknown = sorted({sp.tail() for sp in species.all_items.values()} - set(ALL_TAILS))
    assert not unknown, "fish_data.json 出现未实现的尾型：%s" % unknown


# ---------------------------------------------------------------------------
# 8. 纯函数区的独立性（T05 移植前提）
# ---------------------------------------------------------------------------

def test_pure_region_does_not_need_tkinter():
    """`fish_painter` 模块级不得 import tkinter。

    纯函数区要能在无显示环境跑（CI / XJ380 对拍脚本）。Tk 适配区若需要
    tkinter，必须延迟到函数内部 import。
    """
    path = os.path.join(_ROOT, "pyapp", "fish_painter.py")
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)

    for node in tree.body:  # 只看模块顶层
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith("tkinter"), "顶层 import 了 %s" % a.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("tkinter"), (
                "顶层 from %s import" % node.module)


def test_pure_region_uses_no_randomness_or_clock():
    """纯函数区不得 import random / time —— 双端一致的硬前提。"""
    path = os.path.join(_ROOT, "pyapp", "fish_painter.py")
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)

    banned = {"random", "time", "datetime", "secrets"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] not in banned, "import 了 %s" % a.name
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned, (
                "from %s import" % node.module)
