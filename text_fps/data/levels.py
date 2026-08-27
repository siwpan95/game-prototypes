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
        name="Warehouse Entrance",
        description=(
            "You stand before a rusted metal door, barely hanging on its hinges. "
            "The air reeks of old machine oil and damp concrete. Faded hazard signs "
            "peel off the walls. Something stirs inside."
        ),
        exits={"east": "storage"},
        enemies=[
            create_enemy("Guard"),
        ],
        items=[
            create_medkit(25),
        ],
        cover_objects=["concrete pillar"],
        destructibles=[],
        traps=[],
    )

    # --- Storage ---
    storage = Room(
        room_id="storage",
        name="Storage Room",
        description=(
            "Rows of metal shelving stretch into the darkness, loaded with dusty crates. "
            "A single flickering bulb casts long shadows. The floor is littered with "
            "packing straw and broken glass."
        ),
        exits={"west": "entrance", "east": "corridor"},
        enemies=[
            create_enemy("Guard"),
            create_enemy("Guard"),
        ],
        items=[
            create_ammo("pistol", 15),
        ],
        cover_objects=["metal shelf", "stacked crates"],
        destructibles=["barrel"],
        traps=[],
    )

    # --- Corridor ---
    corridor = Room(
        room_id="corridor",
        name="Dark Corridor",
        description=(
            "A narrow corridor with exposed pipes overhead, dripping condensation. "
            "Emergency lights cast a sickly red glow. Footprints in the dust suggest "
            "recent activity."
        ),
        exits={"west": "storage", "east": "office"},
        enemies=[
            create_enemy("Soldier"),
        ],
        items=[
            create_armor(25),
        ],
        cover_objects=["pipe junction", "overturned cabinet"],
        destructibles=[],
        traps=[{"name": "tripwire", "damage": 10, "triggered": False}],
    )

    # --- Office ---
    office = Room(
        room_id="office",
        name="Foreman's Office",
        description=(
            "A cramped office with a shattered desk and papers scattered everywhere. "
            "A dead monitor flickers with static. The far wall has a bullet-ridden "
            "window overlooking the warehouse floor."
        ),
        exits={"west": "corridor"},
        enemies=[
            create_enemy("Soldier"),
        ],
        items=[
            create_medkit(25),
            create_ammo("pistol", 15),
            create_weapon_mod_item("silencer"),
        ],
        cover_objects=["steel desk", "filing cabinet"],
        destructibles=["computer monitor"],
        traps=[],
    )

    return Level(
        level_id=1,
        name="Warehouse",
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
        name="Main Gate",
        description=(
            "The chain-link gate hangs open, rusted off its hinges. Sandbags line the "
            "perimeter, and a guard tower looms in the distance. Spent shell casings "
            "glint on the ground."
        ),
        exits={"north": "barracks"},
        enemies=[
            create_enemy("Guard"),
        ],
        items=[
            create_medkit(25),
            create_medkit(25),
            create_ammo("pistol", 15),
            create_ammo("rifle", 30),
        ],
        cover_objects=["sandbags", "guard post"],
        destructibles=["fuel barrel"],
        traps=[],
    )

    # --- Barracks ---
    barracks = Room(
        room_id="barracks",
        name="Barracks",
        description=(
            "Bunk beds are arranged in tight rows, mattresses torn and stained. "
            "Footlockers sit at the foot of each bed, some forced open. A bulletin "
            "board on the wall displays faded deployment schedules."
        ),
        exits={"south": "gate", "east": "armory", "north": "control_room"},
        enemies=[
            create_enemy("Soldier"),
            create_enemy("Soldier"),
        ],
        items=[
            create_ammo("pistol", 15),
            create_grenade(30),
        ],
        cover_objects=["bunk bed", "footlocker"],
        destructibles=[],
        traps=[],
    )

    # --- Armory ---
    armory = Room(
        room_id="armory",
        name="Armory",
        description=(
            "Weapon racks line the walls, most emptied out. A few rifles remain in "
            "their clamps. The steel door to the safe has been blown open. Crates of "
            "ammunition are stacked against the far wall."
        ),
        exits={"west": "barracks"},
        enemies=[
            create_enemy("Heavy Trooper"),
        ],
        items=[
            create_ammo("shotgun", 8),
            create_ammo("rifle", 30),
            create_medkit(50),
            create_weapon_mod_item("extended_mag"),
        ],
        cover_objects=["weapon rack", "ammo crate"],
        destructibles=["unstable shelf"],
        traps=[],
    )

    # --- Control Room ---
    control_room = Room(
        room_id="control_room",
        name="Control Room",
        description=(
            "Banks of monitors fill the room, most displaying static. A central console "
            "still glows with a tactical map. The air conditioning hums loudly, masking "
            "any sound of movement."
        ),
        exits={"south": "barracks", "north": "hangar"},
        enemies=[
            create_enemy("Sniper"),
            create_enemy("Soldier"),
        ],
        items=[
            create_medkit(50),
            create_armor(25),
        ],
        cover_objects=["console bank", "server rack"],
        destructibles=[],
        traps=[{"name": "mine", "damage": 15, "triggered": False}],
    )

    # --- Hangar (Boss) ---
    hangar = Room(
        room_id="hangar",
        name="Hangar Bay",
        description=(
            "A massive hangar with a partially disassembled transport plane. Cranes "
            "hang from the ceiling like skeletal fingers. Fuel drums are everywhere. "
            "At the far end, a commanding figure stands amid the chaos."
        ),
        exits={"south": "control_room"},
        enemies=[
            create_enemy("Commander", loot=[create_weapon_mod_item("scope")]),
            create_enemy("Soldier"),
            create_enemy("Soldier"),
        ],
        items=[
            create_medkit(50),
            create_ammo("rifle", 30),
        ],
        cover_objects=["airplane wing", "fuel drum", "crane base"],
        destructibles=["fuel drum", "fuel drum"],
        traps=[],
    )

    return Level(
        level_id=2,
        name="Military Base",
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
        name="Elevator Shaft",
        description=(
            "The elevator groans as it descends into the earth. Dim emergency strips "
            "line the shaft. A digital display counts down the floors: B3... B4... B5. "
            "The air grows colder with each meter."
        ),
        exits={"south": "lab_entrance"},
        enemies=[
            create_enemy("Guard"),
        ],
        items=[
            create_medkit(25),
            create_medkit(25),
            create_ammo("pistol", 15),
        ],
        cover_objects=["elevator frame"],
        destructibles=[],
        traps=[],
    )

    # --- Lab Entrance ---
    lab_entrance = Room(
        room_id="lab_entrance",
        name="Lab Entrance",
        description=(
            "A decontamination chamber with cracked glass panels. Warning lights pulse "
            "amber. The smell of antiseptic mingles with something acrid. Bioscanners "
            "on the walls are dark and broken."
        ),
        exits={"north": "elevator", "east": "research_wing", "west": "server_room"},
        enemies=[
            create_enemy("Soldier"),
            create_enemy("Heavy Trooper"),
        ],
        items=[
            create_armor(25),
            create_ammo("pistol", 15),
        ],
        cover_objects=["decon booth", "supply cart"],
        destructibles=[],
        traps=[{"name": "laser grid", "damage": 12, "triggered": False}],
    )

    # --- Research Wing ---
    research_wing = Room(
        room_id="research_wing",
        name="Research Wing",
        description=(
            "Glass-walled labs line both sides of the corridor. Inside, bubbling vats "
            "of unknown chemicals cast an eerie green glow. Notes and data pads are "
            "scattered across workstations. Something scratched the inside of one of the "
            "containment cells."
        ),
        exits={"west": "lab_entrance", "south": "containment"},
        enemies=[
            create_enemy("Sniper"),
            create_enemy("Soldier"),
            create_enemy("Soldier"),
        ],
        items=[
            create_medkit(50),
            create_weapon_mod_item("scope"),
        ],
        cover_objects=["lab bench", "chemical vat"],
        destructibles=["glass partition"],
        traps=[],
    )

    # --- Containment ---
    containment = Room(
        room_id="containment",
        name="Containment Block",
        description=(
            "Heavy blast doors stand open, their locking mechanisms destroyed. Rows of "
            "containment cells line the walls, most empty. Thick scratches scar the "
            "interior of the doors. A cold draft blows from somewhere deeper inside."
        ),
        exits={"north": "research_wing", "south": "core"},
        enemies=[
            create_enemy("Heavy Trooper"),
            create_enemy("Heavy Trooper"),
        ],
        items=[
            create_grenade(30),
            create_ammo("shotgun", 8),
        ],
        cover_objects=["blast door", "containment cell"],
        destructibles=["unstable wall"],
        traps=[
            {"name": "mine", "damage": 20, "triggered": False},
            {"name": "tripwire", "damage": 10, "triggered": False},
        ],
    )

    # --- Server Room ---
    server_room = Room(
        room_id="server_room",
        name="Server Room",
        description=(
            "Rows of server racks hum and blink with amber and green lights. The heat "
            "is oppressive despite the overworked cooling system. Cables snake across "
            "the floor like roots. A terminal displays scrolling data in a language "
            "you don't recognize."
        ),
        exits={"east": "lab_entrance"},
        enemies=[
            create_enemy("Sniper"),
            create_enemy("Soldier"),
        ],
        items=[
            create_medkit(25),
            create_armor(25),
            create_weapon_mod_item("silencer"),
        ],
        cover_objects=["server rack", "cooling unit"],
        destructibles=["overheated server"],
        traps=[],
    )

    # --- Core (Boss) ---
    core = Room(
        room_id="core",
        name="Lab Core",
        description=(
            "The heart of the underground facility. A massive cylindrical chamber "
            "surrounded by catwalks and monitoring stations. In the center, something "
            "pulses with a faint bioluminescence. The Commander of this operation "
            "awaits, flanked by elite guards."
        ),
        exits={"north": "containment"},
        enemies=[
            create_enemy("Commander", loot=[
                create_weapon_mod_item("extended_mag"),
                create_medkit(50),
            ]),
            create_enemy("Soldier"),
            create_enemy("Soldier"),
            create_enemy("Heavy Trooper"),
        ],
        items=[
            create_medkit(50),
            create_ammo("rifle", 30),
            create_ammo("shotgun", 8),
        ],
        cover_objects=["catwalk railing", "monitoring station", "support pillar"],
        destructibles=["generator", "fuel canister"],
        traps=[
            {"name": "laser grid", "damage": 15, "triggered": False},
        ],
    )

    return Level(
        level_id=3,
        name="Underground Lab",
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
