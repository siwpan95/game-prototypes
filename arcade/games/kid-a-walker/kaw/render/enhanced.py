# -*- coding: utf-8 -*-
"""增强型伪 3D 渲染器（Stage 1）。

在原始 raycasting 基础上加三件事：
  1. 地面 / 天花板纹理投射（floor casting，numpy 向量化 + 降采样）
  2. 俯仰（pitch）—— 地平线上下平移，可以抬头看天花板、低头看地面
  3. 装饰物从「整面彩色墙」改成「带深度遮挡的 billboard 精灵」

几何约定（与 raycast.py 一致）：
  眼高 0.5、天花板 1.0、墙高 1.0，单位为「一格」。
  距离 d 处：垂直 1 单位 = H/d 像素，水平 1 单位 = K_PX_H/d 像素。
  水平与垂直比例不同，是 raycasting 的固有拉伸，精灵沿用同一比例才不自相矛盾。
"""
import math

import numpy as np
import pygame

from ..config import (
    C_FLOOR_B,
    C_FLOOR_T,
    C_FOG,
    C_CEIL_BOT,
    C_CEIL_TOP,
    C_GRID,
    C_WALL_FAR,
    C_WALL_NR,
    FLOOR_BUFFER_SCALE,
    FLOOR_TEX_SIZE,
    FLOOR_TILE_UNITS,
    H,
    K_PX_H,
    K_PX_V,
    MAX_DEPTH,
    NUM_RAYS,
    SPRITE_TEX_SIZE,
    SPRITE_VIEW_RADIUS,
    TAN_HALF_FOV,
    W,
    _RAY_CORRECTION,
    _RAY_COS,
    _RAY_SIN,
)
from .raycast import Renderer
from .textures import (
    SPRITE_SPECS,
    build_mip_chain,
    build_sprite_surfaces,
    make_tile_texture,
)

_FOG_V = np.asarray(C_FOG, np.float32)


class EnhancedRenderer(Renderer):
    """伪 3D 增强渲染器。接口与 Renderer 完全一致，可直接替换。"""

    # 着 shading 表级数：把「距离明暗 + 雾化」烘焙成离屏纹理，运行时只做一次查表
    SHADE_LEVELS = 20

    def __init__(self, surf):
        super().__init__(surf)
        self.floor_scale = max(1, int(FLOOR_BUFFER_SCALE))
        self._fw = W // self.floor_scale
        self._fh = H // self.floor_scale
        # numpy 只能写 24 位面（surfarray 不支持 32 位）；缩放目标必须与显示面同格式
        self._fc_surf = pygame.Surface((self._fw, self._fh), 0, 24)
        try:
            self._fc_up = pygame.Surface((self._fw, self._fh)).convert()
        except pygame.error:      # 无显示模式时（离屏测试）退回默认格式
            self._fc_up = pygame.Surface((self._fw, self._fh))

        self.floor_tex = make_tile_texture(
            FLOOR_TEX_SIZE, base=C_FLOOR_T, shade=C_FLOOR_B,
            grid=C_GRID, grid_strength=0.22, line_w=0.050, panel=True, seed=7)
        # 天花板整体压暗，烘焙进纹理，运行时与地面共用同一条着色曲线
        self.ceil_tex = np.clip(
            make_tile_texture(
                FLOOR_TEX_SIZE, base=C_CEIL_BOT, shade=C_CEIL_TOP,
                grid=C_GRID, grid_strength=0.16, line_w=0.070,
                panel=False, seed=11).astype(np.float32) * 0.85, 0, 255
        ).astype(np.uint8)

        self._build_shade_atlas()
        self._sprites = build_sprite_surfaces(SPRITE_TEX_SIZE)

        # ── 地面投射的复用缓冲（避免每帧分配）──
        fw, fh = self._fw, self._fh
        self._xs = np.arange(fw, dtype=np.float32)[:, None]      # (fw, 1)
        self._ys = np.arange(fh, dtype=np.float32)[None, :]      # (1, fh)
        self._buf_a = np.empty((fw, fh), np.float32)
        self._buf_b = np.empty((fw, fh), np.float32)
        self._p = np.empty((1, fh), np.float32)
        self._row_d = np.empty((1, fh), np.float32)
        self._tmp = np.empty((fw, fh), np.float32)
        self._fx = np.empty((fw, fh), np.float32)
        self._fy = np.empty((fw, fh), np.float32)
        self._idx = np.empty((fw, fh), np.int32)
        self._idx_f = np.empty((fw, fh), np.float32)
        self._mip = np.empty((1, fh), np.int32)
        self._lvl_i = np.empty((1, fh), np.int32)
        self._mip_f = np.empty((1, fh), np.float32)
        self._m_n = np.empty((1, fh), np.int32)
        self._m_n_f = np.empty((1, fh), np.float32)
        self._vis = np.empty((1, fh), np.float32)
        self._lvl_f = np.empty((1, fh), np.float32)
        self._base = np.empty((1, fh), np.int32)

    # mip 层数：64 → 32 → 16 → 8 → 4
    MIP_COUNT = 5

    def _build_shade_atlas(self):
        """把「亮度 × 雾化 × mip」预烘成一张扁平查表纹理，运行时逐像素只做一次整数查表。

        Doom/Wolf3D 的 shade table 手法，顺带把 mip 也烘进去：
          atlas[level][half][mip]  ->  mip_n x mip_n x 3 的块
        逐行只需算出 (着色等级, 地/顶, mip) 三个下标，全屏没有一次浮点乘加。
        """
        L = self.SHADE_LEVELS
        M = self.MIP_COUNT
        fog = np.asarray(C_FOG, np.float32)

        f_mips = build_mip_chain(self.floor_tex, M)
        c_mips = build_mip_chain(self.ceil_tex, M)

        blocks = []
        offsets = np.zeros((L * 2 * M,), np.int32)
        cur = 0
        for i in range(L):
            vis = i / (L - 1)
            bright = 0.12 + 0.88 * vis
            fog_t = (1.0 - vis) ** 1.4
            for half, chain in ((0, c_mips), (1, f_mips)):
                for m in range(M):
                    tex = chain[m].astype(np.float32)
                    v = tex * bright
                    v += (fog - v) * fog_t
                    blk = np.clip(v, 0, 255).astype(np.uint8)
                    blocks.append(blk.reshape(-1, 3))
                    offsets[(i * 2 + half) * M + m] = cur
                    cur += blk.shape[0] * blk.shape[1]

        self._atlas = np.concatenate(blocks, axis=0)
        self._off = offsets
        self._mip_n = np.array([c.shape[0] for c in f_mips], np.int32)
        # mip 选择系数 n / posZ（垂直方向每行的世界跨度 = row_d² / posZ，
        # 它总是大于横向跨度，所以按垂直导数选 mip 即可）
        self._tile_r = 1.0 / FLOOR_TILE_UNITS
        self._mip_k = FLOOR_TEX_SIZE / (0.5 * self._fh * FLOOR_TILE_UNITS)
        self._mip_k_log = math.log2(self._mip_k)

    # ─── 对外接口 ───
    def draw_world(self, px, py, angle, pitch, zbuf, world,
                   max_depth=MAX_DEPTH):
        self._cam = (float(px), float(py), float(angle), float(pitch))
        horizon = H * 0.5 + pitch
        self.render_floor_ceiling(px, py, angle, horizon, max_depth)
        self.render_walls(px, py, angle, zbuf, world, max_depth, horizon)
        self.render_sprites(px, py, angle, zbuf, world, horizon, max_depth)

    # ─── 1. 地面 / 天花板投射 ───
    def render_floor_ceiling(self, px, py, angle, horizon, max_depth):
        fw, fh = self._fw, self._fh
        hz = horizon / self.floor_scale
        pos_z = 0.5 * fh
        M = self.MIP_COUNT
        L = self.SHADE_LEVELS

        # 每行的世界距离：d = posZ / |y - horizon|
        p = self._p
        np.subtract(self._ys, hz, out=p)
        is_floor = p >= 0.0                     # (1, fh) 地平线以下 → 地面
        np.abs(p, out=p)
        np.maximum(p, 0.5, out=p)
        row_d = self._row_d
        np.divide(pos_z, p, out=row_d)                 # (1, fh)

        dir_x, dir_y = math.cos(angle), math.sin(angle)
        plane_x, plane_y = -dir_y * TAN_HALF_FOV, dir_x * TAN_HALF_FOV
        rd0_x, rd0_y = dir_x - plane_x, dir_y - plane_y
        rd1_x, rd1_y = dir_x + plane_x, dir_y + plane_y

        # 世界坐标（按 [x, y] 索引，匹配 surfarray 布局）
        # 换算到 tile 单位：一块地砖 = FLOOR_TILE_UNITS 个世界格
        tr = self._tile_r
        fx, fy, tmp = self._fx, self._fy, self._tmp
        np.multiply(row_d, (rd1_x - rd0_x) * tr / fw, out=tmp)
        np.multiply(tmp, self._xs, out=fx)
        fx += row_d * rd0_x * tr + px * tr
        np.multiply(row_d, (rd1_y - rd0_y) * tr / fw, out=tmp)
        np.multiply(tmp, self._xs, out=fy)
        fy += row_d * rd0_y * tr + py * tr

        # 行内可见度 → 着色等级下标
        vis, lvl_f = self._vis, self._lvl_f
        np.multiply(row_d, -0.05, out=vis)
        vis += 1.0
        np.clip(vis, 0.0, 1.0, out=vis)
        tmp2 = np.minimum(row_d / max(1e-3, max_depth), 1.0)
        vis *= 1.0 - tmp2 ** 1.4
        np.multiply(vis, L - 1, out=lvl_f)
        np.multiply(lvl_f, 2, out=lvl_f)
        # 地平线以上取天花板(half=0)，以下取地面(half=1)
        np.add(lvl_f, is_floor, out=lvl_f)
        np.clip(lvl_f, 0.0, L * 2 - 1.0, out=lvl_f)

        # mip 选择：2^m ≈ n · row_d² / posZ —— 相邻行跨过的世界越长，mip 越粗
        np.log2(row_d, out=self._mip_f)
        np.multiply(self._mip_f, 2.0, out=self._mip_f)
        # +1.0 再截断 = 四舍五入，并额外留半级余量（宁可略糊，不要摩尔纹）
        np.add(self._mip_f, self._mip_k_log + 1.0, out=self._mip_f)
        np.copyto(self._mip, self._mip_f, casting='unsafe')
        np.clip(self._mip, 0, M - 1, out=self._mip)

        mip, mip_n = self._mip, self._m_n
        np.take(self._mip_n, mip, out=mip_n)
        n_mip_f = self._m_n_f
        np.copyto(n_mip_f, mip_n, casting='unsafe')
        off = self._off
        base = self._base
        lvl_i = self._lvl_i
        np.copyto(lvl_i, lvl_f, casting='unsafe')
        np.multiply(lvl_i, M, out=lvl_i)
        np.add(lvl_i, mip, out=lvl_i)
        np.take(off, lvl_i, out=base)                  # (1, fh)

        # 纹理内偏移：tx, ty ∈ [0, mip_n)
        idx = self._idx
        idx_f = self._idx_f
        np.floor(fy, out=tmp)
        np.subtract(fy, tmp, out=fy)
        np.floor(fx, out=tmp)
        np.subtract(fx, tmp, out=fx)
        np.multiply(fy, n_mip_f, out=fy)      # ty
        np.multiply(fx, n_mip_f, out=fx)      # tx
        # 纹理按 [x, y] 展平（x 为主序），所以是 tx * n + ty —— 不能写反
        np.multiply(fx, mip_n, out=idx_f)
        np.add(idx_f, fy, out=idx_f)
        np.copyto(idx, idx_f, casting='unsafe')
        np.add(idx, base, out=idx)

        out = self._atlas[idx.ravel()].reshape(fw, fh, 3)
        pygame.surfarray.blit_array(self._fc_surf, out)
        self._fc_up.blit(self._fc_surf, (0, 0))
        # 直接缩放进目标面：省掉一次全屏搬运（scale+blit 两步约 2.9ms → 1.6ms）
        pygame.transform.scale(self._fc_up, (W, H), self.surf)

    # ─── 2. 墙体（只把 '#' 当实体，装饰物交给精灵）───
    def _cast_solid(self, px, py, cos_v, sin_v, world):
        """DDA：只被实心墙(1)挡住，装饰物格子让射线穿过。"""
        mx, my = int(px), int(py)
        ddx = abs(1.0 / cos_v) if abs(cos_v) > 1e-9 else 1e18
        ddy = abs(1.0 / sin_v) if abs(sin_v) > 1e-9 else 1e18
        sx = 1 if cos_v > 0 else -1
        sy = 1 if sin_v > 0 else -1
        dist_x = (mx + 1 - px) * ddx if cos_v > 0 else (px - mx) * ddx
        dist_y = (my + 1 - py) * ddy if sin_v > 0 else (py - my) * ddy
        side = 0
        for _ in range(MAX_DEPTH * 4):
            if dist_x < dist_y:
                dist_x += ddx
                mx += sx
                side = 0
            else:
                dist_y += ddy
                my += sy
                side = 1
            if world.cell(mx, my) == 1:
                d = ((mx - px + (1 - sx) / 2) / cos_v if side == 0
                     else (my - py + (1 - sy) / 2) / sin_v)
                return abs(d), side
        return float(MAX_DEPTH), 0

    def render_walls(self, px, py, angle, zbuf, world,
                     max_depth=MAX_DEPTH, horizon=None):
        if horizon is None:
            horizon = H * 0.5
        max_d = max_depth if max_depth is not None else MAX_DEPTH
        col_w = self.col_w
        cos_a, sin_a = math.cos(angle), math.sin(angle)

        for i in range(NUM_RAYS):
            cos_r = _RAY_COS[i] * cos_a - _RAY_SIN[i] * sin_a
            sin_r = _RAY_SIN[i] * cos_a + _RAY_COS[i] * sin_a

            raw_d, side = self._cast_solid(px, py, cos_r, sin_r, world)
            if raw_d > max_d:
                raw_d = max_d
            zbuf[i] = raw_d

            dist = max(0.001, raw_d * _RAY_CORRECTION[i])
            h = min(H, int(H / dist))
            top = int(horizon - h * 0.5)

            fog_t = min(1.0, raw_d / max_d) * 0.7
            dark = 0.65 if side == 1 else 1.0
            bright = max(0.08, dark * (1.0 - raw_d * 0.025))

            near = (int(C_WALL_NR[0] * bright), int(C_WALL_NR[1] * bright),
                    int(C_WALL_NR[2] * bright))
            far = (int(C_WALL_FAR[0] * bright), int(C_WALL_FAR[1] * bright),
                   int(C_WALL_FAR[2] * bright))
            col = self._lerp(near, far, fog_t)
            col = self._lerp(col, C_FOG, fog_t ** 1.5)

            x = i * col_w
            pygame.draw.rect(self.surf, col, (x, top, col_w + 1, h))

    # ─── 3. 装饰物 billboard 精灵（按深度排序 + zbuf 逐列遮挡）───
    def render_sprites(self, px, py, angle, zbuf, world, horizon, max_depth):
        R = SPRITE_VIEW_RADIUS
        bx, by = int(math.floor(px)), int(math.floor(py))
        items = []
        for jy in range(by - R, by + R + 1):
            for ix in range(bx - R, bx + R + 1):
                ct = world.cell(ix + 0.5, jy + 0.5)
                if 2 <= ct <= 12:
                    dx, dy = (ix + 0.5) - px, (jy + 0.5) - py
                    if dx * dx + dy * dy > 4.0:      # 去掉贴脸的那一格
                        items.append((dx * dx + dy * dy, ix + 0.5, jy + 0.5, ct))
        if not items:
            return
        # 注意：不能用「圆形距离」筛可见性 —— 60° 广角下屏幕两侧的目标
        # 直线距离可以远超扫描半径，却仍在画面内。改为只按扫描盒收集，
        # 是否可见交给下面的屏幕坐标 + zbuf 判定。
        items.sort(reverse=True)  # 远 → 近

        dir_x, dir_y = math.cos(angle), math.sin(angle)
        plane_x, plane_y = -dir_y * TAN_HALF_FOV, dir_x * TAN_HALF_FOV
        inv_det = 1.0 / (plane_x * dir_y - dir_x * plane_y)

        col_w = self.col_w
        for _, wx, wy, ct in items:
            entry = self._sprites.get(ct)
            if entry is None:
                continue
            sprite, w_w, w_h = entry

            sdx, sdy = wx - px, wy - py
            t_x = inv_det * (dir_y * sdx - dir_x * sdy)
            t_y = inv_det * (-plane_y * sdx + plane_x * sdy)
            if t_y <= 0.08 or t_y > max_depth:
                continue

            screen_x = (W * 0.5) * (1.0 + t_x / t_y)
            wpx = K_PX_H * w_w / t_y
            hpx = K_PX_V * w_h / t_y
            if wpx < 1 or hpx < 1:
                continue

            left = screen_x - wpx * 0.5
            y_bottom = horizon + (0.5 * K_PX_V) / t_y
            top = y_bottom - hpx

            # 逐列深度遮挡
            iw = int(wpx)
            c0 = int(max(0.0, left))
            c1 = int(min(W - 1.0, left + wpx))
            if c1 < c0:
                continue
            vis = []
            run_start = None
            for cx in range(c0, c1 + 1):
                ri = int(cx / col_w)
                if ri < 0:
                    ri = 0
                elif ri >= NUM_RAYS:
                    ri = NUM_RAYS - 1
                ok = zbuf[ri] > t_y
                if ok and run_start is None:
                    run_start = cx
                elif not ok and run_start is not None:
                    vis.append((run_start, cx - run_start))
                    run_start = None
            if run_start is not None:
                vis.append((run_start, c1 - run_start + 1))
            if not vis:
                continue

            scaled = pygame.transform.scale(sprite, (iw, int(hpx)))
            shade = 1.0 - min(0.72, t_y * 0.045)
            scaled.set_alpha(int(255 * max(0.28, shade)))

            for rx, rw in vis:
                sx_off = rx - int(left)
                if sx_off < 0:
                    rw += sx_off
                    sx_off = 0
                if rw <= 0 or sx_off + rw > iw:
                    rw = min(rw, iw - sx_off)
                    if rw <= 0:
                        continue
                self.surf.blit(scaled, (rx, int(top)),
                               area=(sx_off, 0, rw, int(hpx)))

    # ─── 覆盖：不再用纯色渐变背景 ───
    def _ensure_bg_cache(self):
        self._bg_cache = None
