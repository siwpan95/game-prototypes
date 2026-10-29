# -*- coding: utf-8 -*-
"""角色主动技（Phase 4）：按 skill.kind dispatch 到技能实现。

数值来自 data.CHARS[char]["skill"]；Q 键触发，冷却与全局 CDR 联动。
"""
import math

from weapons import Bullet, rot_cache


def cast(game):
    """施放当前角色主动技。冷却判定在 Game 层（skill_t<=0 才进这里）。"""
    fn = _SKILLS.get(game.skill_cfg["kind"])
    if fn:
        fn(game, game.skill_cfg)
        game.bus.emit("skill_cast", dict(kind=game.skill_cfg["kind"]))


def _berserk(game, cfg):
    """屠魔·狂暴：攻速提升 + 受伤加深（Player.berserk_t 驱动）。"""
    p = game.player
    p.berserk_t = cfg["dur"]
    game.particles.ring(p.x, p.y, (230, 96, 60), n=26, speed=250, life=0.5, size=4)
    game.shake.add(0.25)
    game._floater("狂暴！", (230, 96, 60), 26)


def _icespear(game, cfg):
    """战巫·冰锥：锁定最强敌的大号冰锥（复用直线弹 + 减速字段）。"""
    p = game.player
    tgt = game.strongest_enemy() or game.nearest_enemy(p.x, p.y, 1e9)
    if tgt is None:
        return
    a = math.atan2(tgt.y - p.y, tgt.x - p.x)
    st = dict(speed=760.0, damage=cfg["dmg"], pierce=1, size=26,
              lifetime=1.8, slow_amt=cfg["slow"], slow_dur=cfg["slow_dur"])
    game.projectiles.append(Bullet(p.x, p.y, a, st, rot_cache("spear"),
                                   kind="spear"))
    game.particles.burst(p.x, p.y, (170, 220, 255), n=12, speed=220,
                         life=0.35, size=4)


def _shieldbash(game, cfg):
    """盾卫·盾击：向前猛冲 + 击晕震退周围敌人。"""
    p = game.player
    r = cfg["radius"]
    p.x += math.cos(p.facing) * cfg["dash"]
    p.y += math.sin(p.facing) * cfg["dash"]
    game.pulses.append([p.x, p.y, 20.0, r, (140, 230, 170), 5, 0.4])
    game.particles.ring(p.x, p.y, (140, 230, 170), n=18, speed=300,
                        life=0.45, size=4)
    game.shake.add(0.3)
    # 直接扫描敌人列表：施放是瞬发一次性，不与哈希重建时机耦合
    for e in game.enemies:
        dx, dy = e.x - p.x, e.y - p.y
        d = math.hypot(dx, dy) or 1.0
        if d <= r + e.radius:
            game.deal_damage(e, cfg["dmg"])
            e.apply_slow(cfg["stun"], cfg["stun_dur"])     # 击晕 = 近乎定身
            if not e.boss:
                e.x += dx / d * 140.0
                e.y += dy / d * 140.0


_SKILLS = {
    "berserk": _berserk,
    "icespear": _icespear,
    "shieldbash": _shieldbash,
}
