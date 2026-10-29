# -*- coding: utf-8 -*-
"""武器系统：dispatch table + 12 种武器行为。

武器数值全部来自 data.WEAPONS；本文件只实现"怎么打"。
新增 kind 步骤：data.py 加条目 -> 这里加一个 _fire_xxx 并注册进 _FIRE。
"""
import math
import random

import pygame

from data import WEAPONS, WEAPON_MAX_LEVEL, EVOLUTIONS
from settings import COL, PHASE3
from entities import Ally, Swing
import fx


# ---------------------------------------------------------------- 弹体
class Bullet:
    """直线弹（战斧/冈格尼尔/寒冬之弓）。rot_speed>0 时自旋。"""
    __slots__ = ("x", "y", "vx", "vy", "damage", "pierce", "size", "life",
                 "angle", "rot_speed", "hit", "rot_cache", "kind",
                 "slow_amt", "slow_dur", "lifesteal", "boom_radius")

    def __init__(self, x, y, angle, st, rot_cache, rot_speed=0.0, kind="axe"):
        self.x, self.y = x, y
        sp = st["speed"]
        self.vx, self.vy = math.cos(angle) * sp, math.sin(angle) * sp
        self.damage = st["damage"]
        self.pierce = st["pierce"]
        self.size = st["size"]
        self.life = st["lifetime"]
        self.angle = math.degrees(angle)
        self.rot_speed = rot_speed
        self.hit = set()
        self.rot_cache = rot_cache
        self.kind = kind
        self.slow_amt = st.get("slow_amt", 0.0)
        self.slow_dur = st.get("slow_dur", 0.0)
        self.lifesteal = st.get("lifesteal", 0)
        self.boom_radius = st.get("boom_radius", 0.0)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.rot_speed:
            self.angle += self.rot_speed * dt

    def dead(self):
        return self.life <= 0 or self.pierce <= 0

    def draw(self, surf, cx, cy, w, h):
        sx, sy = self.x - cx, self.y - cy
        if -40 <= sx <= w + 40 and -40 <= sy <= h + 40:
            img = self.rot_cache.get(self.angle)
            surf.blit(img, (int(sx - img.get_width() / 2), int(sy - img.get_height() / 2)))


class HomingBullet:
    """追踪弹（渡鸦）：朝当前目标转向。lifesteal>0 时命中吸血（进化后）。"""
    __slots__ = ("x", "y", "vx", "vy", "damage", "pierce", "size", "life",
                 "speed", "target", "hit", "spr", "angle", "lifesteal")

    TURN = 7.0   # rad/s 转向速率

    def __init__(self, x, y, st, target):
        self.x, self.y = x, y
        self.speed = st["speed"]
        a = random.uniform(0, math.tau)
        self.vx, self.vy = math.cos(a) * self.speed, math.sin(a) * self.speed
        self.damage = st["damage"]
        self.pierce = st["pierce"]
        self.size = st["size"]
        self.life = st["lifetime"]
        self.target = target
        self.hit = set()
        self.spr = _SPR["raven"]
        self.angle = 0.0
        self.lifesteal = st.get("lifesteal", 0)

    def update(self, dt, game):
        if self.target is not None and self.target.hp <= 0:
            self.target = None
        if self.target is None:
            self.target = game.nearest_enemy(self.x, self.y, 700.0)
        if self.target is not None:
            want = math.atan2(self.target.y - self.y, self.target.x - self.x)
            cur = math.atan2(self.vy, self.vx)
            d = (want - cur + math.pi) % math.tau - math.pi
            cur += max(-self.TURN * dt, min(self.TURN * dt, d))
            self.vx, self.vy = math.cos(cur) * self.speed, math.sin(cur) * self.speed
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        self.angle = math.degrees(math.atan2(self.vy, self.vx))

    def dead(self):
        return self.life <= 0 or self.pierce <= 0

    def draw(self, surf, cx, cy, w, h):
        sx, sy = self.x - cx, self.y - cy
        if -40 <= sx <= w + 40 and -40 <= sy <= h + 40:
            img = _ROT["raven"].get(self.angle)
            surf.blit(img, (int(sx - img.get_width() / 2), int(sy - img.get_height() / 2)))


class OrbitBlade:
    """环绕体（雷锤/海拉之镰）：由武器每帧摆位，tick 制伤害。"""
    __slots__ = ("x", "y")

    def __init__(self):
        self.x = self.y = 0.0


# ---------------------------------------------------------------- 武器
# 环绕型 kind（持续存在，不走 _FIRE 计时开火）
ORBIT_KINDS = ("orbit", "scythe")
# 环绕体渲染的旋转速度（度/秒）
_ORBIT_VIS_SPIN = {"orbit": 240.0, "scythe": 120.0}


class Weapon:
    def __init__(self, key):
        self.key = key
        self.d = WEAPONS[key]
        self.level = 1
        self.timer = 0.35          # 起手延迟
        self.orbit_angle = 0.0
        self.hammers = []
        self.evolved = False       # 进化形态

    @property
    def display_name(self):
        if self.evolved:
            return EVOLUTIONS[self.key]["name"]
        return self.d["name"]

    # 合成当前等级数值：base + 各级增量（+ 进化加成）
    def stats(self):
        st = dict(self.d["base"])
        for inc in self.d["levels"][:self.level]:
            for k, v in inc.items():
                st[k] = st.get(k, 0) + v
        if self.evolved:
            for k, v in EVOLUTIONS[self.key]["bonus"].items():
                st[k] = st.get(k, 0) + v
        return st

    def can_upgrade(self):
        return self.level < WEAPON_MAX_LEVEL

    def upgrade(self):
        self.level += 1

    def level_desc(self):
        return f"Lv{self.level}/{WEAPON_MAX_LEVEL}"

    def update(self, game, dt):
        st = self.stats()
        kind = self.d["kind"]

        if kind in ORBIT_KINDS:
            self._update_orbit(game, st, dt)
            return

        self.timer -= dt
        if self.timer > 0:
            return
        fired = _FIRE[kind](game, self, st)
        if fired:
            self.timer = st["cooldown"] * game.cdr_mult()
        else:
            self.timer = 0.1       # 没目标，稍后再试

    # ---- 环绕型（雷锤/镰刀）----
    def _update_orbit(self, game, st, dt):
        while len(self.hammers) < st["count"]:
            self.hammers.append(OrbitBlade())
        while len(self.hammers) > st["count"]:
            self.hammers.pop()
        p = game.player
        self.orbit_angle += st["speed"] * dt
        n = len(self.hammers)
        for i, h in enumerate(self.hammers):
            a = self.orbit_angle + i * math.tau / n
            h.x = p.x + math.cos(a) * st["radius"]
            h.y = p.y + math.sin(a) * st["radius"]
        # tick 伤害
        self.timer -= dt
        if self.timer <= 0:
            self.timer = st["cooldown"]
            hs = st["size"]
            for h in self.hammers:
                for e in game.hash.query(h.x, h.y, hs + 30):
                    dx, dy = e.x - h.x, e.y - h.y
                    if dx * dx + dy * dy <= (hs + e.radius) ** 2:
                        game.deal_damage(e, st["damage"])
                        if st.get("lifesteal"):
                            p.hp = min(p.hp_max, p.hp + st["lifesteal"])

    def draw(self, surf, game, cx, cy, vw, vh, t):
        """持久型武器自绘（环绕锤/镰）。"""
        kind = self.d["kind"]
        if kind not in ORBIT_KINDS:
            return
        spr_key = "hammer" if kind == "orbit" else "scythe"
        spin = _ORBIT_VIS_SPIN[kind]
        for hm in self.hammers:
            sx, sy = hm.x - cx, hm.y - cy
            if -40 <= sx <= vw + 40 and -40 <= sy <= vh + 40:
                ang = (t * spin) % 360
                img = _ROT[spr_key].get(ang)
                surf.blit(img, (int(sx - img.get_width() / 2),
                                int(sy - img.get_height() / 2)))


# ================================================================ 开火 handlers
def _aimed_spread(game, p, st, rot_key, rot_speed, spread, aim):
    """共用：沿 aim 方向扇形发射 n 发直线弹。"""
    n = st["count"]
    for i in range(n):
        a = aim + (i - (n - 1) / 2) * spread
        game.projectiles.append(Bullet(p.x, p.y, a, st, _ROT[rot_key],
                                       rot_speed=rot_speed, kind=rot_key))


def _fire_axe(game, w, st):
    p = game.player
    tgt = game.nearest_enemy(p.x, p.y, 900.0)
    aim = math.atan2(tgt.y - p.y, tgt.x - p.x) if tgt else p.facing
    _aimed_spread(game, p, st, "axe", 620.0, 0.22, aim)
    return True


def _fire_spear(game, w, st):
    p = game.player
    tgt = game.strongest_enemy()
    if tgt is None:
        return False
    aim = math.atan2(tgt.y - p.y, tgt.x - p.x)
    _aimed_spread(game, p, st, "spear", 0.0, 0.30, aim)
    game.shake.add(0.12)
    return True


def _fire_arrow(game, w, st):
    """寒冬之弓：瞄准最近敌人，命中减速。"""
    p = game.player
    tgt = game.nearest_enemy(p.x, p.y, 900.0)
    if tgt is None:
        return False
    aim = math.atan2(tgt.y - p.y, tgt.x - p.x)
    _aimed_spread(game, p, st, "arrow", 0.0, 0.18, aim)
    return True


def _fire_homing(game, w, st):
    p = game.player
    n = st["count"]
    for _ in range(n):
        tgt = game.random_enemy_near(p.x, p.y, 700.0)
        if tgt is None:
            return False
        game.projectiles.append(HomingBullet(p.x, p.y, st, tgt))
    return True


def _fire_pulse(game, w, st):
    return _pulse_at(game, st, game.player.x, game.player.y, COL["rune"],
                     n=12, slow=False)


def _fire_frost(game, w, st):
    ok = _pulse_at(game, st, game.player.x, game.player.y, COL["frost"],
                   n=16, slow=True)
    return ok


def _pulse_at(game, st, x, y, color, n=12, slow=False):
    r = st["radius"]
    game.pulses.append([x, y, 12.0, r, color, 4, 0.38])
    hits = 0
    for e in game.hash.query(x, y, r):
        dx, dy = e.x - x, e.y - y
        if dx * dx + dy * dy <= (r + e.radius) ** 2:
            game.deal_damage(e, st["damage"])
            hits += 1
            if slow:
                sb = game.boons.bonus("slow_bonus")   # 斯卡蒂·寒冬之拥
                e.apply_slow(min(0.85, 0.45 + sb), min(4.0, 2.0 + sb))
    if st.get("lifesteal") and hits:                  # 冥界余烬：命中反哺生命
        p = game.player
        p.hp = min(p.hp_max, p.hp + st["lifesteal"] * hits)
    game.particles.ring(x, y, color, n=n, speed=220, life=0.4, size=3)
    return True


def _fire_ally(game, w, st):
    """维京号角：召唤/续期英灵战士。"""
    p = game.player
    game.particles.ring(p.x, p.y, (150, 200, 255), n=14, speed=200,
                        life=0.4, size=3)
    for a in game.allies:            # 续期在场英灵
        a.life = max(a.life, st["lifetime"] * 0.6)
    while len(game.allies) < min(st["count"], PHASE3["ally_cap"]):
        ang = random.uniform(0, math.tau)
        game.allies.append(Ally(p.x + math.cos(ang) * 40,
                                p.y + math.sin(ang) * 40,
                                st["damage"], st["speed"], st["lifetime"]))
    return True


def _fire_melee(game, w, st):
    """诅咒之刃：身前扇形横斩 + 吸血。"""
    p = game.player
    tgt = game.nearest_enemy(p.x, p.y, st["radius"] + 60)
    aim = math.atan2(tgt.y - p.y, tgt.x - p.x) if tgt else p.facing
    r = st["radius"]
    arc = 1.05
    game.swings.append(Swing(p.x, p.y, aim, r, st.get("lifetime", 0.15), arc))
    dealt = 0.0
    for e in game.hash.query(p.x, p.y, r):
        dx, dy = e.x - p.x, e.y - p.y
        d = math.hypot(dx, dy)
        if d <= r + e.radius:
            da = (math.atan2(dy, dx) - aim + math.pi) % math.tau - math.pi
            if abs(da) <= arc:
                dealt += game.deal_damage(e, st["damage"])
    if dealt > 0 and st.get("lifesteal_pct"):
        p.hp = min(p.hp_max, p.hp + dealt * st["lifesteal_pct"])
    return True


def _fire_quake(game, w, st):
    """地裂斩：在最近敌群脚下崩裂（多目标）。"""
    p = game.player
    targets = []
    pool = sorted(game.enemies, key=lambda e: (e.x - p.x) ** 2 + (e.y - p.y) ** 2)
    for e in pool:
        if all((e.x - t[0]) ** 2 + (e.y - t[1]) ** 2 > 160 ** 2 for t in targets):
            targets.append((e.x, e.y))
        if len(targets) >= st["count"]:
            break
    if not targets:
        return False
    for x, y in targets:
        _quake_at(game, st, x, y)
    return True


def _quake_at(game, st, x, y):
    r = st["radius"]
    game.pulses.append([x, y, 14.0, r, (255, 160, 90), 5, 0.45])
    game.particles.burst(x, y, (170, 110, 70), n=14, speed=240, life=0.5, size=4)
    game.shake.add(0.2)
    for e in game.hash.query(x, y, r):
        dx, dy = e.x - x, e.y - y
        if dx * dx + dy * dy <= (r + e.radius) ** 2:
            game.deal_damage(e, st["damage"])


def _fire_boom(game, w, st):
    """炸药桶：朝最近敌掷出旋转桶身，命中引爆 AOE。"""
    p = game.player
    tgt = game.nearest_enemy(p.x, p.y, 620.0)
    if tgt is None:
        return False
    a = math.atan2(tgt.y - p.y, tgt.x - p.x)
    game.projectiles.append(Bullet(p.x, p.y, a, st, _ROT["axe"],
                                   rot_speed=220.0, kind="boom"))
    return True


def _fire_smash(game, w, st):
    """食人妖重锤：以自身为中心重击 + 击退。"""
    p = game.player
    r = st["radius"]
    game.pulses.append([p.x, p.y, 16.0, r, (255, 200, 120), 5, 0.4])
    game.particles.ring(p.x, p.y, (255, 200, 120), n=16, speed=260, life=0.4, size=4)
    game.shake.add(0.25)
    kb = st.get("knockback", 0.0)
    for e in game.hash.query(p.x, p.y, r):
        dx, dy = e.x - p.x, e.y - p.y
        d = math.hypot(dx, dy)
        if d <= r + e.radius:
            game.deal_damage(e, st["damage"])
            if kb and not e.boss:
                nx, ny = (dx / d if d else 1.0), (dy / d if d else 0.0)
                e.x += nx * kb
                e.y += ny * kb
                e.apply_slow(0.4, 0.5)
    return True


_FIRE = {
    "axe": _fire_axe,
    "spear": _fire_spear,
    "arrow": _fire_arrow,
    "homing": _fire_homing,
    "pulse": _fire_pulse,
    "frost": _fire_frost,
    "ally": _fire_ally,
    "melee": _fire_melee,
    "quake": _fire_quake,
    "smash": _fire_smash,
    "boom": _fire_boom,
}


def rot_cache(kind):
    """按 kind 取旋转帧缓存（技能弹体复用武器精灵）。"""
    return _ROT[kind]


# ---------------------------------------------------------------- 精灵
_SPR = {}
_ROT = {}


def init_sprites():
    if _SPR:
        return
    _SPR["axe"] = fx.bake_axe(16, (205, 214, 228))
    _ROT["axe"] = fx.RotCache(_SPR["axe"], 24)
    _SPR["hammer"] = fx.bake_hammer(14, (235, 200, 110))
    _ROT["hammer"] = fx.RotCache(_SPR["hammer"], 16)
    _SPR["spear"] = fx.bake_spear(14, (188, 226, 255))
    _ROT["spear"] = fx.RotCache(_SPR["spear"], 24)
    _SPR["raven"] = fx.bake_raven(10, (58, 52, 72))
    _ROT["raven"] = fx.RotCache(_SPR["raven"], 16)
    _SPR["arrow"] = fx.bake_arrow(11, (170, 220, 250))
    _ROT["arrow"] = fx.RotCache(_SPR["arrow"], 24)
    _SPR["scythe"] = fx.bake_scythe(17, (196, 130, 220))
    _ROT["scythe"] = fx.RotCache(_SPR["scythe"], 16)
