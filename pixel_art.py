# -*- coding: utf-8 -*-
"""程序化像素风精灵（零外部资源）：每敌型一张独立剪影点阵。

点阵字符 -> 调色板：
    . 透明   b 基色(取自数据表)  d 暗部  l 亮部  e 眼白  w 纯白
    o 橙(引信/核心)  r 红(血眼)  g 金(宝箱锁/光环)  k 近黑(弓/武器)
运行时只烘焙一次（启动时），之后纯 blit——性能与旧圆形精灵持平。
"""
import pygame

from data import ENEMIES, BOSSES


def _shade(c, f):
    return (max(0, min(255, int(c[0] * f))),
            max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))))


def _bake(rows, base, scale):
    h = len(rows)
    w = max(len(r) for r in rows)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pal = {"b": base, "d": _shade(base, 0.5), "l": _shade(base, 1.6),
           "e": (250, 245, 235), "w": (255, 255, 255),
           "o": (255, 150, 60), "r": (230, 70, 70), "g": (255, 208, 96),
           "k": (26, 26, 32)}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = pal.get(ch)
            if c:
                s.set_at((x, y), c)
    return pygame.transform.scale(s, (w * scale, h * scale))


def _scale_for(rows, radius):
    w = max(len(r) for r in rows)
    return max(2, round(radius * 2 / w))


# ================================================================ 敌型点阵
ART = {
    # 尸鬼：佝偻人形，垂臂
    "draugr": [
        "....bbbbbbbb....",
        "...bllllllllb...",
        "...blebbbbelb...",
        "...bbbbbbbbbb...",
        "....bbbbbbbb....",
        "...bbbbbbbbbb...",
        "..bbllbbbbllbb..",
        "..bb.bbbbbb.bb..",
        "..bb.bbddbb.bb..",
        "...b.bbddbb.b...",
        "...b.bbddbb.b...",
        "...bb.bbbb.bb...",
        "..bb...bb...bb..",
        ".bb....bb....bb.",
        ".bb....bb....bb.",
        "......bb........",
    ],
    # 狂狼：四足侧影，立耳翘尾
    "wolf": [
        "bb..........bb..",
        "bbbb..bbbb.bbbb.",
        "bebbbbbbbbbbbbb.",
        "bbbbbbbbbbbbbbb.",
        ".bbbbbbbbbbbbbb.",
        "..bbbbbbbbbbbbb.",
        "..bbb.bb.bb.bbb.",
        "..bb...bb...bb..",
        ".bbb...bb...bbb.",
        ".bb....bb....bb.",
    ],
    # 巨魔：庞大壮硕，右臂持棍
    "troll": [
        "..dddddddddddd..",
        ".dbbbbbbbbbbbbd.",
        ".bbebbbbbbbebbb.",
        ".bbbbbbbbbbbbbb.",
        "..bbbbbbbbbbbb..",
        "..bbbbbbbbbbbb..",
        ".bbbbbbbbbbbbbbk",
        ".bbbbbbbbbbbbbbk",
        "..bbb.bbbb.bbb.k",
        "..bbb.bbbb.bbb.k",
        "..bbb.bbbb.bbb..",
        "...bb.bbbb.bb...",
        "...bb.bbbb.bb...",
        "...bb..bb..bb...",
        "..bb...bb...bb..",
        "..b....bb....b..",
    ],
    # 怨灵：兜帽幽灵，裙摆飘散（无腿）
    "wraith": [
        "...bbbbbbbbbb...",
        "..bllllllllllb..",
        "..blebbbbbbelb..",
        "..bbbbbbbbbbbb..",
        "..bbbbbbbbbbbb..",
        "...bbbbbbbbbb...",
        "...bbbbbbbbbb...",
        "...bb.bbbb.bb...",
        "...bb.bbbb.bb...",
        "..bbb..bb..bbb..",
        "..bb....b...bb..",
        ".bbb.........bbb",
    ],
    # 血尸鬼：重甲宽体，板甲拼缝
    "brute": [
        ".bbbbbbbbbbbbbb.",
        "bddbbbbbbbbbbddb",
        "bdebbbbbbbbbbedb",
        "bddbbbbbbbbbbddb",
        "bbbbbbbbbbbbbbbb",
        ".bbbbbbbbbbbbbb.",
        "..bbbbbbbbbbbb..",
        "..bbb.bbbb.bbb..",
        "..bbb.bbbb.bbb..",
        "..bbb..bb..bbb..",
        "...bb..bb..bb...",
        "...b...bb...b...",
    ],
    # 哥布林射手：小个子持弓（左侧弓臂 k + 弓弦 w）
    "goblin_archer": [
        ".....bbbb.......",
        "....bbbbbb...k..",
        "....bebbbb..k...",
        ".....bbbb..k....",
        ".....bbbb.k.....",
        "....bbbbbbkw....",
        "....bbbbbb.k....",
        ".....bbbb..k....",
        ".....b..b..k....",
        "....bb..bb.k....",
        "...bb....bbk....",
        "...b......b.....",
    ],
    # 自爆尸鬼：圆滚身躯，头顶引信，腹中发光核心
    "bomber": [
        ".......oo.......",
        "......oo........",
        "....bbbbbb......",
        "..bbbbbbbbbb....",
        ".bbbbbbbbbbbb...",
        ".bbbbbbbbbbbb...",
        "bbbbbbbbbbbbbb..",
        "bbbbbooooobbbbb.",
        ".bbbbbbbbbbbb...",
        "..bbbbbbbbbb....",
        "...bbbbbbbb.....",
        "....bbbbbb......",
        "....bb..bb......",
        "...bb....bb.....",
    ],
    # 哀嚎女妖：长袍飘带 + 头顶光环
    "healer": [
        "......gg........",
        "....bbbbbb......",
        "...bbbbbbbb.....",
        "...bebbbebb.....",
        "...bbbbbbbb.....",
        "...bbbbbbbb.....",
        "..bbbbbbbbbb....",
        "..bbbbbbbbbb....",
        ".bbbbbbbbbbbb...",
        ".bbbbbbbbbbbb...",
        ".bbb.bbbb.bbb...",
        "..bb.bbbb.bb....",
        "..bb.bbbb.bb....",
        "..bb...bb.bb....",
        "....bb...bb.....",
        "....b.....b.....",
    ],
    # 寒冰巨蛇：S 形蜿蜒蛇身，蛇首带眼
    "icesnake": [
        ".bbbb...........",
        "bbbbbb...bbbbb..",
        "bbebbbbbbbbbbbb.",
        "bbbbbbbbbbbbbbb.",
        ".bbbbbbbbbbbbbb.",
        "..bbbbbbbbbbbbb.",
        "...bbbbbbbbbbb..",
        "..bbbbb.bbbbbb..",
        "..bbb....bbbbb..",
        "..bb......bbbb..",
    ],
    # 嗜血亲王：披风下摆展开，血红双眼
    "vampire": [
        "...bbbbbbbb.....",
        "..bbbbbbbbbb....",
        "..bebbbbbebb....",
        "..brbbbbbbbb....",
        "..bbbbbbbbbb....",
        "..bbbbbbbbbb....",
        ".bbbbbbbbbbbb...",
        ".bbbbbbbbbbbbb..",
        ".bb.bbbbbb.bbb..",
        ".bb..bbbb..bbb..",
        ".bb..bbbb..bbb..",
        "bb...bbbb...bbb.",
        "bb...bbbb...bbb.",
        "bbb..bbbb..bbbb.",
        ".bbbbbbbbbbbbb..",
        "..bbbbbbbbbbb...",
    ],
}

# 宝箱怪：伪装（闭眼闭齿）/ 惊醒（圆睁双眼、獠牙毕露）
MIMIC_ART = (
    [
        "..dddddddddd..",
        ".dbbbbbbbbbbd.",
        ".dbbbbbbbbbbd.",
        ".dbbbbbbbbbbd.",
        ".dbggggggggbd.",
        ".dbbbbbbbbbbd.",
        ".dbwbwbwbwbbd.",
        ".dbbbbbbbbbbd.",
        ".dbbbbbbbbbbd.",
        "..dbbbbbbbbd..",
        "...dddddddd...",
    ],
    [
        "..dddddddddd..",
        ".dbbbbbbbbbbd.",
        ".dbebbbbbbbbd.",
        ".dbebbbbbbbbd.",
        ".dbggggggggbd.",
        ".dbbbbbbbbbbd.",
        ".dbwbwbwbwbbd.",
        ".dbbbbbbbbbbd.",
        ".dbbbbbbbbbbd.",
        "..dbbbbbbbbd..",
        "...dddddddd...",
    ],
)

# ================================================================ Boss 点阵
BOSS_ART = {
    # 霜巨人尤弥尔：巨角人形，冰白瞳
    "jotunn": [
        "w..................w",
        "....bbbbbbbbbbbb....",
        "...bbbbbbbbbbbbbb...",
        "..bbbbbbbbbbbbbbbb..",
        "..bbebbbbbbbbbbbb...",
        "..bbbbbbbbbbbbbbbb..",
        "..bbbbbbbbbbbbbbbb..",
        "...bbbbbbbbbbbbbb...",
        "...bbbbbbbbbbbbbb...",
        "..bbbbbbbbbbbbbbbb..",
        ".bbbbbbbbbbbbbbbbbb.",
        ".bbbbbbbbbbbbbbbbbb.",
        ".bbb.bbbbbbbbbb.bbb.",
        ".bbb.bbbbbbbbbb.bbb.",
        ".bbb..bbbbbbbb..bbb.",
        "..bb..bbbbbbbb..bb..",
        "..bb..bbbbbbbb..bb..",
        "..bb...bbbbbb...bb..",
        "..bb...bbbbbb...bb..",
        "...b...bbbbbb...b...",
        "...b...bbbbbb...b...",
        "..bb...bbbbbb...bb..",
        "..bb............bb..",
    ],
    # 黑龙尼德霍格：双翼展开，角首
    "nidhogg": [
        ".dd..............dd.",
        ".dd..bbbbbbbbb..dd.",
        "..dd.bbbbbbbbbb.dd..",
        "...dbbebbbbbbbbdd...",
        "...bbbbbbbbbbbbbb...",
        "...bbbbbbbbbbbbbb...",
        "....bbbbbbbbbbbb....",
        "...bbbbbbbbbbbbbb...",
        "..bbbbbbbbbbbbbbbb..",
        ".bbbbbbbbbbbbbbbbbb.",
        ".bbbbbbbbbbbbbbbbbb.",
        ".dd.bbbbbbbbbbbb.dd.",
        ".dd..bbbbbbbbbb..dd.",
        ".dd..bbbbbbbbbb..dd.",
        ".dd...bbbbbbbb...dd.",
        "......bbbbbbbb......",
        "......bbbb..bb......",
    ],
    # 尘世巨蟒约尔曼冈德：盘绕蛇躯
    "jormungandr": [
        "...bbbbbbbbbbbb.....",
        "..bbbbbbbbbbbbbb....",
        ".bbbbbbbbbbbbbbb....",
        ".bbbbbbbbbbbbbbb....",
        ".bbbbbbbbbbbbbbb....",
        "..bbbbbbbbbbbbbbb...",
        "...bbbbbbbbbbbbbbb..",
        "..bbbbbbbbbbbbbbbbb.",
        "..bbbbbbbbbbbbbbbbb.",
        ".bbbbbbbbbbbbbbbbb..",
        ".bbbbbbbbbbbbbbbbb..",
        ".bbbbbbbbbbbbbbbbb..",
        "..bbbbbbbbbbbbbbb...",
        "...bbbbbbbbbbbbb....",
        "...bbbbbbbbbbbbb....",
        "....bbbbbbbbbbb.....",
    ],
    # 魔狼芬里尔：巨狼呲牙，血红眼
    "fenrir": [
        "bb..............bbb",
        "bbbb..bbbbbbbbbbbbb",
        "bebbbbbbbbbbbbbbbbb",
        "brbbbbbbbbbbbbbbbbb",
        ".bbbbbbbbbbbbbbbbb.",
        "..bbbbbbbbbbbbbbb..",
        "..bbbbbbbbbbbbbbb..",
        "...bbbbbbbbbbbbb...",
        "...bbb.bbbb.bbbb...",
        "....bb...bb..bbb...",
        "...bbb...bb..bbb...",
        "...bb....bb...bb...",
        "..bbb....bb...bb...",
        "..bb.....bb...bbb..",
        ".bbb.....bb...bbb..",
        ".bb......bb....bb..",
    ],
}

# ================================================================ 公共接口
def bake_enemy_sprite(kind, radius):
    art = ART.get(kind)
    if art is None:                      # 未配点阵的敌型兜底为旧圆形
        from fx import bake_circle
        return bake_circle(radius, ENEMIES[kind]["color"])
    return _bake(art, ENEMIES[kind]["color"], _scale_for(art, radius))


def bake_boss_sprite(kind, radius):
    art = BOSS_ART.get(kind)
    if art is None:
        from fx import bake_circle
        return bake_circle(radius, BOSSES[kind]["color"],
                           outline=(255, 120, 120))
    return _bake(art, BOSSES[kind]["color"], _scale_for(art, radius))


def bake_mimic_pair(radius):
    dorm, awake = MIMIC_ART
    base = ENEMIES["mimic"]["color"]
    return (_bake(dorm, base, _scale_for(dorm, radius)),
            _bake(awake, base, _scale_for(awake, radius)))
