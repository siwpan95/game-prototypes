"""Consistency check between the two pygame clients.

`text_adventure/` and `text_adventure_zh/` are legacy front ends of the same game.
Their puzzle pools were removed in M5 (one implementation now lives in the top-level
``gameplay_pool``), so what is left to keep in step is the *client* surface: the same
set of modules, and flat imports that still resolve.

This is a **smoke test**, not a unit test: it imports each client in its own child
process (they export identically named top-level modules, so they cannot share an
interpreter) and compares their structure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDS = {"zh": "text_adventure_zh", "en": "text_adventure"}

#: Modules every pygame client must provide.
CLIENT_MODULES = ["engine.py", "ui.py", "events.py", "domain.py", "main.py"]


def _introspect(build: str) -> dict:
    """Return what one client exposes: its modules and the class it defines."""
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, r'{ROOT}')\n"
        "from shared.paths import bootstrap_import_path\n"
        f"bootstrap_import_path('{build}')\n"
        "import gameplay_pool, engine, ui, events, domain\n"
        "from gameplay_pool import PUZZLE_CLASSES\n"
        "out = {\n"
        "    'pool_file': gameplay_pool.__file__.replace('\\\\', '/'),\n"
        "    'engine_module': engine.__file__.replace('\\\\', '/'),\n"
        "    'kinds': sorted(c.__name__ for c in PUZZLE_CLASSES),\n"
        "    'engine_attrs': sorted(a for a in dir(engine.Engine) if not a.startswith('__')),\n"
        "    'ui_attrs': sorted(a for a in dir(ui.UI) if not a.startswith('__')),\n"
        "    'spawns': hasattr(ui.UI, 'run'),\n"
        "}\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    if result.returncode != 0:
        print(f"FAIL  could not introspect the {build} client:\n{result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    import json

    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> int:
    failures: list[str] = []
    data = {name: _introspect(name) for name in BUILDS}

    # 1. Every client ships the same modules.
    for name, directory in BUILDS.items():
        present = {path.name for path in (ROOT / directory).glob("*.py")}
        missing = [module for module in CLIENT_MODULES if module not in present]
        if missing:
            failures.append(f"{directory}: missing {missing}")
        else:
            print(f"OK    {directory} provides {len(CLIENT_MODULES)} client modules")

    # 2. No client carries its own puzzle pool any more (M5: one implementation).
    for name, directory in BUILDS.items():
        legacy = ROOT / directory / "gameplay_pool"
        if legacy.exists():
            files = sorted(path.name for path in legacy.glob("*.py"))
            failures.append(
                f"{directory}/gameplay_pool still exists ({len(files)} files): "
                "the unified pool at the project root is the only implementation"
            )
    if not failures:
        print("OK    neither client carries a duplicate puzzle pool")

    # 3. Both clients resolve the *same* unified pool.
    pool_files = {name: data[name]["pool_file"] for name in BUILDS}
    if len(set(pool_files.values())) != 1:
        failures.append(f"clients resolve different pools: {pool_files}")
    elif "gameplay_pool" not in pool_files["zh"]:
        failures.append(f"unexpected pool path: {pool_files['zh']}")
    else:
        print(f"OK    both clients use the same pool — {Path(pool_files['zh']).name}")

    # 4. Same kinds, same engine surface.
    if data["zh"]["kinds"] != data["en"]["kinds"]:
        failures.append(f"kind lists differ: {data['zh']['kinds']} vs {data['en']['kinds']}")
    else:
        print(f"OK    both clients expose the same {len(data['zh']['kinds'])} kinds")

    for attribute in ("engine_attrs", "ui_attrs"):
        only_zh = set(data["zh"][attribute]) - set(data["en"][attribute])
        only_en = set(data["en"][attribute]) - set(data["zh"][attribute])
        if only_zh or only_en:
            failures.append(
                f"{attribute} differ (zh-only {sorted(only_zh)}, en-only {sorted(only_en)})"
            )
    if not any("engine_attrs" in line or "ui_attrs" in line for line in failures):
        print("OK    engine and UI surfaces match")

    if failures:
        print("\nCLIENT CONSISTENCY FAILED:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("\nCLIENT CONSISTENCY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
