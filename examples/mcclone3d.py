# -*- coding: utf-8 -*-
"""mcclone3d 交互 demo —— 第一人称体素沙盒（《我的世界》风格机制致敬）。

    python examples/mcclone3d.py                # 交互
    python examples/mcclone3d.py --smoke 3      # 3 秒后自动退出（自检）
    python examples/mcclone3d.py --flag auto    # 自动机演示（不按键也能录）

## 接线只有一份

内核**不在本文件里 new**，而是走引擎的配置树：

    _engine.setup()                       # 定位引擎 + 登记服务短名 + 指配置目录
    await mount_tree(configs/cordis.mcclone.yml, want=WANT)

于是「demo 怎么挂的 = headless 验收怎么挂的」——`cli.py` 走的是同一棵树。
内核实例从 `ctx.mcclone_kernel` 取（配置树里的 `id`）。

## 玩法都在内核，本文件只管三件事

输入映射（键 → 内核方法）、网格上传（内核的 `chunk_meshes()` → GL 顶点表）、
以及画出来（世界 / 天空 / 选中框 / 准星 / hotbar）。
"""
from __future__ import annotations

import asyncio
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ⚠ 必须放在 sys.path **最前**：本文件名与包名同名（`examples/mcclone3d.py` vs 包
# `mcclone3d/`），而 `sys.path[0]` 在按路径运行时是 `examples/` —— 不置顶的话
# `from mcclone3d import ...` 会命中**本文件自己**，报
# 「cannot import name '_engine' from 'mcclone3d'（考虑改名）」（实测踩过）。
while _ROOT in sys.path:
    sys.path.remove(_ROOT)
sys.path.insert(0, _ROOT)

# stdio 编码兜底（本文件会打印中文与 ✔/⚠，GBK 控制台下 print 会抛异常把结论丢掉）
for _s in (sys.stdout, sys.stderr):
    _rec = getattr(_s, 'reconfigure', None)
    if _rec is not None:
        try:
            _rec(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

import pyglet                                                  # noqa: E402
from pyglet.gl import (GL_BLEND, GL_DEPTH_TEST, GL_FALSE, GL_LINES,  # noqa: E402
                       GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA, GL_TRIANGLES,
                       GL_TRUE, glBlendFunc, glDisable, glEnable)
from pyglet.math import Mat4, Vec3                             # noqa: E402

from mcclone3d import _engine, blocks as B, mesh, textures     # noqa: E402
from mcclone3d.kernel import EYE_HEIGHT                        # noqa: E402

#: 本 demo 需要配置树里的哪些服务（与 `cli.py` 同一份声明）
WANT = ('mcclone',)

# ---------------------------------------------------------------- 着色器 --
WORLD_VS = '''#version 330 core
in vec3 position;
in vec4 colors;
in vec2 tex_coords;
out vec4 v_col;
out vec2 v_uv;
out float v_dist;
uniform WindowBlock { mat4 projection; mat4 view; } window;
void main() {
    vec4 vp = window.view * vec4(position, 1.0);
    v_dist = length(vp.xyz);
    v_col = colors;
    v_uv = tex_coords;
    gl_Position = window.projection * vp;
}'''

# 顶点色 rgba：rgb = 面亮度（内核的 FACE_BRIGHT），a 预留自发光
WORLD_FS = '''#version 330 core
in vec4 v_col;
in vec2 v_uv;
in float v_dist;
out vec4 out_color;
uniform sampler2D u_atlas;
uniform vec3  u_fog;
uniform float u_fog_near;
uniform float u_fog_far;
void main() {
    vec4 tex = texture(u_atlas, v_uv);
    if (tex.a < 0.08) discard;                     // 火把这类镂空贴图
    vec3 lit = tex.rgb * v_col.rgb;
    lit = mix(lit, u_fog, smoothstep(u_fog_near, u_fog_far, v_dist));
    out_color = vec4(lit, tex.a);
}'''

SKY_VS = '''#version 330 core
in vec3 position;
in vec4 colors;
out vec2 v_uv;
void main() { v_uv = position.xy * 0.5 + 0.5; gl_Position = vec4(position.xy, 0.0, 1.0); }'''

SKY_FS = '''#version 330 core
in vec2 v_uv;
out vec4 out_color;
uniform vec3 u_top;
uniform vec3 u_bottom;
uniform float u_stars;                 // 0 = 白天无星、1 = 深夜满天
// 星空：**不用噪声贴图**，直接把屏幕像素当格子做哈希 ——
// 这样不引资源、不占显存，且"星星位置"在每台机器上完全一致（可截图对拍）。
float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}
void main() {
    float t = pow(clamp(v_uv.y, 0.0, 1.0), 0.7);
    vec3 col = mix(u_bottom, u_top, t);
    if (u_stars > 0.001) {
        vec2 cell = floor(v_uv * vec2(320.0, 180.0));
        float h = hash21(cell);
        // 只有极少数格子亮：阈值 0.994 ⇒ 约 0.6% 的格子，且越靠天顶越密
        float star = step(0.994, h) * u_stars * smoothstep(0.25, 0.95, v_uv.y);
        col += vec3(star) * (0.5 + 0.5 * hash21(cell + 7.1));
    }
    out_color = vec4(col, 1.0);
}'''

LINE_VS = '''#version 330 core
in vec3 position;
uniform WindowBlock { mat4 projection; mat4 view; } window;
uniform vec3 u_origin;
void main() { gl_Position = window.projection * window.view * vec4(position + u_origin, 1.0); }'''

# 生物：与方块同一套投影/图集，但**逐实例**给"脚底位置"与"受击染色"。
# 之所以不复用 WORLD_VS：那套的 `u_origin` 只用于选中框（画线），
# 而生物要的是"带贴图 + 顶点色 + 可染色"的实体着色 —— 混用会让方块的 uniform
# 被生物的循环覆盖（实测踩过：方块整片变成生物的位置）。
MOB_VS = '''#version 330 core
in vec3 position;
in vec4 colors;
in vec2 tex_coords;
out vec4 v_col;
out vec2 v_uv;
out float v_dist;
uniform WindowBlock { mat4 projection; mat4 view; } window;
uniform vec3 u_origin;                 // 生物的脚底中心（局部坐标 → 世界坐标）
void main() {
    vec4 vp = window.view * vec4(position + u_origin, 1.0);
    v_dist = length(vp.xyz);
    v_col = colors;
    v_uv = tex_coords;
    gl_Position = window.projection * vp;
}'''

MOB_FS = '''#version 330 core
in vec4 v_col;
in vec2 v_uv;
in float v_dist;
out vec4 out_color;
uniform sampler2D u_atlas;
uniform vec3  u_fog;
uniform float u_fog_near;
uniform float u_fog_far;
uniform vec3  u_tint;                  // 受击闪红
uniform vec3  u_light;                 // 该生物所在格的光照乘子（逐实例，见 _sync_mob_verts）
void main() {
    vec4 tex = texture(u_atlas, v_uv);
    if (tex.a < 0.08) discard;
    vec3 lit = tex.rgb * v_col.rgb * u_light * u_tint;
    lit = mix(lit, u_fog, smoothstep(u_fog_near, u_fog_far, v_dist));
    out_color = vec4(lit, tex.a);
}'''

#: 叠加层（准星）：顶点**已经是 NDC**，不乘任何矩阵
UI_VS = '''#version 330 core
in vec3 position;
in vec4 colors;
out vec4 v_col;
void main() { v_col = colors; gl_Position = vec4(position.xy, 0.0, 1.0); }'''

#: 叠加层的片元：用颜色属性而不是 uniform（同一个程序同时画准星/热键栏框）
UI_FS = '''#version 330 core
in vec4 v_col;
out vec4 out_color;
uniform vec4 u_color;
void main() { out_color = v_col * u_color; }'''

LINE_FS = '''#version 330 core
out vec4 out_color;
uniform vec4 u_color;
void main() { out_color = u_color; }'''

#: 单位盒的 12 条棱（两个端点一条线）
_BOX = []
for _i in range(8):
    _BOX.append((_i & 1, (_i >> 1) & 1, (_i >> 2) & 1))
_LINKS = ((0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3),
          (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7))
_BOX_V = []
for _a, _b in _LINKS:
    _BOX_V.append(_BOX[_a])
    _BOX_V.append(_BOX[_b])


def _mount_kernel():
    """按配置树挂载内核，返回内核实例。

    ⚠ 取服务的名字是**服务短名**（`ctx.mcclone`），不是配置树里的 `id`
    （实测踩过：写成 `ctx.mcclone_kernel` 拿到 `None`，一路崩到 `.summary()`）。
    原因在引擎侧：cordis 按 `- name:` 注册服务，`id:` 只是该 entry 的标识。
    """
    _engine.setup(verbose=True)
    from world3d.host.tree import mount_tree
    ctx = asyncio.run(mount_tree(_engine.config_dir() + os.sep + 'cordis.mcclone.yml',
                                 want=WANT, require_gl=False))
    kernel = getattr(ctx, _engine.SERVICE_NAME, None)
    if kernel is None:
        raise RuntimeError(
            f'配置树挂载后拿不到内核（ctx.{_engine.SERVICE_NAME} 是 None）——'
            f' 检查 configs/cordis.mcclone.yml 的 `- name:` 是否等于 {_engine.SERVICE_NAME!r}')
    return kernel


class McCloneApp:
    """本 demo 的窗口与主循环（**不用引擎的 DemoApp**：第一人称相机与准星/热键栏
    的输入语义和那套"演示动画"宿主差别较大，自己拿窗口更直接）。

    仍复用引擎的三件事：`world3d.math` 的矩阵、pyglet 的窗口、以及内核。
    """

    TITLE = 'mcclone3d · 体素沙盒（WASD 走 / 左键挖 / 右键放 / 1-9 选方块）'
    HELP = ('WASD 走  SPACE 跳  F 飞行  Ctrl 加速  鼠标左键拖动转视角  '
            '左键挖 右键放  1-9 换方块  R 重生  Ctrl+S 存档  ESC 退出')
    FOV = 68.0
    Z_NEAR, Z_FAR = 0.08, 400.0

    def __init__(self, width=1280, height=720, kernel=None, auto=False,
                 verbose=False):
        self.kernel = kernel if kernel is not None else _mount_kernel()
        self.window = pyglet.window.Window(width, height, caption=self.TITLE,
                                           resizable=True)
        # ⚠ 投影要按**窗口实际尺寸**算（窗口可能被系统 DPI 缩放）：先前按构造参数算，
        # 1600×900 的窗口配 1280×720 的投影 ⇒ 画面横向拉伸（实测 proj[0]=0.834，应为 1.46）。
        # 注意 `_apply_projection` 依赖 `self.window`，所以它只能放在建窗之后。
        self.window.push_handlers(on_draw=self.on_draw, on_resize=self.on_resize,
                                  on_key_press=self.on_key_press,
                                  on_mouse_press=self.on_mouse_press,
                                  on_mouse_drag=self.on_mouse_drag,
                                  on_mouse_scroll=self.on_mouse_scroll)
        self.window.view = Mat4()
        self.time = 0.0
        self.auto = bool(auto)
        self.verbose = bool(verbose)
        self._last_beat = -1.0
        self._shot_pending = None          # `--shot`：到点后**在 on_draw 里**抓帧
        self._keys = set()
        self._verts: dict = {}
        self._setup_gl()
        self._apply_projection(self.window.width, self.window.height)
        self._say_spawn()

    # ------------------------------------------------------------ GL 资源
    def _setup_gl(self):
        """建 GL 资源：三套着色器 + 程序化图集纹理 + 叠加层几何。

        **没有外部素材**：图集像素由 `mcclone3d.textures` 现算（16×16 像素材质），
        这里只负责上传；`GL_NEAREST` 是必须的（线性过滤会把像素质感糊掉）。
        """
        from pyglet.graphics.shader import Shader, ShaderProgram
        from pyglet.gl import GL_NEAREST, glClearColor
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.6, 0.75, 0.9, 1.0)

        self.world_prog = ShaderProgram(Shader(WORLD_VS, 'vertex'),
                                        Shader(WORLD_FS, 'fragment'))
        self.sky_prog = ShaderProgram(Shader(SKY_VS, 'vertex'),
                                      Shader(SKY_FS, 'fragment'))
        self.line_prog = ShaderProgram(Shader(LINE_VS, 'vertex'),
                                       Shader(LINE_FS, 'fragment'))
        # 生物：**独立一套**（见 MOB_VS 的说明：与 WORLD 共用会让 uniform 互相覆盖）
        self.mob_prog = ShaderProgram(Shader(MOB_VS, 'vertex'),
                                      Shader(MOB_FS, 'fragment'))

        # 图集（程序化生成 → 上传）
        # ⚠ **必须 NEAREST**：像素材质放大要用硬边，线性过滤会把它糊成"毛玻璃"
        # （实测第一版就是糊的：远看草地像水彩）。mipmap 只用于缩小时防闪烁。
        size = textures.LAYOUT.size
        img = pyglet.image.ImageData(size, size, 'RGBA', textures.build_atlas())
        try:
            img = img.get_mipmapped_text()
            mip = True
        except Exception:                              # 老驱动/尺寸不支持就退回单级
            img = img.get_texture()
            mip = False
        self.atlas = img
        from pyglet.gl import GL_NEAREST_MIPMAP_LINEAR
        self.atlas.min_filter = GL_NEAREST_MIPMAP_LINEAR if mip else GL_NEAREST
        self.atlas.mag_filter = GL_NEAREST

        # 天空：全屏四边形（顶点着色器直接吐 NDC）
        quad = (-1.0, -1.0, 0.0, 1.0, -1.0, 0.0, 1.0, 1.0, 0.0,
                -1.0, -1.0, 0.0, 1.0, 1.0, 0.0, -1.0, 1.0, 0.0)
        self.sky_quad = self.sky_prog.vertex_list(
            6, GL_TRIANGLES, position=('f', quad), colors=('f', (1.0,) * 24))

        # 选中框：单位盒线框（每帧只换 u_origin/u_color）
        flat = []
        for (vx, vy, vz) in _BOX_V:
            flat += [vx, vy, vz]
        self.box = self.line_prog.vertex_list(
            len(_BOX_V), GL_LINES, position=('f', flat))

        # 准星：屏幕中心的小十字（顶点已是 NDC）
        self.ui_prog = ShaderProgram(Shader(UI_VS, 'vertex'), Shader(UI_FS, 'fragment'))
        c = 0.012
        ch = (-c, 0.0, 0.0, c, 0.0, 0.0, 0.0, -c, 0.0, 0.0, c, 0.0)
        self.crosshair = self.ui_prog.vertex_list(4, GL_LINES, position=('f', ch),
                                                  colors=('f', (1.0,) * 16))
        # --- HUD（血条 / 饥饿条 / hotbar / 死亡遮罩）---
        # 分两条顶点表：**静态底板**（槽位底，建一次）+ **动态条**（每帧按生存状态改）。
        # 这样每帧只改动态那条（≤22 个矩形），静态的 29 个矩形一个字节都不动。
        self._hud_quads_static = self._build_hud_layout()
        flat = []
        for (x0, y0, x1, y1, _c) in self._hud_quads_static:
            flat += [x0, y0, 0.0, x1, y0, 0.0, x1, y1, 0.0,
                     x0, y0, 0.0, x1, y1, 0.0, x0, y1, 0.0]
        cols = []
        for (_x0, _y0, _x1, _y1, col) in self._hud_quads_static:
            cols += list(col) * 6
        self.hud_bg = self.ui_prog.vertex_list(len(self._hud_quads_static) * 6,
                                               GL_TRIANGLES,
                                               position=('f', flat), colors=('f', cols))
        # 动态条的最大条数：血 10 + 饥饿 10 + hotbar 选中框 1 + 死亡遮罩 1
        self._hud_dyn_max = 22
        self.hud_fg = self.ui_prog.vertex_list(
            self._hud_dyn_max * 6, GL_TRIANGLES,
            position=('f', [0.0] * (self._hud_dyn_max * 18)),
            colors=('f', [1.0] * (self._hud_dyn_max * 24)))
        # 复用的缓冲（每帧原地改写，避免 60fps 下反复分配）
        self._hud_pos = [0.0] * (self._hud_dyn_max * 18)
        self._hud_col = [1.0] * (self._hud_dyn_max * 24)
        self._hud_used_quads = 0
        # --- Phase 2-C 天气：屏幕空间降水（雨=竖线，雪=短线+摆动）---
        # 复用 `ui_prog`（NDC 顶点表 + uniform 颜色），不引第二套着色器。
        self._rain_max = 320
        self._rain = self.ui_prog.vertex_list(self._rain_max * 2, GL_LINES,
                                              position=('f', [0.0] * (self._rain_max * 6)),
                                              colors=('f', [1.0] * (self._rain_max * 8)))
        self._rain_pos = [0.0] * (self._rain_max * 6)
        self._rain_col = [1.0] * (self._rain_max * 8)
        self._rain_t = 0.0
        print(f'[mcclone3d] 图集 {size}x{size} / {len(textures.ATLAS_TILE_NAMES)} 张贴图，'
              f'着色器 3 套 + HUD 就绪', flush=True)

    # ------------------------------------------------------------ HUD 几何
    @staticmethod
    def _hud_quads(items):
        """把 `[(x0,y0,x1,y1,rgba)]` 展开成三角形顶点（返回 NDC 坐标元组列表）。"""
        out = []
        for (x0, y0, x1, y1, col) in items:
            out.append((x0, y0, x1, y1, col))
        return out

    def _build_hud_layout(self):
        """静态底板：hotbar 底、血条槽、饥饿条槽。

        NDC 坐标（x 右、y 上，各 ±1）；**按 16:9 设计**，窗口比例变了会拉伸
        —— 这是刻意取舍：像素风 UI 拉伸一点不影响读，省掉一套正交投影。
        """
        q = []
        # hotbar：9 格，底部居中
        slot_w, gap = 0.062, 0.006
        total = 9 * slot_w + 8 * gap
        x = -total / 2
        for _ in range(9):
            q.append((x, -0.94, x + slot_w, -0.86, (0.0, 0.0, 0.0, 0.42)))
            x += slot_w + gap
        # 血条槽（左）与饥饿条槽（右）：10 段
        seg_w, seg_gap = 0.036, 0.005
        bx = -0.92
        for _ in range(10):
            q.append((bx, -0.80, bx + seg_w, -0.755, (0.0, 0.0, 0.0, 0.42)))
            bx += seg_w + seg_gap
        hx = 0.92 - 10 * seg_w - 9 * seg_gap
        for _ in range(10):
            q.append((hx, -0.80, hx + seg_w, -0.755, (0.0, 0.0, 0.0, 0.42)))
            hx += seg_w + seg_gap
        return q

    def _hud_dynamic_quads(self):
        """按当前生存状态生成动态条：血量、饥饿、hotbar 选中框、死亡遮罩。"""
        k = self.kernel
        q = []
        seg_w, seg_gap = 0.036, 0.005
        # 血量：把 0..max 映射成 10 段（**半颗心也画**，所以按比例填宽）
        hp_frac = max(0.0, min(1.0, k.health / max(1e-6, k.max_health)))
        for i in range(10):
            x0 = -0.92 + i * (seg_w + seg_gap)
            fill = max(0.0, min(1.0, hp_frac * 10 - i))
            if fill > 0:
                q.append((x0, -0.80, x0 + seg_w * fill, -0.755, (0.82, 0.18, 0.18, 0.95)))
        # 饥饿
        hg_frac = max(0.0, min(1.0, k.hunger / max(1e-6, k.max_hunger)))
        base = 0.92 - 10 * seg_w - 9 * seg_gap
        for i in range(10):
            x0 = base + i * (seg_w + seg_gap)
            fill = max(0.0, min(1.0, hg_frac * 10 - i))
            if fill > 0:
                q.append((x0, -0.80, x0 + seg_w * fill, -0.755, (0.85, 0.62, 0.22, 0.95)))
        # hotbar 选中框
        slot_w, gap = 0.062, 0.006
        total = 9 * slot_w + 8 * gap
        x = -total / 2 + k.selected * (slot_w + gap)
        q.append((x, -0.94, x + slot_w, -0.86, (1.0, 1.0, 1.0, 0.35)))
        # 死亡遮罩（整屏偏红）
        if k.state == 'dead':
            q.append((-1.0, -1.0, 1.0, 1.0, (0.55, 0.05, 0.05, 0.45)))
        return q

    def _refresh_hud(self):
        """把动态条写进顶点表。

        ⚠ pyglet 2.1 的 `VertexList` **没有 `.vertices` 可赋值**（实测
        `AttributeError: 'VertexList' object has no attribute 'vertices'`）——
        要改内容得走 `set_attribute_data(name, data)`。
        本函数把"当前该画几个矩形"写进**复用的缓冲**（不每帧新建列表），
        然后一次推给 GPU；多出来的顶点用 `resize` 收掉，否则会重复画上一帧的残影。
        """
        quads = self._hud_dynamic_quads()[:self._hud_dyn_max]
        pos, col = self._hud_pos, self._hud_col
        i = 0
        for (x0, y0, x1, y1, c4) in quads:
            for (vx, vy) in ((x0, y0), (x1, y0), (x1, y1),
                             (x0, y0), (x1, y1), (x0, y1)):
                pos[i * 3 + 0] = vx
                pos[i * 3 + 1] = vy
                pos[i * 3 + 2] = 0.0
                col[i * 4 + 0] = c4[0]
                col[i * 4 + 1] = c4[1]
                col[i * 4 + 2] = c4[2]
                col[i * 4 + 3] = c4[3]
                i += 1
        n = i
        if n != self._hud_used_quads * 6:
            self.hud_fg.resize(max(1, n))       # 顶点数按本帧实际用量收缩/扩张
            self._hud_used_quads = n // 6
        if n:
            self.hud_fg.set_attribute_data('position', pos[:n * 3])
            self.hud_fg.set_attribute_data('colors', col[:n * 4])

    def _apply_projection(self, w, h):
        self.window.projection = Mat4.perspective_projection(
            w / max(1, h), z_near=self.Z_NEAR, z_far=self.Z_FAR, fov=self.FOV)
        self.window.view = Mat4()

    def meshes_ready(self):
        """世界网格是否已全部上传（截图 / 验收前的门）。"""
        return not self.kernel.dirty_chunks

    def _say_spawn(self):
        s = self.kernel.summary()
        print(f'[mcclone3d] spawn={s["pos"]} 种子={s["seed"]} 世界={self.kernel.size}'
              f'x{self.kernel.height} 方块={s["blocks"]}', flush=True)

    def sanity_report(self, tag='sanity'):
        """自检式体检：相机 / 朝向 / 网格 / 视锥内是否有面。

        为什么要有它：**"画面看着不对"不是判据**。渲染问题必须能量化——
        实测吃过两次亏：一次把"玩家悬空"误判成渲染错，一次把雾当成了没画出来。
        这里把"眼睛在哪、朝哪、几个区块的顶点表、视锥里有没有面"一次打清楚，
        让"看到的东西"与"数值"对得上。
        """
        k = self.kernel
        eye, target = self._camera()
        w = k.weather_state()                # Phase 2-C：天气快照（打印与截图对拍用）
        d = k.look_dir()
        inside = 0
        total = 0
        for key, vl in self._verts.items():
            cx, cy, cz = key
            x0, y0, z0 = cx * 16, cy * 16, cz * 16
            vx, vy, vz = x0 + 8, y0 + 8, z0 + 8
            total += 1
            if abs(vx - eye[0]) < 60 and abs(vy - eye[1]) < 60 and abs(vz - eye[2]) < 60:
                inside += 1
        print(f'[{tag}] eye={tuple(round(v, 1) for v in eye)} '
              f'dir={tuple(round(v, 3) for v in d)} '
              f'pos={tuple(round(v, 1) for v in k.pos)} '
              f'块表={len(self._verts)}（近处 {inside}）'
              f' 面总数={k.mesh_stats()["faces"]} '
              f'proj[0]={self.window.projection[0]:.3f} '
              f'定值面={k.world.get(128, 32, 128)} '
              # Phase 2-C：天气读数与截图/日志一起看（"看着像下雨"不算判据）
              f'天气={w["name"]}({w["kind"]}, 强度{w["intensity"]:.2f}, '
              f'天光×{w["light_scale"]:.2f}) '
              f'水={k.fluid.flowing_count()}格', flush=True)
        return eye, d

    # ------------------------------------------------------------ 输入
    def on_resize(self, w, h):
        self.window.projection = Mat4.perspective_projection(
            w / max(1, h), z_near=self.Z_NEAR, z_far=self.Z_FAR, fov=self.FOV)

    def on_key_press(self, symbol, modifiers):
        k = self.kernel
        if symbol == pyglet.window.key.ESCAPE:
            self.window.close()
            return
        if symbol == pyglet.window.key.F:
            k.flying = not k.flying
            print(f'[mcclone3d] 飞行={"开" if k.flying else "关"}', flush=True)
            return
        if symbol == pyglet.window.key.R:
            k.reset()
            self._drop_meshes()
            print('[mcclone3d] 重生', flush=True)
            return
        digit = getattr(pyglet.window.key, '_%d' % 0, None)
        for i in range(1, 10):
            if symbol == getattr(pyglet.window.key, '_%d' % i):
                k.select(i - 1)
                print(f'[mcclone3d] 选中 {i}: '
                      f'{B.name_of(k.selected_block())}', flush=True)
        if symbol == pyglet.window.key.S and (modifiers & pyglet.window.key.MOD_CTRL):
            import json
            path = os.path.join(_ROOT, 'saves', 'quicksave.mc3d')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            k.save(path)
            print(f'[mcclone3d] 已存档 {path}', flush=True)
        self._keys.add(symbol)

    def on_mouse_press(self, x, y, button, modifiers):
        k = self.kernel
        if button == pyglet.window.MOUSE_LEFT:
            ok, name = k.dig()
            if ok:
                print(f'[mcclone3d] 挖掉 {name}', flush=True)
            else:
                # 没有方块可挖时这一下挥向生物（`attack()` 的文档承诺；
                # 先前 demo 根本没接，玩家打不到生物）
                r = k.attack()
                if r is not None:
                    print(f'[mcclone3d] 击中 {r[0]}' + ('（致死）' if r[1] else ''),
                          flush=True)
        elif button == pyglet.window.MOUSE_RIGHT:
            ok, at = k.place()
            if ok:
                print(f'[mcclone3d] 放下 {B.name_of(k.selected_block())} @ {at}', flush=True)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.kernel.yaw += dx * 0.26
        self.kernel.pitch = max(-89.0, min(89.0, self.kernel.pitch - dy * 0.26))

    def on_mouse_scroll(self, x, y, sx, sy):
        self.kernel.scroll(-1 if sy > 0 else 1)

    def _move_input(self):
        key = pyglet.window.key
        fwd = (1.0 if key.W in self._keys else 0.0) - (1.0 if key.S in self._keys else 0.0)
        side = (1.0 if key.D in self._keys else 0.0) - (1.0 if key.A in self._keys else 0.0)
        jump = (key.SPACE in self._keys) or (key.LSHIFT in self._keys)
        return (fwd, side), jump

    # ------------------------------------------------------------ 网格
    def _drop_meshes(self):
        for vl in self._verts.values():
            vl.delete()
        self._verts.clear()

    def _sync_meshes(self, budget=16):
        """把内核新标脏的区块上传成 GL 顶点表（每帧限量，避免长时间卡顿）。

        预算的必要性：首次进入要上传整张地图（256 个区块）；每帧全做完会让首帧
        卡住好几秒。**默认 16** 是实测量出来的折中（每区块约 30~80ms：建面 + 上传）。
        ⚠ 截图/验收前必须等 `meshes_ready()` 为真 —— 否则拍到的是"还没传完的世界"，
        那会被误读成"渲染丢了地形"（实测踩过：3 秒时只传了 172/256）。
        """
        from pyglet.gl import GL_TRIANGLES as _T
        built = self.kernel.chunk_meshes(limit=budget)
        for key, _stats in built:
            old = self._verts.pop(key, None)
            if old is not None:
                old.delete()
            mb, _st = self.kernel._meshes[key]
            if not mb.indices:
                continue
            self._verts[key] = self.world_prog.vertex_list_indexed(
                len(mb.positions) // 3, _T, mb.indices,
                position=('f', mb.positions), colors=('f', mb.colors),
                tex_coords=('f', mb.uvs))
        return built

    # ------------------------------------------------------------ 主循环
    def _camera(self):
        k = self.kernel
        eye = k.eye_pos()
        dx, dy, dz = k.look_dir()
        return eye, (eye[0] + dx, eye[1] + dy, eye[2] + dz)

    def update(self, dt):
        self.time += dt
        if self.auto:
            self.kernel.auto_step(dt)
        else:
            move, jump = self._move_input()
            self.kernel.step(dt, move, jump)
        self._sync_meshes()
        # 心跳（`--flag verbose`）：目视验证时要能看到"玩家到底站在哪"
        if self.verbose and self.time - self._last_beat > 1.0:
            self._last_beat = self.time
            s = self.kernel.summary()
            # 手上那格的光照也打出来：**"看着暗"与"光照数值低"要能对上**，
            # 否则目视结论没有依据（说不出是材质暗还是没光）
            lv = self.kernel.light_at(int(self.kernel.pos[0]),
                                      int(self.kernel.pos[1]) + 1,
                                      int(self.kernel.pos[2]))
            print(f'[mcclone3d] t={self.time:5.1f}s pos={s["pos"]} '
                  f'grounded={s["grounded"]} fly={s["flying"]} '
                  f'faces={s["faces"]} 挖={s["dig"]} 放={s["placed"]} | '
                  f'{s["day"]:.0f}s day={s["day_factor"]:.2f} '
                  f'{"夜" if s["night"] else "昼"} 头顶光={lv[0]}(方块{lv[1]}/天{lv[2]}) '
                  f'已算光={s["lit_chunks"]}块', flush=True)

    def _sync_mob_verts(self):
        """每帧把生物画出来（**每种生物只上传一份网格**，实例靠 uniform 变换）。

        生物网格是"局部坐标下的一份"（`mesh.build_mob_mesh`），所以：
        * **新增一种生物不需要改渲染代码**（`MobKind.parts` 是数据）；
        * 40 只羊只占一份网格的显存。

        朝向不做旋转：本项目的生物是块状的（1×1 的部件），转不转肉眼看不出，
        而加一套矩阵 uniform 会让"每个实例一次 draw call"变成"每次都要算矩阵"。
        这条取舍是**故意的**，不是漏了。
        """
        from pyglet.gl import GL_TRIANGLES as _T
        k = self.kernel
        if not hasattr(self, '_mob_verts'):
            self._mob_verts = {}
        if not k.mobs:
            if self._mob_verts:
                for vl in self._mob_verts.values():
                    vl.delete()
                self._mob_verts = {}
            return
        # 新出现的生物种类：上传一份网格
        for mob in k.mobs:
            name = mob.kind.name
            if name in self._mob_verts:
                continue
            mb, _st = mesh.build_mob_mesh(mob.kind)
            if not mb.indices:
                self._mob_verts[name] = None
                continue
            self._mob_verts[name] = self.mob_prog.vertex_list_indexed(
                len(mb.positions) // 3, _T, mb.indices,
                position=('f', mb.positions), colors=('f', mb.colors),
                tex_coords=('f', mb.uvs))
        st = k.cycle.sky()
        night = 1.0 - max(0.0, min(1.0, k.day_factor()))   # 与区块网格同一口径
        self.mob_prog.use()
        self.mob_prog['u_atlas'] = 0
        self.atlas.bind()
        self.mob_prog['u_fog'] = tuple(st['horizon'])
        self.mob_prog['u_fog_near'] = 110.0
        self.mob_prog['u_fog_far'] = 260.0
        for mob in k.mobs:
            vl = self._mob_verts.get(mob.kind.name)
            if vl is None:
                continue
            # 部件以**中心**为原点 ⇒ 平移到"脚底中心"要减半格
            self.mob_prog['u_origin'] = (mob.pos[0] - 0.5, mob.pos[1], mob.pos[2] - 0.5)
            # 受击闪烁：直接乘一层红（不引第二套材质）
            self.mob_prog['u_tint'] = ((1.0, 0.30, 0.30) if mob.hurt_t > 0.0
                                       else (1.0, 1.0, 1.0))
            # 逐实例光照：取该生物**脚底那格**的有效光（方块光与天光折算取大），
            # 与区块网格的 `face_light` 同口径。网格按种类只建一份，
            # 所以光照必须走 uniform 而不是烘进顶点色（mesh.build_mob_mesh 的说明）。
            # ⚠ `light_color` 第一参是**标量**亮度（面亮度），不是三元组 ——
            # 传 (1,1,1) 会炸 "can't multiply sequence by non-int"。
            mx, my, mz = int(mob.pos[0]), int(mob.pos[1]), int(mob.pos[2])
            lvl = max(k.light.block(mx, my, mz),
                      int(round(k.light.sky(mx, my, mz) * k.day_factor())))
            self.mob_prog['u_light'] = mesh.light_color(1.0, lvl, night)
            vl.draw(_T)

    def on_draw(self):
        self.window.clear()
        self.window.view = self._view_matrix()
        self.update(1 / 60.0)
        self._draw_sky()
        self._draw_world()
        # 生物在方块**之后**画（它们有实心几何，得参与深度测试）
        self._sync_mob_verts()
        self._draw_selection()
        self._update_precip(1 / 60.0)
        self._draw_precip()
        self._draw_overlay()
        if self._shot_pending is not None:
            self._capture(self._shot_pending)
            self._shot_pending = None
            pyglet.clock.schedule_once(lambda dt: self.window.close(), 0.05)

    def _capture(self, path):
        """截当前帧到 PNG（目视验证用；`shots/` 已 gitignore）。

        必须**在 on_draw 里**抓（此时后台缓冲还是本帧内容）—— 换到定时器里抓，
        拿到的往往是清屏后的空帧，看着像"渲染全黑"。
        """
        from pyglet.image import get_buffer_manager
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        get_buffer_manager().get_color_buffer().save(path)
        print(f'[mcclone3d] 截图 {path}', flush=True)

    def _view_matrix(self):
        eye, target = self._camera()
        return Mat4.look_at(Vec3(*eye), Vec3(*target), Vec3(0.0, 1.0, 0.0))

    def _draw_sky(self):
        """天穹：色带**全部来自内核的昼夜状态**（`sun.sky_at`）。

        ⚠ Phase 2-A 之前这里是写死的正午色（`u_top`/`u_bottom` 两个常量）——
        于是"地面按昼夜变暗、天空纹丝不动"，截图一眼就能看出是假的。
        现在顶色取 `sky`、地平线色取 `horizon`，两者都由引擎的 `sky_state` 给出，
        与光照**同源同相位**（`day_factor` 就是从同一个 sun 高度角算的）。
        """
        st = self.kernel.cycle.sky()
        glDisable(GL_DEPTH_TEST)
        self.sky_prog.use()
        self.sky_prog['u_top'] = tuple(st['sky'])
        self.sky_prog['u_bottom'] = tuple(st['horizon'])
        self.sky_prog['u_stars'] = float(st.get('stars', 0.0))
        self.sky_quad.draw(GL_TRIANGLES)
        glEnable(GL_DEPTH_TEST)

    def _draw_world(self):
        st = self.kernel.cycle.sky()
        self.world_prog.use()
        self.world_prog['u_atlas'] = 0
        self.atlas.bind()
        # 雾色跟地平线色一致：否则夜里会出现"远处一片白雾"这种穿帮
        self.world_prog['u_fog'] = tuple(st['horizon'])
        # 雾的起止距离按"可玩视距"调：太近会把 70 格外的地形全洗成天空色
        # （实测踩过：飞到 14 格高空俯视时，整个远景被雾吃掉，看着像"世界是空的"）
        self.world_prog['u_fog_near'] = 110.0
        self.world_prog['u_fog_far'] = 260.0
        for vl in self._verts.values():
            vl.draw(GL_TRIANGLES)

    def _draw_selection(self):
        hit = self.kernel.raycast()
        if hit is None:
            return
        (x, y, z), _n = hit
        self.line_prog.use()
        self.line_prog['u_origin'] = (x - 0.002, y - 0.002, z - 0.002)
        self.line_prog['u_color'] = (0.05, 0.05, 0.05, 0.9)
        self.box.draw(GL_LINES)

    # ------------------------------------------------------------ 天气粒子
    #: 降水粒子的确定性伪随机（不用 random —— 回放要对得上）
    @staticmethod
    def _rnd(i: int, salt: int) -> float:
        return ((i * 2654435761 + salt * 40503) & 0x7FFFFFFF) / 2147483647.0

    def _update_precip(self, dt: float):
        """屏幕空间降水（**纯表现层**：不参与任何玩法判定）。

        雨是竖直短线、雪是慢速短线 + 横向摆动；到底部即回到顶部循环。
        用屏幕 NDC 坐标，不做深度测试 ⇒ 永远画在最前（雨雪在镜头前）。
        """
        k = self.kernel
        st = k.weather_state()
        kind, inten = st['kind'], st['intensity']
        self._rain_t += dt
        if kind == 'clear' or inten <= 0.02:
            # ⚠ **不要**在这里 resize + 写空数据：`resize(2)` 之后
            # `set_attribute_data` 收到的是整表长度的数组 ⇒ ValueError
            # （"Expected 6, got 1920"，实测踩过）。晴天压根不画，直接返回。
            return
        snow = (kind == 'snow')
        speed = 1.35 if snow else 3.2
        n = int(self._rain_max * min(1.0, inten))
        n += n % 2
        pos, col = self._rain_pos, self._rain_col
        t = self._rain_t
        for i in range(n):
            sx = self._rnd(i, 1) * 2.0 - 1.0                  # 起始 x（NDC）
            phase = self._rnd(i, 2)
            # ⚠ y 的初相位必须**按序号均匀铺满整个周期**（`i / n * SPAN`），
            #   不能只靠 `phase * 常数`：那样 320 条线会挤成几团"锯齿粗线"
            #   （实测截图里只看得见 2~3 条）。速度只做 ±20% 微差，保持自然。
            fall = (t * speed * (0.8 + 0.4 * phase) + (i / max(1.0, n)) * 2.6) % 2.6
            sy = 1.0 - fall / 1.3                            # 1 → -1 循环
            x = sx + (0.03 * math.sin(t * 1.7 + i) if snow else 0.0)
            ln = 0.028 if snow else 0.075
            j = i * 6
            pos[j] = x; pos[j + 1] = sy; pos[j + 2] = 0.0
            pos[j + 3] = x + (0.012 if snow else 0.004)
            pos[j + 4] = sy - ln; pos[j + 5] = 0.0
            c = i * 8
            a = 0.55 + 0.35 * inten
            for q in range(2):
                col[c + q * 4] = 1.0
                col[c + q * 4 + 1] = 1.0
                col[c + q * 4 + 2] = 1.0
                col[c + q * 4 + 3] = a
        # ⚠ `resize` 收的是**顶点数**，而 n 是**线段数** ⇒ 必须 ×2
        #   （漏了会报 "Expected 960, got 1920"，实测踩过）
        self._rain.resize(max(2, n * 2))
        self._rain.set_attribute_data('position', pos[:n * 6])
        self._rain.set_attribute_data('colors', col[:n * 8])

    def _draw_precip(self):
        st = self.kernel.weather_state()
        if st['kind'] == 'clear' or st['intensity'] <= 0.02:
            return
        # ⚠ **必须关深度测试**（同 `_draw_overlay`）：粒子在 NDC 的 z=0，
        #   而世界几何的深度更小 ⇒ 开着深度测试时**只有天空区域的雨线可见**，
        #   地面上的全被地形遮住（实测：满屏只看得见 2~3 条）。
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.ui_prog.use()
        self.ui_prog['u_color'] = (1.0, 1.0, 1.0, 0.75)
        self._rain.draw(GL_LINES)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_overlay(self):
        """准星 + HUD（血条 / 饥饿条 / hotbar / 死亡遮罩）。顶点已是 NDC。"""
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.ui_prog.use()
        self.ui_prog['u_color'] = (1.0, 1.0, 1.0, 1.0)
        self.hud_bg.draw(GL_TRIANGLES)          # 槽位底
        self._refresh_hud()                     # 按当前状态填动态条
        self.hud_fg.draw(GL_TRIANGLES)
        self.ui_prog['u_color'] = (1.0, 1.0, 1.0, 0.55)
        self.crosshair.draw(GL_LINES)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='mcclone3d 交互 demo')
    ap.add_argument('--smoke', type=float, default=None,
                    help='N 秒后自动关闭（自检用）')
    ap.add_argument('--shot', default=None, help='N 秒后截一帧到该路径再退出')
    ap.add_argument('--flag', default='', help='逗号分隔：auto = 跑自动机, verbose = 每秒打印状态')
    ap.add_argument('--width', type=int, default=1280)
    ap.add_argument('--height', type=int, default=720)
    ap.add_argument('--time', type=float, default=None,
                    help='世界时刻（秒，一昼夜 600s：0=日出 150=正午 300=日落 450=午夜）')
    ap.add_argument('--phase', type=float, default=None,
                    help='直接给相位 0..1（截图常用：0.25 正午 / 0.52 日落 / 0.75 午夜）')
    args = ap.parse_args(argv)

    flags = set(x.strip() for x in args.flag.split(',') if x.strip())
    app = McCloneApp(args.width, args.height, auto='auto' in flags,
                     verbose='verbose' in flags)
    # 时刻在**内核装配之后**设（内核是引擎服务，demo 只调它的接口）
    if args.phase is not None:
        app.kernel.cycle.skip_to_phase(args.phase)
    elif args.time is not None:
        app.kernel.cycle.time = float(args.time)
    if args.phase is not None or args.time is not None:
        from mcclone3d import sun as _sun
        print(f'[mcclone3d] 时刻：{_sun.describe(app.kernel.cycle.time)} '
              f'day_factor={app.kernel.day_factor():.3f}', flush=True)
        # 时刻变了 ⇒ 顶点色里的光照要重刷（几何不用重建）
        app.kernel.dirty_chunks |= set(app.kernel._meshes or ())
    if args.shot:
        # `--shot <路径>`：N 秒（默认 2.0）后设一个"待抓"标记 —— 真正的抓帧发生在
        # `on_draw` 里（后台缓冲才有效），抓完自己关窗。
        delay = args.smoke if args.smoke else 2.0
        pyglet.clock.schedule_once(
            lambda dt: setattr(app, '_shot_pending', args.shot), delay)
    elif args.smoke:
        pyglet.clock.schedule_once(lambda dt: app.window.close(), args.smoke)
    pyglet.app.run()
    print('== MCCLONE_DEMO_OK ==', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
