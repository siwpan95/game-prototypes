"""
表情绘制引擎
从 app.py 提取，职责：加载表情配置、绘制表情、管理粒子、自动眨眼
音效播放委托给 AudioManager
"""
import json
import os
import copy
import math
import random
import pygame


class FaceEngine:
    """表情绘制引擎"""

    def __init__(self, config_path, base_dir=None, audio_manager=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = base_dir
        full_path = os.path.join(base_dir, config_path)
        self.config = self._load_json(full_path)
        self.current = "default"
        self.audio = audio_manager
        self.time_acc = 0.0
        self.blink_timer = 0.0
        self.blink_state = False
        self.expr_names = list(self.config.get("expressions", {}).keys())
        self.particles = []

    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _deep_merge(self, base, override):
        result = copy.deepcopy(base)
        for k, v in override.items():
            if isinstance(v, dict) and k in result and isinstance(result[k], dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = copy.deepcopy(v)
        return result

    def _get_cfg(self, name):
        base = self.config["default"]
        if name in self.config.get("expressions", {}):
            return self._deep_merge(base, self.config["expressions"][name])
        return copy.deepcopy(base)

    def set_expression(self, name, play_sound=True):
        if name != self.current:
            self.current = name
            cfg = self._get_cfg(name)
            if play_sound and self.audio:
                self.audio.play_expression(cfg.get("sound"))
            self._spawn_particles(cfg)

    def _spawn_particles(self, cfg):
        face_color = tuple(int(max(0, min(255, c))) for c in cfg["face"]["color"])
        count = 8 if cfg.get("cheeks", {}).get("show", False) else 4
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(40, 120)
            self.particles.append({
                "x": 0.0, "y": 0.0,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": random.uniform(0.5, 1.2),
                "max_life": random.uniform(0.5, 1.2),
                "color": face_color,
                "size": random.uniform(3, 8),
            })

    def update_particles(self, dt):
        alive = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] > 0:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["vy"] += 50 * dt
                alive.append(p)
        self.particles = alive

    def draw_particles(self, surface, cx, cy):
        for p in self.particles:
            alpha = max(0.0, min(1.0, p["life"] / p["max_life"]))
            size = p["size"] * alpha
            color = p["color"]
            if size > 0.5:
                s = pygame.Surface((int(size * 2), int(size * 2)), pygame.SRCALPHA)
                # 确保颜色值都是 int 且范围在 [0, 255]，防止浮点/NaN 导致 pygame 报错
                safe_color = tuple(int(max(0, min(255, c))) for c in color)
                safe_alpha = int(max(0, min(255, 200 * alpha)))
                pygame.draw.circle(s, (*safe_color, safe_alpha), (int(size), int(size)), int(size))
                surface.blit(s, (int(cx + p["x"] - size), int(cy + p["y"] - size)))

    # ─── Drawing helpers ───────────────────────────────────────────

    def _draw_heart(self, surface, cx, cy, size, color):
        pts = []
        for deg in range(360):
            rad = math.radians(deg)
            x = size * 0.6 * (16 * math.sin(rad) ** 3) / 16
            y = -size * 0.6 * (13 * math.cos(rad) - 5 * math.cos(2 * rad) -
                                2 * math.cos(3 * rad) - math.cos(4 * rad)) / 16
            pts.append((cx + x, cy + y))
        if len(pts) > 2:
            pygame.draw.polygon(surface, color, pts)

    def _draw_arc_smooth(self, surface, color, rect, start_angle, end_angle, width=3, segments=30):
        pts = []
        for i in range(segments + 1):
            angle = start_angle + (end_angle - start_angle) * i / segments
            x = rect.centerx + rect.width / 2 * math.cos(angle)
            y = rect.centery - rect.height / 2 * math.sin(angle)
            pts.append((x, y))
        if len(pts) > 1:
            pygame.draw.lines(surface, color, False, pts, width)

    def _draw_wavy_line(self, surface, color, x1, y1, x2, y2, amplitude=8, frequency=3, width=3):
        pts = []
        steps = 40
        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            y += amplitude * math.sin(2 * math.pi * frequency * t)
            pts.append((x, y))
        if len(pts) > 1:
            pygame.draw.lines(surface, color, False, pts, width)

    # ─── Main draw ─────────────────────────────────────────────────

    def draw_face(self, surface, cx, cy, face_scale=1.0, dt=0.0):
        cfg = self._get_cfg(self.current)
        anim = cfg.get("animation", {})

        bounce_speed = anim.get("bounce_speed", 0)
        squish = anim.get("squish", 0)
        shake = anim.get("shake", 0)
        wobble_speed = anim.get("wobble_speed", 0)
        pulse_speed = anim.get("pulse_speed", 0)

        t = self.time_acc

        offset_y = 0
        if bounce_speed > 0:
            offset_y = -abs(math.sin(bounce_speed * t)) * 15 * face_scale

        shake_x, shake_y = 0, 0
        if shake > 0:
            shake_x = math.sin(shake * 17.3 * t) * shake * face_scale
            shake_y = math.cos(shake * 13.7 * t) * shake * 0.5 * face_scale

        squish_x, squish_y = 1.0, 1.0
        if squish > 0:
            pulse = math.sin(bounce_speed * t * 2) if bounce_speed > 0 else math.sin(t * 3)
            squish_x = 1.0 + squish * pulse
            squish_y = 1.0 - squish * pulse
        if wobble_speed > 0:
            w = math.sin(wobble_speed * t)
            squish_x *= (1.0 + 0.03 * w)
            squish_y *= (1.0 - 0.03 * w)
        if pulse_speed > 0:
            p = math.sin(pulse_speed * t)
            squish_x *= (1.0 + 0.04 * p)
            squish_y *= (1.0 + 0.04 * p)

        fcx = cx + shake_x
        fcy = cy + offset_y + shake_y
        s = face_scale

        # Face
        f = cfg["face"]
        face_size = int(f["size"] * s * max(squish_x, 0.5))
        face_size_y = int(f["size"] * s * max(squish_y, 0.5))
        outline_w = max(1, int(f.get("outline_width", 2) * s))
        outline_color = tuple(f.get("outline_color", [0, 0, 0]))
        face_color = tuple(f["color"])

        face_rect = pygame.Rect(0, 0, face_size * 2, face_size_y * 2)
        face_rect.center = (int(fcx), int(fcy))
        pygame.draw.ellipse(surface, face_color, face_rect)
        if outline_w > 0:
            pygame.draw.ellipse(surface, outline_color, face_rect, outline_w)

        # Cheeks
        ch = cfg.get("cheeks", {})
        if ch.get("show", False):
            cheek_color = tuple(ch.get("color", [255, 150, 150]))
            cheek_size = int(ch.get("size", 25) * s)
            cheek_ox = int(ch.get("offset_x", 80) * s)
            cheek_oy = int(ch.get("offset_y", 20) * s)
            if pulse_speed > 0:
                p = 1.0 + 0.15 * math.sin(pulse_speed * t)
                cheek_size = int(cheek_size * p)
            alpha_surf = pygame.Surface((cheek_size * 2, cheek_size * 2), pygame.SRCALPHA)
            safe_cheek_color = tuple(int(max(0, min(255, c))) for c in cheek_color)
            pygame.draw.circle(alpha_surf, (*safe_cheek_color, 120), (cheek_size, cheek_size), cheek_size)
            surface.blit(alpha_surf, (int(fcx - cheek_ox - cheek_size), int(fcy + cheek_oy - cheek_size)))
            surface.blit(alpha_surf, (int(fcx + cheek_ox - cheek_size), int(fcy + cheek_oy - cheek_size)))

        # Eyes
        e = cfg["eyes"]
        ey = fcy + e.get("offset_y", -30) * s
        sp = e.get("spacing", 60) * s
        esz = int(e.get("size", 20) * s)
        pupil_sz = int(e.get("pupil_size", 8) * s)
        eye_color = tuple(e.get("color", [255, 255, 255]))
        pupil_color = tuple(e.get("pupil_color", [40, 40, 40]))
        eye_type = e.get("type", "normal")
        brow_color = tuple(e.get("eyebrow_color", [80, 60, 30]))
        brow_oy = e.get("eyebrow_offset_y", -55) * s

        left_x = fcx - sp
        right_x = fcx + sp
        left_ox = e.get("left_offset_x", 0) * s
        right_ox = e.get("right_offset_x", 0) * s
        look_dx, look_dy = 0, 0
        if e.get("look_up", False): look_dy = -4 * s
        elif e.get("look_down", False): look_dy = 4 * s
        if e.get("look_side", False): look_dx = 4 * s
        if e.get("look_up_right", False): look_dx, look_dy = 4 * s, -4 * s

        actual_eye_h = esz
        if self.blink_state:
            actual_eye_h = max(2, esz // 5)
        if e.get("half_closed", False):
            actual_eye_h = max(2, esz // 2)

        for side, sx, side_ox in [("left", left_x, left_ox), ("right", right_x, right_ox)]:
            ex = sx + side_ox
            ey_pos = ey

            right_closed = e.get("right_closed", False) and side == "right"
            left_closed = e.get("left_closed", False) and side == "left"

            if eye_type == "heart":
                self._draw_heart(surface, int(ex + look_dx), int(ey_pos + look_dy), esz, eye_color)
            elif eye_type == "sunglasses":
                lens_w = int(esz * 2.2)
                lens_h = int(esz * 1.5)
                lens_rect = pygame.Rect(0, 0, lens_w, lens_h)
                lens_rect.center = (int(ex), int(ey_pos))
                pygame.draw.ellipse(surface, tuple(e.get("color", [30, 30, 30])), lens_rect)
                pygame.draw.ellipse(surface, (60, 60, 60), lens_rect, max(1, int(2 * s)))
                if side == "left":
                    pygame.draw.line(surface, (60, 60, 60),
                                     (int(ex + lens_w // 2), int(ey_pos)),
                                     (int(fcx), int(ey_pos)), max(1, int(3 * s)))
            elif right_closed or left_closed:
                line_rect = pygame.Rect(int(ex - esz), int(ey_pos - 3 * s), esz * 2, int(6 * s))
                pygame.draw.arc(surface, pupil_color, line_rect, 0.2, 2.9, max(1, int(2 * s)))
            else:
                eye_rect = pygame.Rect(0, 0, esz * 2, actual_eye_h * 2)
                eye_rect.center = (int(ex), int(ey_pos))
                pygame.draw.ellipse(surface, eye_color, eye_rect)
                pygame.draw.ellipse(surface, (100, 100, 100), eye_rect, 1)

                if actual_eye_h > 5:
                    cross_eyed = e.get("cross_eyed", False)
                    px = ex + look_dx
                    py = ey_pos + look_dy
                    if cross_eyed:
                        px = ex + 4 * s if side == "left" else ex - 4 * s
                    pygame.draw.circle(surface, pupil_color, (int(px), int(py)), pupil_sz)
                    if pupil_sz > 3:
                        pygame.draw.circle(surface, (255, 255, 255),
                                           (int(px - pupil_sz * 0.3), int(py - pupil_sz * 0.3)),
                                           max(1, pupil_sz // 3))

            # Eyebrow
            brow_angle = e.get("eyebrow_angle", 0)
            if side == "left" and "eyebrow_angle_left" in e:
                brow_angle = e["eyebrow_angle_left"]
            elif side == "right" and "eyebrow_angle_right" in e:
                brow_angle = e["eyebrow_angle_right"]
            brow_len = esz + int(8 * s)
            rad = math.radians(brow_angle)
            bx1 = ex - brow_len * math.cos(rad)
            by1 = ey_pos + brow_oy - brow_len * math.sin(rad)
            bx2 = ex + brow_len * math.cos(rad)
            by2 = ey_pos + brow_oy + brow_len * math.sin(rad)
            pygame.draw.line(surface, brow_color, (int(bx1), int(by1)), (int(bx2), int(by2)),
                             max(1, int(3 * s)))

        # Mouth
        m = cfg["mouth"]
        my = fcy + m.get("offset_y", 50) * s
        mw = int(m.get("width", 120) * s)
        mh = int(m.get("height", 40) * s)
        mc = tuple(m.get("color", [180, 60, 60]))
        mt = max(1, int(m.get("thickness", 3) * s))
        mouth_type = m.get("type", "neutral")

        if mouth_type == "smile":
            rect = pygame.Rect(int(fcx - mw // 2), int(my - mh // 2), mw, mh)
            self._draw_arc_smooth(surface, mc, rect, 0.2, 2.9, mt)
        elif mouth_type == "big_smile":
            rect = pygame.Rect(int(fcx - mw // 2), int(my - mh // 3), mw, mh)
            pts = []
            for i in range(31):
                angle = 0.2 + 2.7 * i / 30
                x = rect.centerx + rect.width / 2 * math.cos(angle)
                y = rect.centery - rect.height / 2 * math.sin(angle)
                pts.append((x, y))
            pts.append((rect.right, my + mh // 4))
            pts.append((rect.left, my + mh // 4))
            if len(pts) > 2:
                pygame.draw.polygon(surface, mc, pts)
            pygame.draw.line(surface, (255, 255, 255),
                             (int(fcx - mw // 3), int(my - mh // 4)),
                             (int(fcx + mw // 3), int(my - mh // 4)), max(1, int(2 * s)))
        elif mouth_type == "frown":
            rect = pygame.Rect(int(fcx - mw // 2), int(my - mh // 2), mw, mh)
            self._draw_arc_smooth(surface, mc, rect, 3.3, 6.1, mt)
        elif mouth_type == "round":
            rect = pygame.Rect(int(fcx - mw // 2), int(my - mh // 2), mw, mh)
            pygame.draw.ellipse(surface, mc, rect, mt)
        elif mouth_type == "straight":
            pygame.draw.line(surface, mc, (int(fcx - mw // 2), int(my)),
                             (int(fcx + mw // 2), int(my)), mt)
        elif mouth_type == "smirk_side":
            pts = []
            segments = 25
            for i in range(segments + 1):
                frac = i / segments
                x = fcx - mw // 2 + mw * frac
                curve = math.sin(frac * math.pi) * mh * 0.5
                if frac > 0.6:
                    curve *= (1.0 - (frac - 0.6) / 0.4 * 0.6)
                pts.append((int(x), int(my + curve)))
            if len(pts) > 1:
                pygame.draw.lines(surface, mc, False, pts, mt)
        elif mouth_type == "small_smile":
            rect = pygame.Rect(int(fcx - mw // 2), int(my - mh // 2), mw, mh)
            self._draw_arc_smooth(surface, mc, rect, 0.5, 2.6, mt)
        elif mouth_type == "wavy":
            self._draw_wavy_line(surface, mc,
                                 int(fcx - mw // 2), int(my),
                                 int(fcx + mw // 2), int(my),
                                 amplitude=mh * 0.4, frequency=2, width=mt)
        elif mouth_type == "tilted":
            pygame.draw.line(surface, mc,
                             (int(fcx - mw // 2), int(my - 5 * s)),
                             (int(fcx + mw // 2), int(my + 5 * s)), mt)
        elif mouth_type == "tongue_out":
            rect = pygame.Rect(int(fcx - mw // 2), int(my - mh // 3), mw, int(mh * 0.7))
            self._draw_arc_smooth(surface, mc, rect, 0.2, 2.9, mt)
            tw = int(15 * s)
            tongue_rect = pygame.Rect(int(fcx - tw), int(my + 2), tw * 2, int(25 * s))
            pygame.draw.ellipse(surface, (255, 100, 100), tongue_rect)
            pygame.draw.ellipse(surface, mc, tongue_rect, max(1, int(2 * s)))
        elif mouth_type == "yawn":
            rect = pygame.Rect(int(fcx - mw // 2), int(my - mh // 2), mw, mh)
            pygame.draw.ellipse(surface, (60, 20, 20), rect)
            pygame.draw.ellipse(surface, mc, rect, mt)
        else:
            pygame.draw.line(surface, mc, (int(fcx - mw // 2), int(my)),
                             (int(fcx + mw // 2), int(my)), mt)

        # Particles
        self.draw_particles(surface, int(fcx), int(fcy + 100 * s))

    def update(self, dt):
        self.time_acc += dt
        self.update_particles(dt)

        cfg = self._get_cfg(self.current)
        blink_interval = cfg.get("animation", {}).get("blink_interval", 3.0)
        if blink_interval > 0:
            self.blink_timer += dt
            if not self.blink_state and self.blink_timer > blink_interval:
                self.blink_state = True
                self.blink_timer = 0.0
            elif self.blink_state and self.blink_timer > 0.15:
                self.blink_state = False
                self.blink_timer = 0.0
        else:
            self.blink_state = False
