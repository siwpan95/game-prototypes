# -*- coding: utf-8 -*-
"""
全自动零玩家引擎 — 事件→进度条→状态机 驱动游戏流程

架构：
  AutoEngine 持有 pipeline（SM_Recruit→SM_Shop→SM_Explore→SM_Battle→SM_Rest→SM_Loop）
  每个阶段对应一个 GenericStateMachine + 一个 CanvasProgressBar。
  进度条动画驱动状态转移，状态转移时执行游戏实际操作。
"""

import json
import os
import random
import time
from typing import Optional, Callable

from core.state_machine import GenericStateMachine


# ==================== 配置加载 ====================
def load_auto_config() -> dict:
    """加载自动化配置文件"""
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==================== 冒险者名字池 ====================
ADVENTURER_NAMES = [
    "亚瑟", "梅林", "兰斯洛特", "莫德雷德", "加拉哈德",
    "艾琳", "索菲亚", "雷恩", "艾尔文", "莉亚",
    "罗兰", "塞西尔", "阿尔弗雷德", "维多利亚", "伊丽莎白",
    "卡珊德拉", "帕拉丁", "西格玛", "奥莉薇", "霍克",
    "菲奥娜", "格雷", "泽菲", "尤娜", "弗林",
]

# 阶段短名映射
SM_SHORT_LABELS = {
    "SM_Recruit": "招募",
    "SM_Shop": "购物",
    "SM_Warehouse": "仓库",
    "SM_Explore": "探索",
    "SM_Rest": "休息",
}

# 阶段主题颜色（用于迷你进度条高亮）
_SM_THEMES_COLORS = {
    "SM_Recruit": ("#9B59B6", "#EDE1F2"),
    "SM_Shop": ("#F5A623", "#FFF8E7"),
    "SM_Warehouse": ("#8D6E63", "#EFEBE9"),
    "SM_Explore": ("#4A90D9", "#D6E8F7"),
    "SM_Rest": ("#6ABF69", "#DFF0D8"),
}


def _get_theme(sm_name: str) -> object:
    """获取阶段主题颜色信息（返回 (bar_color, bg_color) 或 None）"""
    return _SM_THEMES_COLORS.get(sm_name)


# ==================== 自动化引擎 ====================
class AutoEngine:
    """全自动零玩家游戏引擎。

    负责：
    1. 创建并管理所有状态机实例
    2. 驱动管线（事件→进度条→状态机）
    3. 执行实际游戏操作（招募/购物/探索/战斗/休息）
    4. 与 UI 进度条和日志系统交互
    """

    def __init__(self, app):
        """
        Args:
            app: ExplorationApp 实例，提供 engine、_log、进度条容器等
        """
        self.app = app
        self.engine = app.engine
        self.config = load_auto_config()
        self.global_cfg = self.config["global"]
        self.pipeline = self.config["pipeline"]

        # ---- 状态机实例 ----
        self.state_machines: dict[str, GenericStateMachine] = {}

        # ---- 进度条引用（由 UI 层注入）----
        self.progress_bars: dict[str, any] = {}

        # 主进度条更新回调（由 UI 层注入）
        self._main_progress_callback: Optional[Callable] = None

        # ---- 管线状态 ----
        self.stage_index = 0
        self.current_sm_name = ""
        self.running = False
        self.paused = False
        self._after_id = None

        # ---- 统计 ----
        self.loop_count = 0
        self.total_battles = 0
        self.total_recruits = 0
        self.start_time = 0.0

        # ---- 辅助状态 ----
        self._pending_next_stage = False  # 标记在动画回调后推进
        self._speed_multiplier = 1.0       # 动画速度倍率

        self._init_state_machines()

    def _init_state_machines(self):
        """创建所有状态机实例"""
        for name in self.pipeline:
            sm = GenericStateMachine(
                machine_name=name,
                full_config=self.config,
                on_action=self._on_sm_action
            )
            self.state_machines[name] = sm

    # ==================== 状态机回调 ====================
    def _on_sm_action(self, action_type: str, state_id: str, detail: dict):
        """状态机动作回调：记录到日志面板"""
        desc = detail.get("description", "")
        if not desc:
            return
        sm_name = getattr(self, '_last_sm_name', self.current_sm_name)
        self._auto_log(f"[{sm_name}] {state_id}: {desc}", "auto_action")

    # ==================== 日志 ====================
    def _auto_log(self, msg: str, tag: str = None):
        """写入自动化日志"""
        ts = time.strftime("%H:%M:%S")
        full_msg = f"[Auto {ts}] {msg}"
        try:
            if hasattr(self.app, '_auto_log_text') and self.app._auto_log_text is not None:
                self.app._auto_log_text.configure(state="normal")
                self.app._auto_log_text.insert("end", f"{full_msg}\n")
                self.app._auto_log_text.see("end")
                self.app._auto_log_text.configure(state="disabled")
        except Exception:
            pass
        # 同时写入主日志
        try:
            if hasattr(self.app, '_log'):
                self.app._log(full_msg, tag)
        except Exception:
            pass
        # 兜底：直接写文件日志
        try:
            from gui.app import _write_file_log
            _write_file_log(full_msg)
        except Exception:
            pass

    # ==================== 控制 ====================
    def start(self):
        """启动自动化流程"""
        if self.running:
            return
        self.running = True
        self.paused = False
        self.stage_index = 0
        self.loop_count = 0
        self.total_battles = 0
        self.total_recruits = 0
        self.start_time = time.time()
        self._auto_log("══════════ 全自动零玩家模式启动 ══════════", "auto_start")
        self._auto_log(f"管线: {' → '.join(self.pipeline)}")
        self._advance_pipeline()

    def stop(self):
        """停止自动化"""
        self.running = False
        self.paused = False
        if self._after_id:
            try:
                self.app.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        # 停止所有进度条（兼容两种格式）
        for name, bar in self.progress_bars.items():
            try:
                if isinstance(bar, dict):
                    canvas = bar.get("canvas")
                    if canvas:
                        cw = canvas.winfo_width() or 120
                        rect = bar.get("rect")
                        if rect:
                            canvas.coords(rect, 0, 0, 0, 10)
                        txt = bar.get("text")
                        if txt:
                            canvas.itemconfig(txt, text="")
                else:
                    bar.stop()
            except Exception:
                pass

        # 重置主进度条
        if callable(self._main_progress_callback):
            self._main_progress_callback(0, "已停止")

        # 保存进度
        self.engine.save()
        elapsed = time.time() - self.start_time if self.start_time else 0
        self._auto_log(
            f"══════════ 自动化停止 | 循环: {self.loop_count} | "
            f"战斗: {self.total_battles} | 招募: {self.total_recruits} | "
            f"用时: {elapsed:.0f}秒 ══════════", "auto_stop"
        )

    def pause_resume(self) -> bool:
        """切换暂停/恢复，返回当前是否暂停"""
        self.paused = not self.paused
        for bar in self.progress_bars.values():
            try:
                if isinstance(bar, dict):
                    # 迷你进度条不支持暂停/恢复动画
                    continue
                else:
                    if self.paused:
                        bar.pause()
                    else:
                        bar.resume()
            except Exception:
                pass
        if not self.paused and self._pending_next_stage:
            self._pending_next_stage = False
            self._advance_pipeline()
        return self.paused

    def set_speed(self, multiplier: float):
        """设置动画速度倍率"""
        self._speed_multiplier = max(0.25, min(5.0, multiplier))

    # ==================== 管线推进 ====================
    def _advance_pipeline(self):
        """推进到下一阶段"""
        if not self.running or self.paused:
            if self.paused:
                self._pending_next_stage = True
            return

        # 管线循环：到底自动回到起点头
        if self.stage_index >= len(self.pipeline):
            self.loop_count += 1
            self._auto_log(f"\n─── 第 {self.loop_count} 轮完成，进入下一轮 ───", "auto_loop")
            self.stage_index = 0

        sm_name = self.pipeline[self.stage_index]
        self.current_sm_name = sm_name
        self._last_sm_name = sm_name

        sm = self.state_machines[sm_name]

        self._auto_log(f"▸▸▸ 启动阶段: {sm_name} ▸▸▸")

        # 高亮当前进度条
        self._highlight_bar(sm_name)

        # 重置状态机到初始状态
        sm.reset()

        # 开始执行该阶段的自动流程
        self._execute_stage(sm_name)

    def _highlight_bar(self, sm_name: str):
        """高亮当前阶段的进度条（兼容迷你进度条和完整进度条）"""
        from core.config import C_TEXT_HINT
        for name, bar in self.progress_bars.items():
            try:
                # 兼容两种格式：dict(迷你) / object(完整)
                if isinstance(bar, dict):
                    frame = bar.get("frame")
                    label = bar.get("label")
                    if name == sm_name:
                        if frame:
                            colors = _SM_THEMES_COLORS.get(name)
                            if colors:
                                bar_color, _ = colors
                                frame.configure(bg=bar_color)
                                if label:
                                    label.configure(bg=bar_color, fg="#FFFFFF")
                    else:
                        if frame:
                            frame.configure(bg="#D4C5A9")
                        if label:
                            label.configure(bg="#D4C5A9", fg=C_TEXT_HINT)
                else:
                    # 完整 CanvasProgressBar 对象
                    if name == sm_name:
                        try:
                            bar.container.configure(highlightbackground="#2A9D8F",
                                                    highlightthickness=2)
                        except Exception:
                            pass
                    else:
                        try:
                            bar.container.configure(highlightbackground="#E0D5C0",
                                                    highlightthickness=0)
                        except Exception:
                            pass
            except Exception:
                pass

    # ==================== 阶段执行 ====================
    def _execute_stage(self, sm_name: str):
        """执行一个阶段的自动化流程"""
        sm = self.state_machines[sm_name]
        bar = self.progress_bars.get(sm_name)

        if sm.is_finished:
            self._finish_stage()
            return

        state_id = sm.current_state_id
        self._auto_log(f"  [{sm_name}] 当前状态: {state_id}")

        # 更新迷你进度条（如果有）
        self._update_mini_bar(sm_name, 0)

        # 动画延迟（受速度倍率影响）
        animation_delay = max(3, int(15 / self._speed_multiplier)) if not self.paused else 50

        # 使用主进度条动画回调（如果 UI 层提供了）
        if callable(self._main_progress_callback):
            self._main_progress_callback(0, f"[{SM_SHORT_LABELS.get(sm_name, sm_name)}] {sm.current_content}")

        def _on_anim_complete():
            self._on_stage_step_complete(sm_name)

        # 播放进度条动画
        if bar is not None:
            try:
                if isinstance(bar, dict):
                    # 迷你进度条：用 after 模拟动画
                    self._animate_mini_bar(sm_name, animation_delay, _on_anim_complete)
                else:
                    # 完整 CanvasProgressBar
                    bar.animate(
                        step=2, delay=animation_delay,
                        on_complete=_on_anim_complete,
                        easing="ease_in_out"
                    )
                return
            except Exception:
                pass

        # 无进度条时直接执行
        self.app.root.after(300, lambda: _on_anim_complete())

    def _animate_mini_bar(self, sm_name: str, delay: int, on_complete: Callable):
        """为迷你进度条模拟动画效果"""
        steps = 0
        total_steps = 50

        def _step():
            nonlocal steps
            if not self.running or self.paused:
                if self.paused:
                    self._pending_next_stage = True
                return
            if steps < total_steps:
                steps += 2
                pct = int(steps / total_steps * 100)
                self._update_mini_bar(sm_name, pct)
                if callable(self._main_progress_callback):
                    sm_info = self.state_machines.get(sm_name)
                    content = sm_info.current_content if sm_info else ""
                    self._main_progress_callback(pct, content)
                self.app.root.after(delay, _step)
            else:
                on_complete()

        _step()

    def _update_mini_bar(self, sm_name: str, pct: int):
        """更新迷你进度条的显示值"""
        bar = self.progress_bars.get(sm_name)
        if not bar or not isinstance(bar, dict):
            return
        canvas = bar.get("canvas")
        rect = bar.get("rect")
        txt = bar.get("text")
        if not canvas or not rect:
            return
        cw = canvas.winfo_width() or 120
        fill_w = max(0, min(cw, int(cw * pct / 100)))
        canvas.coords(rect, 0, 0, fill_w, 10)
        if txt:
            canvas.itemconfig(txt, text=f"{pct}%" if pct > 0 else "")
        # 同时调用 app 层的迷你进度更新方法（用于高亮等）
        if hasattr(self.app, '_set_mini_progress'):
            self.app._set_mini_progress(sm_name, pct)

    def _on_stage_step_complete(self, sm_name: str):
        """进度条动画完成 → 执行游戏操作 → 状态转移 → 继续"""
        if not self.running:
            return
        if self.paused:
            self._pending_next_stage = True
            return

        sm = self.state_machines[sm_name]
        bar = self.progress_bars.get(sm_name)

        # 1. 执行当前状态对应的游戏操作
        self._do_game_action(sm_name, sm.current_state_id)

        # 2. 确定下一个事件并触发状态转移
        next_event = self._decide_next_event(sm_name, sm.current_state_id)

        if next_event:
            sm.trigger(next_event)
            if bar:
                if not isinstance(bar, dict):
                    bar.set_status(f"{sm_name}: {sm.current_content}")
            self._auto_log(f"  [{sm_name}] {sm.current_state_id} → ({next_event})")

            # 3. 继续下一个状态
            self.app.root.after(200, lambda: self._execute_stage(sm_name))
        else:
            # 无可用事件 → 阶段结束
            self._finish_stage()

    def _finish_stage(self):
        """当前阶段结束，线性推进到下一阶段"""
        sm_name = self.current_sm_name
        bar = self.progress_bars.get(sm_name)

        # 标记完成
        if isinstance(bar, dict):
            self._update_mini_bar(sm_name, 100)
            if hasattr(self.app, '_set_mini_progress'):
                self.app._set_mini_progress(sm_name, 100)
        else:
            try:
                bar.set_status(f"{sm_name}: ✓ 完成")
                bar.set_progress(100)
                bar.stop()
            except Exception:
                pass

        if callable(self._main_progress_callback):
            self._main_progress_callback(100, f"✓ {SM_SHORT_LABELS.get(sm_name, sm_name)} 阶段完成")

        self._auto_log(f"  ✓ {sm_name} 阶段完成")
        self.engine.save()

        # 线性推进：总是 +1，到末尾自动回卷
        self.stage_index += 1

        delay = 500
        self._after_id = self.app.root.after(delay, self._advance_pipeline)

    # ==================== 事件决策 ====================
    def _decide_next_event(self, sm_name: str, state_id: str) -> Optional[str]:
        """根据当前游戏状态决定下一个事件"""
        sm = self.state_machines[sm_name]
        events = sm.available_events
        if not events:
            return None

        # ---- SM_Recruit ----
        if sm_name == "SM_Recruit":
            if state_id == "checking_slots":
                return "slots_available" if len(self.engine.party) < self.global_cfg["party_size"] else "slots_full"
            if state_id == "recruiting":
                return "recruit_done"

        # ---- SM_Shop ----
        elif sm_name == "SM_Shop":
            if state_id == "checking_market":
                return "market_ok"
            if state_id == "buying_gear":
                return "gear_done"
            if state_id == "buying_consumables":
                return "consumables_done"

        # ---- SM_Warehouse ----
        elif sm_name == "SM_Warehouse":
            if state_id == "checking_inventory":
                cap = self.global_cfg.get("inventory_cap", 20)
                if len(self.engine.inventory) >= cap:
                    return "inventory_full"
                return "has_items" if len(self.engine.inventory) > 0 else "empty"
            if state_id == "auto_equipping":
                return "equip_done"
            if state_id == "selling_junk":
                return "sell_done"
            if state_id == "selling_all":
                return "all_sold"

        # ---- SM_Explore（已合并战斗）----
        elif sm_name == "SM_Explore":
            if state_id == "selecting_dungeon":
                return "dungeon_selected"
            if state_id == "entering":
                return "entered"
            if state_id == "on_floor":
                return random.choice(["floor_event", "floor_battle", "floor_complete"])
            if state_id == "handling_event":
                return "event_done"
            if state_id == "fighting":
                return self._battle_result
            if state_id == "looting":
                return "loot_done"
            if state_id == "retreating":
                return "retreat_done"
            if state_id == "floor_decision":
                return self._decide_explore_continue()
            if state_id == "camping":
                return "camp_done"

        # ---- SM_Rest ----
        elif sm_name == "SM_Rest":
            if state_id == "checking_health":
                return "need_rest" if self._needs_rest() else "healthy"
            if state_id == "resting":
                return "rest_done"

        # 默认返回第一个可用事件
        return events[0] if events else None

    # ==================== 游戏操作执行 ====================
    def _do_game_action(self, sm_name: str, state_id: str):
        """根据当前状态执行实际游戏操作"""
        # ---- SM_Recruit ----
        if sm_name == "SM_Recruit":
            if state_id == "recruiting":
                self._auto_recruit()

        # ---- SM_Shop ----
        elif sm_name == "SM_Shop":
            if state_id == "checking_market":
                self.engine.refresh_market()
                self._auto_log(f"  市场波动: {self.engine.get_market_status()}")
                self._auto_log(f"  波动系数: {self.engine.market_multiplier:.2f}")
            elif state_id == "buying_gear":
                self._auto_buy_equipment()
            elif state_id == "buying_consumables":
                self._auto_buy_consumables()

        # ---- SM_Warehouse ----
        elif sm_name == "SM_Warehouse":
            if state_id == "auto_equipping":
                self._auto_equip_all()
            elif state_id == "selling_junk":
                self._auto_sell_junk()
            elif state_id == "selling_all":
                self._auto_sell_all()

        # ---- SM_Explore（已合并战斗）----
        elif sm_name == "SM_Explore":
            if state_id == "selecting_dungeon":
                self._auto_select_dungeon()
            elif state_id == "entering":
                self._auto_enter_dungeon()
            elif state_id == "handling_event":
                self._handle_explore_event()
            elif state_id == "fighting":
                self._auto_battle()
            elif state_id == "looting":
                self._auto_log(f"  📦 打扫战场中……")
            elif state_id == "retreating":
                self._auto_log(f"  🏃 撤退回城……")
            elif state_id == "camping":
                self._auto_camp()

        # ---- SM_Rest ----
        elif sm_name == "SM_Rest":
            if state_id == "resting":
                self._auto_rest()

        # 刷新 UI
        if hasattr(self.app, '_refresh_all'):
            self.app._refresh_all()

    # ==================== 招募 ====================
    def _auto_recruit(self):
        """自动招募一名冒险者"""
        from data.loader import get_loader
        loader = get_loader()

        if len(self.engine.party) >= self.global_cfg["party_size"]:
            return

        # 随机选职业
        jobs = list(loader.jobs.keys())
        if not jobs:
            self._auto_log("  ⚠ 无可用职业！")
            return

        job_key = random.choice(jobs)
        race_key = random.choice(list(loader.races.keys()))
        name = random.choice(ADVENTURER_NAMES)

        # 掷骰偏移（±5%）
        job = loader.jobs[job_key]
        race = loader.races.get(race_key)
        hp_mod = race.hp_mod if race else 0
        atk_mod = race.atk_mod if race else 0
        def_mod = race.def_mod if race else 0
        spd_mod = race.spd_mod if race else 0
        mp_mod = race.mp_mod if race else 0

        rng = lambda base: max(1, int(base * random.uniform(0.95, 1.05)))
        stats = {
            "hp": rng(job.base_hp + hp_mod),
            "mp": rng(50 + mp_mod),
            "atk": rng(job.base_atk + atk_mod),
            "def": rng(job.base_def + def_mod),
            "spd": rng(job.base_spd + spd_mod),
        }

        result = self.engine.recruit(name, job_key, race_key, stat_overrides=stats)
        if result:
            self.total_recruits += 1
            self._auto_log(f"  ✓ 招募 {name} ({race_key} {job_key}) "
                          f"HP:{stats['hp']} ATK:{stats['atk']} "
                          f"DEF:{stats['def']} SPD:{stats['spd']}")
        else:
            self._auto_log(f"  ⚠ 招募 {name} 失败（队伍已满）")

    # ==================== 购物 ====================
    def _auto_buy_equipment(self):
        """自动购买装备"""
        from data.loader import get_loader
        loader = get_loader()

        # 按价格排序装备
        equips = sorted(loader.equipment.values(),
                        key=lambda e: self.engine._item_base_price(e))

        budget = int(self.engine.gold * self.global_cfg.get("auto_buy_budget_pct", 0.6))
        bought = 0
        spent = 0

        for eq in equips:
            price = self.engine.get_buy_price(eq)
            if spent + price > budget:
                continue
            if self.engine.gold < price:
                break
            self.engine.gold -= price
            self.engine.inventory.append(eq.name)
            spent += price
            bought += 1

        if bought:
            self._auto_log(f"  ✓ 购买了 {bought} 件装备，花费 {spent}G")
        else:
            self._auto_log(f"  - 预算不足或无需购买装备")

    def _auto_buy_consumables(self):
        """自动购买消耗品"""
        from data.loader import get_loader
        loader = get_loader()

        budget = max(5, int(self.engine.gold * 0.15))
        # 优先买治疗药水
        priorities = ["治疗药水", "魔力药水", "力量药剂", "强效治疗药水"]

        bought = 0
        spent = 0
        for name in priorities:
            item = loader.consumables.get(name)
            if not item:
                continue
            price = self.engine.get_buy_price(item)
            if spent + price > budget:
                continue
            qty = min(3, max(1, (budget - spent) // price))
            if qty <= 0:
                continue
            cost = price * qty
            if self.engine.gold < cost:
                continue
            self.engine.gold -= cost
            self.engine.add_consumable(name, qty)
            spent += cost
            bought += qty

        if bought:
            self._auto_log(f"  ✓ 购买了 {bought} 个消耗品，花费 {spent}G")

    def _auto_equip_all(self):
        """自动为所有角色装备最优装备"""
        from data.loader import get_loader
        loader = get_loader()

        equipped = 0
        for idx, a in enumerate(self.engine.party):
            for slot in ["weapon", "armor", "accessory", "shield"]:
                # 找背包中该槽位最好的装备
                best = None
                best_score = 0
                for eq_name in self.engine.inventory[:]:
                    eq = loader.equipment.get(eq_name)
                    if not eq or eq.slot != slot:
                        continue
                    # 简单评分
                    score = (getattr(eq, 'atk_bonus', 0) * 2 +
                             getattr(eq, 'def_bonus', 0) +
                             getattr(eq, 'spd_bonus', 0) +
                             getattr(eq, 'hp_bonus', 0) // 5)
                    if score > best_score:
                        best_score = score
                        best = eq_name

                if best and self.engine.equip(idx, best):
                    equipped += 1

        if equipped:
            self._auto_log(f"  ✓ 为队伍装备了 {equipped} 件物品")

    # ==================== 探索 ====================
    def _auto_select_dungeon(self):
        """自动选择合适的 dungeon"""
        # 如果已在探索中（从战斗返回），不要重置进度
        if self.engine.exploring and self.engine.current_dungeon:
            self._auto_log(f"  → 继续探险: {self.engine.current_dungeon.name} 第{self.engine.current_floor}层")
            return

        from data.loader import get_loader
        loader = get_loader()

        unlocked = loader.dungeons[:self.engine.unlocked_dungeons]
        if not unlocked:
            self._auto_log("  ⚠ 无可用地下城！")
            return

        # 选择最高解锁的地下城
        dungeon = unlocked[-1]
        self._auto_log(f"  ✓ 选择地下城: {dungeon.name} (难度:{dungeon.difficulty})")

        self.engine.current_dungeon = dungeon
        self.engine.current_floor = 1

    def _auto_enter_dungeon(self):
        """进入地下城"""
        # 已在地下城中，不需要重新进入
        if self.engine.exploring:
            return

        if self.engine.current_dungeon:
            dungeon = self.engine.current_dungeon
            self.engine.exploring = True
            self.engine.between_floors = False
            self.engine.battle_log = []
            self.engine.clear_floor_buffs()
            self._auto_log(f"  ▸ 踏入{dungeon.name}，开始探险！共 {dungeon.floors} 层")
            self._auto_log(f"  👥 队伍: {' · '.join(a.name for a in self.engine.party if a.is_alive())}")

    def _auto_camp(self):
        """扎营休整"""
        healed_count = 0
        for a in self.engine.party:
            if a.is_alive():
                heal_hp = int(self.engine._full_hp(a) * 0.2)
                heal_mp = int(a.max_mp * 0.15)
                a.hp = min(self.engine._full_hp(a), a.hp + heal_hp)
                a.mp = min(a.max_mp, a.mp + heal_mp)
                healed_count += 1
        self._auto_log(f"  🏕 扎营休整，{healed_count}人恢复了部分体力")

    def _handle_explore_event(self):
        """处理探索随机事件：触发 → 自动决策 → 应用效果"""
        result = self.engine.trigger_event()
        if result is None:
            self._auto_log("  - 风平浪静，无事发生")
            return
        event, desc = result
        self._auto_log(f"  📋 [{event.event_type}] {desc}")
        # 自动随机选一个选项
        if event.choices:
            choice = random.choice(event.choices)
            idx = event.choices.index(choice)
            choice_text = choice.get("text", "未知选项")
            self._auto_log(f"  → 自动选择: {choice_text}")
            msg = self.engine.resolve_event(event, idx)
            self._auto_log(f"  → {msg}")
        else:
            self._auto_log("  - 事件无选项")

    def _decide_explore_continue(self) -> str:
        """楼层间决策：楼层推进 + 通关检查 + 健康评估"""
        from data.loader import get_loader
        loader = get_loader()

        if self.engine.current_dungeon is None:
            return "retreat"

        dungeon = self.engine.current_dungeon
        total = dungeon.floors

        # 统一楼层推进（战斗/事件/空地都用这个计数）
        self.engine.current_floor += 1

        # 通关检查：楼层数超过总层 → 地下城已打通
        if self.engine.current_floor > total:
            for ii, d in enumerate(loader.dungeons):
                if d.name == dungeon.name and ii + 1 < len(loader.dungeons):
                    self.engine.unlocked_dungeons = max(
                        self.engine.unlocked_dungeons, ii + 2)
                    self._auto_log(f"  🏆 通关！解锁新地下城: {loader.dungeons[ii + 1].name}")
                    break
            self.engine.exploring = False
            self.engine.current_dungeon = None
            self._auto_log(f"  🎉 {dungeon.name} 探索完成！")
            return "retreat"

        self._auto_log(f"  → 第 {self.engine.current_floor}/{total} 层")

        # 检查队伍 HP
        alive = [a for a in self.engine.party if a.is_alive()]
        if not alive:
            return "retreat"

        hp_pcts = [self.engine.hp_pct(a) for a in alive]
        avg_hp = sum(hp_pcts) / len(hp_pcts)

        if avg_hp < 0.15:
            return "retreat"

        if avg_hp < 0.25:
            return "rest"

        # 80% 继续，20% 扎营
        if random.random() < 0.2:
            return "rest"

        return "continue"

    # ==================== 战斗 ====================
    _battle_result: str = "victory"

    @staticmethod
    def _spawn_monster(dungeon, is_boss: bool):
        """复用 wilderness_tab 的怪物生成逻辑"""
        from data.loader import get_loader
        from core.models import Dungeon
        loader = get_loader()
        name = dungeon.boss_name if is_boss else random.choice(dungeon.monster_names)
        base = loader.monsters.get(name)
        if base is None:
            base = loader.monsters.get("史莱姆")
        scale = 1.0 + dungeon.difficulty * 0.3
        return base.copy_scaled(scale, dungeon.gold_mult, dungeon.exp_mult)

    def _auto_battle(self):
        """执行自动战斗"""
        from core.battle import BattleSystem
        from data.loader import get_loader
        loader = get_loader()

        if not self.engine.party or not self.engine.current_dungeon:
            self._battle_result = "defeat"
            return

        dungeon = self.engine.current_dungeon
        floor = self.engine.current_floor

        # 选择怪物
        is_boss = (floor >= dungeon.floors)
        monster = self._spawn_monster(dungeon, is_boss)

        if monster is None:
            self._battle_result = "victory"
            self._auto_log(f"  - 第 {floor} 层无敌人")
            return

        if is_boss:
            self._auto_log(f"  ⚔ BOSS 战！{monster.name}")
        else:
            self._auto_log(f"  ⚔ 遭遇 {monster.name} (HP:{monster.hp} ATK:{monster.atk})")

        # 执行战斗
        victory, battle_log, gold_earned, exp_earned = BattleSystem.run(
            self.engine.party, monster, self.engine.floor_buffs
        )
        self.total_battles += 1

        if victory:
            self.engine.gold += gold_earned
            self.engine.total_monsters_killed += 1

            # 经验分配与升级
            lvl_msgs = self.engine.grant_exp(exp_earned)

            # 战利品掉落
            loot_msgs = []
            if random.random() < 0.2 and loader.equipment:
                eq_name = random.choice(list(loader.equipment.keys()))
                self.engine.inventory.append(eq_name)
                self.engine.total_treasures_found += 1
                loot_msgs.append(f"📦 掉落装备 [{eq_name}]")
            if random.random() < 0.15 and loader.consumables:
                item_name = random.choice(list(loader.consumables.keys()))
                self.engine.add_consumable(item_name)
                loot_msgs.append(f"🧪 掉落消耗品 [{item_name}]")

            self.engine.clear_floor_buffs()
            self._battle_result = "victory"

            self._auto_log(f"  ✓ 战斗胜利！获得 {gold_earned}G, {exp_earned}EXP")
            for msg in lvl_msgs:
                self._auto_log(f"  {msg}")
            for msg in loot_msgs:
                self._auto_log(f"  {msg}")
        else:
            self._auto_log(f"  ✗ 战斗失败……")
            self._battle_result = "defeat"
            self.engine.exploring = False
            self.engine.current_dungeon = None
            self.engine.clear_floor_buffs()

            if all(not a.is_alive() for a in self.engine.party):
                self._auto_log(f"  💀 全队阵亡！")

    def _auto_loot(self):
        """战利品已在 _auto_battle 中处理，这里做额外操作"""
        pass

    # ==================== 休息 ====================
    def _needs_rest(self) -> bool:
        """判断是否需要休息"""
        threshold = self.global_cfg.get("rest_threshold_hp_pct", 0.3)
        for a in self.engine.party:
            if a.dead:
                return True
            if self.engine.hp_pct(a) < threshold:
                return True
            if a.mp < a.max_mp * 0.3:
                return True
        return False

    def _auto_rest(self):
        """自动在旅店休息"""
        if self.engine.gold < 20:
            self._auto_log(f"  ⚠ 金币不足，无法休息（需要20G，当前{self.engine.gold}G）")
            return

        result = self.engine.inn_rest()
        if result:
            self._auto_log(f"  🏨 旅店休息完成（花费20G），全员恢复！")

    # ==================== 仓库管理 ====================
    def _auto_sell_junk(self):
        """出售背包中的低品质装备回收金币"""
        from data.loader import get_loader
        loader = get_loader()
        sold = 0
        earned = 0
        for eq_name in self.engine.inventory[:]:
            eq = loader.equipment.get(eq_name)
            if eq is None:
                continue
            # 卖出价值低于 20G 的装备（保留好装备）
            price = self.engine.get_sell_price(eq)
            if price < 20:
                self.engine.inventory.remove(eq_name)
                self.engine.gold += price
                sold += 1
                earned += price
                if sold >= 10:
                    break
        if sold:
            self._auto_log(f"  ♻ 出售 {sold} 件低品质装备，获得 {earned}G")

    def _auto_sell_all(self):
        """背包达到上限 → 全部卖出（不区分品质）"""
        from data.loader import get_loader
        loader = get_loader()
        total = len(self.engine.inventory)
        earned = 0
        for eq_name in self.engine.inventory[:]:
            eq = loader.equipment.get(eq_name)
            price = self.engine.get_sell_price(eq) if eq else 1
            earned += price
        self.engine.gold += earned
        self.engine.inventory.clear()
        self._auto_log(f"  🧹 背包已达上限，全量清仓卖出 {total} 件物品，获得 {earned}G")

    # ==================== 状态查询 ====================
    def get_pipeline_status(self) -> list:
        """返回管线各阶段状态"""
        result = []
        for i, name in enumerate(self.pipeline):
            sm = self.state_machines.get(name)
            result.append({
                "name": name,
                "index": i,
                "is_current": (i == self.stage_index % len(self.pipeline)),
                "state": sm.current_state_id if sm else "unknown",
                "content": sm.current_content if sm else "",
                "is_finished": sm.is_finished if sm else False,
            })
        return result

    def get_stats(self) -> dict:
        return {
            "loop_count": self.loop_count,
            "total_battles": self.total_battles,
            "total_recruits": self.total_recruits,
            "elapsed": int(time.time() - self.start_time) if self.start_time else 0,
            "gold": self.engine.gold,
            "party_size": len(self.engine.party),
        }
