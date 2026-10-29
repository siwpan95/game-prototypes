# -*- coding: utf-8 -*-
"""波次管理：时间驱动难度曲线 + 敌型解锁 + 精英定时投放 + Boss。"""
import math
import random

from settings import SPAWN, BOSS_TIME, ELITE_TIMES, GAME_MAX_SPAWN_T, DIFFICULTIES
from data import ENEMIES, MAPS
from entities import Enemy


def lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


class Spawner:
    def __init__(self):
        self.timer = 1.0
        self.elites_sent = 0
        self.boss_sent = False

    # ---- 难度曲线 ----
    @staticmethod
    def interval(t):
        return lerp(SPAWN["interval_start"], SPAWN["interval_end"],
                    t / GAME_MAX_SPAWN_T)

    @staticmethod
    def batch(t):
        return int(round(lerp(SPAWN["batch_start"], SPAWN["batch_end"],
                              t / GAME_MAX_SPAWN_T)))

    @staticmethod
    def unlocked(t):
        return [k for k, d in ENEMIES.items() if d["unlock"] <= t]

    @staticmethod
    def weights(map_key):
        """地图权重覆盖（熔岩图偏自爆/远程），否则用默认。"""
        return MAPS[map_key].get("enemy_w") or \
            {k: d["weight"] for k, d in ENEMIES.items()}

    @classmethod
    def pick_kind(cls, t, map_key="snow"):
        pool = cls.unlocked(t)
        if not pool:
            return "draugr"
        w = cls.weights(map_key)
        total = sum(w.get(k, 0) for k in pool)
        if total <= 0:
            return pool[0]
        r = random.uniform(0, total)
        acc = 0
        for k in pool:
            acc += w.get(k, 0)
            if r <= acc:
                return k
        return pool[-1]

    # ---- 主更新 ----
    def update(self, game, dt):
        t = game.time

        # Boss（无尽模式：game.next_boss_at 由 Game 层滚动推进）
        if not self.boss_sent and t >= game.next_boss_at:
            self.boss_sent = True
            game.spawn_boss()
            return

        # 精英
        while self.elites_sent < len(ELITE_TIMES) and t >= ELITE_TIMES[self.elites_sent]:
            self.elites_sent += 1
            game.spawn_elite(self.pick_kind(t, game.map_key))

        # 常规波次（出怪频率吃难度系数）
        self.timer -= dt
        if self.timer <= 0:
            self.timer = self.interval(t) * DIFFICULTIES[game.difficulty_key]["spawn_mult"]
            if len(game.enemies) < SPAWN["max_enemies"]:
                for _ in range(self.batch(t)):
                    game.spawn_enemy(self.pick_kind(t, game.map_key))

    # ---- 出怪位置：玩家屏幕外沿环带 ----
    @staticmethod
    def ring_pos(px, py):
        a = random.uniform(0, math.tau)
        r = random.uniform(SPAWN["ring_min"], SPAWN["ring_max"])
        return px + math.cos(a) * r, py + math.sin(a) * r
