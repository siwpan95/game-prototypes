"""Consistency check between the two builds' puzzle classes.

`text_adventure/` and `text_adventure_zh/` are parallel implementations of the
same 14 kinds. Nothing structurally enforces that, so they drift — and the drift
is silent until a feature is exercised in one build only. That happened while
adding the daily puzzle: the `_rng()` helper was added to the Chinese base class
and the English one kept using the module-level `random`, which only failed when
the English build was actually played.

This is a **smoke test**, not a unit test: it imports each build in its own child
process (the two builds export identically named top-level modules, so they cannot
share an interpreter) and compares the class-level structure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Class attributes that must *agree*, because features depend on their values.
#: ``puzzle_name`` is deliberately absent: it is the display name and differs by
#: language ("数独" vs "Sudoku") — the check only requires that both builds have it.
ATTRIBUTES = ["puzzle_type", "content_kind"]

#: Attributes that must merely exist in both builds.
PRESENT_ATTRIBUTES = ["puzzle_name"]

#: Methods every puzzle class must provide, in addition to its own.
BASELINE_METHODS = ["_generate", "check_answer", "get_hint", "pick_content", "pick_from", "_rng", "reset"]


def _introspect(build: str) -> dict:
    """Return {class name: {"attrs": {...}, "methods": [...]}} for one build."""
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, r'{ROOT}')\n"
        "from shared.paths import bootstrap_import_path\n"
        f"bootstrap_import_path('{build}')\n"
        "from gameplay_pool import PUZZLE_CLASSES\n"
        f"attrs = {ATTRIBUTES!r} + {PRESENT_ATTRIBUTES!r}\n"
        "out = {}\n"
        "for cls in PUZZLE_CLASSES:\n"
        "    out[cls.__name__] = {\n"
        "        'attrs': {a: getattr(cls, a, None) for a in attrs},\n"
        "        'methods': sorted(m for m in dir(cls) if not m.startswith('__')),\n"
        "    }\n"
        "print(json.dumps(out, ensure_ascii=False, default=str))\n"
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
        print(f"FAIL  could not introspect the {build} build:\n{result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    import json

    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> int:
    failures: list[str] = []
    zh = _introspect("zh")
    en = _introspect("en")

    if set(zh) != set(en):
        failures.append(
            f"class sets differ: en-only {sorted(set(en) - set(zh))}, "
            f"zh-only {sorted(set(zh) - set(en))}"
        )
    else:
        print(f"OK    both builds define the same {len(zh)} classes")

    for name in sorted(set(zh) & set(en)):
        for attribute in ATTRIBUTES:
            mine, theirs = zh[name]["attrs"][attribute], en[name]["attrs"][attribute]
            if mine != theirs:
                failures.append(f"{name}.{attribute}: zh={mine!r} en={theirs!r}")
        for attribute in PRESENT_ATTRIBUTES:
            if not zh[name]["attrs"].get(attribute) or not en[name]["attrs"].get(attribute):
                failures.append(f"{name}.{attribute}: missing in one of the builds")

        missing = [m for m in BASELINE_METHODS if m not in en[name]["methods"]]
        if missing:
            failures.append(f"{name}: English build lacks {missing}")
        missing = [m for m in BASELINE_METHODS if m not in zh[name]["methods"]]
        if missing:
            failures.append(f"{name}: Chinese build lacks {missing}")

        # Methods the two builds share must be the same set, or a feature added to
        # one build has nowhere to live in the other.
        only_zh = {
            m for m in set(zh[name]["methods"]) - set(en[name]["methods"])
            if not m.startswith("_")
        }
        only_en = {
            m for m in set(en[name]["methods"]) - set(zh[name]["methods"])
            if not m.startswith("_")
        }
        if only_zh or only_en:
            failures.append(f"{name}: public methods differ (zh-only {sorted(only_zh)}, en-only {sorted(only_en)})")

    print(f"OK    checked {len(BASELINE_METHODS)} baseline methods per class")
    if failures:
        print("\nBUILD CONSISTENCY FAILED:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nThe two builds must stay structurally equal; fix the build named above.",
            file=sys.stderr,
        )
        return 1
    print("\nBUILD CONSISTENCY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
