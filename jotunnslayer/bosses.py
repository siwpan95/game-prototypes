# -*- coding: utf-8 -*-
"""Boss 技能系统：按 boss key dispatch 到对应 pattern。

Boss 基础移动（追击）由 Enemy.update 处理；俯冲类位移用
Enemy.diving/dvx/dvy 直线冲刺。技能状态存 Enemy 的通用槽位：
    skill_t  距下次技能的倒计时
    sub_t    当前技能的阶段计时
    bphase   通用阶段/交替标记
"""
import math
import random

from data import BOSSES
from settings import COL
from entities import Enemy, Shockwave, BreathZone, EnemyBullet


def update_boss(game, dt):
    b = game.boss
    if b is None:
        return
    fn = _PATTERNS.get(b.key)
    if fn:
        fn(game, b, dt)


# ---------------------------------------------------------------- 尤弥尔
def _jotunn(game, b, dt):
    d = BOSSES["jotunn"]
    b.skill_t -= dt
    if b.skill_t <= 0:
        b.skill_t = d["stomp_period"]
        game.shockwaves.append(Shockwave(
            b.x, b.y, d["stomp_radius"], d["ring_speed"],
            d["stomp_dmg"], d["stomp_warn"]))
        game.shake.add(0.3)


# ---------------------------------------------------------------- 尼德霍格
def _nidhogg(game, b, dt):
    d = BOSSES["nidhogg"]
    if b.diving:                       # 俯冲流程：蓄力(dvx=0) -> 锁向冲刺 -> 落地
        b.sub_t -= dt
        if b.dvx == 0.0 and b.dvy == 0.0:
            if b.sub_t <= 0.9:         # 蓄力结束：锁定玩家方向
                p = game.player
                a = math.atan2(p.y - b.y, p.x - b.x)
                b.dvx = math.cos(a) * d["dive_speed"]
                b.dvy = math.sin(a) * d["dive_speed"]
        elif b.sub_t <= 0:             # 冲刺结束：落地 AOE
            b.diving = False
            b.dvx = b.dvy = 0.0
            game.pulses.append([b.x, b.y, 20.0, d["dive_radius"],
                                (255, 120, 50), 5, 0.4])
            game.particles.burst(b.x, b.y, (255, 150, 60), n=18,
                                 speed=280, life=0.5, size=5)
            game.shake.add(0.5)
            p = game.player
            if math.hypot(p.x - b.x, p.y - b.y) <= d["dive_radius"] + p.radius:
                if game.hurt_player(d["dive_dmg"]):
                    game.hurt_flash = 0.4
        return

    b.skill_t -= dt
    if b.skill_t <= 0:
        if b.bphase == 1:              # 扇形喷吐
            b.bphase = 2
            b.skill_t = d["breath_period"]
            p = game.player
            ang = math.atan2(p.y - b.y, p.x - b.x)
            game.breaths.append(BreathZone(
                b.x, b.y, ang, d["breath_range"], d["breath_arc"],
                d["breath_warn"] + d["breath_dur"], d["breath_dps"],
                warn=d["breath_warn"]))
            game.shake.add(0.15)
        else:                          # 蓄力俯冲
            b.bphase = 1
            b.skill_t = d["dive_period"]
            b.diving = True
            b.sub_t = d["dive_charge"] + 0.9
            b.dvx = b.dvy = 0.0        # 蓄力阶段原地


# ---------------------------------------------------------------- 约尔曼冈德
def _jormungandr(game, b, dt):
    d = BOSSES["jormungandr"]
    b.skill_t -= dt
    if b.skill_t <= 0:
        if b.bphase == 1:              # 环形水刃
            b.bphase = 2
            b.skill_t = d["blade_period"]
            n = d["blade_count"]
            off = random.uniform(0, math.tau / n)
            for i in range(n):
                a = off + i * math.tau / n
                game.enemy_bullets.append(EnemyBullet(
                    b.x, b.y, math.cos(a) * d["blade_speed"],
                    math.sin(a) * d["blade_speed"], d["blade_dmg"],
                    size=8, life=5.0, color=(90, 200, 190)))
        else:                          # 蛇形突进
            b.bphase = 1
            b.skill_t = d["lunge_period"]
            p = game.player
            a = math.atan2(p.y - b.y, p.x - b.x)
            b.diving = True
            b.sub_t = 0.55
            b.dvx = math.cos(a) * d["lunge_speed"]
            b.dvy = math.sin(a) * d["lunge_speed"]
    if b.diving:
        b.sub_t -= dt
        if b.sub_t <= 0:
            b.diving = False


# ---------------------------------------------------------------- 芬里尔
def _fenrir(game, b, dt):
    d = BOSSES["fenrir"]
    ratio = b.hp / b.hp_max
    if b.bphase == 1 and ratio < d["phase2_hp"]:
        b.bphase = 2
        b.speed *= 1.25
        _howl(game, b, d)
    elif b.bphase == 2 and ratio < d["phase3_hp"]:
        b.bphase = 3
        b.speed *= 1.3
        _howl(game, b, d)

    if b.diving:
        b.sub_t -= dt
        if b.sub_t <= 0:
            b.diving = False
        return
    b.skill_t -= dt
    if b.skill_t <= 0:
        b.skill_t = d["bite_period"]
        p = game.player
        a = math.atan2(p.y - b.y, p.x - b.x)
        b.diving = True
        b.sub_t = 0.4
        b.dvx = math.cos(a) * d["bite_speed"]
        b.dvy = math.sin(a) * d["bite_speed"]


def _howl(game, b, d):
    """魔狼嚎叫：召唤狼群 + 屏震。"""
    game.shake.add(0.6)
    game.pulses.append([b.x, b.y, 20.0, 240.0, COL["boss"], 4, 0.5])
    for _ in range(d.get("summon_wolves", 5)):
        a = random.uniform(0, math.tau)
        r = random.uniform(60.0, 140.0)
        game.enemies.append(Enemy("wolf", b.x + math.cos(a) * r,
                                  b.y + math.sin(a) * r, 1.0))


_PATTERNS = {
    "jotunn": _jotunn,
    "nidhogg": _nidhogg,
    "jormungandr": _jormungandr,
    "fenrir": _fenrir,
}
