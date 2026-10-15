"""村庄与结构：**确定性选址 + 地形整平 + 房屋 / 农田 / 道路 / 灯火**。

这是 Phase 2-C 的最后一批（"世界纵深"的收尾：不只地下有东西，地表也有"人类痕迹"）。

## 一、结构为什么走 `set_generated`（不进存档增量）

同 `world.plant_trees` 的理由：**结构是地形的一部分，不是玩家改动**。
本项目"存档只存种子 + 增量"这条纪律要求 —— 只要 `(seed, size, height)` 一样，
结构就必须逐格重算出**完全一样**的东西。

好处是**老存档不用升级**（v3 不变）：`load()` 里先 `generate()` + 装修（树/村庄），
再重放玩家的增量。读一个 2-A 时代的档，村庄会照样出现在同样的位置。

⚠ 反过来的代价：**结构一旦改了摆放规则，老存档里的村庄会跟着变位置**（存档只存了
"玩家改了哪几格"，没存村庄）。这与树/洞穴/矿脉是同一个性质，见设计稿 §三。

## 二、选址（`village_sites`，纯函数）

粗格撒点（每 `VILLAGE_CELL` 格一个候选）+ 哈希概率 ⇒ 拿到一批候选，
再对每个候选检查两条**硬判据**：

1. **平坦**：范围内地表极差 ≤ `FLAT_TOL`。不整平直接盖房会盖出"悬空屋/半埋屋"，
   而整平幅度必须有界（否则会把地图削出一道悬崖）—— 所以"平坦"是选址的前提，
   不是"事后补救"。
2. **不在水边**（`hi > sea + 2`）与 **不在雪线之上**（`lo < snow_line - 2`）：
   水里盖房会泡汤；雪线以上盖房会让村子边上就是雪地，很突兀。

⚠ **刻意没有"不许压在洞口上"这条**（2026-10-15 实测）：加上它以后**一个村庄都选不出来**
——256 世界的 worm 洞口有 352 个（每 ~186 格一个），村庄占地 ~500 格 ⇒ 几乎必然撞上。
正确口径是：洞口落在整平范围内就**被垫土填掉**（村庄地面因此是完整的）。

## 三、整平（只填不削）

`base_y` 取范围内**最高**地表高度，然后把每列从 `地表 + 1` 垫到 `base_y`（填泥土），
再把 `base_y` 那层铺成草地，最后清掉上方 `_CLEAR_H` 格（去掉树/草/水）。

**为什么只填不削**：削会把已有地形挖开（可能切掉洞穴顶、把树根切一半），
而填是"往空气里加方块"，不破坏既有结构。代价是村庄略微"垫"起来，
但幅度被 `FLAT_TOL` 限制在 ≤4 格，看着就是一块平整的高地。

## 四、布局与"灯火即安全区"

中心一口井 + 四象限四栋房 + 两块农田 + 十字道路 + 火把。

⚠ 火把不只是装饰：**村里的方块光照高 ⇒ 敌对生物刷不进来**。
`mobs.spawn_allowed` 的"只在暗处刷"判据（Phase 2-A 就有）在这里天然生效 ——
"村庄是安全区"这条玩法语义因此是**机制**，不是文案。`cli --only village`
的"村里不刷僵尸"就是验这一条。

## 五、确定性

位置、朝向、房屋尺寸、屋顶材质、作物分布，全部由 `(seed, vx, vz)` 的哈希决定
（不引 `random` —— 那要赌跨平台逐位一致，见 `world._hash01` 的说明）。
同种子两次生成 ⇒ 逐格相同（单测钉住）。
"""

from __future__ import annotations

from .blocks import (AIR, BRICK, COBBLE, CROP, DIRT, GLASS, GRASS, GRAVEL,
                     LOG, PLANKS, TORCH, WATER)

__all__ = ['VILLAGE_CELL', 'VILLAGE_CHANCE', 'VILLAGE_R', 'FLAT_TOL',
           'village_sites', 'build_village', 'plant_villages',
           'HOUSE_HW', 'HOUSE_WALL', 'HOUSE_OFF']

#: 候选间距（格）：每 `VILLAGE_CELL × VILLAGE_CELL` 的地块最多出 1 个村庄。
#: 这个数必须 > 2×(VILLAGE_R + HOUSE_OFF + HOUSE_HW)，否则相邻村庄会**叠在一起**。
VILLAGE_CELL = 96
#: 候选成为村庄的概率（太高会让地表"满地是村"）
VILLAGE_CHANCE = 0.55
#: 村庄半径（整平范围）。井在中心，四象限房 + 上下两块田。
#: ⚠ 必须够大：房子的**挑檐屋顶**会比墙体再宽一圈（`HOUSE_OFF + HOUSE_HW + 1 = 12`），
#:   屋顶落在整平区外的话会"悬在半空"或"埋进山坡"（实测：R=11 时最外圈屋顶出界）。
VILLAGE_R = 13
#: 选址的平坦容差。**实测定标**（2026-10-15，256 世界 71 个采样点）：
#: R=11 范围内地表极差 中位 6 / p75 7 / max 12 ⇒ TOL=8 通过率 89%，
#: TOL=4 只有 21%（初版就是 4 ⇒ 整张地图 0 个村庄）。
FLAT_TOL = 8
#: 房子半宽：`HOUSE_HW=3` ⇒ 7×7 占地（含墙）
HOUSE_HW = 3
#: 墙高（不含屋顶）
HOUSE_WALL = 3
#: 房子中心到村庄中心的偏移（四象限）
HOUSE_OFF = 8
#: 垫土后要清空的高度（墙 3 + 屋顶 2 + 余量）
_CLEAR_H = 9
#: 屋顶可选材质（按哈希挑，让村庄里的房子有差异）
_ROOFS = (BRICK, PLANKS, COBBLE)


def village_sites(seed: int, size: int, height: int, sea: int, snow_line: int):
    """本世界所有村庄的中心与地基高度：`[(vx, vy, vz), ...]`（**纯函数**）。

    ⚠ **刻意不检查"洞口"**（2026-10-15 实测）：初版把"村庄范围内不许有天然洞口"
    当第三条判据，结果**一个村庄都没生成** —— 256 世界的 worm 洞口有 **352** 个
    （每 ~186 格一个），而村庄占地 ~500 格 ⇒ 几乎必然撞上一个，判据等于全拒。
    正确口径是：洞口落在整平范围内就**被垫土填掉**（村庄地面因此是完整的），
    这是可接受的代价（设计稿 §四）。要保护的是建筑不被"半埋"，而不是地面没有洞。
    """
    from .world import _hash01, surface_height         # 局部导入：避开与 world 的环

    margin = VILLAGE_R + HOUSE_OFF + HOUSE_HW + 2
    span = size - 2 * margin
    if span <= 0:
        return []                                       # 世界太小，放不下村庄
    n = span // VILLAGE_CELL + 1
    jitter = max(1, VILLAGE_CELL // 3)
    out = []
    for gx in range(n):
        for gz in range(n):
            # 先按概率筛（省掉大部分候选的采样成本 —— 采样 27×27 列不便宜）
            if _hash01(gx, gz, seed ^ 0x71A6) > VILLAGE_CHANCE:
                continue
            vx = margin + gx * VILLAGE_CELL + int(_hash01(gx, gz, seed ^ 0x71A7) * jitter)
            vz = margin + gz * VILLAGE_CELL + int(_hash01(gx, gz, seed ^ 0x71A8) * jitter)
            if not (margin <= vx <= size - margin and margin <= vz <= size - margin):
                continue

            hs = [surface_height(x, z, seed, height)
                  for x in range(vx - VILLAGE_R, vx + VILLAGE_R + 1, 2)
                  for z in range(vz - VILLAGE_R, vz + VILLAGE_R + 1, 2)]
            if not hs:
                continue
            lo, hi = min(hs), max(hs)
            if hi - lo > FLAT_TOL:
                continue                                # ① 不够平
            if hi <= sea + 2:
                continue                                # ② 水边
            if lo >= snow_line - 2:
                continue                                # ② 雪线之上
            # 地基取**中位**（不是最高点）：削填各半 ⇒ 单侧幅度 ≤ FLAT_TOL/2 = 4 格，
            # 只填不削的话幅度会是 8 格（村庄"垫"起来很明显）。
            base = (lo + hi) // 2
            if base <= sea + 1:
                continue                                # 地基不能在水下
            out.append((vx, base, vz))
    return out


# ---------------------------------------------------------------- 建造
def build_village(world, vx: int, vy: int, vz: int) -> dict:
    """在 `(vx, vy, vz)` 盖一座村庄（就地改写 `world`，返回统计）。

    调用方负责先确认 `(vx, vy, vz)` 来自 `village_sites`（选址判据已过）。
    所有写入都走 `set_generated` ⇒ **不进存档增量**。
    """
    seed = world.seed
    r = VILLAGE_R
    stats = {'houses': 0, 'farms': 0, 'torches': 0, 'crops': 0, 'path': 0,
             'paved': 0}

    # ---- ① 整平：垫土 + 铺草地 + 清空上方（每列独立，顺序无依赖）
    for x in range(vx - r, vx + r + 1):
        for z in range(vz - r, vz + r + 1):
            if not (0 <= x < world.size and 0 <= z < world.size):
                continue
            h = world.surface_at(x, z)
            if h > vy:
                for y in range(vy + 1, h + 1):          # 理论上不会（vy 取 hmax）：削掉
                    world.set_generated(x, y, z, AIR)
            else:
                for y in range(h + 1, vy + 1):          # 垫土到地基
                    world.set_generated(x, y, z, DIRT)
            world.set_generated(x, vy, z, GRASS)        # 地基那层铺草地
            for y in range(vy + 1, vy + 1 + _CLEAR_H):  # 上方清空（去掉树/草）
                if world.get(x, y, z) != AIR:
                    world.set_generated(x, y, z, AIR)
            stats['paved'] += 1

    # ---- ② 十字道路（砂砾，3 格宽）：只把草地改成砂砾，不改动别的
    for x in range(vx - r + 1, vx + r):
        for dz in (-1, 0, 1):
            if world.get(x, vy, vz + dz) == GRASS:
                world.set_generated(x, vy, vz + dz, GRAVEL)
                stats['path'] += 1
    for z in range(vz - r + 1, vz + r):
        for dx in (-1, 0, 1):
            if world.get(vx + dx, vy, z) == GRASS:
                world.set_generated(vx + dx, vy, z, GRAVEL)
                stats['path'] += 1

    # ---- ③ 中心井（圆石围一圈 + 中间水）+ 四角火把
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            center = (dx == 0 and dz == 0)
            world.set_generated(vx + dx, vy, vz + dz,
                                WATER if center else COBBLE)
    for (dx, dz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        world.set_generated(vx + dx, vy + 1, vz + dz, TORCH)
        stats['torches'] += 1

    # ---- ④ 四象限四栋房（门朝村庄中心）
    off = HOUSE_OFF
    for (sx, sz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        _house(world, vx + sx * off, vy, vz + sz * off, seed, stats,
               toward=(-sx, -sz))

    # ---- ⑤ 两块农田（北 / 南），中间隔着井
    for (ax, az, tz) in ((vx, vz - off, (0, 1)), (vx, vz + off, (0, -1))):
        _farm(world, ax, vy, az, seed, stats, toward=tz)
    return stats


def _house(world, hx: int, base_y: int, hz: int, seed: int, stats: dict,
           toward=(-1, -1)):
    """一栋 7×7 房：木板墙 + 玻璃窗 + 挑檐阶梯屋顶 + 朝内门洞 + 屋内火把。

    `toward` 是"门该朝哪个方向"（单位向量，指向村庄中心）。
    `hx/hz` 是房子中心，`base_y` 是地基那层（地面）。
    """
    from .world import _hash01

    hw, wall = HOUSE_HW, HOUSE_WALL
    put = world.set_generated
    roof = _ROOFS[int(_hash01(hx, hz, seed ^ 0x52EE) * len(_ROOFS)) % len(_ROOFS)]
    dx, dz = toward

    # 屋内地面（木板 —— "进屋了"这件事看得出来）
    for x in range(hx - hw, hx + hw + 1):
        for z in range(hz - hw, hz + hw + 1):
            put(x, base_y, z, PLANKS)

    # 门洞（2 格高，开在朝中心那一面）
    if dx:
        door_x, door_z = hx + dx * hw, hz
        door_cells = {(door_x, base_y + dy, door_z) for dy in (1, 2)}
    else:
        door_x, door_z = hx, hz + dz * hw
        door_cells = {(door_x, base_y + dy, door_z) for dy in (1, 2)}

    # 窗：门那一面的两侧各 2 格处；另两面的中间
    win_y = base_y + wall - 1
    windows = set()
    if dx:
        for zz in (hz - 2, hz + 2):
            windows.add((hx + dx * hw, win_y, zz))
        for xx in (hx - 2, hx + 2):
            windows.add((xx, win_y, hz - hw))
            windows.add((xx, win_y, hz + hw))
    else:
        for xx in (hx - 2, hx + 2):
            windows.add((xx, win_y, hz + dz * hw))
        for zz in (hz - 2, hz + 2):
            windows.add((hx - hw, win_y, zz))
            windows.add((hx + hw, win_y, zz))

    # 墙（一圈），门洞与窗按集合处理
    for dy in range(1, wall + 1):
        for x in range(hx - hw, hx + hw + 1):
            for z in range(hz - hw, hz + hw + 1):
                if abs(x - hx) != hw and abs(z - hz) != hw:
                    continue                            # 只砌外圈
                y = base_y + dy
                if (x, y, z) in door_cells:
                    put(x, y, z, AIR)
                elif (x, y, z) in windows:
                    put(x, y, z, GLASS)
                else:
                    put(x, y, z, PLANKS)

    # 挑檐屋顶：第一层比墙宽一圈，第二层收回来封顶
    for i, half in enumerate((hw + 1, hw)):
        for x in range(hx - half, hx + half + 1):
            for z in range(hz - half, hz + half + 1):
                put(x, base_y + wall + 1 + i, z, roof)

    # 屋内火把（墙角，离门最远的那个角）—— 屋子里的光只来自它
    tx, tz = hx - dx * (hw - 1), hz - dz * (hw - 1)
    put(tx, base_y + wall - 1, tz, TORCH)
    # 门廊火把（门外那一格）：夜里从街上就能看出"这里有人住"，
    # 而且它让**村道**也有光照 ⇒ 村子边缘才不是"一跨出去就可能遇敌"。
    put(door_x + dx, base_y + 1, door_z + dz, TORCH)
    stats['houses'] += 1
    stats['torches'] += 2


def _farm(world, ax: int, base_y: int, az: int, seed: int, stats: dict,
          toward=(0, 1)):
    """一块 5×5 田：圆石田埂（朝村中心留缺口）+ 内部作物 + 一条水渠。

    ⚠ 尺寸刻意**只有 5×5**（2026-10-15 实测踩到）：初版 7×7 时田埂到 `vx ± 3`，
    而房子内边在 `vx ± 5` ⇒ **出门就是田埂**（1 格高的石坎杵在门口）。
    缩小到 5×5 后田埂在 `vx ± 2`，与房子留出 2 格空地（门口走两步就是路）。

    作物种在土上（`CROP` 在 `base_y + 1`），水渠在 `base_y` 那层的一条水带。
    收获走 `recipes.drops_for(CROP)` ⇒ 掉小麦（3 麦烤 1 面包）。
    """
    put = world.set_generated
    span = 2                                        # 5×5（含田埂），内部 3×3 田
    gap = (ax, az + toward[1] * span)               # 田埂缺口（朝村中心）
    for x in range(ax - span, ax + span + 1):
        for z in range(az - span, az + span + 1):
            edge = (abs(x - ax) == span) or (abs(z - az) == span)
            if edge:
                if (x, z) == gap:
                    continue                        # 留个缺口，玩家走进去收麦
                put(x, base_y + 1, z, COBBLE)       # 田埂（1 格高，能跳过去）
                continue
            put(x, base_y, z, DIRT)                 # 田土
            if z == az:
                put(x, base_y, z, WATER)            # 中间一条水渠
                put(x, base_y + 1, z, AIR)
            else:
                put(x, base_y + 1, z, CROP)
                stats['crops'] += 1
    stats['farms'] += 1


def plant_villages(world) -> int:
    """在世界上盖好全部村庄，返回村庄数；**同时把位置记到 `world.villages`**。

    `world.villages` 是 `[(vx, vy, vz), ...]` —— 刷怪（`kernel._try_spawn_mobs` 的
    村民通道）与验收都要用它，所以放在这里一次算好，避免重复选址。
    """
    sites = village_sites(world.seed, world.size, world.height, world.sea_level,
                          world.snow_line)
    for (vx, vy, vz) in sites:
        build_village(world, vx, vy, vz)
    world.villages = list(sites)
    return len(sites)
