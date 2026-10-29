# -*- coding: utf-8 -*-
"""
游戏导航状态机（Game State Machine）
==================================

把《暗黑破坏神：灾厄纪元》的界面导航建模成一个有限状态机（FSM），
由 zhuangtaiji 的纯标准库状态机引擎驱动。

设计要点
--------
* 状态（states）对应游戏中的各个界面/场景；事件（events）对应导航动作。
* ``GameFSM`` 作为导航控制器：
    - ``goto(event, context)``  触发转移；成功则通过 on_enter 回调渲染新界面
    - ``can_go(event)``         当前状态是否允许该事件（守卫/非法转移拦截）
    - ``available_events``      当前状态可用的导航事件
    - ``current_state``         当前界面状态
    - ``history``               转移轨迹
* 状态机代码来自 ``<zhuangtaiji 仓根>/core``（2026-09-23 去本地化：原
  ``原路径`` 已不存在），按"复制即复用"原则
  内联到本项目 ``statemachine/`` 包，与源项目零耦合、零外部引用。

状态图（单一数据源 ``GAME_FSM_CONFIG``）
---------------------------------------
    preload --load_complete--> main_menu
    main_menu --new_game/continue_game--> hub
    main_menu --open_settings--> settings
    hub --explore--> explore
    hub --open_workshop--> workshop
    hub --open_status--> status
    hub --open_settings--> settings
    hub --return_menu--> main_menu
    explore --select_region--> dungeon
    explore --return_hub--> hub
    dungeon --enter_battle--> combat
    dungeon --escape--> explore
    combat --win--> victory --return_hub--> hub
    combat --lose--> main_menu
    combat --return_hub--> hub
    status --return_hub--> hub
    workshop --start_custom--> custom_combat
    workshop --return_hub--> hub
    custom_combat --custom_win--> custom_victory --return_workshop--> workshop
    custom_combat --custom_lose--> workshop
    custom_combat --return_workshop--> workshop
    custom_combat --return_hub--> hub
    settings --back_to_hub(has_player)--> hub
    settings --back_to_menu--> main_menu
"""
from typing import Any, Dict, List, Optional

from statemachine import GenericStateMachine


# 状态 -> GameGUI 中负责渲染该界面的方法名
SCREEN_MAP: Dict[str, str] = {
    "preload": "show_preload",
    "main_menu": "create_main_menu",
    "hub": "show_main_hub",
    "explore": "show_explore",
    "dungeon": "show_dungeon_view",
    "combat": "show_combat",
    "victory": "show_combat",
    "status": "show_status",
    "workshop": "show_hell_workshop",
    "custom_combat": "show_custom_combat",
    "custom_victory": "show_custom_combat",
    "settings": "show_settings",
}


# 游戏导航状态图（单一数据源）
GAME_FSM_CONFIG: Dict[str, Any] = {
    "state_machines": {
        "game": {
            "initial": "preload",
            "states": {
                "preload": {
                    "transitions": {"load_complete": "main_menu"},
                },
                "main_menu": {
                    "transitions": {
                        "new_game": "hub",
                        "continue_game": "hub",
                        "open_settings": "settings",
                    },
                },
                "hub": {
                    "transitions": {
                        "explore": "explore",
                        "open_workshop": "workshop",
                        "open_status": "status",
                        "open_settings": "settings",
                        "return_menu": "main_menu",
                    },
                },
                "explore": {
                    "transitions": {
                        "select_region": "dungeon",
                        "return_hub": "hub",
                    },
                },
                "dungeon": {
                    "transitions": {
                        "enter_battle": "combat",
                        "escape": "explore",
                    },
                },
                "combat": {
                    "transitions": {
                        "win": "victory",
                        "lose": "main_menu",
                        "return_hub": "hub",
                    },
                },
                "victory": {
                    "transitions": {
                        "return_hub": "hub",
                    },
                },
                "status": {
                    "transitions": {
                        "return_hub": "hub",
                    },
                },
                "workshop": {
                    "transitions": {
                        "start_custom": "custom_combat",
                        "return_hub": "hub",
                    },
                },
                "custom_combat": {
                    "transitions": {
                        "custom_win": "custom_victory",
                        "custom_lose": "workshop",
                        "return_workshop": "workshop",
                        "return_hub": "hub",
                    },
                },
                "custom_victory": {
                    "transitions": {
                        "return_workshop": "workshop",
                    },
                },
                "settings": {
                    "transitions": {
                        # 仅当已有角色时才能返回主城（主菜单打开设置时无角色）
                        "back_to_hub": {"target": "hub", "guard": "has_player"},
                        "back_to_menu": "main_menu",
                    },
                },
            },
        },
    },
}


class GameFSM:
    """游戏导航状态机控制器。"""

    def __init__(self, gui, machine_name: str = "game"):
        self.gui = gui
        # 构造期间不触发界面渲染：初始界面（preload）由 GUI 自行调用 show_preload
        self._ready = False

        self.fsm = GenericStateMachine(
            machine_name,
            GAME_FSM_CONFIG,
            on_action=self._on_action,
            # 实例级守卫：当前是否已有角色
            guards={"has_player": lambda ctx: self.gui.player is not None},
        )
        self._ready = True

    # ---------- 渲染回调 ----------
    def _on_action(self, action_type: str, state_id: str, detail: dict) -> None:
        # 仅在进入新状态时渲染界面；构造初始状态时不渲染
        if not self._ready or action_type != "enter":
            return
        method_name = SCREEN_MAP.get(state_id)
        if method_name and hasattr(self.gui, method_name):
            getattr(self.gui, method_name)()

    # ---------- 对外 API ----------
    def goto(self, event: str, context: Optional[dict] = None):
        """触发导航事件；成功则渲染新界面，返回 (new_state, reason)。"""
        return self.fsm.trigger(event, context or {})

    def can_go(self, event: str) -> bool:
        """当前状态是否允许该导航事件。"""
        return self.fsm.can_trigger(event)

    @property
    def current_state(self) -> str:
        return self.fsm.current_state_id

    @property
    def available_events(self) -> List[str]:
        return self.fsm.available_events

    def get_history(self, limit: int = 20):
        return self.fsm.get_history(limit)

    def get_state_info(self) -> dict:
        return self.fsm.get_state_info()
