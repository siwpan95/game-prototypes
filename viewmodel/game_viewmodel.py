"""GameViewModel - 一局麻将连连看的状态机与命令中枢。

职责:
  - 持有 GameState，对外只读
  - 提供命令: 新局/选牌/撤销/提示/洗牌/切模式/暂停/计时
  - 维护撤销栈、连击、死局检测、胜负判定
  - 通过事件回调 (listener) 通知视图刷新，自身不碰 UI

事件类型 (event.type):
  new_game / select / deselect / match / reject / hint / hint_empty
  shuffle / shuffle_empty / undo / undo_empty / win / lose / deadlock
  pause / resume / tick / mode_changed
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from models.board import Board, Pos
from models.game_state import GameMode, GameState, MoveRecord
from models.tile import Tile
from services.deck import build_standard_deck
from services.layouts import LayoutKind, generate_layout
from services.matcher import (
    can_link, find_hint_pair, has_solution, is_free, tile_match,
)
from services.scorer import score_for_match, time_bonus, COMBO_WINDOW
from allin_engine.core.event_bus import EventBus


Listener = Callable[["GameEvent"], None]

# 已知事件类型契约（引擎 EventBus 无通配订阅，显式枚举注册分发器）
GAME_EVENTS = (
    "new_game", "select", "deselect", "match", "reject", "hint", "hint_empty",
    "shuffle", "shuffle_empty", "undo", "undo_empty", "win", "lose", "deadlock",
    "pause", "resume", "tick", "mode_changed",
)


@dataclass
class GameEvent:
    type: str
    data: Dict[str, Any] = field(default_factory=dict)


class GameViewModel:
    def __init__(
        self,
        layout: LayoutKind = LayoutKind.TURTLE,
        mode: GameMode = GameMode.MAHJONG,
        time_limit: int = 300,
        hints: int = 3,
        shuffles: int = 3,
    ) -> None:
        self._layout: LayoutKind = layout
        self._time_limit: int = time_limit
        self._init_hints: int = hints
        self._init_shuffles: int = shuffles
        self.state: GameState = GameState(mode=mode, time_limit=time_limit)
        # 事件总线（引擎 EventBus：递归保护 + 单回调容错）
        self._bus = EventBus()
        self._legacy_listeners: List[Listener] = []
        for _t in GAME_EVENTS:
            self._bus.subscribe(_t, self._make_dispatcher(_t))

    # ---- 监听（对外 API 不变，内部走引擎 EventBus）--------
    def add_listener(self, fn: Listener) -> None:
        self._legacy_listeners.append(fn)

    def _make_dispatcher(self, etype: str):
        """把总线 payload 包回 GameEvent 信封，回传给旧式监听者。"""
        def _dispatch(data: Any) -> None:
            ev = GameEvent(etype, data if isinstance(data, dict) else {})
            for fn in list(self._legacy_listeners):
                try:
                    fn(ev)
                except Exception:
                    # 视图回调异常不应影响状态机
                    pass
        return _dispatch

    def _emit(self, etype: str, **data: Any) -> None:
        self._bus.publish(etype, **data)

    # ============================================================
    #  生命周期
    # ============================================================
    def start_new_game(
        self,
        layout: Optional[LayoutKind] = None,
        mode: Optional[GameMode] = None,
    ) -> None:
        if layout is not None:
            self._layout = layout
        old_mode = self.state.mode
        new_mode = mode if mode is not None else old_mode

        # 连连看使用单层平面布局; 上海麻将使用分层布局
        effective_layout = (
            LayoutKind.LINK_FLAT if new_mode == GameMode.LINK else self._layout
        )

        deck = build_standard_deck()
        random.shuffle(deck)
        slots = generate_layout(effective_layout)
        board = Board()
        for pos, tile in zip(slots, deck):
            board.place(pos, tile)

        self.state = GameState(
            board=board,
            mode=new_mode,
            time_limit=self._time_limit,
            hints_left=self._init_hints,
            shuffles_left=self._init_shuffles,
            running=True,
        )
        mode_changed = (new_mode != old_mode)
        self._emit("new_game", mode_changed=mode_changed)
        if mode_changed:
            self._emit("mode_changed", mode=new_mode.value)

    def restart(self) -> None:
        self.start_new_game()

    # ============================================================
    #  计时 (由 View 的 after 循环驱动)
    # ============================================================
    def tick(self, dt: float = 0.0) -> None:
        """由主循环按固定步长推进计时；dt 由循环注入（不再读墙钟）。"""
        if not self.state.running or self.state.paused:
            return
        self.state.elapsed += dt

        if self.state.time_limit > 0 and self.state.elapsed >= self.state.time_limit:
            self.state.elapsed = self.state.time_limit
            self.state.lost = True
            self.state.running = False
            self._emit("lose")
            return
        self._emit("tick")

    def toggle_pause(self) -> None:
        if not self.state.running:
            return
        self.state.paused = not self.state.paused
        self._emit("resume" if not self.state.paused else "pause")

    # ============================================================
    #  选牌 (核心交互)
    # ============================================================
    def select(self, pos: Pos) -> None:
        st = self.state
        if not st.running or st.paused or st.won or st.lost:
            return
        tile = st.board.get(pos)
        if tile is None:
            return

        # 自由牌检查 (仅 mahjong 模式)
        if st.mode == GameMode.MAHJONG and not is_free(st.board, pos):
            self._emit("reject", reason="不是自由牌", pos=pos, tile=tile)
            return

        # 首次选中
        if st.selected is None:
            st.selected = pos
            self._emit("select", pos=pos, tile=tile)
            return

        # 再次点击同一张 -> 取消
        prev = st.selected
        if prev == pos:
            st.selected = None
            self._emit("deselect", pos=pos)
            return

        ptile = st.board.get(prev)
        if ptile is None:
            st.selected = None
            return

        # 配对检查
        if not tile_match(ptile, tile):
            st.selected = pos  # 切换为新选中
            self._emit("reject", reason="不配对", pos=pos, tile=tile,
                       prev=prev, prev_tile=ptile)
            self._emit("select", pos=pos, tile=tile)
            return

        # 连通检查 (仅 link 模式)
        if st.mode == GameMode.LINK and not can_link(st.board, prev, pos):
            st.selected = None
            self._emit("reject", reason="连线不通", pos=pos, tile=tile,
                       prev=prev, prev_tile=ptile)
            return

        # 执行消除
        self._do_match(prev, pos)

    def _do_match(self, pos_a: Pos, pos_b: Pos) -> None:
        st = self.state
        ta = st.board.get(pos_a)
        tb = st.board.get(pos_b)
        if ta is None or tb is None:
            return

        # 保存消除前的计时/连击状态（撤销时回滚，避免超时瞬间再次判负）
        elapsed_before = st.elapsed
        combo_before = st.combo
        last_match_at_before = st.last_match_at

        # 计分 (含连击)
        now = st.elapsed
        if st.last_match_at < 0:
            # 本局首次配对：不计连击
            dt = 999.0
            combo_lvl = 0
        else:
            dt = now - st.last_match_at
            combo_lvl = st.combo if dt < COMBO_WINDOW else 0
        breakdown = score_for_match(ta, tb, combo_lvl, dt)
        st.score += breakdown.total
        st.combo = combo_lvl + 1
        st.last_match_at = now

        # 撤销记录（含消除前状态，使撤销成为真正的逆操作）
        rec = MoveRecord(
            pos_a, ta, pos_b, tb,
            score_delta=breakdown.total,
            elapsed_before=elapsed_before,
            combo_before=combo_before,
            last_match_at_before=last_match_at_before,
        )
        st.history.append(rec)

        # 消除
        st.board.remove(pos_a)
        st.board.remove(pos_b)
        st.selected = None
        st.moves += 1

        self._emit(
            "match",
            pos_a=pos_a, pos_b=pos_b,
            tile_a=ta, tile_b=tb,
            breakdown=breakdown,
            combo=st.combo,
        )

        # 胜负 / 死局
        if st.board.is_empty():
            bonus = time_bonus(st.time_left) if st.time_limit > 0 else 0
            st.score += bonus
            st.won = True
            st.running = False
            # 记录通关奖励，使撤销能一并回滚（否则撤销后分数残留奖励分）
            rec.win_bonus = bonus
            self._emit("win", time_bonus=bonus, final_score=st.score, moves=st.moves)
        elif not has_solution(st.board, st.mode.value):
            self._emit("deadlock")

    # ============================================================
    #  撤销
    # ============================================================
    def undo(self) -> None:
        st = self.state
        if not st.history:
            self._emit("undo_empty")
            return
        rec = st.history.pop()
        st.board.restore(rec.pos_a, rec.tile_a)
        st.board.restore(rec.pos_b, rec.tile_b)
        st.score = max(0, st.score - rec.score_delta - rec.win_bonus)
        st.moves = max(0, st.moves - 1)
        st.selected = None
        # 回滚消除前的计时/连击状态，使撤销成为真正的逆操作
        st.elapsed = rec.elapsed_before
        st.combo = rec.combo_before
        st.last_match_at = rec.last_match_at_before
        st.won = False
        st.lost = False
        if not st.running:
            st.running = True  # 撤销可复活超时/死局，并回滚计时避免瞬间再次超时
        self._emit("undo", record=rec)

    # ============================================================
    #  提示
    # ============================================================
    def use_hint(self) -> None:
        st = self.state
        if not st.running or st.paused:
            return
        if st.hints_left <= 0:
            self._emit("hint_empty")
            return
        pair = find_hint_pair(st.board, st.mode.value)
        if pair is None:
            self._emit("hint_empty", reason="无可用配对")
            return
        st.hints_left -= 1
        self._emit("hint", pair=pair, hints_left=st.hints_left)

    # ============================================================
    #  洗牌 (保留布局，重排剩余牌面；尽量洗到有解)
    # ============================================================
    def shuffle(self) -> None:
        st = self.state
        if not st.running or st.paused:
            return
        if st.shuffles_left <= 0:
            self._emit("shuffle_empty")
            return
        st.shuffles_left -= 1

        # 走 ECS 适配器 API（不再直接戳 board.tiles）
        positions = st.board.occupied_positions()
        tiles = [st.board.get(p) for p in positions]

        for attempt in range(20):
            random.shuffle(tiles)
            for p in positions:
                st.board.remove(p)
            for p, t in zip(positions, tiles):
                st.board.place(p, t)
            if has_solution(st.board, st.mode.value):
                break

        st.selected = None
        st.combo = 0
        self._emit("shuffle", positions=positions, shuffles_left=st.shuffles_left)

    # ============================================================
    #  模式切换
    # ============================================================
    def toggle_mode(self) -> None:
        new_mode = GameMode.LINK if self.state.mode == GameMode.MAHJONG else GameMode.MAHJONG
        self.start_new_game(mode=new_mode)

    def set_layout(self, layout: LayoutKind) -> None:
        self.start_new_game(layout=layout)
