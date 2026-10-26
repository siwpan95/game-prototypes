# -*- coding: utf-8 -*-
"""
highway_scene —— Endless Highway 的 3D 场景层（world3d 引擎）。

职责边界：

- **本模块**只管"世界长什么样"：程序化几何、着色器、跟随相机、把 ECS 状态
  映射成 3D 变换并绘制。
- **ecs/** 只管"世界怎么动"：玩法状态（位置/速度/里程/漂移/碰撞）。
- 两者通过 ``world.get_entities_with(...)`` 解耦——ECS 不 import 本模块。

渲染方案沿用 3dworld 引擎 ``WorldRenderer`` 的成熟做法：自定义着色器 +
``position``/``colors`` 顶点属性 + ``model`` 矩阵 uniform，配合引擎自带的
``core.geometry.box_data``（含面向光的面明暗烘焙），无需 IBL / 后处理即可
得到干净的沙漠公路画面。

坐标约定见 ``ecs/components.py``：x 横向、y 竖向、z 纵深（-z 为屏幕深处）。
"""

from __future__ import annotations

import math

import pyglet
from pyglet.gl import GL_TRIANGLES
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.math import Mat4, Vec3

from world3d.core.geometry import box_data
from world3d.engine.mathkit import look_at_matrix

from ecs.components import Decoration, GameState, Lateral, Position, VehicleControl

__all__ = ['HighwayScene', 'ChaseCamera']

# ── 着色器（position + colors + model；tint 用于撞击闪红；含距离雾）───
VERT_SRC = '''#version 330 core
in vec3 position;
in vec4 colors;
out vec4 vertex_colors;
out vec3 v_world;
uniform WindowBlock { mat4 projection; mat4 view; } window;
uniform mat4 model;
uniform vec3 tint;
uniform vec3 uFlash;
uniform float uFlashAmt;
void main() {
    vec4 wp = model * vec4(position, 1.0);
    gl_Position = window.projection * window.view * wp;
    // 撞击闪红用 mix（不是乘 tint）：车身基色是纯绿 (0,1,0)，
    // 乘法永远调不出红色来。
    vertex_colors = vec4(mix(colors.rgb * tint, uFlash, uFlashAmt), colors.a);
    v_world = wp.xyz;
}'''

FRAG_SRC = '''#version 330 core
in vec4 vertex_colors;
in vec3 v_world;
out vec4 final_colors;
uniform vec3 uCamPos;
uniform vec3 uFogColor;
uniform float uFogNear;
uniform float uFogFar;
void main() {
    // 雾在片元里按世界坐标算距离：地面是一整块巨大的四边形，
    // 若把距离当 varying 插值，会沿对角线出现明显的雾带。
    float d = length(v_world - uCamPos);
    float f = clamp((d - uFogNear) / max(0.001, uFogFar - uFogNear), 0.0, 1.0);
    f = f * f * (3.0 - 2.0 * f);              // smoothstep
    final_colors = vec4(mix(vertex_colors.rgb, uFogColor, f), vertex_colors.a);
}'''

# 装饰物模板的基准尺寸（与配置里的 size 像素值换算：scale = size / NOMINAL）
NOMINAL_DECO_SIZE = 30.0


def _merge_boxes(boxes):
    """把多个盒体合并成一份顶点数据。

    Args:
        boxes: [(sx, sy, sz, ox, oy, oz, rgb), ...]
    Returns:
        (verts, colors) —— 可直接喂 ``program.vertex_list``
    """
    verts, colors = [], []
    for sx, sy, sz, ox, oy, oz, rgb in boxes:
        v, c = box_data(sx, sy, sz, ox, oy, oz, rgb)
        verts += v
        colors += c
    return verts, colors


def _trs_matrix(tx, ty, tz, angle_z=0.0, scale=1.0):
    """列主序 4x4：先绕 Z 旋转、再缩放、最后平移（与 pyglet Mat4 一致）。"""
    c = math.cos(angle_z) * scale
    s = math.sin(angle_z) * scale
    return (c, s, 0.0, 0.0,
            -s, c, 0.0, 0.0,
            0.0, 0.0, scale, 0.0,
            tx, ty, tz, 1.0)


class ChaseCamera:
    """跟随相机：车后上方，视线看向远方路面；横向带缓动跟随。"""

    def __init__(self, height=4.5, back=11.0, look_ahead=30.0, damping=6.0):
        self.height = float(height)
        self.back = float(back)
        self.look_ahead = float(look_ahead)
        self.damping = float(damping)
        self.eye = (0.0, self.height, self.back)
        self.target = (0.0, 1.2, -self.look_ahead)

    def update(self, dt, car_x=0.0):
        k = 1.0 - math.exp(-self.damping * dt)
        want_eye = (car_x * 0.35, self.height, self.back)
        want_target = (car_x * 0.25, 1.2, -self.look_ahead)
        self.eye = tuple(a + (b - a) * k for a, b in zip(self.eye, want_eye))
        self.target = tuple(a + (b - a) * k for a, b in zip(self.target, want_target))
        return self

    def view_matrix(self):
        """视图矩阵（列主序 16 元组）。"""
        return look_at_matrix(self.eye, self.target, (0.0, 1.0, 0.0))

    def view(self):
        return Mat4(*self.view_matrix())


class HighwayScene:
    """3D 场景：地面 / 公路 / 车道线 / 车辆 / 路旁装饰物。"""

    def __init__(self, cfg3d: dict):
        c = cfg3d
        self.road_half_width = float(c.get("road_half_width", 6.0))
        self.road_length = float(c.get("road_length", 400.0))
        self.far_z = float(c.get("road_far_z", -390.0))
        self.near_z = float(c.get("road_near_z", 14.0))
        self.road_color = tuple(c.get("road_color", (0.13, 0.13, 0.16)))
        self.edge_color = tuple(c.get("edge_color", (1.0, 0.85, 0.12)))
        self.dash_color = tuple(c.get("center_dash_color", (0.95, 0.95, 0.95)))
        self.ground_color = tuple(c.get("ground_color", (0.86, 0.78, 0.55)))
        self.fog_color = tuple(c.get("fog_color", c.get("sky_color",
                                                        (0.72, 0.82, 0.92))))
        self.fog_near = float(c.get("fog_near", 70.0))
        self.fog_far = float(c.get("fog_far", 330.0))
        self.dash_length = float(c.get("dash_length", 3.0))
        self.dash_gap = float(c.get("dash_gap", 4.0))
        self.dash_count = int(c.get("dash_count", 56))
        self.car_half_width = float(c.get("car_half_width", 1.1))
        self.player_color = tuple(c.get("player_color", (0.0, 1.0, 0.0)))
        self.windshield_color = tuple(c.get("windshield_color", (0.39, 0.78, 1.0)))

        self.program = None
        self.static_lists = []
        self.dash_vlist = None
        self.car_vlist = None
        self.deco_templates = {}

    # ── 构建 ────────────────────────────────────────────────────────
    def build(self):
        """创建着色器与全部几何资源（必须在 GL 上下文就绪后调用）。"""
        self.program = ShaderProgram(Shader(VERT_SRC, 'vertex'),
                                     Shader(FRAG_SRC, 'fragment'))
        self._build_static()
        self._build_dash()
        self._build_car()
        self._build_decorations()
        return self

    def _vlist(self, verts, colors):
        return self.program.vertex_list(len(verts) // 3, GL_TRIANGLES,
                                         position=('f', verts), colors=('f', colors))

    def _build_static(self):
        """地面 / 路肩 / 路面 / 边线——一次建好，每帧只画不重建。"""
        mid_z = (self.far_z + self.near_z) * 0.5
        hw = self.road_half_width
        length = self.near_z - self.far_z

        # 沙漠地面（大平板，顶面 y=0）
        ground = _merge_boxes([
            (600.0, 0.4, 700.0, 0.0, -0.2, -150.0, self.ground_color),
        ])
        # 路肩（浅色碎石带）
        shoulder = _merge_boxes([
            (1.4, 0.08, length, -(hw + 0.7), 0.04, mid_z, (0.72, 0.64, 0.44)),
            (1.4, 0.08, length, (hw + 0.7), 0.04, mid_z, (0.72, 0.64, 0.44)),
        ])
        # 路面
        road = _merge_boxes([
            (hw * 2.0, 0.14, length, 0.0, 0.07, mid_z, self.road_color),
        ])
        # 黄色边线
        edges = _merge_boxes([
            (0.30, 0.06, length, -(hw - 0.35), 0.17, mid_z, self.edge_color),
            (0.30, 0.06, length, (hw - 0.35), 0.17, mid_z, self.edge_color),
        ])

        for verts, colors in (ground, shoulder, road, edges):
            self.static_lists.append(self._vlist(verts, colors))

    def _build_dash(self):
        """中央虚线（单段模板 + 每帧 model 矩阵平移复用）。"""
        verts, colors = _merge_boxes([
            (0.40, 0.06, self.dash_length, 0.0, 0.0, 0.0, self.dash_color),
        ])
        self.dash_vlist = self._vlist(verts, colors)

    def _build_car(self):
        """车辆：车身 / 车窗 / 车轮 / 车灯，全部用盒体拼。"""
        body = self.player_color
        dark = tuple(c * 0.75 for c in body)
        verts, colors = _merge_boxes([
            (2.0, 0.62, 4.2, 0.0, 0.72, 0.0, body),                 # 车身
            (1.62, 0.52, 1.9, 0.0, 1.30, -0.15, dark),              # 驾驶舱
            (1.50, 0.34, 0.12, 0.0, 1.30, 0.78, self.windshield_color),  # 前挡风
            (0.34, 0.52, 0.70, -1.02, 0.28, 1.45, (0.05, 0.05, 0.05)),  # 车轮
            (0.34, 0.52, 0.70, 1.02, 0.28, 1.45, (0.05, 0.05, 0.05)),
            (0.34, 0.52, 0.70, -1.02, 0.28, -1.45, (0.05, 0.05, 0.05)),
            (0.34, 0.52, 0.70, 1.02, 0.28, -1.45, (0.05, 0.05, 0.05)),
            (0.42, 0.16, 0.10, -0.62, 0.68, 2.10, (1.0, 0.94, 0.72)),   # 车灯
            (0.42, 0.16, 0.10, 0.62, 0.68, 2.10, (1.0, 0.94, 0.72)),
        ])
        self.car_vlist = self._vlist(verts, colors)

    def _build_decorations(self):
        """四类路旁装饰物的模板几何（局部原点在底部中心）。"""
        # 仙人掌：主干 + 双臂
        self.deco_templates['cactus'] = self._vlist(*_merge_boxes([
            (0.55, 2.60, 0.55, 0.0, 1.30, 0.0, (0.20, 0.47, 0.20)),
            (0.34, 1.10, 0.34, -0.48, 1.25, 0.0, (0.20, 0.47, 0.20)),
            (0.34, 0.85, 0.34, 0.46, 1.60, 0.0, (0.22, 0.52, 0.22)),
            (0.26, 0.34, 0.26, 0.0, 2.75, 0.0, (0.24, 0.56, 0.24)),
        ]))
        # 岩石：主块 + 副块
        self.deco_templates['rock'] = self._vlist(*_merge_boxes([
            (1.45, 0.85, 1.20, 0.0, 0.42, 0.0, (0.63, 0.47, 0.27)),
            (0.70, 0.50, 0.62, 0.52, 0.72, 0.18, (0.70, 0.53, 0.31)),
        ]))
        # 枯灌木：低矮一丛
        self.deco_templates['dead_bush'] = self._vlist(*_merge_boxes([
            (1.05, 0.46, 0.95, 0.0, 0.23, 0.0, (0.71, 0.63, 0.35)),
            (0.52, 0.36, 0.46, 0.30, 0.60, 0.10, (0.78, 0.70, 0.40)),
        ]))
        # 护栏：立柱 + 横杆 + 反光片
        self.deco_templates['guardrail'] = self._vlist(*_merge_boxes([
            (0.22, 1.20, 0.22, 0.0, 0.60, 0.0, (0.47, 0.27, 0.12)),
            (1.80, 0.20, 0.16, 0.0, 0.98, 0.0, (0.55, 0.33, 0.15)),
            (0.18, 0.14, 0.18, 0.0, 1.18, 0.0, (0.86, 0.71, 0.31)),
        ]))

    # ── 绘制 ────────────────────────────────────────────────────────
    def dash_positions(self, dash_offset: float):
        """中央虚线每一段的 z 坐标（随 offset 朝镜头滚动）。"""
        spacing = self.dash_length + self.dash_gap
        period = spacing * self.dash_count
        out = []
        for i in range(self.dash_count):
            out.append(self.near_z - ((i * spacing + dash_offset) % period))
        return out

    def render(self, window, view_matrix, world, camera_pos=(0.0, 0.0, 0.0)):
        """把 ECS 状态画成一帧 3D 画面。"""
        state = world.get_singleton(GameState)
        window.view = view_matrix

        prog = self.program
        prog.use()

        # 雾参数（雾色 = 天空色，让地平线无缝衔接）
        prog['uCamPos'] = Vec3(*camera_pos)
        prog['uFogColor'] = Vec3(*self.fog_color)
        prog['uFogNear'] = float(self.fog_near)
        prog['uFogFar'] = float(self.fog_far)
        prog['uFlash'] = Vec3(1.0, 0.18, 0.12)
        prog['uFlashAmt'] = 0.0

        # 1) 静态件（地面 / 路肩 / 路面 / 边线）
        prog['tint'] = Vec3(1.0, 1.0, 1.0)
        prog['model'] = Mat4()
        for vl in self.static_lists:
            vl.draw(GL_TRIANGLES)

        # 2) 中央虚线
        offset = state.dash_offset if state is not None else 0.0
        for z in self.dash_positions(offset):
            prog['model'] = Mat4(*_trs_matrix(0.0, 0.17, z))
            self.dash_vlist.draw(GL_TRIANGLES)

        # 3) 玩家车辆（含转向侧倾；撞击时闪红）
        dead = state is not None and not state.alive
        for entity in world.get_entities_with(Position, VehicleControl):
            pos = world.get_component(entity, Position)
            lean = 0.0
            lat = world.get_component(entity, Lateral)
            if lat is not None:
                lean = -max(-0.30, min(0.30, lat.vx * 0.025))
            prog['tint'] = Vec3(1.0, 1.0, 1.0)
            prog['uFlashAmt'] = 1.0 if dead else 0.0
            prog['model'] = Mat4(*_trs_matrix(pos.x, 0.0, pos.z, lean))
            self.car_vlist.draw(GL_TRIANGLES)
        prog['uFlashAmt'] = 0.0

        # 4) 路旁装饰物
        prog['tint'] = Vec3(1.0, 1.0, 1.0)
        for entity in world.get_entities_with(Position, Decoration):
            deco = world.get_component(entity, Decoration)
            if not deco.active:
                continue
            vl = self.deco_templates.get(deco.deco_type)
            if vl is None:
                continue
            pos = world.get_component(entity, Position)
            scale = max(0.25, deco.size / NOMINAL_DECO_SIZE)
            prog['model'] = Mat4(*_trs_matrix(pos.x, 0.0, pos.z, 0.0, scale))
            vl.draw(GL_TRIANGLES)

    # ── 杂项 ────────────────────────────────────────────────────────
    def dispose(self):
        """释放 GL 资源（退出时调用）。"""
        for vl in list(self.static_lists) + [self.dash_vlist, self.car_vlist]:
            if vl is not None:
                try:
                    vl.delete()
                except Exception:
                    pass
        self.static_lists = []
        self.dash_vlist = None
        self.car_vlist = None
        for vl in self.deco_templates.values():
            try:
                vl.delete()
            except Exception:
                pass
        self.deco_templates = {}


def make_key_state_reader(window):
    """把 pyglet 键盘状态包成 ``KeyState``（ECS 侧不依赖 pyglet）。"""
    from ecs.components import KeyState

    handler = pyglet.window.key.KeyStateHandler()
    window.push_handlers(handler)
    state = KeyState()
    left = pyglet.window.key.LEFT
    right = pyglet.window.key.RIGHT

    def read():
        state.left = bool(handler[left])
        state.right = bool(handler[right])
        return state

    return read
