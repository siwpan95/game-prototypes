# -*- coding: utf-8 -*-
"""按出口方向分组的房间模板池。"""
from .templates import *  # noqa: F401,F403  —— 43 个 make_room_* 生成函数

# ─── 按出口方向分组的模板池 ───
# 键为出口方向集合的 frozenset，值为 list[生成函数]

_ALL_TEMPLATES = {
    frozenset({'N','S','E','W'}): [make_room_cross, make_room_chamber,
                                    make_room_dark_cross, make_room_hub,
                                    make_room_golden_treasury, make_room_energy_core,
                                    make_room_battle_arena, make_room_trader_outpost,
                                    make_room_portal_gate],
    frozenset({'N','S'}):         [make_room_hall_ns, make_room_hall_ns_glow,
                                    make_room_maze_ns, make_room_long_corridor_ns,
                                    make_room_secret_ns, make_room_red_warning,
                                    make_room_garden, make_room_debris,
                                    make_room_shrine, make_room_floating_platforms,
                                    make_room_forgotten_tomb, make_room_acid_pool],
    frozenset({'E','W'}):         [make_room_hall_ew, make_room_maze_ew,
                                    make_room_long_corridor_ew, make_room_glow_hall,
                                    make_room_fire_exit, make_room_crystal_cavern,
                                    make_room_neon_highway, make_room_ancient_library,
                                    make_room_abandoned_lab, make_room_pit_trap],
    # 注：tech_nook / data_temple / generator_room 曾错放在 N/E/W 组，但三者
    # 实现分别只开 N/S/E、N/S/E、N/S/W 口（generator_room 的 docstring 就写着
    # N/S/W）——声明与实际不符，玩家从错误方向进入会撞墙。按实现修正分组。
    frozenset({'N','E','W'}):     [make_room_tee_n],
    frozenset({'S','E','W'}):     [make_room_tee_s, make_room_bone_garden],
    frozenset({'N','S','E'}):     [make_room_tee_e, make_room_tech_nook,
                                    make_room_data_temple],
    frozenset({'N','S','W'}):     [make_room_tee_w, make_room_generator_room],
    frozenset({'N','E'}):         [make_room_corner_ne],
    frozenset({'N','W'}):         [make_room_corner_nw],
    frozenset({'S','E'}):         [make_room_corner_se],
    frozenset({'S','W'}):         [make_room_corner_sw],
}

_OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
_DIR_DELTA = {'N': (0, -1), 'S': (0, 1), 'W': (-1, 0), 'E': (1, 0)}
