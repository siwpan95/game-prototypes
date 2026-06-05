import random
import time

# 房间类型
ROOM_EMPTY = "空地"
ROOM_MONSTER = "怪物"
ROOM_TREASURE = "宝藏"
ROOM_TRAP = "陷阱"
ROOM_EXIT = "出口"

# 慢速打印
def slow_print(text, delay=0.02):
    for ch in text:
        print(ch, end='', flush=True)
        time.sleep(delay)
    print()

# 随机生成地图
def create_map(size=4):
    """生成 size x size 的随机地图，确保有且只有一个出口"""
    room_types = [ROOM_EMPTY, ROOM_MONSTER, ROOM_TREASURE, ROOM_TRAP]
    # 初始化地图，大部分房间随机，出口和玩家出生点固定
    dungeon = [[random.choice(room_types) for _ in range(size)] for _ in range(size)]
    # 随机放置出口（不能是出生点）
    exit_pos = (random.randint(0, size-1), random.randint(0, size-1))
    dungeon[exit_pos[0]][exit_pos[1]] = ROOM_EXIT
    # 出生点设为空地，保证安全
    start_pos = (0, 0)
    dungeon[start_pos[0]][start_pos[1]] = ROOM_EMPTY
    # 如果出口也在(0,0)则重新放置
    while exit_pos == start_pos:
        exit_pos = (random.randint(0, size-1), random.randint(0, size-1))
        dungeon[exit_pos[0]][exit_pos[1]] = ROOM_EXIT
    return dungeon, start_pos, exit_pos

# 显示当前可探索的方向
def show_exits(pos, size):
    r, c = pos
    exits = []
    if r > 0: exits.append("北")
    if r < size - 1: exits.append("南")
    if c > 0: exits.append("西")
    if c < size - 1: exits.append("东")
    return exits

# 怪物战斗
def fight_monster(hp, attack, monster_name):
    slow_print(f"⚔️ 一只 {monster_name} 出现了！")
    monster_hp = random.randint(3, 8)
    while monster_hp > 0 and hp > 0:
        action = input("【战斗】攻击(a) 或 防御(d): ").strip().lower()
        if action == 'a':
            dmg = random.randint(1, attack)
            monster_hp -= dmg
            slow_print(f"你造成 {dmg} 点伤害，怪物剩余生命 {monster_hp}")
        else:
            slow_print("你进行防御，减少了伤害。")
        if monster_hp > 0:
            monster_dmg = max(0, random.randint(2, 5) - (2 if action == 'd' else 0))
            hp -= monster_dmg
            slow_print(f"怪物攻击造成 {monster_dmg} 点伤害，你的生命 {hp}")
    if hp <= 0:
        slow_print("💀 你被击败了……")
        return 0
    slow_print(f"你击败了 {monster_name}！")
    # 随机掉落物品
    if random.random() < 0.5:
        loot = random.choice(["生命药水", "力量符文", "破旧护符"])
        slow_print(f"怪物掉落了: {loot}")
        return hp, loot
    return hp, None

def apply_trap(hp):
    dmg = random.randint(5, 10)
    slow_print(f"💥 你触发了陷阱！受到 {dmg} 点伤害。")
    return max(0, hp - dmg)

def use_item(item, hp, attack, inventory):
    if item == "生命药水":
        heal = random.randint(5, 10)
        hp += heal
        slow_print(f"喝下药水，恢复 {heal} 生命，当前生命 {hp}")
        inventory.remove(item)
    elif item == "力量符文":
        attack += 2
        slow_print(f"使用符文，攻击力永久提升至 {attack}")
        inventory.remove(item)
    elif item == "破旧护符":
        slow_print("护符微微发光，似乎能在危急时刻救你一命。")
        inventory.remove(item)  # 自动消耗型防护（简化）
    return hp, attack

def game():
    size = 4
    dungeon, (r, c), exit_pos = create_map(size)
    hp = 20
    attack = 5
    inventory = []
    revealed = [[False for _ in range(size)] for _ in range(size)]
    revealed[r][c] = True  # 出生点已知

    slow_print("🏰 你被投入了随机生成的地牢，寻找出口逃出生天！")
    slow_print(f"地牢大小: {size}x{size}，你从 ({r},{c}) 出发。")
    
    while True:
        current_room = dungeon[r][c]
        slow_print(f"\n📍 当前房间: ({r},{c}) - 类型: {current_room}")
        revealed[r][c] = True

        if current_room == ROOM_EXIT:
            slow_print("🎉 你找到了出口！重获自由！")
            break

        # 房间事件处理
        if current_room == ROOM_MONSTER:
            result = fight_monster(hp, attack, random.choice(["哥布林", "骷髅兵", "史莱姆"]))
            if result == 0:
                slow_print("游戏结束。")
                return
            else:
                hp, loot = result if len(result) == 2 else (result[0], None)
                if loot:
                    inventory.append(loot)
                    slow_print(f"获得物品: {loot}。背包: {inventory}")
        elif current_room == ROOM_TREASURE:
            treasure = random.choice(["生命药水", "力量符文", "破旧护符"])
            slow_print(f"✨ 你发现了一个宝箱，里面有: {treasure}")
            inventory.append(treasure)
            slow_print(f"背包: {inventory}")
        elif current_room == ROOM_TRAP:
            hp = apply_trap(hp)
            if hp <= 0:
                slow_print("你没能挺过陷阱……游戏结束。")
                return

        # 使用物品
        if inventory:
            use_item_choice = input("是否使用物品？(y/n): ").strip().lower()
            if use_item_choice == 'y':
                print("你的物品:", inventory)
                item_use = input("输入要使用的物品名，或按回车跳过: ").strip()
                if item_use in inventory:
                    hp, attack = use_item(item_use, hp, attack, inventory)

        # 移动
        exits = show_exits((r, c), size)
        move = input(f"可以移动的方向: {exits}\n选择移动方向(或输入'退出'): ").strip().lower()
        if move == '退出':
            slow_print("你放弃了冒险。")
            return
        # 简单映射中文方向到坐标变化
        direction_map = {"北": (-1, 0), "南": (1, 0), "西": (0, -1), "东": (0, 1)}
        if move in direction_map and move in exits:
            dr, dc = direction_map[move]
            r += dr
            c += dc
        else:
            slow_print("这里没有路，请重新选择。")
            continue

        # 生命值过低警告
        if hp <= 5:
            slow_print("⚠️ 你的生命值极低，赶紧找出口！")

    slow_print(f"最终生命: {hp}，背包: {inventory}")
    slow_print("=== 冒险结束 ===")

if __name__ == "__main__":
    game()