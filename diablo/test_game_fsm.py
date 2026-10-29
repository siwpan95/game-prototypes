# -*- coding: utf-8 -*-
"""
无头验证：游戏导航状态机（不依赖 tkinter）

用一个 FakeGUI 记录每次"渲染"调用的方法名，驱动整张状态图，
验证：
  1) 所有合法跳转都能到达正确界面；
  2) 非法跳转被拦截；
  3) 守卫（has_player）在正确时机生效；
  4) 渲染回调确实调用了对应的 GUI 方法。
"""
import sys
from typing import List


class FakeGUI:
    """模拟 GameGUI：记录被调用的渲染方法，不创建任何 tkinter 控件。"""
    def __init__(self):
        self.player = None
        self.rendered: List[str] = []

    def _record(self, name: str):
        self.rendered.append(name)

    def show_preload(self): self._record("show_preload")
    def create_main_menu(self): self._record("create_main_menu")
    def show_main_hub(self): self._record("show_main_hub")
    def show_explore(self): self._record("show_explore")
    def show_dungeon_view(self): self._record("show_dungeon_view")
    def show_combat(self): self._record("show_combat")
    def show_status(self): self._record("show_status")
    def show_hell_workshop(self): self._record("show_hell_workshop")
    def show_custom_combat(self): self._record("show_custom_combat")
    def show_settings(self): self._record("show_settings")


def assert_eq(actual, expected, msg):
    if actual != expected:
        print(f"  ✗ FAIL: {msg} | expected={expected!r} actual={actual!r}")
        sys.exit(1)
    print(f"  ✓ {msg}: {actual!r}")


def main():
    gui = FakeGUI()
    from game_fsm import GameFSM
    fsm = GameFSM(gui)

    print("初始状态")
    assert_eq(fsm.current_state, "preload", "初始状态应为 preload")
    assert_eq(gui.rendered, [], "构造期间不应渲染任何界面")

    # preload -> main_menu (由 GUI 自行调用 show_preload，这里模拟加载完成)
    fsm.goto("load_complete")
    assert_eq(fsm.current_state, "main_menu", "load_complete 后应到 main_menu")
    assert_eq(gui.rendered[-1], "create_main_menu", "main_menu 应渲染 create_main_menu")

    # 非法跳转：main_menu 没有 explore 事件
    bad, reason = fsm.goto("explore")
    assert_eq(bad, None, "main_menu 下 explore 应被拦截")
    print(f"    拦截原因: {reason}")

    # 守卫：无角色时 settings 不能 back_to_hub
    fsm.goto("open_settings")
    assert_eq(fsm.current_state, "settings", "open_settings 后应到 settings")
    bad, reason = fsm.goto("back_to_hub")
    assert_eq(bad, None, "无角色时 back_to_hub 应被守卫拦截")
    print(f"    守卫原因: {reason}")
    fsm.goto("back_to_menu")
    assert_eq(fsm.current_state, "main_menu", "back_to_menu 应回 main_menu")

    # new_game（无 player 也能进 hub？需要 player；用假 player 模拟创建角色）
    gui.player = object()  # 模拟已创建角色
    fsm.goto("new_game")
    assert_eq(fsm.current_state, "hub", "new_game 后应到 hub")

    # hub -> explore -> dungeon -> combat
    fsm.goto("explore")
    assert_eq(fsm.current_state, "explore", "explore")
    fsm.goto("select_region")
    assert_eq(fsm.current_state, "dungeon", "select_region 后应到 dungeon")
    assert_eq(gui.rendered[-1], "show_dungeon_view", "dungeon 应渲染 show_dungeon_view")
    fsm.goto("enter_battle")
    assert_eq(fsm.current_state, "combat", "enter_battle 后应到 combat")
    assert_eq(gui.rendered[-1], "show_combat", "combat 应渲染 show_combat")

    # 战斗中非法返回 workshop
    bad, _ = fsm.goto("return_workshop")
    assert_eq(bad, None, "combat 下 return_workshop 应被拦截")

    # combat -> win -> victory -> return_hub -> hub
    fsm.goto("win")
    assert_eq(fsm.current_state, "victory", "win 后应到 victory")
    assert_eq(gui.rendered[-1], "show_combat", "victory 复用 combat 界面")
    fsm.goto("return_hub")
    assert_eq(fsm.current_state, "hub", "victory 后 return_hub 应回 hub")

    # hub -> workshop -> custom_combat -> custom_win -> custom_victory -> return_workshop
    fsm.goto("open_workshop")
    assert_eq(fsm.current_state, "workshop", "open_workshop")
    fsm.goto("start_custom")
    assert_eq(fsm.current_state, "custom_combat", "start_custom 后应到 custom_combat")
    assert_eq(gui.rendered[-1], "show_custom_combat", "custom_combat 应渲染 show_custom_combat")
    fsm.goto("custom_win")
    assert_eq(fsm.current_state, "custom_victory", "custom_win 后应到 custom_victory")
    assert_eq(gui.rendered[-1], "show_custom_combat", "custom_victory 复用 custom_combat 界面")
    fsm.goto("return_workshop")
    assert_eq(fsm.current_state, "workshop", "custom_victory 后 return_workshop 应回 workshop")

    # custom_combat -> custom_lose -> workshop
    fsm.goto("start_custom")
    fsm.goto("custom_lose")
    assert_eq(fsm.current_state, "workshop", "custom_lose 应直接回 workshop")
    assert_eq(gui.rendered[-1], "show_hell_workshop", "custom_lose 应渲染 workshop")

    # 有角色时 settings -> back_to_hub（先回到 hub 才能打开设置）
    fsm.goto("return_hub")          # workshop -> hub
    fsm.goto("open_settings")       # hub -> settings
    fsm.goto("back_to_hub")
    assert_eq(fsm.current_state, "hub", "有角色时 back_to_hub 应回 hub")

    # combat -> lose -> main_menu（从 hub 进 combat 再 lose）
    fsm.goto("explore"); fsm.goto("select_region"); fsm.goto("enter_battle")
    fsm.goto("lose")
    assert_eq(fsm.current_state, "main_menu", "lose 应直接回 main_menu")

    # 状态历史非空
    hist = fsm.get_history(limit=5)
    assert_eq(len(hist) > 0, True, "应记录转移历史")
    print(f"    最近历史: {[h['from']+'->'+h['to'] for h in hist]}")

    print("\n全部通过 ✅ 状态机导航逻辑正确。")


if __name__ == "__main__":
    main()
