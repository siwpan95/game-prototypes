"""Client consistency check: one desktop client, one puzzle pool, two languages.

`text_adventure/` and `text_adventure_zh/` used to be parallel implementations of the
same game, and their drift was real: a helper added to the Chinese base class only was
missing in English, and a latent `UnboundLocalError` in the English crossword handler
survived because nothing exercised that screen. Both directories are gone (M5); what
this check guards now is that they *stay* gone, and that the one client really speaks
both languages from one implementation.

Runs the client in a child process per language: two languages in one interpreter
would fight over the display and over which modules are imported.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Directories that must not come back: each was a copy of the puzzle pool or of the
#: desktop client. A copy means the import depends on ``sys.path`` order.
RETIRED = ("text_adventure", "text_adventure_zh")
RETIRED_POOLS = tuple(f"{name}/gameplay_pool" for name in RETIRED)

#: The only implementation of each layer.
REQUIRED = ("gameplay_pool", "client", "puzzle_service", "shared")


def _introspect(language: str) -> dict:
    """What the desktop client exposes in one language."""
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, r'{ROOT}')\n"
        "from shared.paths import bootstrap_import_path\n"
        "bootstrap_import_path()\n"
        "import gameplay_pool\n"
        "from client import translations\n"
        "from client.engine import Engine\n"
        "from client.events import EventBus\n"
        "from client.ui import UI\n"
        "from gameplay_pool import PUZZLE_CLASSES\n"
        f"engine = Engine(event_bus=EventBus(), lang='{language}')\n"
        "puzzle = engine.start_new_puzzle()\n"
        "out = {\n"
        "    'pool_file': gameplay_pool.__file__.replace('\\\\', '/'),\n"
        "    'kinds': sorted(c.__name__ for c in PUZZLE_CLASSES),\n"
        "    'engine_lang': engine.lang,\n"
        "    'content': engine.content.name if engine.content else None,\n"
        "    'puzzle_name': puzzle.puzzle_name,\n"
        "    'hint': puzzle.get_hint(),\n"
        "    'ui_lang': UI(engine=engine, lang='%s').lang,\n"
        "    'strings': len(translations.TEXT),\n"
        "}\n"
        "print(json.dumps(out, ensure_ascii=False))\n" % language
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=300,
    )
    if result.returncode != 0:
        print(f"FAIL  could not introspect the {language} client:\n{result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> int:
    failures: list[str] = []

    # 1. The retired copies stay retired.
    for name in RETIRED:
        if (ROOT / name).exists():
            failures.append(f"{name}/ came back: the desktop client is `client/` and the pool is `gameplay_pool/`")
    for name in RETIRED_POOLS:
        if (ROOT / name).exists():
            failures.append(f"{name}/ came back: one pool, at the project root")
    if not failures:
        print(f"OK    no retired copies present ({len(RETIRED)} client dirs, {len(RETIRED_POOLS)} pool dirs)")

    # 2. The unified layers exist.
    missing = [name for name in REQUIRED if not (ROOT / name).is_dir()]
    if missing:
        failures.append(f"missing package(s): {missing}")
    else:
        print(f"OK    unified packages present: {', '.join(REQUIRED)}")

    # 3. One client, two languages.
    zh = _introspect("zh")
    en = _introspect("en")
    if zh["pool_file"] != en["pool_file"]:
        failures.append(f"languages resolve different pools: {zh['pool_file']} vs {en['pool_file']}")
    else:
        print(f"OK    both languages use the same pool — {Path(zh['pool_file']).parent.name}/")
    if zh["kinds"] != en["kinds"]:
        failures.append(f"kind lists differ: {zh['kinds']} vs {en['kinds']}")
    else:
        print(f"OK    both languages expose the same {len(zh['kinds'])} kinds")

    # 4. The language really reaches the engine, the UI, the puzzle and the content.
    for language, data in (("zh", zh), ("en", en)):
        if data["engine_lang"] != language or data["ui_lang"] != language:
            failures.append(
                f"{language}: engine speaks {data['engine_lang']!r}, ui speaks {data['ui_lang']!r}"
            )
        if not data["content"]:
            failures.append(f"{language}: no content pack loaded")
        elif not data["content"].endswith(language):
            failures.append(f"{language}: content pack is {data['content']!r}")
        if not data["puzzle_name"] or not data["hint"]:
            failures.append(f"{language}: puzzle has no name or hint")
    if not any("speaks" in line or "content pack" in line for line in failures):
        print("OK    language reaches engine, UI, puzzle and content pack")

    # 5. The names actually differ between the languages — otherwise the translation
    #    layer is decorative and one of the two is showing the wrong language.
    if zh["puzzle_name"] == en["puzzle_name"]:
        failures.append(f"both languages call the puzzle {zh['puzzle_name']!r}")
    else:
        print(f"OK    puzzle names differ by language: {zh['puzzle_name']!r} / {en['puzzle_name']!r}")
    if zh["hint"] == en["hint"]:
        failures.append(f"both languages produce the same hint: {zh['hint']!r}")
    else:
        print("OK    hints differ by language")

    if failures:
        print("\nCLIENT CONSISTENCY FAILED:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("\nCLIENT CONSISTENCY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
