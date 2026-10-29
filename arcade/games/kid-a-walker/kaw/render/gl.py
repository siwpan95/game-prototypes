# -*- coding: utf-8 -*-
"""ModernGL 真 3D 渲染器 + 后处理管线（Stage 2 / 3 / 4）。

两种呈现模式，走**同一条 GL 管线**（因此无头验证也能覆盖后处理）：

- ``window``   ：主窗口用 ``pygame.OPENGL`` 建立，moderngl 接管该上下文。
  3D → scene FBO → bloom（EEVEE 式 mip 链：软膝亮通 → Karis box 下采样 →
  tent 上采样累加，半精度 HDR）→ 后处理(扫描线/暗角/曝光) → 屏幕帧缓冲，
  2D 覆盖层（HUD/粒子/界面）作为纹理叠在最上层。**无像素读回**，最快路径。
- ``offscreen``：主窗口保持 pygame 2D，GL 在独立离屏上下文里渲染同一条管线，
  最后把合成结果读回、blit 到 2D 主屏。用于无头环境 / GL 窗口创建失败的回退。

2D 内容统一画到 Game 传入的 ``canvas``（window 模式为离屏 SRCALPHA Surface，
offscreen 模式即主屏本身），``present(canvas)`` 时作为纹理叠加到 3D 之上。

对外接口与 2D 后端一致（另加两个）：
    draw_world(px, py, angle, pitch, zbuf, world, max_depth)  # 3D → scene FBO
    present(canvas)                                           # bloom+后处理+叠加+呈现
    project(wx, wy, wz) -> (sx, sy, dist) | None              # 世界坐标 → 屏幕
    render_scanlines()                                        # no-op（后处理里做）
    _ensure_bg_cache()                                        # no-op
"""
import numpy as np
import pygame

from ..config import (
    C_CEIL_BOT,
    C_CEIL_TOP,
    C_FLOOR_B,
    C_FLOOR_T,
    C_FOG,
    C_WALL_FAR,
    C_WALL_NR,
    GL_BB_H,
    GL_BB_W,
    GL_BLOOM_CLAMP,
    GL_BLOOM_KNEE,
    GL_BLOOM_MIPS,
    GL_BLOOM_SAMPLE_SCALE,
    GL_BLOOM_STRENGTH,
    GL_BLOOM_THRESHOLD,
    GL_EYE_Z,
    GL_EXPOSURE,
    GL_FAR,
    GL_FOG_DENSITY,
    GL_FOV_Y,
    GL_NEAR,
    GL_PITCH_SCALE,
    GL_REGION_RADIUS,
    GL_SCANLINE_ALPHA,
    GL_VIGNETTE_MAX,
    H,
    MAX_DEPTH,
    W,
)
from .camera import perspective, upload, view_matrix
from .meshgen import build_region_mesh, region_cells

# 装饰物发光色（0~1），与 raycast 的 deco_colors 同一套色相
DECO_COLORS = {
    2:  (0.00, 1.00, 0.78),   # 发光柱 - 青绿
    3:  (0.80, 0.24, 0.24),   # 红色警示
    4:  (0.86, 0.74, 0.30),   # 金色装饰
    5:  (0.24, 0.86, 0.47),   # 绿色植被
    6:  (0.72, 0.39, 0.94),   # 紫色能量
    7:  (1.00, 0.59, 0.24),   # 橙色光源
    8:  (0.46, 0.46, 0.50),   # 灰色碎石
    9:  (0.31, 0.86, 1.00),   # 科技装饰
    10: (0.39, 0.71, 1.00),   # 蓝色水晶
    11: (0.63, 0.39, 0.86),   # 紫水晶
    12: (1.00, 1.00, 0.39),   # 传送门 - 金
}


# ─────────────────────── 着色器 ─────────────────────────
_WORLD_VERT = """#version 330
in vec3 in_pos;
in vec3 in_normal;
in vec2 in_uv;
uniform mat4 u_view;
uniform mat4 u_proj;
out vec3 v_normal;
out vec2 v_uv;
out float v_dist;
void main() {
    vec4 vp = u_view * vec4(in_pos, 1.0);
    gl_Position = u_proj * vp;
    v_normal = in_normal;
    v_uv = in_uv;
    v_dist = -vp.z;
}
"""

_WORLD_FRAG = """#version 330
in vec3 v_normal;
in vec2 v_uv;
in float v_dist;
uniform vec3 u_base;
uniform vec3 u_base_far;
uniform vec3 u_fog;
uniform float u_fog_density;
uniform float u_maxd;
uniform float u_grid_str;   // 每组不同：墙最明显、地板中等、天花板最弱
out vec4 frag;
void main() {
    // 程序化网格：每 1 个世界单位一条线。
    // fwidth 屏幕空间抗锯齿：线宽恒约 1px，掠射角下远处自然淡出，
    // 消除低矮天花板视角的 moire 与多边形切面感（GLSL 330 内建导数）
    vec2 g = abs(fract(v_uv - 0.5) - 0.5) / fwidth(v_uv);
    float line = 1.0 - min(min(g.x, g.y), 1.0);
    float fade = exp(-v_dist * 0.10);   // 远处额外淡化（雾对高频闪烁掩蔽有限）
    vec3 col = mix(u_base, u_base_far, clamp(v_dist / u_maxd, 0.0, 1.0));
    col *= (1.0 - u_grid_str * line * fade);
    // 重力照明：地板最亮、墙面居中、天花板略暗（软曲线，避免天花板死黑）
    float ndl = 0.5 + 0.5 * v_normal.z;
    col *= (0.72 + 0.30 * ndl);
    // 指数雾
    float fog_t = 1.0 - exp(-v_dist * u_fog_density);
    col = mix(col, u_fog, clamp(fog_t, 0.0, 1.0));
    frag = vec4(col, 1.0);
}
"""

_BB_VERT = """#version 330
in vec2 in_corner;     // 单位四边形角：x∈[-0.5,0.5], y∈[0,1]（左下原点）
in vec3 in_inst_pos;   // 实例属性：装饰物世界位置
in vec3 in_inst_col;   // 实例属性：发光色
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec3 u_right;
uniform vec3 u_up;
uniform float u_w;
uniform float u_h;
out vec2 v_uv;
out vec3 v_col;
void main() {
    vec3 world = in_inst_pos + u_right * (in_corner.x * u_w) + u_up * (in_corner.y * u_h);
    gl_Position = u_proj * u_view * vec4(world, 1.0);
    v_uv = in_corner + vec2(0.5, 0.0);
    v_col = in_inst_col;
}
"""

_BB_FRAG = """#version 330
in vec2 v_uv;
in vec3 v_col;
out vec4 frag;
void main() {
    float d = length(vec2((v_uv.x - 0.5) * 1.0, (v_uv.y - 0.5) * 0.55));
    float a = smoothstep(0.5, 0.06, d);
    vec3 col = v_col * (0.55 + 0.9 * a);
    frag = vec4(col, a);
}
"""

_FULLSCREEN_VERT = """#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

_BRIGHT_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_scene;
uniform vec4 u_curve;      // EEVEE 软膝曲线四元组 {t-knee, knee*2, 0.25/knee, t}
uniform float u_clamp;     // 单像素亮度上限，<=0 关闭
out vec4 frag;
void main() {
    vec3 m = texture(u_scene, v_uv).rgb;
    // 亮度取最大分量（EEVEE 同款）：能量集中，光晕形态贴光斑
    float br = max(m.r, max(m.g, m.b));
    // 阈值以下二次软膝过渡，替代硬 smoothstep —— 防暗部 banding
    float rq = clamp(br - u_curve.x, 0.0, u_curve.y);
    rq = u_curve.z * rq * rq;
    m *= max(rq, br - u_curve.w) / max(1e-5, br);
    // 强度钳制
    if (u_clamp > 0.0) {
        br = max(1e-5, max(m.r, max(m.g, m.b)));
        m *= 1.0 - max(0.0, br - u_clamp) / br;
    }
    frag = vec4(m, 1.0);
}
"""

_DOWN_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_tex;
uniform vec2 u_texel;      // 源级纹素 1/size
out vec4 frag;
void main() {
    // 4x4 box 下采样 + Karis 亮度加权（抗闪烁，EEVEE/CoD 同款）
    vec4 d = u_texel.xyxy * vec4(-1.0, -1.0, 1.0, 1.0);
    vec3 s1 = texture(u_tex, v_uv + d.xy).rgb;
    vec3 s2 = texture(u_tex, v_uv + d.zy).rgb;
    vec3 s3 = texture(u_tex, v_uv + d.xw).rgb;
    vec3 s4 = texture(u_tex, v_uv + d.zw).rgb;
    float w1 = 1.0 / (max(s1.r, max(s1.g, s1.b)) + 1.0);
    float w2 = 1.0 / (max(s2.r, max(s2.g, s2.b)) + 1.0);
    float w3 = 1.0 / (max(s3.r, max(s3.g, s3.b)) + 1.0);
    float w4 = 1.0 / (max(s4.r, max(s4.g, s4.b)) + 1.0);
    frag = vec4((s1 * w1 + s2 * w2 + s3 * w3 + s4 * w4) / (w1 + w2 + w3 + w4), 1.0);
}
"""

_UP_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_tex;
uniform vec2 u_texel;      // 源级（更粗）纹素 1/size
uniform float u_scale;     // tent 半径缩放
out vec4 frag;
void main() {
    // 9-tap 双线性 tent 上采样（输出=模糊分量；叠加由 ONE,ONE 加法混合完成）
    vec4 d = u_texel.xyxy * vec4(1.0, 1.0, -1.0, 0.0) * u_scale;
    vec3 s;
    s  = texture(u_tex, v_uv - d.xy).rgb;
    s += texture(u_tex, v_uv - d.wy).rgb * 2.0;
    s += texture(u_tex, v_uv - d.zy).rgb;
    s += texture(u_tex, v_uv + d.zw).rgb * 2.0;
    s += texture(u_tex, v_uv).rgb * 4.0;
    s += texture(u_tex, v_uv + d.xw).rgb * 2.0;
    s += texture(u_tex, v_uv + d.zy).rgb;
    s += texture(u_tex, v_uv + d.wy).rgb * 2.0;
    s += texture(u_tex, v_uv + d.xy).rgb;
    frag = vec4(s * (1.0 / 16.0), 1.0);
}
"""

_POST_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_scene;
uniform sampler2D u_bloom;
uniform vec2 u_res;
uniform float u_bloom_strength;
uniform float u_exposure;
uniform float u_scanline;
uniform float u_vignette;
out vec4 frag;
void main() {
    vec3 col = texture(u_scene, v_uv).rgb;
    col += texture(u_bloom, v_uv).rgb * u_bloom_strength;
    col *= u_exposure;
    // 扫描线：每 10 行压暗 2 行
    float sl = step(fract(v_uv.y * u_res.y / 10.0), 0.2);
    col *= 1.0 - u_scanline * sl;
    // 暗角（画幅比校正后取径向距离）
    vec2 d = v_uv - 0.5;
    d.x *= u_res.x / u_res.y;
    float vig = smoothstep(0.30, 0.95, length(d));
    col *= mix(1.0, 1.0 - u_vignette, vig);
    frag = vec4(col, 1.0);
}
"""

_OVERLAY_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_tex;
out vec4 frag;
void main() {
    // pygame 表面是顶左原点，GL 纹理 v=0 在底部 → 采样时翻 y
    vec2 uv = vec2(v_uv.x, 1.0 - v_uv.y);
    frag = texture(u_tex, uv);
}
"""


def _img_to_bytes(surf):
    """pygame Surface → RGBA 字节（兼容 tobytes/tostring 两代 API）。"""
    to = getattr(pygame.image, "tobytes", None) or pygame.image.tostring
    return to(surf, "RGBA")


class GLRenderer:
    """ModernGL 真 3D 渲染器。接口与 2D 后端一致，另加 present()/project()。"""

    is_gl = True

    def __init__(self, surf, world=None, mode="offscreen", ctx=None):
        self.surf = surf            # offscreen 模式的 2D 主屏；window 模式不使用
        self.world = world
        self.mode = mode            # 'offscreen'（读回）| 'window'（真窗口）
        self._ctx = ctx
        self._fbo_scene = None
        self._bloom_mips = None    # [(fbo, w, h), ...] 1/2 → 1/2^N
        self._bloom_fmt = ""       # 实际采用的 bloom 纹理格式名
        self._fbo_out = None        # offscreen 模式的合成目标
        self._prog_world = None
        self._prog_bb = None
        self._prog_bright = None
        self._prog_down = None
        self._prog_up = None
        self._prog_post = None
        self._prog_overlay = None
        self._vaos = {}
        self._bb_vao = None
        self._bb_count = 0
        self._quad_bright = None
        self._quad_down = None
        self._quad_up = None
        self._quad_post = None
        self._quad_overlay = None
        self._overlay_tex = None
        self._region_key = None
        self._proj = perspective(GL_FOV_Y, W / H, GL_NEAR, GL_FAR)
        self._view = np.eye(4, dtype=np.float32)
        self._init_gl()

    # ── 初始化 ──
    def _init_gl(self):
        import moderngl
        if self._ctx is None:
            if self.mode == "window":
                # pygame.OPENGL 窗口已建立，接管当前上下文
                self._ctx = moderngl.get_context()
            else:
                self._ctx = moderngl.create_standalone_context()
        ctx = self._ctx

        # 场景 FBO：颜色 + 深度
        scene_tex = ctx.texture((W, H), 4)
        self._fbo_scene = ctx.framebuffer(
            color_attachments=[scene_tex],
            depth_attachment=ctx.depth_renderbuffer((W, H)))
        # bloom mip 链：1/2 → 1/2^GL_BLOOM_MIPS，半精度浮点（带格式回退）
        mw, mh = W // 2, H // 2
        self._bloom_mips = []
        for _ in range(GL_BLOOM_MIPS):
            self._bloom_mips.append(
                (self._mk_bloom_fbo(ctx, mw, mh), mw, mh))
            mw, mh = max(1, mw // 2), max(1, mh // 2)
        # offscreen 模式的合成目标
        if self.mode == "offscreen":
            self._fbo_out = ctx.framebuffer(color_attachments=[ctx.texture((W, H), 4)])

        # 2D 覆盖层纹理
        self._overlay_tex = ctx.texture((W, H), 4)
        self._overlay_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        # 着色器程序
        self._prog_world = ctx.program(vertex_shader=_WORLD_VERT, fragment_shader=_WORLD_FRAG)
        self._prog_bb = ctx.program(vertex_shader=_BB_VERT, fragment_shader=_BB_FRAG)
        self._prog_bright = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                        fragment_shader=_BRIGHT_FRAG)
        self._prog_down = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                      fragment_shader=_DOWN_FRAG)
        self._prog_up = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                    fragment_shader=_UP_FRAG)
        self._prog_post = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                      fragment_shader=_POST_FRAG)
        self._prog_overlay = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                         fragment_shader=_OVERLAY_FRAG)

        # 全屏四边形（TRIANGLE_STRIP，4 顶点）
        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], np.float32).tobytes()

        def mk(prog):
            return ctx.vertex_array(prog, [(ctx.buffer(quad), "2f", "in_pos")])

        self._quad_bright = mk(self._prog_bright)
        self._quad_down = mk(self._prog_down)
        self._quad_up = mk(self._prog_up)
        self._quad_post = mk(self._prog_post)
        self._quad_overlay = mk(self._prog_overlay)

        # 场景 FBO 初始清屏（菜单期 draw_world 不会被调用，避免未初始化显存上屏）
        self._fbo_scene.use()
        ctx.clear(0.0, 0.0, 0.0, 1.0)

    # ── bloom 纹理格式回退链 ──
    def _mk_bloom_fbo(self, ctx, w, h):
        """建单个 bloom 级 FBO：优先 R11F_G11F_B10F（省 1/4 带宽的 packed
        半精度），失败退 RGBA16F，再失败退 RGBA8。整条链共用同一种格式。"""
        import moderngl
        if not self._bloom_fmt:
            candidates = (
                # internal_format 覆盖：GL_R11F_G11F_B10F（0x8C3A，3 分量 packed）
                ("R11F_G11F_B10F", lambda: ctx.texture((w, h), 3, internal_format=0x8C3A)),
                ("RGBA16F",        lambda: ctx.texture((w, h), 4, dtype="f2")),
                ("RGBA8",          lambda: ctx.texture((w, h), 4)),
            )
            for name, mk_tex in candidates:
                try:
                    tex = mk_tex()
                    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    fbo = ctx.framebuffer(color_attachments=[tex])
                    # 可写探测：真渲染一帧才知道可附加性
                    fbo.use()
                    ctx.viewport = (0, 0, w, h)
                    ctx.clear(0.0, 0.0, 0.0, 0.0)
                    self._bloom_fmt = name
                    return fbo
                except Exception:
                    continue
            # 理论到不了这里：RGBA8 一定可渲染
            raise RuntimeError("no renderable bloom format")
        mk_tex = {
            "R11F_G11F_B10F": lambda: ctx.texture((w, h), 3, internal_format=0x8C3A),
            "RGBA16F":        lambda: ctx.texture((w, h), 4, dtype="f2"),
        }.get(self._bloom_fmt)
        if mk_tex is None:
            mk_tex = lambda: ctx.texture((w, h), 4)
        tex = mk_tex()
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        fbo = ctx.framebuffer(color_attachments=[tex])
        fbo.use()
        ctx.viewport = (0, 0, w, h)
        ctx.clear(0.0, 0.0, 0.0, 0.0)
        return fbo

    # ── 世界切换（重开 / 重新加载）──
    def set_world(self, world):
        if world is self.world:
            return
        self.world = world
        self._region_key = None
        self._bb_vao = None
        self._bb_count = 0
        self._vaos.clear()

    # ── 区域网格（按需重建）──
    def _ensure_region(self, world, px, py):
        cx, cy = world.world_to_chunk(px, py)
        key = (cx, cy, GL_REGION_RADIUS)
        if key == self._region_key:
            return
        self._region_key = key

        cells, base_x, base_y = region_cells(world, cx, cy, GL_REGION_RADIUS, 21)
        meshes = build_region_mesh(cells, float(base_x), float(base_y))

        ctx = self._ctx
        self._vaos.clear()
        for grp, name in ((0, "floor"), (1, "wall"), (2, "ceil")):
            arr = meshes[name]
            if arr.shape[0] == 0:
                continue
            vbo = ctx.buffer(arr.astype(np.float32).tobytes())
            self._vaos[grp] = ctx.vertex_array(
                self._prog_world,
                [(vbo, "3f 3f 2f", "in_pos", "in_normal", "in_uv")])

        # 装饰物 billboard：实例化渲染（静态单位 quad + 每实例 pos/color）
        mask = (cells >= 2) & (cells <= 12)
        ys, xs = np.nonzero(mask)
        if ys.size:
            wx = (base_x + xs + 0.5).astype(np.float32)
            wy = (base_y + ys + 0.5).astype(np.float32)
            types = cells[ys, xs]
            col = np.array([DECO_COLORS.get(int(t), (1.0, 1.0, 1.0))
                            for t in types], np.float32)
            inst = np.concatenate(
                [np.stack([wx, wy, np.zeros_like(wx)], 1), col], 1)
            # 单位 quad：每顶点仅 corner (x, y) 共 2 floats
            quad = np.array([
                (-0.5, 0.0), (0.5, 0.0), (0.5, 1.0),
                (-0.5, 0.0), (0.5, 1.0), (-0.5, 1.0),
            ], np.float32)
            quad_buf = ctx.buffer(quad.tobytes())
            inst_buf = ctx.buffer(np.ascontiguousarray(inst).tobytes())
            self._bb_vao = ctx.vertex_array(
                self._prog_bb,
                [(quad_buf, "2f /v", "in_corner"),
                 (inst_buf, "3f 3f /i", "in_inst_pos", "in_inst_col")])
            self._bb_count = int(ys.size)
        else:
            self._bb_vao = None
            self._bb_count = 0

    # ── 3D 场景 → scene FBO ──
    def draw_world(self, px, py, angle, pitch, zbuf, world, max_depth=MAX_DEPTH):
        import moderngl
        ctx = self._ctx
        self._view = view_matrix(px, py, GL_EYE_Z, angle, float(pitch) * GL_PITCH_SCALE)

        self._fbo_scene.use()
        ctx.viewport = (0, 0, W, H)
        fog = np.asarray(C_FOG, np.float32) / 255.0
        ctx.clear(fog[0], fog[1], fog[2], 1.0)

        if world is None:            # 菜单 / 重开期：空场景
            return

        self._ensure_region(world, px, py)

        # ── 世界几何（不透明：开深度、关混合）──
        ctx.disable(moderngl.BLEND)
        ctx.enable(moderngl.DEPTH_TEST)
        pw = self._proj
        self._prog_world["u_view"].write(upload(self._view))
        self._prog_world["u_proj"].write(upload(pw))
        self._prog_world["u_fog"].write(fog.tobytes())
        self._prog_world["u_fog_density"].value = GL_FOG_DENSITY
        self._prog_world["u_maxd"].value = float(max_depth)
        bases = {
            0: (np.asarray(C_FLOOR_T, np.float32) / 255.0,
                np.asarray(C_FLOOR_B, np.float32) / 255.0, 0.12),
            1: (np.asarray(C_WALL_NR, np.float32) / 255.0,
                np.asarray(C_WALL_FAR, np.float32) / 255.0, 0.18),
            2: (np.asarray(C_CEIL_BOT, np.float32) / 255.0,
                np.asarray(C_CEIL_TOP, np.float32) / 255.0, 0.07),
        }
        for grp, vao in self._vaos.items():
            near, far, gstr = bases[grp]
            self._prog_world["u_base"].write(near.tobytes())
            self._prog_world["u_base_far"].write(far.tobytes())
            self._prog_world["u_grid_str"].value = gstr
            vao.render()

        # ── 装饰物 billboard（发光，加法混合）──
        if self._bb_vao is not None:
            right = np.array([self._view[0, 0], self._view[0, 1], self._view[0, 2]],
                             np.float32)
            up = np.array([self._view[1, 0], self._view[1, 1], self._view[1, 2]],
                          np.float32)
            self._prog_bb["u_view"].write(upload(self._view))
            self._prog_bb["u_proj"].write(upload(pw))
            self._prog_bb["u_right"].write(right.tobytes())
            self._prog_bb["u_up"].write(up.tobytes())
            self._prog_bb["u_w"].value = GL_BB_W
            self._prog_bb["u_h"].value = GL_BB_H
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
            self._bb_vao.render(instances=self._bb_count)

    # ── 后处理 + 覆盖层合成 + 呈现 ──
    def present(self, canvas=None):
        import moderngl
        ctx = self._ctx
        mips = self._bloom_mips

        ctx.disable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.BLEND)

        # 1) 亮部提取（EEVEE 软膝曲线 + 钳制）→ mip0（半分辨率）
        f0, w0, h0 = mips[0]
        f0.use()
        ctx.viewport = (0, 0, w0, h0)
        self._fbo_scene.color_attachments[0].use(0)
        self._prog_bright["u_scene"].value = 0
        knee = GL_BLOOM_KNEE * GL_BLOOM_THRESHOLD
        self._prog_bright["u_curve"].value = (
            GL_BLOOM_THRESHOLD - knee, knee * 2.0,
            0.25 / max(1e-5, knee), GL_BLOOM_THRESHOLD)
        self._prog_bright["u_clamp"].value = GL_BLOOM_CLAMP
        self._quad_bright.render(mode=moderngl.TRIANGLE_STRIP)

        # 2) 下采样链 mip[i] → mip[i+1]（4x4 box + Karis 加权）
        for i in range(len(mips) - 1):
            fsrc, ws, hs = mips[i]
            fdst, wd, hd = mips[i + 1]
            fdst.use()
            ctx.viewport = (0, 0, wd, hd)
            fsrc.color_attachments[0].use(0)
            self._prog_down["u_tex"].value = 0
            self._prog_down["u_texel"].value = (1.0 / ws, 1.0 / hs)
            self._quad_down.render(mode=moderngl.TRIANGLE_STRIP)

        # 3) 上采样累加链 mip[i+1] → mip[i]（9-tap tent + ONE,ONE 加法混合）
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.ONE, moderngl.ONE)
        for i in range(len(mips) - 1, 0, -1):
            fsrc, ws, hs = mips[i]
            fdst, wd, hd = mips[i - 1]
            fdst.use()
            ctx.viewport = (0, 0, wd, hd)
            fsrc.color_attachments[0].use(0)
            self._prog_up["u_tex"].value = 0
            self._prog_up["u_texel"].value = (1.0 / ws, 1.0 / hs)
            self._prog_up["u_scale"].value = GL_BLOOM_SAMPLE_SCALE
            self._quad_up.render(mode=moderngl.TRIANGLE_STRIP)
        ctx.disable(moderngl.BLEND)

        # 4) 合成：scene + bloom(mip0) + 扫描线 + 暗角 + 曝光 → 输出目标
        target = ctx.screen if self.mode == "window" else self._fbo_out
        target.use()
        ctx.viewport = (0, 0, W, H)
        self._fbo_scene.color_attachments[0].use(0)
        f0.color_attachments[0].use(1)
        self._prog_post["u_scene"].value = 0
        self._prog_post["u_bloom"].value = 1
        self._prog_post["u_res"].value = (float(W), float(H))
        self._prog_post["u_bloom_strength"].value = GL_BLOOM_STRENGTH
        self._prog_post["u_exposure"].value = GL_EXPOSURE
        self._prog_post["u_scanline"].value = GL_SCANLINE_ALPHA
        self._prog_post["u_vignette"].value = GL_VIGNETTE_MAX
        self._quad_post.render(mode=moderngl.TRIANGLE_STRIP)

        # 5) 2D 覆盖层纹理叠加（HUD / 粒子 / 界面）
        if canvas is not None:
            self._overlay_tex.write(_img_to_bytes(canvas))
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            self._overlay_tex.use(0)
            self._prog_overlay["u_tex"].value = 0
            self._quad_overlay.render(mode=moderngl.TRIANGLE_STRIP)

        # 6) offscreen 模式：读回 → blit 到 2D 主屏
        if self.mode == "offscreen" and self.surf is not None:
            pixels = self._fbo_out.read(components=4)
            arr = np.flipud(np.frombuffer(pixels, dtype=np.uint8).reshape(H, W, 4))
            self.surf.blit(pygame.image.frombytes(arr.tobytes(), (W, H), "RGBA"), (0, 0))

    # ── 世界坐标 → 屏幕坐标（粒子用，Stage 3）──
    def project(self, wx, wy, wz):
        v, p = self._view, self._proj
        vx = v[0, 0] * wx + v[0, 1] * wy + v[0, 2] * wz + v[0, 3]
        vy = v[1, 0] * wx + v[1, 1] * wy + v[1, 2] * wz + v[1, 3]
        vz = v[2, 0] * wx + v[2, 1] * wy + v[2, 2] * wz + v[2, 3]
        cw = -vz
        if cw <= 0.05:
            return None
        sx = ((p[0, 0] * vx / cw) * 0.5 + 0.5) * W
        sy = (0.5 - (p[1, 1] * vy / cw) * 0.5) * H
        return sx, sy, cw

    # ── 2D 后端兼容 ──
    def render_scanlines(self):
        pass                        # 扫描线已进后处理 shader

    def _ensure_bg_cache(self):
        pass
