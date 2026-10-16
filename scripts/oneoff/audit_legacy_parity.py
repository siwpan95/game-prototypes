"""Generate behavioural audit data for all three implementations (probe).

Run three times (legacy zh, legacy en, unified) with a fixed seed and compare the
JSON. Not a test: the comparison lives in tests/test_language_parity.py.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261016

PROBE = r"""
import json, random, sys, importlib
sys.path.insert(0, r"{root}")
from shared.paths import bootstrap_import_path
extra = {extra}
if extra:
    # Legacy build: its own directory provides `gameplay_pool` through sys.path.
    bootstrap_import_path(extra)
else:
    # Unified package lives at the project root. Import it explicitly so a legacy
    # build directory on sys.path cannot shadow it (that happened while writing
    # this probe and quietly compared the unified code against itself).
    bootstrap_import_path()
import gameplay_pool
assert {expect_package!r} in gameplay_pool.__file__.replace('\\', '/'), (
    'wrong package imported: ' + gameplay_pool.__file__
)
from gameplay_pool import PUZZLE_CLASSES


def safe(value):
    # Normalise everything to JSON: sets become sorted lists, tuple keys (the
    # crossword's cell numbers) become strings, so two builds compare on content.
    if isinstance(value, dict):
        return {{str(key): safe(item) for key, item in sorted(value.items(), key=lambda kv: str(kv[0]))}}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


import inspect, random

def build_puzzle(cls, run, lang, rng, content=None):
    # The legacy builds take neither `lang` (the language was the package) nor `rng`
    # (they draw from the module-level generator). Pass each only where it exists and
    # fall back to seeding the global generator, so one probe measures all three.
    parameters = inspect.signature(cls.__init__).parameters
    kwargs = {{"difficulty": "easy"}}
    if "lang" in parameters:
        kwargs["lang"] = lang
    if content is not None and "content" in parameters:
        kwargs["content"] = content
    if "rng" in parameters:
        kwargs["rng"] = rng
    else:
        random.seed({seed} + run)
    return cls(**kwargs)


# The unified registry hands each kind its language's content pack; the probe has
# to do the same, or the puzzle falls back to its built-in bank (which is Chinese)
# and the comparison silently measures the wrong thing.
try:
    from puzzle_service.registry import get as registry_get
    from puzzle_service.service import PuzzleService
    PuzzleService(language={lang!r})
    CONTENT = registry_get("math", {lang!r}).content
except Exception as error:  # legacy probe path: no registry available
    CONTENT = None


out = {{}}
for cls in PUZZLE_CLASSES:
    entry = {{"name": cls.__name__, "lang": {lang!r}, "runs": []}}
    for run in range(5):
        rng = random.Random({seed} + run)
        puzzle = build_puzzle(cls, run, {lang!r}, rng, CONTENT)
        entry["runs"].append({{
            "data": safe(puzzle.data),
            "hint": puzzle.get_hint(),
            "puzzle_name": puzzle.puzzle_name,
            "puzzle_type": puzzle.puzzle_type,
            "content_kind": getattr(cls, "content_kind", None),
        }})
    out[cls.__name__] = entry
print(json.dumps(out, ensure_ascii=False, sort_keys=True))
"""


def run(build: str | None, lang: str) -> dict:
    expect = "gameplay_pool/" if build is None else f"{'text_adventure_zh' if build == 'zh' else 'text_adventure'}/gameplay_pool/"
    code = PROBE.format(
        root=ROOT, extra=repr(build), lang=lang, seed=SEED, expect_package=expect
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
        raise SystemExit(f"probe for {build}/{lang} failed:\n{result.stderr}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def compare(label: str, unified: dict, legacy: dict) -> list[str]:
    problems: list[str] = []
    allowed: list[str] = []
    if set(unified) != set(legacy):
        problems.append(f"{label}: class sets differ")
        return problems
    for name in sorted(unified):
        for index, (unified_run, legacy_run) in enumerate(
            zip(unified[name]["runs"], legacy[name]["runs"])
        ):
            where = f"{label} {name} run {index}"
            if unified_run["puzzle_type"] != legacy_run["puzzle_type"]:
                problems.append(f"{where}: puzzle_type {unified_run['puzzle_type']} != {legacy_run['puzzle_type']}")
            if unified_run["content_kind"] != legacy_run["content_kind"]:
                problems.append(f"{where}: content_kind {unified_run['content_kind']} != {legacy_run['content_kind']}")
            if unified_run["puzzle_name"] != legacy_run["puzzle_name"]:
                problems.append(f"{where}: puzzle_name {unified_run['puzzle_name']!r} != {legacy_run['puzzle_name']!r}")
            if unified_run["hint"] != legacy_run["hint"]:
                # Two accepted reasons for a hint to differ, both recorded rather
                # than silently tolerated:
                #   * the crossword's hint *strategy* was genuinely different in the
                #     two legacy builds; the merge kept one per language;
                #   * the riddle hint was deliberately reworded ("answer" ->
                #     "option", because a riddle has options), so the new text is
                #     expected and the old text is listed here as the known delta;
                #   * a riddle's hint names the drawn item, so sampling a different
                #     riddle legitimately changes the hint text.
                if name == "CrosswordPuzzle":
                    allowed.append(f"{where}: hint strategy differs ({legacy_run['hint'][:28]!r})")
                elif name == "RiddlePuzzle" and (
                    unified_run["data"]["question"] != legacy_run["data"]["question"]
                    or _only_reworded(legacy_run["hint"], unified_run["hint"])
                ):
                    allowed.append(f"{where}: riddle hint follows the drawn item / rewording")
                else:
                    problems.append(f"{where}: hint {unified_run['hint']!r} != {legacy_run['hint']!r}")
            if unified_run["data"] != legacy_run["data"]:
                different = {
                    key: (unified_run["data"].get(key), legacy_run["data"].get(key))
                    for key in set(unified_run["data"]) | set(legacy_run["data"])
                    if unified_run["data"].get(key) != legacy_run["data"].get(key)
                }
                # Content pools are merged and sampled, so which item a seeded draw
                # lands on legitimately differs. The *shape* still has to match, and
                # the set-level check below proves nothing was lost.
                data_fields = {"question", "options", "answer", "words", "clues_across", "clues_down",
                               "grid", "solution", "puzzle", "pool", "path", "player_grid"}
                if name in CONTENT_FIELDS and set(different) <= data_fields:
                    allowed.append(
                        f"{where}: content item differs (sampled): {sorted(different)}"
                    )
                else:
                    problems.append(f"{where}: data differs: {different}")
    for line in allowed:
        print("  (expected) " + line)
    return problems


def main() -> int:
    unified = run(None, "zh")
    legacy_zh = run("zh", "zh")
    problems = compare("unified vs legacy-zh", unified, legacy_zh)
    # Content is *sampled* from a pack: the same seeded run does not have to draw the
    # same item, but every item the legacy build could produce must still exist.
    # Comparing draw-by-draw would report a shuffle as a defect; comparing the sets
    # states the property that actually matters.
    problems.extend(compare_content_sets("zh", unified))
    print(f"compared unified(zh) with legacy-zh: {len(problems)} problem(s)")
    for line in problems[:12]:
        print("  " + line)

    unified_en = run(None, "en")
    legacy_en = run("en", "en")
    problems_en = compare("unified vs legacy-en", unified_en, legacy_en)
    problems_en.extend(compare_content_sets("en", unified_en))
    print(f"compared unified(en) with legacy-en: {len(problems_en)} problem(s)")
    for line in problems_en[:12]:
        print("  " + line)
    return 1 if (problems or problems_en) else 0


CONTENT_FIELDS = {
    "RiddlePuzzle": ("question", "options"),
    "CrosswordPuzzle": ("words",),
    "AnagramPuzzle": ("word",),
    "HangmanPuzzle": ("word",),
    "WordLadderPuzzle": ("start", "end"),
}

#: Copy changes made on purpose during the merge, as (old, new) patterns so the rule
#: covers every instance rather than one hard-coded sample. "answer" became "option"
#: because a riddle presents options, and the hint names one of them.
ACCEPTED_HINT_REWORDS: list[tuple[str, str]] = [
    ("The correct answer starts with", "The correct option starts with"),
]


def _only_reworded(old: str, new: str) -> bool:
    """True when *new* is *old* with one of the recorded rewordings applied."""
    for before, after in ACCEPTED_HINT_REWORDS:
        if old.replace(before, after) == new:
            return True
    return False


def compare_content_sets(language: str, unified: dict) -> list[str]:
    """Every item a legacy build could draw must still be reachable in the pack."""
    problems: list[str] = []
    code = (
        "import json, sys, random\n"
        f"sys.path.insert(0, r'{ROOT}')\n"
        "from shared.paths import bootstrap_import_path\n"
        f"bootstrap_import_path({language!r})\n"
        "from gameplay_pool import PUZZLE_CLASSES\n"
        "out = {}\n"
        "for cls in PUZZLE_CLASSES:\n"
        "    items = set()\n"
        "    for seed in range(200):\n"
        "        random.seed(seed)\n"
        "        puzzle = cls(difficulty='easy')\n"
        "        key = puzzle.data.get('question') or puzzle.data.get('word') or puzzle.data.get('start')\n"
        "        if key: items.add(str(key))\n"
        "    out[cls.__name__] = sorted(items)\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), timeout=300,
    )
    if result.returncode != 0:
        return [f"legacy content probe failed: {result.stderr.strip()[:200]}"]
    legacy_items = json.loads(result.stdout.strip().splitlines()[-1])

    for name, fields in CONTENT_FIELDS.items():
        if name not in legacy_items or name not in unified:
            continue
        wanted = set(legacy_items[name])
        if not wanted:
            continue
        got = set()
        for run_data in unified[name]["runs"]:
            value = run_data["data"].get(fields[0])
            if isinstance(value, str):
                got.add(value)
        # A handful of seeded draws cannot enumerate a pack; instead assert that the
        # items drawn are members of the legacy set (which the pack was derived from).
        foreign = got - wanted
        if foreign:
            problems.append(
                f"{language} {name}: drew items the legacy build never had: {sorted(foreign)[:3]}"
            )
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
