"""Content packs: puzzle content as data, separate from the code that plays it.

Why this exists: the five content kinds (riddle, hangman, word ladder, anagram,
crossword) keep their words and questions inside their Python modules. That makes
"add twenty riddles" a code change, blocks difficulty curation and community
submission, and duplicates the bank once per language build. A pack is a
directory of JSON files with a manifest; the puzzle classes read from it when it
is available and fall back to their embedded bank when it is not, so nothing
breaks while a pack is being authored.

Design decisions that come from the platform research
(see docs/records/platform-research-2026-10/02-platform-architecture.md):

* **Two version fields.** ``format_version`` describes the pack's own schema;
  ``min_engine_version`` is the oldest engine that can read it. A pack written
  for a newer engine is refused, not half-read (the Minecraft ``pack.mcmeta``
  precedent).
* **A pack contains no executable code.** Only JSON data, so nothing in a pack
  can run inside the host process.
* **Validation is part of loading.** A malformed pack fails loudly with the file
  and the field named; there is no "load what we can and hope".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "PACK_FORMAT_VERSION",
    "ENGINE_VERSION",
    "ContentPackError",
    "ContentPack",
    "load_pack",
    "validate_pack",
    "default_pack_path",
    "PACK_ENV_VAR",
]

#: Schema version of the pack format this engine writes/reads.
PACK_FORMAT_VERSION = 1

#: Engine version, compared against a pack's ``min_engine_version``.
ENGINE_VERSION = "0.2.0"

#: Environment variable naming a pack directory to use instead of the shipped one.
PACK_ENV_VAR = "TEXT_ADVENTURE_CONTENT_PACK"

_PACK_MARKERS = ("manifest.json",)


class ContentPackError(ValueError):
    """A pack is unusable: missing, unreadable, or failing validation."""


@dataclass
class ContentPack:
    """A validated pack, with one accessor per content kind."""

    root: Path
    manifest: dict[str, Any]
    content: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return str(self.manifest.get("name", self.root.name))

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", "0"))

    @property
    def languages(self) -> list[str]:
        return [str(code) for code in self.manifest.get("languages", [])]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "root": str(self.root),
            "languages": self.languages,
            "counts": {kind: len(items) for kind, items in self.content.items()},
        }

    # --- accessors ---------------------------------------------------------

    def items(self, kind: str) -> list[dict[str, Any]]:
        """Every item of *kind* (``[]`` when the pack does not provide that kind)."""
        return list(self.content.get(kind, ()))

    def choose(self, kind: str, difficulty: str) -> dict[str, Any] | None:
        """One random item of *kind* at *difficulty*, or ``None`` if unavailable.

        ``None`` is the signal for "this pack does not supply that content", which
        the puzzle classes answer by falling back to their embedded bank. It is
        deliberately not an exception: a pack may legitimately cover only part of
        the content while it is being authored.
        """
        candidates = self.by_difficulty(kind, difficulty)
        if not candidates:
            return None
        import random

        return random.choice(candidates)

    def by_difficulty(self, kind: str, difficulty: str) -> list[dict[str, Any]]:
        """Items whose difficulty matches, falling back to all items of that kind."""
        matching = [
            item for item in self.items(kind) if item.get("difficulty", difficulty) == difficulty
        ]
        return matching or self.items(kind)

    def words(self, kind: str, difficulty: str, field_name: str = "word") -> list[str]:
        """Word lists (hangman, anagram) are just items with one string field."""
        return [
            str(item[field_name])
            for item in self.by_difficulty(kind, difficulty)
            if field_name in item
        ]


# ---------------------------------------------------------------------------
# Loading and validation
# ---------------------------------------------------------------------------


def default_pack_path() -> Path:
    """Where the shipped pack lives, unless overridden by the environment."""
    override = os.environ.get(PACK_ENV_VAR)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "content" / "packs" / "core-zh"


def load_pack(path: Path | str | None = None, *, language: str | None = None) -> ContentPack:
    """Load and validate a pack, raising :class:`ContentPackError` when unusable."""
    root = Path(path) if path is not None else default_pack_path()
    if not root.is_dir():
        raise ContentPackError(f"content pack directory not found: {root}")

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ContentPackError(
            f"content pack has no {_PACK_MARKERS[0]}: {root} "
            f"(expected one of: {', '.join(_PACK_MARKERS)})"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContentPackError(f"{manifest_path}: invalid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ContentPackError(f"{manifest_path}: manifest must be a JSON object")

    format_version = manifest.get("format_version")
    if not isinstance(format_version, int):
        raise ContentPackError(f"{manifest_path}: 'format_version' must be an integer")
    if format_version > PACK_FORMAT_VERSION:
        raise ContentPackError(
            f"{manifest_path}: pack format_version {format_version} is newer than this "
            f"engine understands ({PACK_FORMAT_VERSION}); upgrade the engine instead of "
            "half-reading the pack"
        )

    min_engine = manifest.get("min_engine_version")
    if min_engine is not None and _version_tuple(str(min_engine)) > _version_tuple(ENGINE_VERSION):
        raise ContentPackError(
            f"{manifest_path}: pack requires engine >= {min_engine}, this engine is "
            f"{ENGINE_VERSION}"
        )

    content: dict[str, list[dict[str, Any]]] = {}
    for kind in manifest.get("content", {}):
        relative = f"{kind}.json"
        file_path = root / relative
        if not file_path.is_file():
            raise ContentPackError(
                f"{manifest_path}: declares content '{kind}' but {relative} is missing"
            )
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContentPackError(f"{file_path}: invalid JSON: {exc}") from exc
        items = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(items, list) or not items:
            raise ContentPackError(f"{file_path}: expected a non-empty 'items' array")
        content[kind] = items

    pack = ContentPack(root=root, manifest=manifest, content=content)
    report = validate_pack(pack, language=language)
    if not report["ok"]:
        details = "; ".join(report["problems"][:5])
        more = "" if len(report["problems"]) <= 5 else f" (+{len(report['problems']) - 5} more)"
        raise ContentPackError(f"{root}: pack failed validation: {details}{more}")
    return pack


def validate_pack(pack: ContentPack, *, language: str | None = None) -> dict[str, Any]:
    """Check every item of every kind. Returns ``{ok, problems, counts}``.

    Problems name the file and the offending item index, so a pack author can fix
    a mistake without guessing which of two hundred riddles is wrong.

    ``language`` selects a *suffixed* item (``id@en``) when the pack carries more
    than one language; items without a suffix are shared. It never filters items
    out: a pack whose manifest names a single language must still be validated in
    full, otherwise most of its content would silently skip checking.
    """
    problems: list[str] = []
    counts: dict[str, int] = {}

    for kind, items in pack.content.items():
        counts[kind] = len(items)
        checker = _CHECKERS.get(kind)
        if checker is None:
            problems.append(f"{kind}.json: unknown content kind {kind!r}")
            continue
        seen: set[str] = set()
        wanted_suffix = f"@{language}" if language else None
        for index, item in enumerate(items):
            where = f"{kind}.json[{index}]"
            if not isinstance(item, dict):
                problems.append(f"{where}: item must be a JSON object")
                continue
            has_suffix = "@" in str(item.get("id", ""))
            if wanted_suffix and has_suffix and not str(item["id"]).endswith(wanted_suffix):
                continue  # a variant for another language, checked when that one is loaded
            problems.extend(checker(item, where))
            key = str(item.get("id", item.get("word", item.get("question", ""))))
            if key in seen:
                problems.append(f"{where}: duplicate entry {key!r}")
            seen.add(key)

    return {"ok": not problems, "problems": problems, "counts": counts}


# --- per-kind checkers ------------------------------------------------------


def _check_difficulty(item: dict[str, Any], where: str) -> list[str]:
    difficulty = item.get("difficulty", "medium")
    if difficulty not in {"easy", "medium", "hard"}:
        return [f"{where}: difficulty must be easy/medium/hard, got {difficulty!r}"]
    return []


def _check_riddle(item: dict[str, Any], where: str) -> list[str]:
    problems = _check_difficulty(item, where)
    question = item.get("question")
    options = item.get("options")
    answer = item.get("answer")
    if not isinstance(question, str) or not question.strip():
        problems.append(f"{where}: 'question' must be a non-empty string")
    if not isinstance(options, list) or len(options) < 2:
        problems.append(f"{where}: 'options' must be an array with at least 2 entries")
    elif not all(isinstance(option, str) and option.strip() for option in options):
        problems.append(f"{where}: every option must be a non-empty string")
    if not isinstance(answer, int) or isinstance(answer, bool):
        problems.append(f"{where}: 'answer' must be an index (integer)")
    elif isinstance(options, list) and not 0 <= answer < len(options):
        problems.append(
            f"{where}: 'answer' index {answer} is outside the {len(options)} options"
        )
    if isinstance(options, list) and len(set(options)) != len(options):
        problems.append(f"{where}: duplicate option text")
    return problems


def _check_word(item: dict[str, Any], where: str) -> list[str]:
    problems = _check_difficulty(item, where)
    word = item.get("word")
    if not isinstance(word, str) or not word.strip():
        problems.append(f"{where}: 'word' must be a non-empty string")
    elif not word.isalpha():
        problems.append(f"{where}: 'word' must contain letters only, got {word!r}")
    return problems


def _check_ladder(item: dict[str, Any], where: str) -> list[str]:
    problems = _check_difficulty(item, where)
    start, end = item.get("start"), item.get("end")
    pool = item.get("pool")
    for name, value in (("start", start), ("end", end)):
        if not isinstance(value, str) or not value.isalpha():
            problems.append(f"{where}: '{name}' must be a word of letters only")
    if isinstance(start, str) and isinstance(end, str) and len(start) != len(end):
        problems.append(f"{where}: 'start' and 'end' must have the same length")
    if not isinstance(pool, list) or len(pool) < 2:
        problems.append(f"{where}: 'pool' must be an array of at least 2 words")
    elif isinstance(start, str) and any(
        not isinstance(word, str) or len(word) != len(start) for word in pool
    ):
        problems.append(
            f"{where}: every pool word must be a string as long as 'start' ({len(start)})"
        )
    return problems


def _check_crossword(item: dict[str, Any], where: str) -> list[str]:
    problems = _check_difficulty(item, where)
    size = item.get("size")
    entries = item.get("words")
    if not isinstance(size, int) or not 3 <= size <= 12:
        problems.append(f"{where}: 'size' must be an integer between 3 and 12")
    if not isinstance(entries, list) or len(entries) < 2:
        problems.append(f"{where}: 'words' must list at least 2 placed words")
        return problems

    # ``blocks`` marks cells that are deliberately not part of any word. The
    # puzzle's own check_answer ignores those cells, so they are legitimate — but
    # a cell that is neither blocked nor named by a word can never be confirmed,
    # and that must fail here rather than in someone's browser.
    blocked = _blocked_cells(item, where, size, problems)

    covered: set[tuple[int, int]] = set()
    for word_index, entry in enumerate(entries):
        spot = f"{where}.words[{word_index}]"
        if not isinstance(entry, dict):
            problems.append(f"{spot}: must be an object")
            continue
        word = entry.get("word")
        row, col, direction = entry.get("row"), entry.get("col"), entry.get("dir")
        if not isinstance(word, str) or not word.isalpha() or not word:
            problems.append(f"{spot}: 'word' must be a word of letters only")
            continue
        if not isinstance(row, int) or not isinstance(col, int):
            problems.append(f"{spot}: 'row' and 'col' must be integers")
            continue
        if direction not in {"across", "down"}:
            problems.append(f"{spot}: 'dir' must be 'across' or 'down'")
            continue
        if not isinstance(size, int):
            continue
        end_row, end_col = (
            (row, col + len(word) - 1) if direction == "across" else (row + len(word) - 1, col)
        )
        if not (0 <= row < size and 0 <= col < size and end_row < size and end_col < size):
            problems.append(
                f"{spot}: {word!r} at ({row},{col}) {direction} does not fit in {size}×{size}"
            )
            continue
        for offset in range(len(word)):
            covered.add((row + (offset if direction == "down" else 0),
                         col + (offset if direction == "across" else 0)))
        if not entry.get("clue") and not (item.get("clues") or {}).get(word):
            problems.append(f"{spot}: needs a 'clue' (or an entry in the top-level 'clues')")

    if isinstance(size, int):
        unchecked = sorted(
            (row, col)
            for row in range(size)
            for col in range(size)
            if (row, col) not in covered and (row, col) not in blocked
        )
        if unchecked:
            problems.append(
                f"{where}: {len(unchecked)} cell(s) are neither blocked nor covered by a word "
                f"(first: {unchecked[0]}); they could never be confirmed. Add them to 'blocks' "
                "or extend a word."
            )
    return problems


def _blocked_cells(
    item: dict[str, Any], where: str, size: Any, problems: list[str]
) -> set[tuple[int, int]]:
    """Parse the optional ``blocks`` list of ``[row, col]`` pairs."""
    raw = item.get("blocks", [])
    if raw is None:
        return set()
    if not isinstance(raw, list):
        problems.append(f"{where}: 'blocks' must be an array of [row, col] pairs")
        return set()
    cells: set[tuple[int, int]] = set()
    for index, pair in enumerate(raw):
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(value, int) for value in pair)
        ):
            problems.append(f"{where}.blocks[{index}]: expected [row, col] integers")
            continue
        row, col = pair
        if isinstance(size, int) and not (0 <= row < size and 0 <= col < size):
            problems.append(f"{where}.blocks[{index}]: ({row},{col}) is outside the grid")
            continue
        cells.add((row, col))
    return cells


_CHECKERS = {
    "riddles": _check_riddle,
    "hangman_words": _check_word,
    "anagram_words": _check_word,
    "word_ladders": _check_ladder,
    "crosswords": _check_crossword,
}


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in value.split("."):
        digits = "".join(character for character in chunk if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)
