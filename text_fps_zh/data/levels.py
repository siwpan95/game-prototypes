"""Level data definitions and loader."""
from models.level import Level
from models.room import Room
from data.enemies import create_enemy
from data.items import (
    create_medkit, create_grenade, create_ammo,
    create_armor, create_weapon_mod_item,
)


def _level_1() -> Level:
    """Level 1: Warehouse — 4 rooms, easy enemies."""

    # --- Entrance ---
    entrance = Room(
        room_id="entrance",
        name="仓库入口",
        description=(
            "你站在一扇锈迹斑斑的铁门前，门轴已经松脱。"
            "空气中弥漫着陈旧的机油味和潮湿的水泥味。墙上褪色的警示标志正在剥落。"
            "里面有什么东西在活动。"
        ),
        exits={"east": "storage"},
        enemies=[
            create_enemy("守卫"),
        ],
        items=[
            create_medkit(25),
        ],
        cover_objects=["水泥柱"],
        destructibles=[],
        traps=[],
    )

    # --- Storage ---
    storage = Room(
        room_id="storage",
        name="储藏室",
        description=(
            "一排排金属货架延伸进黑暗中，上面堆满了落满灰尘的板条箱。"
            "一盏忽明忽暗的灯泡投下长长的影子。地上散落着包装稻草和碎玻璃。"
        ),
        exits={"west": "entrance", "east": "corridor"},
        enemies=[
            create_enemy("守卫"),
            create_enemy("守卫"),
        ],
        items=[
            create_ammo("pistol", 15),
        ],
        cover_objects=["金属货架", "堆叠的板条箱"],
        destructibles=["桶"],
        traps=[],
    )

    # --- Corridor ---
    corridor = Room(
        room_id="corridor",
        name="黑暗走廊",
        description=(
            "一条狭窄的走廊，头顶裸露的管道不断滴下冷凝水。"
            "应急灯投射出病态的红光。灰尘中的脚印暗示着最近有人经过。"
        ),
        exits={"west": "storage", "east": "office"},
        enemies=[
            create_enemy("士兵"),
        ],
        items=[
            create_armor(25),
        ],
        cover_objects=["管道接头", "翻倒的柜子"],
        destructibles=[],
        traps=[{"name": "绊线", "damage": 10, "triggered": False}],
    )

    # --- Office ---
    office = Room(
        room_id="office",
        name="工头办公室",
        description=(
            "一间狭小的办公室，破碎的桌面上散落着纸张。"
            "一台死机的显示器闪烁着静电。远处的墙上有一扇弹痕累累的窗户，"
            "俯瞰着仓库大厅。"
        ),
        exits={"west": "corridor"},
        enemies=[
            create_enemy("士兵"),
        ],
        items=[
            create_medkit(25),
            create_ammo("pistol", 15),
            create_weapon_mod_item("消音器"),
        ],
        cover_objects=["钢制办公桌", "文件柜"],
        destructibles=["电脑显示器"],
        traps=[],
    )

    return Level(
        level_id=1,
        name="仓库",
        rooms={
            "entrance": entrance,
            "storage": storage,
            "corridor": corridor,
            "office": office,
        },
        start_room="entrance",
        boss_room=None,
    )


def _level_2() -> Level:
    """Level 2: Military Base — 5 rooms, medium enemies, boss."""

    # --- Gate ---
    gate = Room(
        room_id="gate",
        name="正门",
        description=(
            "铁丝网大门敞开着，铰链已经锈蚀脱落。沙袋沿着围墙堆放，"
            "远处矗立着一座岗哨塔。地上散落着弹壳，在光线下闪闪发光。"
        ),
        exits={"north": "barracks"},
        enemies=[
            create_enemy("守卫"),
        ],
        items=[
            create_medkit(25),
            create_medkit(25),
            create_ammo("pistol", 15),
            create_ammo("rifle", 30),
        ],
        cover_objects=["沙袋", "岗哨"],
        destructibles=["燃料桶"],
        traps=[],
    )

    # --- Barracks ---
    barracks = Room(
        room_id="barracks",
        name="营房",
        description=(
            "双层床紧密排列着，床垫被撕裂和弄脏。每张床脚放着储物箱，"
            "有些被撬开了。墙上的布告栏展示着褪色的部署时间表。"
        ),
        exits={"south": "gate", "east": "armory", "north": "control_room"},
        enemies=[
            create_enemy("士兵"),
            create_enemy("士兵"),
        ],
        items=[
            create_ammo("pistol", 15),
            create_grenade(30),
        ],
        cover_objects=["双层床", "储物箱"],
        destructibles=[],
        traps=[],
    )

    # --- Armory ---
    armory = Room(
        room_id="armory",
        name="军械库",
        description=(
            "武器架排列在墙边，大部分已经被清空。少数步枪还夹在固定器中。"
            "保险柜的钢门被炸开了。弹药箱靠在远处的墙边堆放着。"
        ),
        exits={"west": "barracks"},
        enemies=[
            create_enemy("重装兵"),
        ],
        items=[
            create_ammo("shotgun", 8),
            create_ammo("rifle", 30),
            create_medkit(50),
            create_weapon_mod_item("扩容弹匣"),
        ],
        cover_objects=["武器架", "弹药箱"],
        destructibles=["不稳定的货架"],
        traps=[],
    )

    # --- Control Room ---
    control_room = Room(
        room_id="control_room",
        name="控制室",
        description=(
            "一排排显示器占满了整个房间，大部分显示着雪花。中央控制台仍然"
            "亮着战术地图。空调发出巨大的嗡嗡声，掩盖了任何行动的声音。"
        ),
        exits={"south": "barracks", "north": "hangar"},
        enemies=[
            create_enemy("狙击手"),
            create_enemy("士兵"),
        ],
        items=[
            create_medkit(50),
            create_armor(25),
        ],
        cover_objects=["控制台组", "服务器机架"],
        destructibles=[],
        traps=[{"name": "地雷", "damage": 15, "triggered": False}],
    )

    # --- Hangar (Boss) ---
    hangar = Room(
        room_id="hangar",
        name="机库",
        description=(
            "一个巨大的机库，停放着部分拆解的运输机。起重机像骷髅手指一样"
            "悬挂在天花板上。到处都是燃料桶。在远处，一个指挥官般的人物"
            "伫立在混乱之中。"
        ),
        exits={"south": "control_room"},
        enemies=[
            create_enemy("指挥官", loot=[create_weapon_mod_item("红点瞄准镜")]),
            create_enemy("士兵"),
            create_enemy("士兵"),
        ],
        items=[
            create_medkit(50),
            create_ammo("rifle", 30),
        ],
        cover_objects=["飞机机翼", "燃料桶", "起重机基座"],
        destructibles=["燃料桶", "燃料桶"],
        traps=[],
    )

    return Level(
        level_id=2,
        name="军事基地",
        rooms={
            "gate": gate,
            "barracks": barracks,
            "armory": armory,
            "control_room": control_room,
            "hangar": hangar,
        },
        start_room="gate",
        boss_room="hangar",
    )


def _level_3() -> Level:
    """Level 3: Underground Lab — 6 rooms, hard enemies, boss."""

    # --- Elevator ---
    elevator = Room(
        room_id="elevator",
        name="电梯井",
        description=(
            "电梯呻吟着向地下深处降落。昏暗的应急灯带沿着井壁排列。"
            "数字显示屏倒数着楼层：B3...B4...B5。每下降一米，空气就变得更冷。"
        ),
        exits={"south": "lab_entrance"},
        enemies=[
            create_enemy("守卫"),
        ],
        items=[
            create_medkit(25),
            create_medkit(25),
            create_ammo("pistol", 15),
        ],
        cover_objects=["电梯框架"],
        destructibles=[],
        traps=[],
    )

    # --- Lab Entrance ---
    lab_entrance = Room(
        room_id="lab_entrance",
        name="实验室入口",
        description=(
            "一间消杀通道，玻璃面板已经破裂。警示灯闪烁着琥珀色的光。"
            "消毒剂的气味与某种刺鼻的味道混合在一起。墙上的生物扫描仪已经"
            "暗灭损坏。"
        ),
        exits={"north": "elevator", "east": "research_wing", "west": "server_room"},
        enemies=[
            create_enemy("士兵"),
            create_enemy("重装兵"),
        ],
        items=[
            create_armor(25),
            create_ammo("pistol", 15),
        ],
        cover_objects=["消杀间", "补给车"],
        destructibles=[],
        traps=[{"name": "激光网", "damage": 12, "triggered": False}],
    )

    # --- Research Wing ---
    research_wing = Room(
        room_id="research_wing",
        name="研究翼",
        description=(
            "走廊两侧是玻璃墙的实验室。里面，未知化学品的气泡容器投射出诡异的"
            "绿色光芒。笔记和数据板散落在工作台上。某个收容间的内侧有抓痕。"
        ),
        exits={"west": "lab_entrance", "south": "containment"},
        enemies=[
            create_enemy("狙击手"),
            create_enemy("士兵"),
            create_enemy("士兵"),
        ],
        items=[
            create_medkit(50),
            create_weapon_mod_item("红点瞄准镜"),
        ],
        cover_objects=["实验台", "化学品桶"],
        destructibles=["玻璃隔断"],
        traps=[],
    )

    # --- Containment ---
    containment = Room(
        room_id="containment",
        name="收容区",
        description=(
            "厚重的防爆门敞开着，锁定机构已被摧毁。一排排收容间排列在墙边，"
            "大部分空空如也。门内侧布满了深深的抓痕。一股冷风从更深处吹来。"
        ),
        exits={"north": "research_wing", "south": "core"},
        enemies=[
            create_enemy("重装兵"),
            create_enemy("重装兵"),
        ],
        items=[
            create_grenade(30),
            create_ammo("shotgun", 8),
        ],
        cover_objects=["防爆门", "收容间"],
        destructibles=["不稳定的墙壁"],
        traps=[
            {"name": "地雷", "damage": 20, "triggered": False},
            {"name": "绊线", "damage": 10, "triggered": False},
        ],
    )

    # --- Server Room ---
    server_room = Room(
        room_id="server_room",
        name="服务器室",
        description=(
            "一排排服务器机架嗡嗡作响，闪烁着琥珀色和绿色的灯光。尽管冷却系统"
            "超负荷运转，热量仍然令人窒息。电缆像树根一样蜿蜒在地板上。"
            "一台终端显示着你无法识别的语言数据。"
        ),
        exits={"east": "lab_entrance"},
        enemies=[
            create_enemy("狙击手"),
            create_enemy("士兵"),
        ],
        items=[
            create_medkit(25),
            create_armor(25),
            create_weapon_mod_item("消音器"),
        ],
        cover_objects=["服务器机架", "冷却装置"],
        destructibles=["过热的服务器"],
        traps=[],
    )

    # --- Core (Boss) ---
    core = Room(
        room_id="core",
        name="实验室核心",
        description=(
            "地下设施的心脏。一个巨大的圆柱形空间，四周环绕着走道和监控站。"
            "中央有什么东西在微弱的生物荧光中脉动。这次行动的指挥官正在等待，"
            "身旁是精锐护卫。"
        ),
        exits={"north": "containment"},
        enemies=[
            create_enemy("指挥官", loot=[
                create_weapon_mod_item("扩容弹匣"),
                create_medkit(50),
            ]),
            create_enemy("士兵"),
            create_enemy("士兵"),
            create_enemy("重装兵"),
        ],
        items=[
            create_medkit(50),
            create_ammo("rifle", 30),
            create_ammo("shotgun", 8),
        ],
        cover_objects=["走道栏杆", "监控站", "支撑柱"],
        destructibles=["发电机", "燃料罐"],
        traps=[
            {"name": "激光网", "damage": 15, "triggered": False},
        ],
    )

    return Level(
        level_id=3,
        name="地下实验室",
        rooms={
            "elevator": elevator,
            "lab_entrance": lab_entrance,
            "research_wing": research_wing,
            "containment": containment,
            "server_room": server_room,
            "core": core,
        },
        start_room="elevator",
        boss_room="core",
    )


_LEVEL_BUILDERS = {
    1: _level_1,
    2: _level_2,
    3: _level_3,
}


def load_level(level_id: int) -> Level:
    """Load a level by its ID. Returns the Level object."""
    builder = _LEVEL_BUILDERS.get(level_id)
    if builder is None:
        raise ValueError(f"Unknown level ID: {level_id}. Available: {list(_LEVEL_BUILDERS.keys())}")
    return builder()


def get_available_levels() -> list:
    """Return list of available level IDs."""
    return list(_LEVEL_BUILDERS.keys())
