# -*- coding: utf-8 -*-
"""21×21 房间模板库（43 个模板）+ 网格绘制辅助函数。"""
import math
import random

from ..config import CHUNK_SIZE

def _mk_empty():
    g = [['#'] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
    return g

def _open_north(g):
    """在北侧中心开3格出口"""
    g[0][9] = g[0][10] = g[0][11] = '.'
    g[1][9] = g[1][10] = g[1][11] = '.'

def _open_south(g):
    g[20][9] = g[20][10] = g[20][11] = '.'
    g[19][9] = g[19][10] = g[19][11] = '.'

def _open_west(g):
    g[9][0]  = g[10][0]  = g[11][0]  = '.'
    g[9][1]  = g[10][1]  = g[11][1]  = '.'

def _open_east(g):
    g[9][20]  = g[10][20]  = g[11][20]  = '.'
    g[9][19]  = g[10][19]  = g[11][19]  = '.'

def _fill_rect(g, r1, c1, r2, c2, ch='.'):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            g[r][c] = ch

def _grid_to_str(g):
    return [''.join(row) for row in g]

# ─── 各类房间模板生成函数 ───

def make_room_cross():
    """十字走廊：四向开口"""
    g = _mk_empty()
    # 水平走廊
    _fill_rect(g, 9, 0, 11, 20)
    # 竖直走廊
    _fill_rect(g, 0, 9, 20, 11)
    _open_north(g); _open_south(g)
    _open_west(g);  _open_east(g)
    return _grid_to_str(g)

def make_room_hall_ns():
    """南北大走廊"""
    g = _mk_empty()
    _fill_rect(g, 0, 7, 20, 13)
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_hall_ew():
    """东西大走廊"""
    g = _mk_empty()
    _fill_rect(g, 7, 0, 13, 20)
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_hall_ns_glow():
    """南北走廊（含发光柱）"""
    g = _mk_empty()
    _fill_rect(g, 0, 7, 20, 13)
    # 发光柱对称分布
    for r in [4, 8, 12, 16]:
        g[r][8]  = '2'
        g[r][12] = '2'
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_tee_n():
    """T形：N/W/E开口"""
    g = _mk_empty()
    _fill_rect(g, 0, 9, 11, 11)   # 北走廊
    _fill_rect(g, 9, 0, 11, 20)   # 东西走廊
    _open_north(g); _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_tee_s():
    """T形：S/W/E开口"""
    g = _mk_empty()
    _fill_rect(g, 9, 9, 20, 11)   # 南走廊
    _fill_rect(g, 9, 0, 11, 20)   # 东西走廊
    _open_south(g); _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_tee_e():
    """T形：N/S/E开口"""
    g = _mk_empty()
    _fill_rect(g, 0, 9, 20, 11)   # 南北走廊
    _fill_rect(g, 9, 9, 11, 20)   # 东走廊
    _open_north(g); _open_south(g); _open_east(g)
    return _grid_to_str(g)

def make_room_tee_w():
    """T形：N/S/W开口"""
    g = _mk_empty()
    _fill_rect(g, 0, 9, 20, 11)
    _fill_rect(g, 9, 0, 11, 11)
    _open_north(g); _open_south(g); _open_west(g)
    return _grid_to_str(g)

def make_room_corner_ne():
    """L形：N/E开口"""
    g = _mk_empty()
    _fill_rect(g, 0, 9, 10, 11)
    _fill_rect(g, 9, 9, 11, 20)
    _open_north(g); _open_east(g)
    return _grid_to_str(g)

def make_room_corner_nw():
    """L形：N/W开口"""
    g = _mk_empty()
    _fill_rect(g, 0, 9, 10, 11)
    _fill_rect(g, 9, 0, 11, 11)
    _open_north(g); _open_west(g)
    return _grid_to_str(g)

def make_room_corner_se():
    """L形：S/E开口"""
    g = _mk_empty()
    _fill_rect(g, 10, 9, 20, 11)
    _fill_rect(g, 9, 9, 11, 20)
    _open_south(g); _open_east(g)
    return _grid_to_str(g)

def make_room_corner_sw():
    """L形：S/W开口"""
    g = _mk_empty()
    _fill_rect(g, 10, 9, 20, 11)
    _fill_rect(g, 9, 0, 11, 11)
    _open_south(g); _open_west(g)
    return _grid_to_str(g)

def make_room_chamber():
    """中央大厅（四向开口）+ 柱子阵列"""
    g = _mk_empty()
    _fill_rect(g, 2, 2, 18, 18)
    _open_north(g); _open_south(g)
    _open_west(g);  _open_east(g)
    # 内部柱子
    for r in [5, 10, 15]:
        for c in [5, 10, 15]:
            g[r][c] = '#'
    # 发光柱
    g[5][5]   = '2'
    g[5][15]  = '2'
    g[15][5]  = '2'
    g[15][15] = '2'
    return _grid_to_str(g)

def make_room_maze_ns():
    """迷宫型：N/S开口，内部迷宫墙"""
    g = _mk_empty()
    _fill_rect(g, 0, 1, 20, 19)
    # 随机内墙（用固定种子保证每次相同结构）
    inner_walls = [
        (3,3,3,8),(3,12,3,17),(6,1,6,6),(6,10,6,15),
        (9,4,9,9),(9,11,9,16),(12,2,12,7),(12,13,12,18),
        (15,5,15,10),(15,11,15,16),
    ]
    for r1,c1,r2,c2 in inner_walls:
        _fill_rect(g, r1, c1, r2, c2, '#')
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_maze_ew():
    """迷宫型：E/W开口"""
    g = _mk_empty()
    _fill_rect(g, 1, 0, 19, 20)
    inner_walls = [
        (2,3,7,3),(2,9,7,9),(2,15,7,15),
        (13,3,18,3),(13,9,18,9),(13,15,18,15),
        (8,6,12,6),(8,12,12,12),
    ]
    for r1,c1,r2,c2 in inner_walls:
        _fill_rect(g, r1, c1, r2, c2, '#')
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_dark_cross():
    """暗室十字（发光柱 + 四向出口）"""
    g = _mk_empty()
    _fill_rect(g, 9, 0, 11, 20)
    _fill_rect(g, 0, 9, 20, 11)
    # 四角发光柱
    for r, c in [(3,3),(3,17),(17,3),(17,17)]:
        g[r][c] = '2'
    _open_north(g); _open_south(g)
    _open_west(g);  _open_east(g)
    return _grid_to_str(g)

def make_room_long_corridor_ns():
    """细长南北走廊（带侧龛）"""
    g = _mk_empty()
    _fill_rect(g, 0, 8, 20, 12)
    # 左右小龛
    for r in [3, 7, 13, 17]:
        _fill_rect(g, r, 5, r+1, 7)
        _fill_rect(g, r, 13, r+1, 15)
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_long_corridor_ew():
    """细长东西走廊（带上下凹槽）"""
    g = _mk_empty()
    _fill_rect(g, 8, 0, 12, 20)
    for c in [3, 7, 13, 17]:
        _fill_rect(g, 5, c, 7, c+1)
        _fill_rect(g, 13, c, 15, c+1)
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_secret_ns():
    """暗路南北室：弯曲路径，N/S开口"""
    g = _mk_empty()
    # S形路径
    _fill_rect(g, 0, 9, 7, 11)
    _fill_rect(g, 6, 6, 8, 14)
    _fill_rect(g, 7, 8, 14, 10)
    _fill_rect(g, 13, 8, 15, 15)
    _fill_rect(g, 14, 9, 20, 11)
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_hub():
    """中枢大厅：四向出口，宽阔空间"""
    g = _mk_empty()
    _fill_rect(g, 1, 1, 19, 19)
    # 中心岛
    _fill_rect(g, 8, 8, 12, 12, '#')
    g[10][10] = '2'
    # 走廊连接出口
    _fill_rect(g, 0, 9, 1, 11)
    _fill_rect(g, 19, 9, 20, 11)
    _fill_rect(g, 9, 0, 11, 1)
    _fill_rect(g, 9, 19, 11, 20)
    _open_north(g); _open_south(g)
    _open_west(g);  _open_east(g)
    return _grid_to_str(g)

def make_room_glow_hall():
    """发光走廊大厅（双向）"""
    g = _mk_empty()
    _fill_rect(g, 3, 0, 17, 20)
    for c in range(2, 19, 3):
        g[5][c]  = '2'
        g[15][c] = '2'
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_red_warning():
    """红色警示区（N/S）"""
    g = _mk_empty()
    _fill_rect(g, 0, 6, 20, 14)
    for r in [3, 8, 12, 17]:
        g[r][7] = '3'  # 红色装饰
        g[r][13] = '3'
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_golden_treasury():
    """金色宝库（十字）"""
    g = _mk_empty()
    _fill_rect(g, 9, 0, 11, 20)
    _fill_rect(g, 0, 9, 20, 11)
    # 金色装饰物
    for r, c in [(3,3),(3,17),(17,3),(17,17),(10,5),(10,15),(5,10),(15,10)]:
        g[r][c] = '4'
    _open_north(g); _open_south(g)
    _open_west(g);  _open_east(g)
    return _grid_to_str(g)

def make_room_garden():
    """绿色花园（N/S）"""
    g = _mk_empty()
    _fill_rect(g, 0, 4, 20, 16)
    # 绿色植被
    for r in [2, 6, 10, 14, 18]:
        for c in [5, 9, 13]:
            if random.random() > 0.4:
                g[r][c] = '5'
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_energy_core():
    """紫色能量核心（四向）"""
    g = _mk_empty()
    _fill_rect(g, 4, 4, 16, 16)
    # 门廊：把门洞(0-1)连到大厅(4-16)。漏掉这步时四个门全部"通而不达"、
    # 整个区块被隔离（能量核心曾因此成为出生点牢笼）。
    _fill_rect(g, 2, 9, 3, 11)      # N 门廊
    _fill_rect(g, 17, 9, 18, 11)    # S 门廊
    _fill_rect(g, 9, 2, 11, 3)      # W 门廊
    _fill_rect(g, 9, 17, 11, 18)    # E 门廊
    # 中心能量柱
    g[10][10] = '6'
    for r, c in [(6,6),(6,14),(14,6),(14,14)]:
        g[r][c] = '6'
    _open_north(g); _open_south(g)
    _open_west(g);  _open_east(g)
    return _grid_to_str(g)

def make_room_fire_exit():
    """橙色出口（E/W）"""
    g = _mk_empty()
    _fill_rect(g, 6, 0, 14, 20)
    for c in [4, 8, 12, 16]:
        g[7][c] = '7'
        g[13][c] = '7'
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_debris():
    """碎石废墟区（N/S）"""
    g = _mk_empty()
    _fill_rect(g, 0, 5, 20, 15)
    # 随机碎石
    for _ in range(12):
        r = random.randint(2, 18)
        c = random.randint(6, 14)
        if g[r][c] == '.':
            g[r][c] = '8'  # 灰色碎石装饰
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_tech_nook():
    """科技角落（T形 N/S/E）"""
    g = _mk_empty()
    _fill_rect(g, 0, 9, 20, 11)
    _fill_rect(g, 9, 9, 11, 20)
    # 科技装饰
    for r in [3, 7, 14, 18]:
        g[r][10] = '9'  # 青色科技装饰
    _open_north(g); _open_south(g); _open_east(g)
    return _grid_to_str(g)

def make_room_crystal_cavern():
    """水晶洞穴（双向 E/W）"""
    g = _mk_empty()
    _fill_rect(g, 2, 0, 18, 20)
    # 水晶柱
    for r in [4, 8, 12, 16]:
        g[r][6] = 'A'  # 蓝色水晶
        g[r][14] = 'A'
    # 特殊水晶
    g[8][10] = 'B'  # 紫水晶
    g[12][10] = 'B'
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_shrine():
    """神秘祭坛（N/S）"""
    g = _mk_empty()
    _fill_rect(g, 0, 5, 20, 15)
    # 中央祭坛
    _fill_rect(g, 8, 8, 12, 12, '#')
    g[10][10] = '2'  # 中心发光
    # 周围的发光装饰
    for r, c in [(6,7),(6,13),(14,7),(14,13)]:
        g[r][c] = '2'
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_battle_arena():
    """战斗竞技场（四向）"""
    g = _mk_empty()
    _fill_rect(g, 2, 2, 18, 18)
    # 环形障碍物
    for angle in range(0, 360, 30):
        import math
        rad = math.radians(angle)
        r = int(8 + 2 * math.sin(angle * 0.3))
        c = int(10 + 6 * math.cos(rad))
        if 2 <= r <= 18 and 2 <= c <= 18:
            g[r][c] = '#'
    _open_north(g); _open_south(g)
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_data_temple():
    """数据神殿（T形 N/S/E）"""
    g = _mk_empty()
    _fill_rect(g, 0, 7, 20, 13)
    _fill_rect(g, 7, 7, 13, 20)
    # 矩阵装饰
    for r in [3, 6, 9, 12, 15, 18]:
        for c in [8, 10, 12]:
            if random.random() > 0.5:
                g[r][c] = '9'
    _open_north(g); _open_south(g); _open_east(g)
    return _grid_to_str(g)

def make_room_abandoned_lab():
    """废弃实验室（双向 E/W）"""
    g = _mk_empty()
    _fill_rect(g, 3, 0, 17, 20)
    # 实验台
    for c in [4, 8, 12, 16]:
        _fill_rect(g, 4, c, 7, c+2, '#')
        if random.random() > 0.3:
            g[5][c+1] = '8'  # 灰色碎石/破损设备
    # 警示标志
    for c in [6, 14]:
        g[10][c] = '3'  # 红色警示
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_floating_platforms():
    """悬浮平台（N/S）"""
    g = _mk_empty()
    _fill_rect(g, 0, 4, 20, 16)
    # 随机悬浮平台
    platforms = [(3,6),(5,10),(8,8),(11,14),(14,7),(16,12)]
    for r, c in platforms:
        _fill_rect(g, r, c, r, c+2, '#')
        if random.random() > 0.4:
            g[r-1][c+1] = '2'
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_bone_garden():
    """骨骸花园（S/E/W）"""
    g = _mk_empty()
    _fill_rect(g, 4, 0, 20, 20)
    # 骨骸装饰
    for _ in range(8):
        r = random.randint(6, 18)
        c = random.randint(4, 16)
        g[r][c] = '8'
        if c + 1 < 16:
            g[r][c+1] = '8'
    _open_south(g); _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_neon_highway():
    """霓虹高速（E/W）"""
    g = _mk_empty()
    _fill_rect(g, 0, 0, 20, 20)
    # 中心分隔带
    for r in [9, 10, 11]:
        for c in range(0, 20):
            if c % 4 == 0:
                g[r][c] = '9'  # 科技装饰
    # 霓虹灯柱
    for c in [3, 7, 11, 15, 19]:
        g[3][c] = '3'  # 红色
        g[17][c] = '2'  # 青色
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_forgotten_tomb():
    """遗忘陵墓（N/S）"""
    g = _mk_empty()
    _fill_rect(g, 0, 3, 20, 17)
    # 石棺
    _fill_rect(g, 8, 8, 12, 12, '#')
    g[10][10] = '6'  # 紫色能量
    # 石像
    for r, c in [(4,5),(4,14),(16,5),(16,14)]:
        g[r][c] = '8'
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_trader_outpost():
    """商人哨站（十字）"""
    g = _mk_empty()
    _fill_rect(g, 9, 0, 11, 20)
    _fill_rect(g, 0, 9, 20, 11)
    # 商店摊位
    for r, c in [(8,4),(8,15),(12,4),(12,15)]:
        _fill_rect(g, r, c, r+2, c+3, '#')
        g[r+1][c+1] = '4'  # 金色商品
    _open_north(g); _open_south(g)
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_acid_pool():
    """酸液池（N/S）"""
    g = _mk_empty()
    _fill_rect(g, 0, 5, 20, 15)
    # 酸液池
    for r in [6, 8, 10, 12, 14]:
        for c in [6, 8, 10, 12, 14]:
            if random.random() > 0.3:
                g[r][c] = '5'  # 绿色腐蚀
    # 安全路径
    _fill_rect(g, 6, 4, 14, 5, '.')
    _fill_rect(g, 6, 15, 14, 16, '.')
    _open_north(g); _open_south(g)
    return _grid_to_str(g)

def make_room_ancient_library():
    """远古图书馆（E/W）"""
    g = _mk_empty()
    _fill_rect(g, 1, 0, 19, 20)
    # 书架
    for r in [2, 4, 6, 8, 10, 12, 14, 16, 18]:
        for c in [3, 7, 11, 15, 19]:
            if c <= 18:
                g[r][c] = '#'
                if random.random() > 0.5:
                    g[r][c-1] = '4'  # 金色书籍
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_generator_room():
    """发电机室（T形 N/S/W）"""
    g = _mk_empty()
    _fill_rect(g, 0, 9, 20, 11)
    _fill_rect(g, 9, 0, 11, 11)
    # 大型发电机（rows 3-8，**避开 rows 9-11 的西侧门廊**——
    # 原位置 rows 6-14 压在门廊上，把西门封成了死路）
    _fill_rect(g, 3, 3, 8, 7, '#')
    g[8][5] = '7'  # 橙色能量线
    g[8][6] = '7'
    g[12][5] = '7'
    g[12][6] = '7'
    _open_north(g); _open_south(g); _open_west(g)
    return _grid_to_str(g)

def make_room_pit_trap():
    """陷阱坑室（E/W）"""
    g = _mk_empty()
    _fill_rect(g, 0, 0, 20, 20)
    # 中央深坑
    _fill_rect(g, 7, 7, 13, 13, '8')
    # 围绕陷阱的窄桥
    _fill_rect(g, 10, 0, 10, 6, '.')
    _fill_rect(g, 10, 14, 10, 20, '.')
    _fill_rect(g, 0, 10, 6, 10, '.')
    _fill_rect(g, 14, 10, 20, 10, '.')
    _open_west(g); _open_east(g)
    return _grid_to_str(g)

def make_room_portal_gate():
    """传送门大厅（四向）- 稀有事件"""
    g = _mk_empty()
    _fill_rect(g, 4, 4, 16, 16)
    # 门廊：连门洞(0-1)与大厅(4-16)（与 energy_core 同款修复——
    # 少了它四门"通而不达"，传送门大厅会被彻底隔离）
    _fill_rect(g, 2, 9, 3, 11)      # N 门廊
    _fill_rect(g, 17, 9, 18, 11)    # S 门廊
    _fill_rect(g, 9, 2, 11, 3)      # W 门廊
    _fill_rect(g, 9, 17, 11, 18)    # E 门廊
    # 中心传送门
    g[10][10] = 'C'  # 传送门格子
    # 四角发光柱
    for r, c in [(6,6),(6,14),(14,6),(14,14)]:
        g[r][c] = '2'
    # 传送门周围科技装饰
    g[9][10] = '9'
    g[11][10] = '9'
    g[10][9] = '9'
    g[10][11] = '9'
    _open_north(g); _open_south(g)
    _open_west(g);  _open_east(g)
    return _grid_to_str(g)
