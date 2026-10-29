"""Every non-ASCII character the clients draw must exist in the resolved font.

Why this is a check and not a comment: the CJK font family this machine resolves has
no glyph for U+2713, so a "Daily ✓" button drew a **blank box** — worse than saying it
in words, because a box looks like a rendering bug rather than a label. The glyph
survived one edit before a screenshot showed it.

The detection rule, derived from what the font actually does: for an unassigned code
point this family draws a hollow rectangle spanning almost the whole em box. So a
character is suspect when its ink is
  * empty, or
  * a *rectangle* — the outermost rows and columns of its bounding box all inked while
    its interior is mostly blank.
A solid glyph (a CJK ideograph) or a sparse one (a middle dot, an arrow) both fail the
rectangle test, which is what keeps this from crying wolf.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: Characters the desktop client draws beyond plain ASCII and CJK, with where they
#: come from. This list is the contract: adding a symbol here is how it gets checked.
#:
#: The canonical share-card marks (U+2714, U+2718) are *not* here: the card text is
#: shared with the terminal, the browser and the SVG renderer, which all draw them
#: fine, so the desktop substitutes equivalents it can draw
#: (``client.translations.PYGAME_GLYPH_FALLBACKS``) and this list checks the
#: substitutes instead.
SYMBOLS = {
    "·": "separator in the progress line",
    "—": "separator in the number-range label",
    "→": "arrow in the word-ladder prompt (Chinese)",
    "√": "share-card solved mark, as the desktop substitutes it",
    "×": "share-card unsolved mark, as the desktop substitutes it",
}

#: Code points that are unassigned in practice, used to *learn* this font's
#: replacement glyph instead of assuming what it looks like.
PROBES = ("\ue000", "\uf8ff", "\U000f0000")

#: Alpha threshold. Rendering produces a transparent surface whose *alpha* channel
#: carries the glyph; asking for "RGB" drops it and every pixel reads as fully white,
#: which is the mistake this check was written with the first time.
INK = 120


def _is_replacement(mask, reference: list) -> bool:
    """True when *mask* matches what this font draws for an unassigned code point.

    Comparing against the font's *own* replacement glyph beats guessing what a
    replacement looks like: on this family the unassigned U+E000 and the missing U+2713
    produce byte-identical masks (62 ink pixels, rows 9–23, columns 2–11), so equality
    is exact rather than a tuned threshold. An earlier version tried to describe the
    shape ("a hollow rectangle") and got it wrong, because at text sizes the box is
    small and its border is thin.
    """
    return mask == reference


def _decoded(font, char: str):
    """Return ``(mask, width, height)`` of the glyph's ink.

    Reads the alpha channel: ``font.render(..., True, colour)`` returns a transparent
    surface where the glyph is in alpha and the colour is uniform. Decoding "RGB"
    instead yields 255 everywhere, so a mask built from it says every character is a
    solid rectangle — including ``A``.
    """
    import pygame

    surface = font.render(char, True, (255, 255, 255))
    width, height = surface.get_size()
    buffer = pygame.image.tobytes(surface, "RGBA")
    mask = [
        [buffer[(row * width + col) * 4 + 3] > INK for col in range(width)]
        for row in range(height)
    ]
    return mask, width, height


def _ink(mask: list[list[bool]]) -> int:
    return sum(sum(row) for row in mask)


def _is_rectangle(mask: list[list[bool]], width: int, height: int) -> bool:
    """True when the ink forms a hollow rectangle spanning the em box."""
    rows = [index for index, row in enumerate(mask) if any(row)]
    cols = [index for index in range(width) if any(mask[row][index] for row in range(height))]
    if not rows or not cols:
        return False
    top, bottom = rows[0], rows[-1]
    left, right = cols[0], cols[-1]
    box_height = bottom - top + 1
    box_width = right - left + 1
    # A replacement box is large; a legitimate small mark is not.
    if box_height < height * 0.6 or box_width < width * 0.5:
        return False
    # Its border is inked all the way round...
    for col in range(left, right + 1):
        if not (mask[top][col] and mask[bottom][col]):
            return False
    for row in range(top, bottom + 1):
        if not (mask[row][left] and mask[row][right]):
            return False
    # ...and its interior is mostly empty.
    interior = [
        mask[row][col]
        for row in range(top + 1, bottom)
        for col in range(left + 1, right)
    ]
    if not interior:
        return True
    return sum(interior) / len(interior) < 0.35


def main() -> int:
    import pygame

    from shared.font_utils import load_cjk_font

    pygame.init()
    font = load_cjk_font(22)

    # Learn this font's replacement glyph from code points that are unassigned in
    # practice, and require that they agree with each other — otherwise there is no
    # single replacement shape to compare against.
    references = []
    for probe in PROBES:
        mask, _, _ = _decoded(font, probe)
        if _ink(mask) == 0:
            print(
                f"PROBE ERROR: U+{ord(probe):04X} rendered nothing, so this font draws "
                "missing glyphs as blank and the comparison below cannot work",
                file=sys.stderr,
            )
            return 3
        references.append(mask)
    if any(mask != references[0] for mask in references[1:]):
        print(
            "PROBE ERROR: the unassigned code points did not all render the same way, so "
            "there is no single replacement glyph to compare against",
            file=sys.stderr,
        )
        return 3
    reference = references[0]

    problems: list[str] = []
    for char, purpose in SYMBOLS.items():
        mask, _, _ = _decoded(font, char)
        if _ink(mask) == 0:
            problems.append(f"{char!r} (U+{ord(char):04X}, {purpose}) renders nothing")
        elif _is_replacement(mask, reference):
            problems.append(
                f"{char!r} (U+{ord(char):04X}, {purpose}) renders the replacement box — "
                "say it in words instead of using this symbol"
            )

    # Controls: CJK and Latin must render, and must not be mistaken for the box. This is
    # what stops a rule that flags everything.
    for control in ("谜", "A", "·"):
        mask, _, _ = _decoded(font, control)
        if _ink(mask) == 0:
            problems.append(f"control {control!r} renders nothing — the font is broken")
        elif _is_replacement(mask, reference):
            problems.append(f"control {control!r} was mistaken for the replacement box")

    # Self-check: the rule must fire on U+2713, the character whose box started this.
    mask, _, _ = _decoded(font, "\u2713")
    caught = _is_replacement(mask, reference)

    print(f"checked {len(SYMBOLS)} symbol(s) against {len(PROBES)} probe(s) and 3 control(s)")
    print(f"  replacement glyph reference: {_ink(reference)} ink pixel(s)")
    print(f"  U+2713 detected as the box: {caught} (expected: True)")
    if not caught:
        print(
            "SELF-CHECK FAILED: the rule did not flag U+2713, which is known to be missing "
            "from this font. A check that cannot catch the case that motivated it is not a check.",
            file=sys.stderr,
        )
        return 3
    if problems:
        print("\nUNRENDERABLE (would appear as a box or a blank):")
        for line in problems:
            print("  " + line)
        return 1
    print("\nFONT GLYPH COVERAGE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
