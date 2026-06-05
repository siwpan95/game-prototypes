"""
MVVM — ViewModel 层
暴露绑定属性 + 命令方法，View 通过它操作 Model。
ViewModel 注册到 Model 的 notify_fn，收到通知后触发自己的 property_changed 回调。
"""

from typing import Any, Callable, Dict, List, Optional

from .model import GameModel


class PropertyChangedCallback:
    """
    支持多订阅者的属性变更通知。
    View 调用 vm.subscribe("player_state", callback) 来绑定 UI 刷新。
    """
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[], None]]] = {}

    def subscribe(self, property_name: str, handler: Callable[[], None]) -> None:
        self._handlers.setdefault(property_name, []).append(handler)

    def emit(self, property_name: str) -> None:
        for h in self._handlers.get(property_name, []):
            h()


class GameViewModel:
    """
    ViewModel：钝化 Model 数据，暴露给 View 绑定的属性和命令。
    - 属性通过 get_* 方法读取（由 View 主动轮询 / 通知驱动）
    - 命令：cmd_attack(idx), cmd_rest()
    """

    def __init__(self, model: GameModel) -> None:
        self._model: GameModel = model
        self._notifier = PropertyChangedCallback()

        # 将 Model 的 notify_fn 指向自己的 _on_model_changed
        self._model._notify_fn = self._on_model_changed

    # ── Model → ViewModel 通知路由 ────────────────────────

    def _on_model_changed(self, property_name: str) -> None:
        """Model 状态变化，通知所有订阅了该属性的 View 回调"""
        self._notifier.emit(property_name)

    def subscribe(self, property_name: str, handler: Callable[[], None]) -> None:
        """View 调用此方法来绑定 UI 刷新回调"""
        self._notifier.subscribe(property_name, handler)

    # ── 绑定属性（View 通过这些方法读取状态）────────────

    def get_player_state(self) -> Dict[str, Any]:
        return self._model.get_player_state()

    def get_monster_states(self) -> List[Dict[str, Any]]:
        return self._model.get_monster_states()

    def get_log_text(self) -> str:
        return self._model.get_log_text()

    def is_player_dead(self) -> bool:
        return self._model.is_player_dead()

    # ── 命令（View 按钮绑定这些方法）────────────────────

    def cmd_attack(self, idx: int) -> None:
        """攻击第 idx 只怪物（命令）"""
        self._model.attack_monster(idx)

    def cmd_rest(self) -> None:
        """休息命令"""
        self._model.rest()

    def tick(self, dt: float = 1.0) -> None:
        """驱动 Model tick（由 View 的 after 定时器调用）"""
        self._model.tick(dt)

    def cmd_buy_equipment(self, equip: dict) -> bool:
        """商人购买装备"""
        return self._model.buy_equipment(equip)

    def cmd_unequip(self, idx: int) -> bool:
        """卸下装备"""
        return self._model.unequip_item(idx)

    def get_equipped(self) -> list:
        """获取已装备列表"""
        return self._model.get_equipped()

    def get_backpack(self) -> list:
        """获取背包物品列表"""
        return self._model.get_backpack()

    def cmd_move_equip_to_backpack(self, equip_idx: int) -> bool:
        """装备栏 → 背包"""
        return self._model.move_equip_to_backpack(equip_idx)

    def cmd_equip_from_backpack(self, bp_idx: int) -> bool:
        """背包 → 装备栏"""
        return self._model.equip_from_backpack(bp_idx)

    def cmd_swap_equip_from_backpack(self, equip_idx: int, bp_idx: int) -> bool:
        """装备栏 ↔ 背包互换"""
        return self._model.swap_equip_from_backpack(equip_idx, bp_idx)
