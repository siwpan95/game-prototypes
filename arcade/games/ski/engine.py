"""游戏引擎 - 纯游戏逻辑，零 UI 依赖。

增强版特性（参考 1991 原版 SkiFree 机制）：
- 多种障碍物：树 / 岩石 / 旗子（收集）/ 跳台（触发跳跃）
- 雪人（Abominable Snow Monster）：滑行达到 YETI_TRIGGER_DISTANCE 后从底部追击
- 跳跃系统：踩中跳台进入跳跃状态，可越过 blockable 障碍物并赚风格分
- 加速冲刺（F 键）：短暂提速逃脱雪人，有冷却
- 暂停（P 键）与单帧步进（T 键）
- 难度递增：距离越远，滚动越快、障碍越密
- 风格分：跳跃与旗子贡献，自由式模式核心
- 三种游戏模式：无尽 / 回转 / 自由式
- 事件流：tick() 返回本帧事件供 UI 播放特效

引擎保持「输入 → tick → snapshot」三段式纯逻辑，不依赖任何 tkinter 符号。
"""

from __future__ import annotations

import random
from typing import Any

from config import (
    BOOST_COOLDOWN,
    BOOST_DURATION,
    BOOST_SPEED_MULTIPLIER,
    DIFFICULTY_INTERVAL,
    GAME_OVER_SCORE,
    HEIGHT,
    JUMP_DURATION,
    JUMP_STYLE_BONUS,
    MAX_DIFFICULTY,
    MODE_ENDLESS,
    MODE_FREESTYLE,
    MODE_SLALOM,
    OBSTACLE_SCROLL_DIVISOR,
    OBSTACLE_TYPES,
    SKIER_CHARS,
    SKIER_BOOST_CHAR,
    SKIER_CRASH_CHAR,
    SKIER_JUMP_CHAR,
    WIDTH,
    YETI_BASE_SPEED,
    YETI_BOOST_SPEED,
    YETI_TRIGGER_DISTANCE,
)


class GameEngine:
    """纯游戏逻辑引擎：管理状态、移动、碰撞、雪人、跳跃、加速，不涉及任何 UI 渲染。"""

    def __init__(self, mode: str = MODE_ENDLESS):
        self.mode = mode
        self.high_score = 0
        self.reset()

    # ========== 生命周期 ==========

    def reset(self):
        """重置所有状态到初始值（保留 high_score 与 mode）。"""
        self.skier_x = WIDTH // 2
        self.skier_y = 5
        self.skier_direction = 0
        self.speed_x = 0
        self.score = 0
        self.style_score = 0
        self.distance = 0
        self.game_over = False
        self.game_started = False
        self.paused = False
        self.death_reason: str | None = None

        self.obstacles: list[list[Any]] = []
        self._tick_count = 0

        # 跳跃状态
        self.jumping = False
        self._jump_ticks = 0

        # 加速状态
        self.boosting = False
        self._boost_ticks = 0
        self._boost_cooldown = 0

        # 雪人状态
        self.yeti_active = False
        self.yeti_y: float = 0.0  # 浮点位置，便于平滑追击

        # 难度等级
        self.difficulty = 1

    def start(self):
        """开始游戏：重置状态并生成初始障碍物。"""
        self.reset()
        self.game_started = True
        self.game_over = False
        self.obstacles = self._spawn_obstacles(HEIGHT - 1, 20)

    def set_mode(self, mode: str):
        """切换游戏模式（仅未开始时允许）。"""
        if not self.game_started:
            self.mode = mode

    # ========== 输入动作 ==========

    def turn(self, direction_change: int):
        """改变滑雪者方向。-1 左转, +1 右转。"""
        if self.game_over or not self.game_started or self.paused:
            return
        self.skier_direction += direction_change
        self.skier_direction = max(-2, min(2, self.skier_direction))
        self.speed_x = self.skier_direction

    def toggle_pause(self):
        """切换暂停。"""
        if not self.game_started or self.game_over:
            return
        self.paused = not self.paused

    def step_single_frame(self):
        """单帧步进（暂停时按 T 触发）。返回是否真的步进了一帧。"""
        if not self.paused or self.game_over or not self.game_started:
            return False
        # 临时解除暂停跑一帧
        self.paused = False
        self.tick()
        self.paused = True
        return True

    def activate_boost(self):
        """触发加速冲刺（F 键）。冷却中则忽略。"""
        if (
            not self.game_started
            or self.game_over
            or self.paused
            or self.boosting
            or self._boost_cooldown > 0
        ):
            return False
        self.boosting = True
        self._boost_ticks = BOOST_DURATION
        return True

    # ========== 主循环 tick ==========

    def tick(self) -> list[tuple[Any, ...]]:
        """执行一帧游戏逻辑。

        Returns:
            本帧事件列表，例如 [("tree", x, y), ("flag", x, y), ("jump_start",),
            ("boost_start",), ("yeti_spawn",), ("eaten",)]
        """
        if (
            self.game_over
            or not self.game_started
            or self.paused
        ):
            return []

        self._tick_count += 1
        events: list[tuple[Any, ...]] = []

        # 1. 更新跳跃计时
        if self.jumping:
            self._jump_ticks -= 1
            if self._jump_ticks <= 0:
                self.jumping = False
                self.style_score += JUMP_STYLE_BONUS
                events.append(("jump_end",))

        # 2. 更新加速计时
        if self.boosting:
            self._boost_ticks -= 1
            if self._boost_ticks <= 0:
                self.boosting = False
                self._boost_cooldown = BOOST_COOLDOWN
                events.append(("boost_end",))
        elif self._boost_cooldown > 0:
            self._boost_cooldown -= 1

        # 3. 滑雪者横向移动
        self._move_skier()

        # 4. 障碍物滚动（按难度决定滚动节奏）
        scroll_step = self._current_scroll_step()
        if self._tick_count % scroll_step == 0:
            self._move_obstacles()

        # 5. 雪人逻辑
        yeti_event = self._update_yeti()
        if yeti_event:
            events.append(yeti_event)

        # 6. 碰撞检测
        events.extend(self._check_collisions())

        # 7. 难度递增
        if self.distance > 0 and self.distance % DIFFICULTY_INTERVAL == 0:
            if self.difficulty < MAX_DIFFICULTY:
                self.difficulty += 1

        # 8. 失败判定
        if self.score < GAME_OVER_SCORE:
            self.game_over = True
            self.death_reason = "score"
            events.append(("game_over", "score"))

        return events

    def get_snapshot(self) -> dict[str, Any]:
        """返回渲染所需的游戏状态快照（深拷贝关键数据）。"""
        # 决定滑雪者显示字符：跳跃 > 加速 > 方向
        if self.jumping:
            skier_char = SKIER_JUMP_CHAR
        elif self.boosting:
            skier_char = SKIER_BOOST_CHAR
        elif self.game_over:
            skier_char = SKIER_CRASH_CHAR
        else:
            skier_char = SKIER_CHARS.get(self.skier_direction, "▲")

        return {
            "skier_x": self.skier_x,
            "skier_y": self.skier_y,
            "skier_char": skier_char,
            "obstacles": [o[:] for o in self.obstacles],
            "score": self.score,
            "style_score": self.style_score,
            "distance": self.distance,
            "game_over": self.game_over,
            "game_started": self.game_started,
            "paused": self.paused,
            "jumping": self.jumping,
            "boosting": self.boosting,
            "boost_cooldown": self._boost_cooldown,
            "boost_cooldown_max": BOOST_COOLDOWN,
            "yeti_active": self.yeti_active,
            "yeti_y": int(self.yeti_y),
            "difficulty": self.difficulty,
            "mode": self.mode,
            "death_reason": self.death_reason,
            "high_score": self.high_score,
        }

    # ========== 内部：移动 ==========

    def _move_skier(self):
        """滑雪者横向移动（位置受限在屏幕内）。"""
        self.skier_x += self.speed_x
        self.skier_x = max(0, min(self.skier_x, WIDTH - 1))

    def _move_obstacles(self):
        """障碍物向上滚动；移出屏幕的循环复用；定期新增。"""
        scroll_speed = self._current_scroll_speed()

        for obstacle in self.obstacles:
            obstacle[1] -= scroll_speed
            if obstacle[1] < 0:
                # 移出顶部，回收到底部重新生成
                obstacle[1] = HEIGHT - 1
                obstacle[0] = random.randint(0, WIDTH - 1)
                obstacle[2] = self._weighted_random_obstacle_type()
                obstacle[3] = False

        self.distance += scroll_speed

        # 难度越高，补充越快
        replenish_interval = max(10, 20 - self.difficulty)
        if int(self.distance) % replenish_interval == 0:
            new_obs = self._spawn_obstacles(HEIGHT - 5, 3 + self.difficulty)
            self.obstacles.extend(new_obs)

    def _current_scroll_step(self) -> int:
        """障碍物滚动节奏（每隔多少 tick 滚动一次）。加速时更频繁。"""
        base = OBSTACLE_SCROLL_DIVISOR
        if self.boosting:
            return 1  # 加速时每帧都滚
        # 难度提升 → 步进变小（更频繁）
        return max(1, base - self.difficulty // 4)

    def _current_scroll_speed(self) -> int:
        """每滚动一格移动的行数。"""
        return 2 if self.boosting else 1

    # ========== 内部：雪人 ==========

    def _update_yeti(self) -> tuple[Any, ...] | None:
        """更新雪人位置与追击。返回事件或 None。"""
        # 仅无尽模式有雪人
        if self.mode != MODE_ENDLESS:
            return None

        # 触发雪人
        if not self.yeti_active and self.distance >= YETI_TRIGGER_DISTANCE:
            self.yeti_active = True
            self.yeti_y = float(HEIGHT - 1)
            return ("yeti_spawn",)

        if not self.yeti_active:
            return None

        # 雪人相对速度 = 绝对速度 - 当前滚动速度
        scroll_speed = self._current_scroll_speed()
        # 加速时雪人几乎停滞甚至后退
        yeti_speed = YETI_BOOST_SPEED if self.boosting else YETI_BASE_SPEED
        relative = max(0.0, yeti_speed - scroll_speed * 0.5)
        self.yeti_y -= relative

        # 雪人不能超出屏幕底部
        if self.yeti_y > HEIGHT - 1:
            self.yeti_y = float(HEIGHT - 1)

        # 雪人追上玩家 → 被吃掉
        if int(self.yeti_y) <= self.skier_y:
            self.game_over = True
            self.death_reason = "yeti"
            return ("eaten",)

        return None

    # ========== 内部：碰撞 ==========

    def _check_collisions(self) -> list[tuple[Any, ...]]:
        """检测滑雪者与障碍物的碰撞。"""
        events: list[tuple[Any, ...]] = []
        to_remove: list[list[Any]] = []

        for obstacle in self.obstacles:
            x, y, obstacle_type, passed = obstacle
            if passed:
                continue
            if not (abs(x - self.skier_x) <= 1 and abs(y - self.skier_y) <= 1):
                continue

            cfg = OBSTACLE_TYPES.get(obstacle_type)
            if cfg is None:
                continue

            # 跳台：触发跳跃
            if cfg.get("action") == "jump":
                if not self.jumping:
                    self.jumping = True
                    self._jump_ticks = JUMP_DURATION
                    events.append(("jump_start", x, y))
                obstacle[3] = True
                continue

            # 跳跃中：可越过 blockable 障碍物（树/岩石）
            if self.jumping and cfg.get("blockable"):
                obstacle[3] = True  # 标记已处理，不再判定
                continue

            # 收集物：旗子
            if cfg.get("collectible"):
                self.score += cfg["score"]
                # 旗子在自由式里也算风格分
                if self.mode == MODE_FREESTYLE:
                    self.style_score += cfg["score"]
                to_remove.append(obstacle)
                events.append(("flag", x, y))
                continue

            # 阻挡物：扣分
            if "score" in cfg:
                self.score += cfg["score"]
                obstacle[3] = True
                events.append((obstacle_type, x, y))

        for obstacle in to_remove:
            if obstacle in self.obstacles:
                self.obstacles.remove(obstacle)

        return events

    # ========== 内部：生成 ==========

    def _spawn_obstacles(self, start_row: int, num: int) -> list[list[Any]]:
        """在指定行起向下随机生成一批障碍物（按权重）。"""
        obstacles: list[list[Any]] = []
        for _ in range(num):
            row = start_row + random.randint(0, 2) if start_row < HEIGHT - 2 else HEIGHT - 1
            row = min(row, HEIGHT - 1)
            col = random.randint(0, WIDTH - 1)
            obstacle_type = self._weighted_random_obstacle_type()
            obstacles.append([col, row, obstacle_type, False])
        return obstacles

    @staticmethod
    def _weighted_random_obstacle_type() -> str:
        """按权重随机选择障碍物类型。"""
        types = list(OBSTACLE_TYPES.keys())
        weights = [OBSTACLE_TYPES[t].get("weight", 1) for t in types]
        return random.choices(types, weights=weights, k=1)[0]
