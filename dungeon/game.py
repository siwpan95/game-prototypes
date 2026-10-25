# -*- coding: utf-8 -*-
"""游戏主循环 —— 只依赖「世界源 + 规则源 + 表现层」三个接口。

重构的收益在这里体现：**主循环完全不知道地牢是随机格子还是真实房间图**，
也不知道伤害来自 ``randint`` 还是 d20。换源只需要换构造参数。
"""

from __future__ import annotations

from typing import Optional

from .rules import LOOT_TABLE, MONSTER_NAMES, make_rules
from .ui import DIRECTIONS, Printer, describe_room, make_printer, movement_prompt
from .world import ROOM_EMPTY, ROOM_EXIT, ROOM_MONSTER, ROOM_TRAP, ROOM_TREASURE

__all__ = ["Game", "run", "DEFAULT_SIZE"]

DEFAULT_SIZE = 4


class Game:
    def __init__(self, world_source, rules, printer: Optional[Printer] = None,
                 hp: int = 20, attack: int = 5):
        self.world_source = world_source
        self.rules = rules
        self.ui = printer or make_printer()
        self.hp = hp
        self.attack = attack
        self.inventory: list = []
        self.revealed = set()
        self.world = None
        self.result = None      # 'escaped' | 'dead' | 'quit'

    # ------------------------------------------------------------ 主循环 --
    def play(self, seed: Optional[int] = None) -> str:
        self.world = self.world_source.build(seed=seed)
        cur = self.world.start
        self.revealed.add(cur)
        meta = self.world.meta.get("source", "builtin")
        self.ui.say("🏰 你被投入了随机生成的地牢，寻找出口逃出生天！")
        self.ui.say(f"地牢来源: {meta}｜规则: {self.rules.name}｜"
                    f"房间数 {len(self.world.rooms)}｜起点 {cur}")

        while True:
            self.revealed.add(cur)
            self.ui.say("")
            self.ui.say(describe_room(self.world, cur))
            kind = self.world.kind_of(cur)

            if kind == ROOM_EXIT:
                self.ui.say("🎉 你找到了出口！重获自由！")
                self.result = "escaped"
                break

            if not self._handle_room(kind):
                # 房间事件导致死亡
                self.result = "dead"
                break

            self._maybe_use_item()

            nxt = self._choose_move(cur)
            if nxt is None:
                self.ui.say("你放弃了冒险。")
                self.result = "quit"
                break
            cur = nxt

            if self.hp <= 5:
                self.ui.say("⚠️ 你的生命值极低，赶紧找出口！")

        self.ui.say(f"最终生命: {self.hp}，背包: {self.inventory}")
        self.ui.say("=== 冒险结束 ===")
        return self.result

    # ------------------------------------------------------------ 房间 --
    def _handle_room(self, kind: str) -> bool:
        """处理房间事件；返回 False 表示玩家已死亡。"""
        if kind == ROOM_MONSTER:
            return self._fight()
        if kind == ROOM_TREASURE:
            item = self.rules.pick(LOOT_TABLE)
            self.ui.say(f"✨ 你发现了一个宝箱，里面有: {item}")
            self.inventory.append(item)
            self.ui.say(f"背包: {self.inventory}")
        elif kind == ROOM_TRAP:
            dmg = self.rules.trap_damage()
            self.ui.say(f"💥 你触发了陷阱！受到 {dmg} 点伤害。")
            self.hp = max(0, self.hp - dmg)
            if self.hp <= 0:
                self.ui.say("你没能挺过陷阱……游戏结束。")
                return False
        return True

    def _fight(self) -> bool:
        name = self.rules.pick(MONSTER_NAMES)
        self.ui.say(f"⚔️ 一只 {name} 出现了！")
        monster_hp = self.rules.monster_hp()
        while monster_hp > 0 and self.hp > 0:
            action = self.ui.ask("【战斗】攻击(a) 或 防御(d): ").lower()
            defending = action != "a"
            if not defending:
                if self.rules.hits(proficiency=2):
                    dmg = self.rules.player_damage(self.attack)
                    monster_hp -= dmg
                    self.ui.say(f"你造成 {dmg} 点伤害，怪物剩余生命 {monster_hp}")
                else:
                    self.ui.say("你的攻击被闪开了！")
            else:
                self.ui.say("你进行防御，减少了伤害。")
            if monster_hp > 0:
                mdmg = self.rules.monster_damage(defending)
                self.hp -= mdmg
                self.ui.say(f"怪物攻击造成 {mdmg} 点伤害，你的生命 {self.hp}")
        if self.hp <= 0:
            self.ui.say("💀 你被击败了……")
            return False
        self.ui.say(f"你击败了 {name}！")
        if self.rules.drop_chance():
            loot = self.rules.pick(LOOT_TABLE)
            self.ui.say(f"怪物掉落了: {loot}")
            self.inventory.append(loot)
            self.ui.say(f"获得物品: {loot}。背包: {self.inventory}")
        return True

    # ------------------------------------------------------------ 物品 --
    def _maybe_use_item(self) -> None:
        if not self.inventory:
            return
        if self.ui.ask("是否使用物品？(y/n): ").lower() != "y":
            return
        self.ui.say(f"你的物品: {self.inventory}")
        item = self.ui.ask("输入要使用的物品名，或按回车跳过: ")
        if item in self.inventory:
            self._use_item(item)

    def _use_item(self, item: str) -> None:
        if item == "生命药水":
            heal = self.rules.heal_amount()
            self.hp += heal
            self.ui.say(f"喝下药水，恢复 {heal} 生命，当前生命 {self.hp}")
            self.inventory.remove(item)
        elif item == "力量符文":
            self.attack += 2
            self.ui.say(f"使用符文，攻击力永久提升至 {self.attack}")
            self.inventory.remove(item)
        elif item == "破旧护符":
            self.ui.say("护符微微发光，似乎能在危急时刻救你一命。")
            self.inventory.remove(item)

    # ------------------------------------------------------------ 移动 --
    def _choose_move(self, cur):
        """返回下一个房间 id；``None`` 表示玩家退出。"""
        nb = self.world.neighbors_of(cur)
        if not nb:
            return None
        move = self.ui.ask(movement_prompt(self.world, cur))
        if move == "退出":
            return None
        if self.world.grid_mode:
            if move in DIRECTIONS:
                dr, dc = DIRECTIONS[move]
                r, c = self.world.rooms[cur].pos
                target = f"{r+dr},{c+dc}"
                if target in nb:
                    return target
            self.ui.say("这里没有路，请重新选择。")
            return cur
        # 图模式：编号或房间名
        if move.isdigit():
            idx = int(move) - 1
            if 0 <= idx < len(nb):
                return nb[idx]
        if move in nb:
            return move
        for n in nb:
            if self.world.rooms[n].name == move:
                return n
        self.ui.say("这里没有路，请重新选择。")
        return cur


def run(world_source, rules, printer: Optional[Printer] = None,
        seed: Optional[int] = None, hp: int = 20, attack: int = 5) -> str:
    """一行式入口。"""
    return Game(world_source, rules, printer, hp=hp, attack=attack).play(seed=seed)
