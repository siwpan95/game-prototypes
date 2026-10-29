# -*- coding: utf-8 -*-
"""实体：玩家 / 敌人（含精英、Boss）/ 经验宝石。"""
import math
import random

import pygame

from settings import PLAYER, COL, PHASE3
from data import ENEMIES, ELITE, BOSSES, PASSIVES
import fx


# ---------------------------------------------------------------- 玩家
class Player:
    def __init__(self, x, y, hp=None):
        self.x, self.y = x, y
        self.hp_max = hp if hp else PLAYER["hp"]     # 角色表可覆盖
        self.hp = self.hp_max
        self.berserk_t = 0.0   # 屠魔·狂暴剩余时长（攻速+ / 受伤+）
        # 跨局技能树 meta 加成（Game.reset 里按存档等级填入）
        self.dmg_bonus = 0.0
        self.cdr_bonus = 0.0
        self.speed_bonus = 0.0
        self.skill_cd_bonus = 0.0
        self.pickup_bonus = 0.0
        self.crit_bonus = 0.0
        self.xp_bonus = 0.0
        self.base_speed = PLAYER["speed"]
        self.radius = PLAYER["radius"]
        self.base_pickup = PLAYER["pickup_radius"]
        self.iframes = 0.0
        self.facing = 0.0            # 弧度，渲染朝向
        self.regen_acc = 0.0
        self.slow_t = 0.0            # 寒冰巨蛇光环等对玩家的减速
        self.slow_amt = 0.0

        # 被动层数 -> 全局加成
        self.passives = {k: 0 for k in PASSIVES}

        # 烘焙外观：俯视维京（身体+角盔+朝向标记）
        r = self.radius
        body = fx.bake_circle(r, (60, 66, 84), eyes=((238, 240, 246), 0.18, 0.34))
        helm = pygame.Surface((r * 2 + 10, r * 2 + 10), pygame.SRCALPHA)
        c = helm.get_width() // 2
        pygame.draw.circle(helm, COL["player_helm"], (c, c - r // 3), int(r * 0.9))
        pygame.draw.polygon(helm, (222, 226, 236), [(c - r, c - r // 2), (c - r // 2, c - r), (c - r // 3, c - r // 2)])
        pygame.draw.polygon(helm, (222, 226, 236), [(c + r, c - r // 2), (c + r // 2, c - r), (c + r // 3, c - r // 2)])
        self.spr_body = body
        self.spr_helm = helm
        self.spr_face = pygame.Surface((26, 18), pygame.SRCALPHA)
        pygame.draw.polygon(self.spr_face, COL["accent"], [(26, 9), (4, 0), (4, 18)])

    # ---- 被动加成 ----
    def dmg_mult(self):
        m = 1.0 + PASSIVES["might"]["stack"] * self.passives["might"]
        return m * (1.0 + self.dmg_bonus)

    def cooldown_mult(self):
        m = max(0.35, 1.0 - PASSIVES["haste"]["stack"] * self.passives["haste"])
        if self.berserk_t > 0:                       # 狂暴：攻速 +30%
            m *= 0.70
        m *= 1.0 - self.cdr_bonus
        return max(0.30, m)

    def speed(self):
        return (self.base_speed * (1.0 + PASSIVES["swift"]["stack"] * self.passives["swift"])
                * (1.0 + self.speed_bonus))

    def pickup_radius(self):
        return (self.base_pickup * (1.0 + PASSIVES["magnet"]["stack"] * self.passives["magnet"])
                * (1.0 + self.pickup_bonus))

    def add_passive(self, key):
        self.passives[key] += 1
        if key == "vigor":
            self.hp_max += PASSIVES["vigor"]["stack"]
            self.hp = min(self.hp_max, self.hp + PASSIVES["vigor"]["stack"])

    # ---- 更新 ----
    def move(self, ix, iy, dt, mult=1.0):
        if ix or iy:
            m = math.hypot(ix, iy)
            slow = (1.0 - self.slow_amt) if self.slow_t > 0 else 1.0
            self.x += ix / m * self.speed() * mult * slow * dt
            self.y += iy / m * self.speed() * mult * slow * dt
            self.facing = math.atan2(iy, ix)

    def update(self, dt):
        if self.iframes > 0:
            self.iframes -= dt
        if self.berserk_t > 0:
            self.berserk_t -= dt
        if self.slow_t > 0:
            self.slow_t -= dt
            if self.slow_t <= 0:
                self.slow_amt = 0.0
        reg = PASSIVES["regen"]["stack"] * self.passives["regen"]
        if reg:
            self.regen_acc += reg * dt
            if self.regen_acc >= 1.0:
                heal = int(self.regen_acc)
                self.regen_acc -= heal
                self.hp = min(self.hp_max, self.hp + heal)

    def hurt(self, dmg):
        if self.iframes > 0:
            return False
        if self.berserk_t > 0:                       # 狂暴代价：受伤 +20%
            dmg *= 1.2
        self.hp -= dmg
        self.iframes = PLAYER["iframes"]
        return True

    def draw(self, surf, cx, cy):
        sx, sy = int(self.x - cx), int(self.y - cy)
        flick = self.iframes > 0 and (pygame.time.get_ticks() // 60) % 2 == 0
        if not flick:
            surf.blit(self.spr_body, (sx - self.spr_body.get_width() // 2,
                                      sy - self.spr_body.get_height() // 2))
            surf.blit(self.spr_helm, (sx - self.spr_helm.get_width() // 2,
                                      sy - self.spr_helm.get_height() // 2))
        face = pygame.transform.rotate(self.spr_face, -math.degrees(self.facing))
        surf.blit(face, (sx - face.get_width() // 2, sy - face.get_height() // 2))


# ---------------------------------------------------------------- 敌人
class Enemy:
    __slots__ = ("key", "name", "x", "y", "hp", "hp_max", "speed", "dmg", "radius",
                 "xp", "elite", "boss", "slow_t", "slow_amt", "phase", "tick_flash",
                 "spr", "spr_rect", "wobble", "doom_t", "doom_dmg",
                 # Phase 3 行为配置与状态
                 "b_ranged", "b_bomber", "b_healer", "b_aura", "b_vamp",
                 "ai_t", "fuse_t", "dash_t", "heal_cd",
                 # 宝箱怪伪装状态 + 像素精灵双形态
                 "b_mimic", "awake", "spr_dormant", "spr_awake",
                 # Boss 技能状态（bosses.py 使用）
                 "skill_t", "sub_t", "bphase", "dvx", "dvy", "diving", "vx", "vy")

    def __init__(self, key, x, y, hp_scale=1.0, elite=False, is_boss=False,
                 boss_key=None):
        d = BOSSES[boss_key or key] if is_boss else ENEMIES[key]
        self.key = key
        self.name = d["name"]
        self.x, self.y = x, y
        m = ELITE if elite else {}
        self.hp_max = int(d["hp"] * hp_scale * m.get("hp_mult", 1.0))
        self.hp = self.hp_max
        self.speed = d["speed"] * m.get("speed_mult", 1.0)
        self.dmg = d["dmg"]
        self.radius = int(d["radius"] * m.get("size_mult", 1.0))
        self.xp = m.get("xp", d["xp"]) if elite else d["xp"]
        self.elite = elite
        self.boss = is_boss
        self.slow_t = 0.0
        self.slow_amt = 0.0
        self.phase = random.uniform(0, math.tau) if d.get("sine") else 0.0
        self.tick_flash = 0.0
        self.wobble = random.uniform(0, math.tau)
        self.doom_t = 0.0          # 洛基·厄运标记倒计时（>0 = 已标记）
        self.doom_dmg = 0.0

        # Phase 3 行为配置
        self.b_ranged = d.get("ranged")
        self.b_bomber = d.get("bomber")
        self.b_healer = d.get("healer")
        self.b_aura = d.get("aura")
        self.b_vamp = d.get("vampire")
        self.b_mimic = d.get("mimic")
        self.awake = False
        self.ai_t = random.uniform(0.5, 2.0)
        self.fuse_t = -1.0         # >=0 = 引信已点燃
        self.dash_t = 0.0
        self.heal_cd = 0.0
        self.vx = self.vy = 0.0
        # Boss 状态
        self.skill_t = 2.0
        self.sub_t = 0.0
        self.bphase = 1
        self.dvx = self.dvy = 0.0
        self.diving = False

        # 外观烘焙：像素风独立剪影（无点阵的敌型兜底旧圆形）
        import pixel_art
        if is_boss:
            self.spr = pixel_art.bake_boss_sprite(boss_key or key, self.radius)
        else:
            self.spr = pixel_art.bake_enemy_sprite(key, self.radius)
        self.spr_dormant = None
        self.spr_awake = None
        if self.b_mimic:
            self.spr_dormant, self.spr_awake = pixel_art.bake_mimic_pair(self.radius)
        self.spr_rect = self.spr.get_rect()

    # ---- 行为 ----
    def update(self, game, dt):
        p = game.player
        dx, dy = p.x - self.x, p.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        sp = self.speed * (1.0 - self.slow_amt if self.slow_t > 0 else 1.0)
        vx, vy = 0.0, 0.0

        if self.diving:            # Boss 俯冲：锁定方向直线冲
            self.x += self.dvx * dt
            self.y += self.dvy * dt
            self._tick_common(dt)
            return

        if self.b_ranged:          # 哥布林射手：保持射程 + 侧移 + 射击
            rg = self.b_ranged["range_"]
            if dist > rg + 40:
                vx, vy = dx / dist * sp, dy / dist * sp
            elif dist < rg - 40:
                vx, vy = -dx / dist * sp, -dy / dist * sp
            else:
                vx, vy = -dy / dist * sp * 0.7, dx / dist * sp * 0.7
            self.ai_t -= dt
            if self.ai_t <= 0:
                self.ai_t = self.b_ranged["cd"]
                if len(game.enemy_bullets) < PHASE3["enemy_bullet_cap"]:
                    bs = self.b_ranged["bullet_speed"]
                    a = math.atan2(dy, dx)
                    game.enemy_bullets.append(EnemyBullet(
                        self.x, self.y, math.cos(a) * bs, math.sin(a) * bs,
                        self.b_ranged["bullet_dmg"]))
        elif self.b_bomber:        # 自爆尸鬼：冲脸点燃引信
            if self.fuse_t < 0 and dist < self.b_bomber["trigger"]:
                self.fuse_t = self.b_bomber["fuse"]
            if self.fuse_t >= 0:
                self.fuse_t = max(0.0, self.fuse_t - dt)   # 钳在 0 触发爆炸
                sp2 = sp * 0.4     # 点燃后减速
                vx, vy = dx / dist * sp2, dy / dist * sp2
            else:
                vx, vy = dx / dist * sp, dy / dist * sp
        elif self.b_healer:        # 哀嚎女妖：后排盘旋 + 治疗友军
            if dist > 260.0:
                vx, vy = dx / dist * sp, dy / dist * sp
            else:
                vx, vy = -dy / dist * sp, dx / dist * sp
            self.heal_cd -= dt
            if self.heal_cd <= 0:
                self.heal_cd = self.b_healer["cd"]
                hr = self.b_healer["radius"]
                healed = False
                for e in game.hash.query(self.x, self.y, hr):
                    if e is not self and e.hp > 0 and e.hp < e.hp_max:
                        if math.hypot(e.x - self.x, e.y - self.y) <= hr:
                            e.hp = min(e.hp_max, e.hp + self.b_healer["heal"])
                            healed = True
                if healed:
                    game.pulses.append([self.x, self.y, 10.0, hr,
                                        (92, 182, 142), 2, 0.4])
        elif self.b_vamp:          # 嗜血亲王：周期冲刺
            self.dash_t -= dt
            if self.dash_t <= 0:
                self.dash_t = self.b_vamp["dash_cd"]
                sp = self.b_vamp["dash_speed"]
            vx, vy = dx / dist * sp, dy / dist * sp
        elif self.b_mimic:         # 宝箱怪：潜伏伪装，接近后惊醒扑咬
            if not self.awake:
                if dist < self.b_mimic["wake"]:
                    self.awake = True
                    game._floater("宝箱怪惊醒！", (255, 150, 60), 20,
                                  self.x, self.y - self.radius - 10)
                    game.bus.emit("mimic_wake", dict())
                else:
                    self._tick_common(dt)
                    return
            vx, vy = dx / dist * sp * 4.0, dy / dist * sp * 4.0
        else:                      # 基础追击
            vx, vy = dx / dist * sp, dy / dist * sp

        if self.phase:             # 怨灵蛇形漂移
            perp = (-dy / dist, dx / dist)
            s = math.sin(self.phase + pygame.time.get_ticks() * 0.004) * sp * 0.7
            vx += perp[0] * s
            vy += perp[1] * s

        self.x += vx * dt
        self.y += vy * dt

        # 寒冰巨蛇光环：持续减速玩家
        if self.b_aura and dist < self.b_aura["radius"]:
            game.player_aura_slow = max(game.player_aura_slow,
                                        self.b_aura["slow"])
        self._tick_common(dt)

    def _tick_common(self, dt):
        if self.slow_t > 0:
            self.slow_t -= dt
            if self.slow_t <= 0:
                self.slow_amt = 0.0
        if self.tick_flash > 0:
            self.tick_flash -= dt

    def apply_slow(self, amount, duration):
        if amount >= self.slow_amt or self.slow_t <= 0:
            self.slow_amt = max(self.slow_amt, amount)
        self.slow_t = max(self.slow_t, duration)

    def draw(self, surf, cx, cy):
        sx = int(self.x - cx - self.spr_rect.w / 2)
        sy = int(self.y - cy - self.spr_rect.h / 2)
        bob = int(math.sin(pygame.time.get_ticks() * 0.006 + self.wobble) * 1.5) if self.elite else 0
        spr = (self.spr_awake if (self.awake and self.spr_awake)
               else self.spr_dormant or self.spr)
        surf.blit(spr, (sx, sy + bob))
        if self.elite:               # 精英橙环（旧烘焙自带，像素图改为运行期描环）
            pygame.draw.circle(surf, COL["elite_ring"],
                               (int(self.x - cx), int(self.y - cy)),
                               self.radius + 3, 2)
        if self.tick_flash > 0:      # 受击白闪
            flash = pygame.Surface(self.spr_rect.size, pygame.SRCALPHA)
            flash.fill((255, 255, 255, 90))
            surf.blit(flash, (sx, sy + bob), special_flags=pygame.BLEND_RGBA_ADD)
        if self.slow_t > 0:          # 冻结描边
            pygame.draw.circle(surf, COL["frost"],
                               (int(self.x - cx), int(self.y - cy)), self.radius + 2, 2)
        if self.doom_t > 0:          # 厄运标记：红色收缩环
            k = max(0.12, self.doom_t / 3.0)
            pygame.draw.circle(surf, (255, 96, 72),
                               (int(self.x - cx), int(self.y - cy)),
                               int(self.radius + 10 * k), 2)


# ---------------------------------------------------------------- Boss 跺地冲击波
class Shockwave:
    __slots__ = ("x", "y", "r", "max_r", "speed", "dmg", "hit", "warn")

    def __init__(self, x, y, max_r, speed, dmg, warn):
        self.x, self.y = x, y
        self.r = 0.0
        self.max_r = max_r
        self.speed = speed
        self.dmg = dmg
        self.hit = False
        self.warn = warn  # >0 = 前摇警示期

    def update(self, dt):
        if self.warn > 0:
            self.warn -= dt
            return False
        self.r += self.speed * dt
        return self.r >= self.max_r

    def draw(self, surf, cx, cy, w, h):
        sx, sy = self.x - cx, self.y - cy
        if not (-self.max_r < sx < w + self.max_r and -self.max_r < sy < h + self.max_r):
            return
        if self.warn > 0:
            k = 1.0 - self.warn / 0.9
            pygame.draw.circle(surf, (255, 120, 90), (int(sx), int(sy)),
                               int(self.max_r * k), 2)
        else:
            pygame.draw.circle(surf, COL["boss"], (int(sx), int(sy)), int(self.r), 5)
            pygame.draw.circle(surf, (255, 160, 120), (int(sx), int(sy)), int(self.r), 2)

    def hits(self, px, py, pr):
        if self.warn > 0 or self.hit:
            return False
        d = math.hypot(px - self.x, py - self.y)
        return abs(d - self.r) <= pr + 8


# ---------------------------------------------------------------- 经验宝石
class Gem:
    __slots__ = ("x", "y", "xp", "spr", "t", "vx", "vy")

    def __init__(self, x, y, xp):
        self.x, self.y = x, y
        self.xp = xp
        self.t = random.uniform(0, math.tau)
        if xp >= 20:
            self.spr = _GEM_BIG
        elif xp >= 5:
            self.spr = _GEM_MID
        else:
            self.spr = _GEM_SMALL
        # 出生小弹跳
        a = random.uniform(0, math.tau)
        self.vx, self.vy = math.cos(a) * 60, math.sin(a) * 60

    def update(self, dt, px, py, magnet):
        dx, dy = px - self.x, py - self.y
        d = math.hypot(dx, dy)
        if d < 0.001:                   # 与玩家完全重合：等下一帧被拾取
            return
        if d < magnet:
            pull = min(900.0, 200.0 + (magnet - d) * 6.0)
            self.x += dx / d * pull * dt
            self.y += dy / d * pull * dt
        else:
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.vx *= 0.9
            self.vy *= 0.9
        self.t += dt

    def draw(self, surf, cx, cy):
        bob = int(math.sin(self.t * 4) * 2)
        surf.blit(self.spr, (int(self.x - cx - self.spr.get_width() / 2),
                             int(self.y - cy - self.spr.get_height() / 2) + bob))


_GEM_SMALL = None
_GEM_MID = None
_GEM_BIG = None


def init_gem_sprites():
    global _GEM_SMALL, _GEM_MID, _GEM_BIG
    _GEM_SMALL = fx.bake_diamond(6, (74, 160, 255), (150, 210, 255))
    _GEM_MID = fx.bake_diamond(8, (120, 200, 90), (190, 240, 160))
    _GEM_BIG = fx.bake_diamond(11, (255, 208, 96), (255, 240, 190))


# ---------------------------------------------------------------- 神龛
class Shrine:
    """诸神神龛：走近触碰 -> 该神三张赐福卡。"""
    __slots__ = ("x", "y", "god", "color", "spr", "t", "rarity_rolls", "rerolled")

    def __init__(self, x, y, god, color):
        self.x, self.y = x, y
        self.god = god
        self.color = color
        self.t = random.uniform(0, math.tau)
        self.rerolled = False
        # 烘焙：石碑 + 神色符文
        s = pygame.Surface((56, 72), pygame.SRCALPHA)
        pygame.draw.rect(s, (64, 70, 92), (14, 10, 28, 56), border_radius=5)
        pygame.draw.rect(s, (80, 88, 112), (14, 10, 28, 9), border_radius=4)
        pygame.draw.line(s, color, (28, 24), (28, 58), 3)
        pygame.draw.line(s, color, (20, 34), (36, 34), 2)
        pygame.draw.line(s, color, (22, 46), (34, 46), 2)
        pygame.draw.ellipse(s, (46, 52, 70), (4, 60, 48, 10))
        self.spr = s

    def draw(self, surf, cx, cy, ticks):
        sx = int(self.x - cx - 28)
        sy = int(self.y - cy - 36)
        glow = 0.5 + 0.5 * math.sin(ticks * 0.003 + self.t)
        r = int(30 + 8 * glow)
        pygame.draw.circle(surf, self.color, (sx + 28, sy + 62), r, 2)
        pygame.draw.circle(surf, self.color, (sx + 28, sy + 62), r + 6, 1)
        surf.blit(self.spr, (sx, sy - int(3 * glow)))


# ---------------------------------------------------------------- 敌方弹幕
class EnemyBullet:
    """哥布林的箭 / 约尔曼冈德的水刃，共用。"""
    __slots__ = ("x", "y", "vx", "vy", "dmg", "size", "life", "color")

    def __init__(self, x, y, vx, vy, dmg, size=7, life=4.0,
                 color=(255, 120, 90)):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.dmg = dmg
        self.size = size
        self.life = life
        self.color = color

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surf, cx, cy):
        sx, sy = int(self.x - cx), int(self.y - cy)
        pygame.draw.circle(surf, self.color, (sx, sy), self.size)
        pygame.draw.circle(surf, (255, 230, 210), (sx, sy), self.size - 3)


# ---------------------------------------------------------------- 英灵战士
class Ally:
    """维京号角召唤的英灵：索敌近战，无目标时环绕主人。"""
    __slots__ = ("x", "y", "dmg", "radius", "life", "target", "tick_cd",
                 "speed", "spr", "t")

    def __init__(self, x, y, dmg, speed, lifetime):
        self.x, self.y = x, y
        self.dmg = dmg
        self.speed = speed
        self.radius = 13
        self.life = lifetime
        self.target = None
        self.tick_cd = 0.0
        self.t = random.uniform(0, math.tau)
        self.spr = fx.bake_circle(self.radius, (150, 200, 255),
                                  eyes=((240, 246, 255), 0.2, 0.34))

    def update(self, game, dt):
        self.life -= dt
        self.t += dt
        p = game.player
        # 索敌
        if self.target is not None and self.target.hp <= 0:
            self.target = None
        if self.target is None:
            self.target = game.nearest_enemy(self.x, self.y, 520.0)
        if self.target is not None:
            dx, dy = self.target.x - self.x, self.target.y - self.y
            d = math.hypot(dx, dy) or 1.0
            if d > self.target.radius + self.radius:
                self.x += dx / d * self.speed * dt
                self.y += dy / d * self.speed * dt
            else:
                self.tick_cd -= dt
                if self.tick_cd <= 0:
                    self.tick_cd = 0.4
                    game.deal_damage(self.target, self.dmg)
                    game.particles.burst(self.x, self.y, (180, 210, 255), n=3,
                                         speed=110, life=0.2, size=3)
        else:                       # 环绕主人
            a = self.t * 1.6
            tx = p.x + math.cos(a) * 62.0
            ty = p.y + math.sin(a) * 62.0
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            if d > 4:
                self.x += dx / d * self.speed * dt
                self.y += dy / d * self.speed * dt
        return self.life > 0

    def draw(self, surf, cx, cy):
        surf.blit(self.spr, (int(self.x - cx - self.spr.get_width() // 2),
                             int(self.y - cy - self.spr.get_height() // 2)))


# ---------------------------------------------------------------- 熔岩喷泉
class Geyser:
    """熔岩废土机关：周期喷发，敌我通伤。"""
    __slots__ = ("x", "y", "t", "tick")

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = random.uniform(0.0, PHASE3["geyser_cycle"])   # 相位随机化
        self.tick = 0.0

    def update(self, game, dt):
        c = PHASE3["geyser_cycle"]
        w = PHASE3["geyser_warn"]
        e = PHASE3["geyser_erupt"]
        self.t = (self.t + dt) % c
        if self.t >= c - e:                       # 喷发期
            self.tick -= dt
            if self.tick <= 0:
                self.tick = 0.4
                r = PHASE3["geyser_radius"]
                p = game.player
                if math.hypot(p.x - self.x, p.y - self.y) <= r + p.radius:
                    if game.hurt_player(PHASE3["geyser_dmg_player"]):
                        game.hurt_flash = 0.3
                for en in game.hash.query(self.x, self.y, r):
                    if math.hypot(en.x - self.x, en.y - self.y) <= r + en.radius:
                        game.deal_damage(en, PHASE3["geyser_dmg_enemy"],
                                         flat=True, proc=False)
                game.particles.burst(self.x, self.y, (255, 150, 60), n=6,
                                     speed=200, life=0.35, size=4)

    def draw(self, surf, cx, cy):
        sx, sy = int(self.x - cx), int(self.y - cy)
        c = PHASE3["geyser_cycle"]
        w = PHASE3["geyser_warn"]
        e = PHASE3["geyser_erupt"]
        t = self.t
        r = PHASE3["geyser_radius"]
        if t >= c - e:                             # 喷发：火柱
            k = 1.0 - (t - (c - e)) / e
            pygame.draw.circle(surf, (255, 120, 50), (sx, sy), int(r), 4)
            pygame.draw.circle(surf, (255, 200, 120), (sx, sy),
                               int(r * 0.55), 3)
            pygame.draw.circle(surf, (255, 240, 200), (sx, sy), int(10 + 6 * k))
        elif t >= c - e - w:                       # 预警：红圈渐显
            k = (t - (c - e - w)) / w
            pygame.draw.circle(surf, (255, 90, 60), (sx, sy), int(r),
                               max(1, int(3 * k)))
        else:                                      # 待机：暗色裂口
            pygame.draw.circle(surf, (70, 40, 30), (sx, sy), 18, 2)
            pygame.draw.circle(surf, (120, 60, 40), (sx, sy), 10, 2)


# ---------------------------------------------------------------- 近战挥砍视觉
class Swing:
    """诅咒之刃的扇形斩击弧光。"""
    __slots__ = ("x", "y", "angle", "radius", "life", "arc")

    def __init__(self, x, y, angle, radius, life=0.15, arc=1.05):
        self.x, self.y = x, y
        self.angle = angle
        self.radius = radius
        self.life = life
        self.arc = arc

    def update(self, dt):
        self.life -= dt
        return self.life > 0

    def draw(self, surf, cx, cy):
        k = max(0.0, self.life / 0.15)
        r = self.radius
        rect = pygame.Rect(int(self.x - cx - r - 6), int(self.y - cy - r - 6),
                           int(r * 2 + 12), int(r * 2 + 12))
        pygame.draw.arc(surf, (255, 240, 200), rect,
                        math.degrees(self.angle - self.arc / 2) % 360,
                        math.degrees(self.angle + self.arc / 2) % 360,
                        max(2, int(6 * k)))


# ---------------------------------------------------------------- 龙息扇形
class BreathZone:
    """尼德霍格的扇形喷吐：先预警（warn 秒不判定），再持续伤害。"""
    __slots__ = ("x", "y", "angle", "range", "arc", "life", "life0", "tick",
                 "dps", "warn")

    def __init__(self, x, y, angle, rng, arc, life, dps, warn=0.0):
        self.x, self.y = x, y
        self.angle = angle
        self.range = rng
        self.arc = arc
        self.life = life
        self.life0 = life
        self.tick = 0.0
        self.dps = dps
        self.warn = warn

    def update(self, game, dt):
        self.life -= dt
        if self.life > self.life0 - self.warn:      # 预警期不判定
            return self.life > 0
        self.tick -= dt
        if self.tick <= 0:
            self.tick = 0.3
            p = game.player
            dx, dy = p.x - self.x, p.y - self.y
            d = math.hypot(dx, dy)
            if d <= self.range + p.radius:
                da = (math.atan2(dy, dx) - self.angle + math.pi) % math.tau - math.pi
                if abs(da) <= self.arc / 2:
                    if game.hurt_player(self.dps * 0.3):
                        game.hurt_flash = 0.3
        return self.life > 0

    def draw(self, surf, cx, cy):
        k = max(0.0, min(1.0, self.life / 0.4))
        warming = self.life > self.life0 - self.warn
        alpha = 40 if warming else int(70 * k)
        pts = [(self.x - cx, self.y - cy)]
        n = 14
        for i in range(n + 1):
            a = self.angle - self.arc / 2 + self.arc * i / n
            pts.append((self.x - cx + math.cos(a) * self.range,
                        self.y - cy + math.sin(a) * self.range))
        s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        color = (255, 90, 60, alpha) if warming else (255, 130, 40, alpha)
        pygame.draw.polygon(s, color, pts)
        surf.blit(s, (0, 0))


# ---------------------------------------------------------------- 食物（Phase 5）
class Food:
    """旋转肉块：拾取回血。"""
    __slots__ = ("x", "y", "life")

    def __init__(self, x, y, life):
        self.x, self.y = x, y
        self.life = life

    def draw(self, surf, cx, cy):
        sx, sy = self.x - cx, self.y - cy
        t = pygame.time.get_ticks() * 0.004
        # 旋转的肉块：主体 + 高光，随时间旋转
        pts = []
        for i in range(4):
            a = t + i * math.pi / 2
            pts.append((sx + math.cos(a) * 12, sy + math.sin(a) * 12))
        pygame.draw.polygon(surf, (196, 74, 62), pts)
        pygame.draw.circle(surf, (232, 120, 96), (int(sx), int(sy)), 5)
        k = max(0.0, min(1.0, self.life / 5.0))      # 临消失闪烁
        if k < 0.5 and int(pygame.time.get_ticks() / 120) % 2 == 0:
            return


# ---------------------------------------------------------------- 宝箱（Phase 5）
class Chest:
    """精英掉落的宝箱：E 键开启，三选一奖励。"""
    __slots__ = ("x", "y", "opened")

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.opened = False

    def draw(self, surf, cx, cy):
        if self.opened:
            return
        sx, sy = int(self.x - cx), int(self.y - cy)
        t = pygame.time.get_ticks()
        glow = 0.5 + 0.5 * math.sin(t * 0.004)
        pygame.draw.circle(surf, (255, 208, 96), (sx, sy), 15 + int(3 * glow), 1)
        box = pygame.Rect(sx - 13, sy - 10, 26, 20)
        pygame.draw.rect(surf, (146, 104, 40), box, border_radius=4)
        pygame.draw.rect(surf, (218, 168, 72), box, 2, border_radius=4)
        pygame.draw.rect(surf, (240, 200, 110),
                         (sx - 8, sy - 4, 16, 5), border_radius=2)