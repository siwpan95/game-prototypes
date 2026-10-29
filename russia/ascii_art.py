"""
ASCII Art & Kaomoji for Player and Opponent.
Used in pygame rendering.
"""

PLAYER_NORMAL = r"""
   (•̀_•́)  玩家
    /|\
    / \
"""

PLAYER_HIT = r"""
   (×_×)  中弹！
    /|\
    / \
"""

PLAYER_DEAD = r"""
   (✖_✖)  ✝
    /|\
    / \
"""

PLAYER_SHOOT = r"""
   (ﾉಥ益ಥ)ﾉ  开枪！
    /|\
    / \
"""

OPPONENT_NORMAL = r"""
   (¬‿¬)  对手
    /|\
    / \
"""

OPPONENT_HIT = r"""
   (×_×)  中弹！
    /|\
    / \
"""

OPPONENT_DEAD = r"""
   (✖_✖)  ✝
    /|\
    / \
"""

OPPONENT_SHOOT = r"""
   (╯°□°)╯  开枪！
    /|\
    / \
"""


# ── Chamber (弹巢) ASCII ──────────────────────────────────────────────

def chamber_art(bullets: list, max_slots: int = 6) -> str:
    """
    Draw chamber as a circle of slots.
    ◉ = live round, ○ = blank, ▢ = empty
    """
    # Simple linear view
    line = ""
    for i in range(max_slots):
        if i < len(bullets):
            line += " ◉ " if bullets[i] == 1 else " ○ "
        else:
            line += " ▢ "
    return line


# ── Dice ASCII ───────────────────────────────────────────────────────

DICE_FACES = {
    1: r"""
 +-----+
 |     |
 |  *  |
 |     |
 +-----+
""",
    2: r"""
 +-----+
 | *   |
 |     |
 |   * |
 +-----+
""",
    3: r"""
 +-----+
 | *   |
 |  *  |
 |   * |
 +-----+
""",
    4: r"""
 +-----+
 | * * |
 |     |
 | * * |
 +-----+
""",
    5: r"""
 +-----+
 | * * |
 |  *  |
 | * * |
 +-----+
""",
    6: r"""
 +-----+
 | * * |
 | * * |
 | * * |
 +-----+
""",
}


def dice_arts(dice_list: list) -> str:
    """Return ASCII art for a list of dice (up to 3)."""
    return "\nAND\n".join(DICE_FACES.get(d, "") for d in dice_list)


# ── Big "砰" / "BANG" ───────────────────────────────────────────────

BANG_ART = r"""
   ___   ___
  / _ \ | _ \
 | (_) ||   /
  \___/ |_|_\
   ____  ___  ____
  | ___|/ _ \| ___|
  | |_ | | | | |_
  |  _|| |_| |  _|
  |_|   \___/|_|
"""

BLANK_ART = r"""
  ____  _     ____
 |  _ \| |__ | __ )  _ __
 | |_) | '_ \|  _ \| '__|
 |  _ <| |_) | |_) | |
 |_| \_\_.__/|____/|_|
"""

EXPLOSION_ART = r"""
   (╯ಠ_ಠ)╯︵ ┻━┻
   ▒▒▒ 炸膛！▒▒▒
   💀 两枪炸死 💀
"""
