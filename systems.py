"""
系统逻辑 (Systems) - 六一零食大闯关
包含：移动、碰撞、零食生成、状态效果、渲染
增量完善：贪吃蛇身体、追逐敌人
"""
import tkinter as tk
import random
import time
import math

from components import (
    Transform, Render, Movement, Health, Score, Collider,
    GameState, SnackData, StatusEffect, Shield,
)
from entities import create_snack


# ========================
#  游戏常量
# ========================
CANVAS_W = 800
CANVAS_H = 600


# ========================
#  MovementSystem — 自由移动
# ========================
class MovementSystem:
    """处理实体移动，支持反向控制状态"""

    def update(self, world):
        for ent, (trans, move) in world.get_components(Transform, Movement):
            vx = move.vx
            vy = move.vy

            # 检查反向控制状态
            status = world.component_for_entity(ent, StatusEffect)
            if status and status.is_reversed:
                vx *= -1
                vy *= -1

            trans.x += vx * move.speed
            trans.y += vy * move.speed

            # 边界限制
            trans.x = max(16, min(trans.x, CANVAS_W - 16))
            trans.y = max(16, min(trans.y, CANVAS_H - 16))


# ========================
#  SnakeSystem — 贪吃蛇身体（新增）
# ========================
class SnakeSystem:
    """
    贪吃蛇机制：
    - 玩家移动时留下身体轨迹
    - 身体段跟随玩家，越长越危险（碰到自己会扣血）
    - 吃掉零食后身体增长
    """

    def __init__(self, player_id):
        self.player_id = player_id
        # 身体轨迹记录
        self.history = []           # [(x, y), ...]  最新的在前
        self.max_history = 500      # 最大历史点数
        self.segment_count = 3      # 当前身体段数
        self.segment_spacing = 25   # 每段间距（像素）

    def update(self, world):
        state = world.component_for_entity(self.player_id, GameState)
        if state.is_over:
            return

        p_trans = world.component_for_entity(self.player_id, Transform)

        # 记录玩家位置到历史轨迹
        self.history.insert(0, (p_trans.x, p_trans.y))
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]

        # 自碰撞检测：检查玩家是否碰到自己的身体
        if self.segment_count >= 5 and len(self.history) > self.segment_spacing:
            p_health = world.component_for_entity(self.player_id, Health)
            p_status = world.component_for_entity(self.player_id, StatusEffect)
            if p_status and p_status.is_invincible:
                return

            for i in range(self.segment_spacing * 2, min(len(self.history),
                                self.segment_count * self.segment_spacing)):
                bx, by = self.history[i]
                dx = p_trans.x - bx
                dy = p_trans.y - by
                if (dx * dx + dy * dy) < 20 * 20:
                    # 碰到自己身体 → 扣血
                    p_health.hp -= 10
                    # 弹开
                    p_trans.x += (p_trans.x - bx) * 2
                    p_trans.y += (p_trans.y - by) * 2
                    break

    def grow(self, amount=1):
        """吃零食后增长身体"""
        self.segment_count += amount

    def get_body_segments(self, count=None):
        """获取当前身体段的位置列表（用于渲染）"""
        if count is None:
            count = self.segment_count
        segments = []
        for i in range(count):
            idx = (i + 1) * self.segment_spacing
            if idx < len(self.history):
                segments.append(self.history[idx])
        return segments


# ========================
#  EnemySystem — 吃豆人式追逐敌人（新增）
# ========================
class EnemySystem:
    """
    追逐敌人机制：
    - 屏幕上有 1~2 个"魔鬼辣片幽灵"在追逐玩家
    - 碰到敌人会扣血，但吃掉"力量糖果"后可以反杀敌人
    - 敌人被消灭后会在一段时间后重生
    """

    def __init__(self):
        self.enemies = []           # [(eid, x, y, speed, respawn_time), ...]
        self.power_mode = False
        self.power_end_time = 0

    def spawn_enemy(self, world, player_trans):
        """在玩家远处生成一个敌人"""
        # 生成在玩家对面半场
        if player_trans.x < CANVAS_W / 2:
            ex = random.randint(CANVAS_W // 2 + 50, CANVAS_W - 50)
        else:
            ex = random.randint(50, CANVAS_W // 2 - 50)
        ey = random.randint(50, CANVAS_H - 50)

        eid = world.create_entity()
        world.add_component(eid, Transform(ex, ey))
        world.add_component(eid, Render(color="#FF0000", shape="circle", label="E"))
        world.add_component(eid, Movement(speed=random.randint(2, 4)))
        world.add_component(eid, Collider(18))
        world.add_component(eid, Health(1))
        self.enemies.append([eid, 0])  # [eid, respawn_timer]
        return eid

    def update(self, world, player_id):
        state = world.component_for_entity(player_id, GameState)
        if state.is_over:
            return

        p_trans = world.component_for_entity(player_id, Transform)
        p_status = world.component_for_entity(player_id, StatusEffect)
        current_time = time.time() * 1000

        # 检查 power_mode 过期
        if self.power_mode and current_time > self.power_end_time:
            self.power_mode = False

        # 确保至少有 2 个敌人
        active_enemies = sum(1 for e in self.enemies if world.component_for_entity(e[0], Transform))
        if active_enemies < 2:
            self.spawn_enemy(world, p_trans)

        # 更新每个敌人的 AI
        for i, (eid, respawn_timer) in enumerate(self.enemies):
            e_trans = world.component_for_entity(eid, Transform)
            if e_trans is None:
                # 敌人被消灭，等待重生
                if respawn_timer == 0:
                    self.enemies[i][1] = current_time + 5000  # 5 秒后重生
                elif current_time > respawn_timer:
                    self.enemies[i][0] = self.spawn_enemy(world, p_trans)
                    self.enemies[i][1] = 0
                continue

            e_move = world.component_for_entity(eid, Movement)
            if e_move is None:
                continue

            if self.power_mode:
                # 力量模式：敌人逃跑
                dx = e_trans.x - p_trans.x
                dy = e_trans.y - p_trans.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    e_move.vx = (dx / dist) * 1  # 远离玩家
                    e_move.vy = (dy / dist) * 1
            else:
                # 正常模式：追玩家
                dx = p_trans.x - e_trans.x
                dy = p_trans.y - e_trans.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    # 加入一些随机性
                    e_move.vx = (dx / dist) * 1 + random.uniform(-0.3, 0.3)
                    e_move.vy = (dy / dist) * 1 + random.uniform(-0.3, 0.3)

            # 敌人边界限制
            e_trans.x = max(20, min(e_trans.x, CANVAS_W - 20))
            e_trans.y = max(20, min(e_trans.y, CANVAS_H - 20))

    def activate_power_mode(self, duration_ms=6000):
        """激活力量模式，敌人逃跑"""
        self.power_mode = True
        self.power_end_time = time.time() * 1000 + duration_ms

    def kill_enemy(self, eid, world):
        """消灭敌人（力量模式下）"""
        # 移除 Transform 使其不可见（等待重生）
        world.remove_component(eid, Transform)
        world.remove_component(eid, Movement)
        world.remove_component(eid, Collider)
        world.remove_component(eid, Render)
        world.remove_component(eid, Health)


# ========================
#  CollisionSystem — 碰撞检测
# ========================
class CollisionSystem:
    """处理玩家 ↔ 零食 / 敌人的碰撞"""

    def __init__(self, player_id, snake_system=None, enemy_system=None):
        self.player_id = player_id
        self.snake = snake_system
        self.enemy_sys = enemy_system

    def update(self, world):
        state = world.component_for_entity(self.player_id, GameState)
        if state.is_over:
            return

        p_trans = world.component_for_entity(self.player_id, Transform)
        p_collider = world.component_for_entity(self.player_id, Collider)
        p_health = world.component_for_entity(self.player_id, Health)
        p_score = world.component_for_entity(self.player_id, Score)
        p_status = world.component_for_entity(self.player_id, StatusEffect)
        current_time = time.time() * 1000

        # ========== 零食碰撞 ==========
        for snack_id, (snack_trans, snack_data, snack_collider) in world.get_components(
                Transform, SnackData, Collider):

            if snack_id == self.player_id:
                continue

            # 无敌状态不触发碰撞
            if p_status and p_status.is_invincible:
                continue

            dx = p_trans.x - snack_trans.x
            dy = p_trans.y - snack_trans.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < (p_collider.radius + snack_collider.radius):
                # 基础数值变化
                p_health.hp += snack_data.hp_change
                p_score.value += snack_data.score_value

                # 血量上限
                if p_health.hp > 100:
                    p_health.hp = 100

                # ---- 根据 Type 触发特殊逻辑 ----
                if snack_data.type == "buff":
                    # 泡泡糖：获得护盾（无敌）
                    if not p_status.is_invincible:
                        p_status.is_invincible = True
                        p_status.effect_end_time = current_time + snack_data.duration
                        world.add_component(self.player_id, Shield(snack_data.value))

                elif snack_data.type == "debuff":
                    # 秀逗糖：反向控制
                    if not p_status.is_reversed:
                        p_status.is_reversed = True
                        p_status.effect_end_time = current_time + snack_data.duration

                elif snack_data.type == "special":
                    # 钻石糖：清屏
                    self._clear_screen(world)

                elif snack_data.type == "power":
                    # 🆕 力量糖果：激活力量模式 + 蛇身增长
                    if self.snake:
                        self.snake.grow(2)
                    if self.enemy_sys:
                        self.enemy_sys.activate_power_mode(6000)

                # ---- 贪吃蛇身体增长（普通零食也会增长） ----
                if snack_data.type in ("heal", "buff"):
                    if self.snake:
                        self.snake.grow(1)

                print(f"吃到了: {snack_data.name}  HP={snack_data.hp_change:+d}  Score={snack_data.score_value:+d}")

                world.delete_entity(snack_id)

        # ========== 敌人碰撞 ==========
        if self.enemy_sys:
            for eid, _ in self.enemy_sys.enemies:
                e_trans = world.component_for_entity(eid, Transform)
                e_collider = world.component_for_entity(eid, Collider)
                if e_trans is None or e_collider is None:
                    continue

                dx = p_trans.x - e_trans.x
                dy = p_trans.y - e_trans.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < (p_collider.radius + e_collider.radius):
                    if self.enemy_sys.power_mode:
                        # 力量模式：消灭敌人
                        p_score.value += 200
                        print("消灭幽灵！+200分")
                        self.enemy_sys.kill_enemy(eid, world)
                    elif not (p_status and p_status.is_invincible):
                        # 正常：扣血
                        p_health.hp -= 20
                        # 弹开
                        if distance > 0:
                            p_trans.x += dx / distance * 40
                            p_trans.y += dy / distance * 40

        # ========== 状态过期检测 ==========
        if p_status and (p_status.is_invincible or p_status.is_reversed):
            if current_time > p_status.effect_end_time:
                p_status.is_invincible = False
                p_status.is_reversed = False
                if world.component_for_entity(self.player_id, Shield):
                    world.remove_component(self.player_id, Shield)

        # ========== 死亡判定 ==========
        if p_health.hp <= 0:
            state.is_over = True

    def _clear_screen(self, world):
        """删除所有零食（钻石糖效果）"""
        for ent, (snack_data,) in world.get_components(SnackData):
            if ent != self.player_id:
                world.delete_entity(ent)


# ========================
#  SpawnerSystem — 无尽零食生成
# ========================
class SpawnerSystem:
    """当零食少于一定数量时自动补充"""

    def __init__(self):
        self.min_snacks = 10
        self.spawn_batch = 12

    def update(self, world):
        snack_count = len(list(world.get_components(SnackData)))
        if snack_count < self.min_snacks:
            for _ in range(self.spawn_batch):
                x = random.randint(30, CANVAS_W - 30)
                y = random.randint(30, CANVAS_H - 30)
                create_snack(world, x, y)


# ========================
#  RenderSystem — 渲染所有内容
# ========================
class RenderSystem:
    """绘制玩家、零食、蛇身、敌人、护盾、UI"""

    def __init__(self, canvas: tk.Canvas, snake_system=None, enemy_system=None):
        self.canvas = canvas
        self.snake = snake_system
        self.enemy_sys = enemy_system

    def update(self, world):
        self.canvas.delete("all")

        # 找到玩家 ID
        player_ids = list(world.get_components(GameState))
        if not player_ids:
            return
        player_id = player_ids[0][0]

        p_trans = world.component_for_entity(player_id, Transform)
        p_health = world.component_for_entity(player_id, Health)
        p_score = world.component_for_entity(player_id, Score)
        p_state = world.component_for_entity(player_id, GameState)
        p_status = world.component_for_entity(player_id, StatusEffect)

        # ===== 画蛇身 =====
        if self.snake and self.snake.segment_count > 0:
            segments = self.snake.get_body_segments()
            for i, (sx, sy) in enumerate(segments):
                # 越远的段越透明越小
                alpha = max(0.2, 1.0 - i / len(segments))
                r = int(12 * alpha) + 4
                color_int = int(255 * alpha)
                color = f"#{color_int:02x}{color_int:02x}00"
                self.canvas.create_oval(
                    sx - r, sy - r, sx + r, sy + r,
                    fill=color, outline=""
                )

        # ===== 画护盾 =====
        if world.component_for_entity(player_id, Shield):
            if p_trans:
                self.canvas.create_oval(
                    p_trans.x - 35, p_trans.y - 35,
                    p_trans.x + 35, p_trans.y + 35,
                    outline="cyan", width=3
                )

        # ===== 画敌人 =====
        if self.enemy_sys:
            for eid, _ in self.enemy_sys.enemies:
                e_trans = world.component_for_entity(eid, Transform)
                if e_trans is None:
                    continue
                r = 16
                if self.enemy_sys.power_mode:
                    # 力量模式：蓝圈 + 逃跑表情
                    self.canvas.create_oval(
                        e_trans.x - r, e_trans.y - r,
                        e_trans.x + r, e_trans.y + r,
                        fill="#4444FF", outline="#8888FF", width=2
                    )
                    self.canvas.create_text(
                        e_trans.x, e_trans.y,
                        text="逃", font=("微软雅黑", 14, "bold"),
                        fill="white"
                    )
                else:
                    # 正常模式：红色幽灵形状
                    pts = [
                        e_trans.x - r, e_trans.y,
                        e_trans.x - r, e_trans.y - r,
                        e_trans.x + r, e_trans.y - r,
                        e_trans.x + r, e_trans.y,
                        e_trans.x + r - 4, e_trans.y + 7,
                        e_trans.x + r - 8, e_trans.y,
                        e_trans.x, e_trans.y + 5,
                        e_trans.x - r + 8, e_trans.y,
                        e_trans.x - r + 4, e_trans.y + 7,
                    ]
                    self.canvas.create_polygon(
                        pts, fill="#FF3333", outline="#CC0000", width=1
                    )
                    # 白色眼白
                    for ex in [e_trans.x - 5, e_trans.x + 5]:
                        self.canvas.create_oval(
                            ex - 3, e_trans.y - 8, ex + 3, e_trans.y - 2,
                            fill="white", outline=""
                        )
                        self.canvas.create_oval(
                            ex - 1, e_trans.y - 5, ex + 1, e_trans.y - 4,
                            fill="#0000AA", outline=""
                        )

        # ===== 画零食（按 shape 画图形 + label） =====
        for ent, (trans, render) in world.get_components(Transform, Render):
            if ent == player_id:
                continue
            # 跳过敌人
            if self.enemy_sys:
                is_enemy = any(eid == ent for eid, _ in self.enemy_sys.enemies)
                if is_enemy:
                    continue

            snack_data = world.component_for_entity(ent, SnackData)
            self._draw_shape(trans.x, trans.y, render, snack_data)

        # ===== 画玩家 =====
        if p_trans:
            r = 18
            # 黄色圆形身体
            self.canvas.create_oval(
                p_trans.x - r, p_trans.y - r,
                p_trans.x + r, p_trans.y + r,
                fill="#FFDD00", outline="#FF8800", width=2
            )
            # 中央笑脸
            self.canvas.create_text(
                p_trans.x, p_trans.y,
                text="●", font=("Consolas", 8),
                fill="#FF8800"
            )

        # ===== 画玩家 =====
        if p_trans:
            # 玩家身体（黄圈）
            r = 20
            self.canvas.create_oval(
                p_trans.x - r, p_trans.y - r,
                p_trans.x + r, p_trans.y + r,
                fill="#FFDD00", outline="#FF8800", width=2
            )
            # 玩家脸部（👄）
            self.canvas.create_text(
                p_trans.x, p_trans.y,
                text="👄", font=("Segoe UI Emoji", 22)
            )

        # ===== UI =====
        if p_health and p_score:
            self.canvas.create_text(
                10, 10, text=f"HP: {max(0, p_health.hp)}",
                fill="white", font=("Consolas", 16), anchor="nw"
            )
            self.canvas.create_text(
                10, 36, text=f"Score: {p_score.value}",
                fill="#FFD700", font=("Consolas", 16), anchor="nw"
            )
            if self.snake:
                self.canvas.create_text(
                    10, 62, text=f"蛇身: {self.snake.segment_count}节",
                    fill="#FF8800", font=("Consolas", 14), anchor="nw"
                )

        # 状态提示
        if p_status:
            if p_status.is_reversed:
                self.canvas.create_text(
                    CANVAS_W / 2, 30, text="🌀 反向控制 🌀",
                    fill="#33FF33", font=("Consolas", 20, "bold")
                )
            if self.enemy_sys and self.enemy_sys.power_mode:
                self.canvas.create_text(
                    CANVAS_W / 2, 30, text="⚡ 力量模式！吃掉幽灵！⚡",
                    fill="#FFD700", font=("Consolas", 20, "bold")
                )

    def _draw_shape(self, cx, cy, render, snack_data=None):
        """根据 shape 类型画不同图形，中央显示 label"""
        r = 13  # 基础半径
        shape = render.shape
        label = render.label
        color = render.color
        outline = render.outline

        # 特殊类型：加大尺寸
        if snack_data:
            if snack_data.type == "power":
                r = 16
            elif snack_data.type == "special":
                r = 16

        if shape == "circle":
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=color, outline=outline, width=2
            )
        elif shape == "square":
            self.canvas.create_rectangle(
                cx - r, cy - r, cx + r, cy + r,
                fill=color, outline=outline, width=2
            )
        elif shape == "diamond":
            pts = [cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy]
            self.canvas.create_polygon(
                pts, fill=color, outline=outline, width=2
            )
        elif shape == "triangle":
            pts = [cx, cy - r, cx + r, cy + r, cx - r, cy + r]
            self.canvas.create_polygon(
                pts, fill=color, outline=outline, width=2
            )
        elif shape == "star":
            # 五角星
            pts = []
            for i in range(10):
                angle = math.radians(i * 36 - 90)
                rr = r if i % 2 == 0 else r * 0.45
                pts.extend([cx + rr * math.cos(angle), cy + rr * math.sin(angle)])
            self.canvas.create_polygon(
                pts, fill=color, outline=outline, width=2
            )
        else:
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=color, outline=outline, width=2
            )

        # 中央标签文字（深色文字，加大加粗）
        text_color = "#111111" if self._is_light_color(color) else "#FFFFFF"
        self.canvas.create_text(
            cx, cy, text=label,
            fill=text_color, font=("Consolas", 12, "bold")
        )

    @staticmethod
    def _is_light_color(hex_color):
        """判断颜色是否为浅色（决定文字用黑色还是白色）"""
        try:
            c = hex_color.lstrip("#")
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return (r * 0.299 + g * 0.587 + b * 0.114) > 150
        except (ValueError, IndexError):
            return False

        # ===== 游戏结束画面 =====
        if p_state.is_over:
            self.canvas.create_rectangle(0, 200, CANVAS_W, 400, fill="#111111", outline="#880000", width=5)
            self.canvas.create_text(
                CANVAS_W / 2, 270, text="GAME OVER",
                fill="#FF0000", font=("Consolas", 48, "bold")
            )
            if p_score:
                self.canvas.create_text(
                    CANVAS_W / 2, 320,
                    text=f"最终得分: {p_score.value}  蛇身: {self.snake.segment_count if self.snake else 0}节",
                    fill="#CCCCCC", font=("Consolas", 18)
                )
            self.canvas.create_text(
                CANVAS_W / 2, 360,
                text="按 [SPACE] 重新开始",
                fill="#FFD700", font=("Consolas", 16)
            )
