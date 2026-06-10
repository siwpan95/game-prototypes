"""
表情浏览面板
"""
import pygame
from .common import load_font


class BrowsePanel:
    """表情浏览模式：大表情居中，底部键位提示"""

    EXPR_KEYS = {
        pygame.K_1: "default", pygame.K_2: "happy", pygame.K_3: "sad",
        pygame.K_4: "surprised", pygame.K_5: "angry", pygame.K_6: "laugh",
        pygame.K_7: "wink", pygame.K_8: "love", pygame.K_9: "cool",
        pygame.K_0: "sleepy",
    }

    def __init__(self, face):
        self.face = face
        self.font_lg = load_font(36)
        self.font_sm = load_font(18)
        self.font_xs = load_font(14)

    def draw(self, screen, width, height, dt):
        face_cx = width // 2
        face_cy = height // 2 - 20
        self.face.draw_face(screen, face_cx, face_cy, face_scale=1.1, dt=dt)

        # 当前表情名
        name_surf = self.font_lg.render(self.face.current.upper(), True, (255, 255, 255))
        screen.blit(name_surf, (width // 2 - name_surf.get_width() // 2, 20))

        # 键位提示
        y = height - 50
        for idx, (key, expr) in enumerate(self.EXPR_KEYS.items()):
            key_name = pygame.key.name(key)
            color = (255, 255, 100) if expr == self.face.current else (120, 120, 140)
            txt = self.font_xs.render(f"[{key_name}]{expr}", True, color)
            screen.blit(txt, (20 + (idx % 5) * 160, y + (idx // 5) * 20))

        hint = self.font_sm.render("E: 返回签到  ESC: 退出", True, (100, 100, 120))
        screen.blit(hint, (width // 2 - hint.get_width() // 2, height - 25))

    def handle_key(self, key):
        if key in self.EXPR_KEYS:
            self.face.set_expression(self.EXPR_KEYS[key])
            return True
        return False
