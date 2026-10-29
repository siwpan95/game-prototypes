"""
六一零食大闯关 · 无尽模式
玩法：自由移动 → 收集零食 → 蛇身增长 → 躲避幽灵 → 不死不休
方向键/WASD 移动，空格键重开
增量完善：贪吃蛇身体 + 吃豆人式追逐敌人
"""
import tkinter as tk
import random

from ecs import World
from components import (
    Transform, Render, Movement, Health, Score,
    Collider, GameState, StatusEffect,
)
from systems import (
    MovementSystem, SnakeSystem, EnemySystem,
    CollisionSystem, SpawnerSystem, RenderSystem,
    CANVAS_W, CANVAS_H,
)
from entities import create_snack, CONFIG
from audio_manager import AudioManager


class Game(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("六一零食大闯关 · 无尽贪吃模式")
        self.geometry(f"{CANVAS_W}x{CANVAS_H}")
        self.resizable(False, False)

        self.canvas = tk.Canvas(self, bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.focus_set()  # 确保 Canvas 能接收键盘事件

        self.audio = AudioManager()

        # 初始化子系统
        self.snake_sys = SnakeSystem(None)    # player_id 在 setup_game 后设置
        self.enemy_sys = EnemySystem()

        self.world = World()
        self.setup_game()

        self.bind("<KeyPress>", self.on_key)
        self.bind("<KeyRelease>", self.off_key)

        self.game_loop()

    def setup_game(self):
        """初始化 / 重置游戏"""
        self.world._entities.clear()
        self.world._dead_entities.clear()

        # ---- 创建玩家 ----
        self.player = self.world.create_entity()
        self.world.add_component(self.player, Transform(CANVAS_W // 2, CANVAS_H // 2))
        self.world.add_component(self.player, Render(color="#FFDD00", shape="circle", label="P"))
        self.world.add_component(self.player, Movement(speed=5))
        self.world.add_component(self.player, Health(100))
        self.world.add_component(self.player, Score())
        self.world.add_component(self.player, Collider(20))
        self.world.add_component(self.player, GameState())
        self.world.add_component(self.player, StatusEffect())

        # ---- 初始化贪吃蛇系统 ----
        self.snake_sys = SnakeSystem(self.player)

        # ---- 初始化敌人系统 ----
        self.enemy_sys = EnemySystem()
        # 初始生成 2 个敌人
        p_trans = self.world.component_for_entity(self.player, Transform)
        for _ in range(2):
            self.enemy_sys.spawn_enemy(self.world, p_trans)

        # ---- 初始零食 ----
        for _ in range(30):
            x = random.randint(30, CANVAS_W - 30)
            y = random.randint(30, CANVAS_H - 30)
            create_snack(self.world, x, y)

        # ---- 放置 2 个力量糖果（新增） ----
        for _ in range(2):
            px = random.randint(50, CANVAS_W - 50)
            py = random.randint(50, CANVAS_H - 50)
            eid = self.world.create_entity()
            self.world.add_component(eid, Transform(px, py))
            self.world.add_component(eid, Render(color="#FFD700", shape="diamond", label="P", outline="#FF8800"))
            self.world.add_component(eid, Collider(16))
            # 手动构造一个 power 类型的 SnackData
            from components import SnackData
            self.world.add_component(eid, SnackData(
                name="力量糖果", shape="diamond", label="P", snack_type="power",
                hp_change=5, score=50, color="#FFD700", duration=6000, value=0
            ))

    def on_key(self, e):
        """键盘按下"""
        state = self.world.component_for_entity(self.player, GameState)
        if state is None:
            return

        # 空格键重开
        if e.keysym == 'space':
            if state.is_over:
                self.setup_game()
            return

        if state.is_over:
            return

        move = self.world.component_for_entity(self.player, Movement)
        if move is None:
            return

        # 方向键 / WASD
        if e.keysym in ('Left', 'a'):
            move.vx = -1
        elif e.keysym in ('Right', 'd'):
            move.vx = 1
        elif e.keysym in ('Up', 'w'):
            move.vy = -1
        elif e.keysym in ('Down', 's'):
            move.vy = 1

    def off_key(self, e):
        """键盘释放"""
        move = self.world.component_for_entity(self.player, Movement)
        if move is None:
            return
        if e.keysym in ('Left', 'a') and move.vx == -1:
            move.vx = 0
        elif e.keysym in ('Right', 'd') and move.vx == 1:
            move.vx = 0
        elif e.keysym in ('Up', 'w') and move.vy == -1:
            move.vy = 0
        elif e.keysym in ('Down', 's') and move.vy == 1:
            move.vy = 0

    def game_loop(self):
        """主循环"""
        # 更新逻辑
        self.world.update(MovementSystem())
        self.world.update(self.snake_sys)                     # 🆕 贪吃蛇身体
        self.enemy_sys.update(self.world, self.player)        # 🆕 追逐敌人
        self.world.update(CollisionSystem(
            self.player, self.snake_sys, self.enemy_sys
        ))
        self.world.update(SpawnerSystem())
        self.world.update(RenderSystem(
            self.canvas, self.snake_sys, self.enemy_sys
        ))
        self.world.clear_dead_entities()

        self.after(30, self.game_loop)


if __name__ == "__main__":
    game = Game()
    game.mainloop()
