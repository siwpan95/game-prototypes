"""Derive the shipped content pack from the puzzle modules.

The content lived inside the puzzle classes, so the pack is *derived* from them
rather than hand-transcribed: a hand-typed copy of several hundred words would
drift on the first edit and nobody would notice which copy is right.

Run it after changing a bank in the puzzle modules:

    python scripts/build_content_pack.py            # write content/packs/core-zh
    python scripts/build_content_pack.py --check    # fail if the pack is stale

``--check`` is what CI should run: it regenerates in memory and compares with
the files on disk, so a bank edited without regenerating the pack turns red
instead of silently serving the old content.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.paths import bootstrap_import_path  # noqa: E402

PACK_DIR = ROOT / "content" / "packs" / "core-zh"


def _load_banks(language: str) -> dict[str, object]:
    """Import one build's gameplay_pool and return the content constants."""
    if bootstrap_import_path(language) is None:
        raise SystemExit("ENVIRONMENT ERROR: project root not found")
    from gameplay_pool import CrosswordPuzzle, HangmanPuzzle, RiddlePuzzle  # noqa: F401
    from gameplay_pool import anagram_puzzle, crossword_puzzle, hangman_puzzle
    from gameplay_pool import riddle_puzzle, word_ladder

    return {
        "riddles": list(riddle_puzzle.RIDDLES),
        "hangman": dict(hangman_puzzle.WORD_BANK),
        # The anagram bank is a flat word list: difficulty is derived from length
        # by the puzzle itself, so the pack records that derivation explicitly.
        "anagram": list(anagram_puzzle.WORDS),
        "ladders": list(word_ladder.START_END_PAIRS),
        "ladder_pools": dict(word_ladder.WORD_POOLS),
        "crosswords": list(crossword_puzzle.CROSSWORDS),
    }


def build(language: str) -> dict[str, list[dict]]:
    banks = _load_banks(language)
    content: dict[str, list[dict]] = {}

    content["riddles"] = [
        {
            "id": f"riddle-{index + 1:03d}",
            "difficulty": _riddle_difficulty(riddle),
            "question": riddle["question"],
            "options": list(riddle["options"]),
            "answer": int(riddle["answer"]),
        }
        for index, riddle in enumerate(banks["riddles"])
    ]

    for kind, bank in (("hangman_words", banks["hangman"]),):
        items: list[dict] = []
        for difficulty in ("easy", "medium", "hard"):
            for word in bank.get(difficulty, []):
                items.append(
                    {
                        "id": f"hangman-{difficulty}-{word}",
                        "difficulty": difficulty,
                        "word": word,
                    }
                )
        content[kind] = items

    # AnagramPuzzle picks by word length (<=4 easy, 4..6 medium, >=5 hard), so the
    # pack stores the same derivation instead of inventing a different split.
    anagram_items: list[dict] = []
    for word in banks["anagram"]:
        anagram_items.append(
            {
                "id": f"anagram-{word}",
                "difficulty": _anagram_difficulty(word),
                "word": word,
            }
        )
    content["anagram_words"] = anagram_items

    pools = banks["ladder_pools"]
    ladders: list[dict] = []
    for length, start, end in banks["ladders"]:
        pool = list(pools[length])
        # The shipped pool for length 4 contains two 5-letter words ("knife",
        # "flame") — measured 2026-10-16. Carrying them into the pack would keep
        # the defect alive, so the exporter keeps only words of the ladder's own
        # length and reports what it dropped.
        usable = [word for word in pool if len(word) == length]
        dropped = [word for word in pool if len(word) != length]
        ladders.append(
            {
                "id": f"ladder-{length}-{start}-{end}",
                # The puzzle's own easy/medium split is 3-letter vs 4-letter pairs;
                # earlier ladders were never "hard" before the pack existed, so the
                # pack keeps the same cut points instead of inventing a third tier.
                "difficulty": {3: "easy", 4: "medium"}.get(length, "medium"),
                "start": start,
                "end": end,
                "pool": usable,
                "sourcePoolDropped": dropped,
            }
        )
    content["word_ladders"] = ladders

    content["crosswords"] = [
        {
            "id": f"crossword-{index + 1:02d}",
            "difficulty": "medium",
            "size": template["size"],
            "words": [
                {
                    "word": entry["word"],
                    "row": entry["row"],
                    "col": entry["col"],
                    "dir": entry["dir"],
                    "clue": entry["clue"],
                }
                for entry in template["words"]
            ],
            "blocks": _blocked_cells(template),
        }
        for index, template in enumerate(banks["crosswords"])
    ]
    return content


def _blocked_cells(template: dict) -> list[list[int]]:
    """Cells the template leaves empty, recorded explicitly so the pack is self-describing.

    The puzzle's own check_answer skips cells that are not part of any word, so a
    grid with holes plays fine — but the pack must say *which* holes are
    intentional, otherwise a typo in a word's coordinates becomes a silent hole
    instead of a validation failure.
    """
    size = template["size"]
    covered = set()
    for entry in template["words"]:
        for offset in range(len(entry["word"])):
            row = entry["row"] + (offset if entry["dir"] == "down" else 0)
            col = entry["col"] + (offset if entry["dir"] == "across" else 0)
            covered.add((row, col))
    return [
        [row, col]
        for row in range(size)
        for col in range(size)
        if (row, col) not in covered
    ]


def _anagram_difficulty(word: str) -> str:
    """Same cut points AnagramPuzzle uses, so pack selection matches the old behaviour."""
    if len(word) <= 4:
        return "easy"
    if len(word) <= 6:
        return "medium"
    return "hard"


def _riddle_difficulty(riddle: dict) -> str:
    """Riddles carry no difficulty; derive it from the wording length.

    An honest derivation rather than a fixed label: longer questions with more
    options are the harder ones to read. Curation is expected to replace these
    labels later (SPEC-101 §阶段 M2), and the pack is the place to do it.
    """
    question = str(riddle.get("question", ""))
    options = len(riddle.get("options", []))
    if len(question) <= 14 and options <= 4:
        return "easy"
    if len(question) <= 24:
        return "medium"
    return "hard"


def manifest(content: dict[str, list[dict]]) -> dict:
    from puzzle_service.content import PACK_FORMAT_VERSION, ENGINE_VERSION

    return {
        "name": "core-zh",
        "version": "1.0.0",
        "format_version": PACK_FORMAT_VERSION,
        "min_engine_version": ENGINE_VERSION,
        "languages": ["zh"],
        "description": "中文核心内容包：由谜题模块内的题库导出（scripts/build_content_pack.py）",
        "content": {
            kind: {"file": f"{kind}.json", "count": len(items)}
            for kind, items in sorted(content.items())
        },
    }


def render(content: dict[str, list[dict]]) -> dict[str, str]:
    """Return the pack as ``{relative path: file text}`` without touching disk."""
    files = {"manifest.json": json.dumps(manifest(content), ensure_ascii=False, indent=2) + "\n"}
    for kind, items in sorted(content.items()):
        payload = {"kind": kind, "items": items}
        files[f"{kind}.json"] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the shipped content pack")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    parser.add_argument("--check", action="store_true", help="verify the pack is up to date")
    parser.add_argument("--out", default=str(PACK_DIR), help="pack directory")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    files = render(build(args.language))

    if args.check:
        stale: list[str] = []
        for name, text in files.items():
            target = out_dir / name
            if not target.is_file():
                stale.append(f"missing: {name}")
            elif target.read_text(encoding="utf-8") != text:
                stale.append(f"out of date: {name}")
        extra = sorted(
            path.name for path in out_dir.glob("*.json") if path.name not in files
        ) if out_dir.is_dir() else []
        stale.extend(f"not produced by the generator: {name}" for name in extra)
        if stale:
            print("CONTENT PACK STALE:", file=sys.stderr)
            for line in stale:
                print(f"  {line}", file=sys.stderr)
            print("run: python scripts/build_content_pack.py", file=sys.stderr)
            return 1
        print(f"content pack up to date ({len(files)} files, {sum(len(v) for v in build(args.language).values())} items)")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        # newline="\n" is required, not cosmetic: the default translates "\n" to
        # the platform separator, which on Windows produces CRLF files that
        # .gitattributes then rewrites — a noisy diff on every regeneration.
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
    total = sum(len(items) for items in build(args.language).values())
    print(f"wrote {len(files)} files, {total} items to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
