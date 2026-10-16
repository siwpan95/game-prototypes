"""Puzzle kind registry: the plugin seam.

A "kind" is one puzzle type (math, sudoku, minesweeper, ...). It used to be
reachable only through two hand-maintained lists
(``gameplay_pool/__init__.py`` and ``gameplay_pool/random_pick.py``) plus a
14-branch ``isinstance`` chain in each UI. Now a kind is described once, here,
and the rest of the system is written against the description:

* ``name``        stable id used by the RPC surface and by content packs
* ``interaction`` how a client renders it (see ``views``)
* ``actions``     the mutating calls the kind accepts, other than answering
* ``categories``  which selection pools it belongs to (content/mixed/generated)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from shared.paths import bootstrap_import_path

__all__ = [
    "PuzzleKind",
    "LANGUAGES",
    "register",
    "register_kind",
    "discover",
    "all_kinds",
    "get",
    "clear",
    "UnknownKind",
    "UnknownLanguage",
]

# ---------------------------------------------------------------------------
# Language selection
# ---------------------------------------------------------------------------

#: Language code -> import root that provides ``gameplay_pool``.
#:
#: One process may only load one language: both builds export a top-level
#: ``gameplay_pool`` package, so the first one on ``sys.path`` shadows the other.
LANGUAGES: dict[str, str] = {
    "zh": "text_adventure_zh",
    "en": "text_adventure",
}


class UnknownLanguage(LookupError):
    """Raised for a language code that is not registered."""


class UnknownKind(LookupError):
    """Raised for a kind name that is not registered."""


# ---------------------------------------------------------------------------
# Kind description
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PuzzleKind:
    """Everything the rest of the system needs to know about one puzzle type."""

    name: str
    cls: type
    title: str = ""
    interaction: str = "text"  # text | choice | grid | board
    actions: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    answer_type: str = "str"  # str | int | list | dict
    #: How the puzzle is solved: "check" means ``check_answer(answer)`` is the
    #: only path; "action" means completion is a property of the mutated state
    #: (2048 reached its tile, memory matched every pair). "check" is accepted
    #: for both, but never auto-detect completion.
    answered_by: str = "check"
    language: str = ""
    #: Content pack supplying this kind's questions/words (``None`` = generated,
    #: or the pack does not cover this kind and the built-in bank is used).
    content: Any = None
    meta: dict[str, Any] = field(default_factory=dict)

    def create(self, difficulty: str = "medium", rng: Any = None, **kwargs: Any):
        """Instantiate one puzzle of this kind, handing it the content pack.

        Content injection happens here rather than in the puzzle constructor so a
        puzzle can still be built on its own (tests, tooling) without knowing that
        content packs exist.

        Args:
            rng: seeded random source. Setting ``puzzle.rng`` makes selection
                reproducible; puzzles route their choices through
                ``pick_content``/``pick_from`` so no global ``random`` state is
                touched (a global reseed would leak into other sessions).
        """
        puzzle = self.cls(difficulty=difficulty, **kwargs)
        if self.content is not None:
            setattr(puzzle, "content", self.content)
        if rng is not None:
            setattr(puzzle, "rng", rng)
        if self.content is not None or rng is not None:
            if getattr(puzzle, "content_kind", None) or rng is not None:
                # _generate() already ran in the constructor, before the pack and
                # the rng existed; run it again so both actually take effect.
                puzzle._generate()
        return puzzle

    def public(self) -> dict[str, Any]:
        """JSON-safe description (no class object, so it can cross the RPC bridge)."""
        return {
            "name": self.name,
            "title": self.title,
            "interaction": self.interaction,
            "actions": list(self.actions),
            "categories": list(self.categories),
            "answer_type": self.answer_type,
            "answered_by": self.answered_by,
            "difficulty": list(self.meta.get("difficulty", ("easy", "medium", "hard"))),
            "language": self.language,
        }


# ---------------------------------------------------------------------------
# Registry storage
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, PuzzleKind] = {}


def register_kind(kind: PuzzleKind) -> PuzzleKind:
    """Register an already-built description (first registration wins per name)."""
    if kind.name in _REGISTRY:
        existing = _REGISTRY[kind.name]
        if existing.cls is not kind.cls:
            raise ValueError(
                f"puzzle kind {kind.name!r} already registered by {existing.cls!r}; "
                f"refusing to shadow it with {kind.cls!r}"
            )
        return existing
    _REGISTRY[kind.name] = kind
    return kind


def register(
    name: str | None = None,
    *,
    title: str = "",
    interaction: str = "text",
    actions: Iterable[str] = (),
    categories: Iterable[str] = (),
    answer_type: str = "str",
    answered_by: str = "check",
) -> Callable[[type], type]:
    """Class decorator that registers a kind.

    Usage::

        @register(title="Sudoku", interaction="grid", actions=("set_cell",))
        class SudokuPuzzle(BasePuzzle):
            ...
    """

    def decorate(cls: type) -> type:
        puzzle_name = name or getattr(cls, "puzzle_name", cls.__name__.lower())
        kind = PuzzleKind(
            name=puzzle_name,
            cls=cls,
            title=title or puzzle_name,
            interaction=interaction,
            actions=tuple(actions),
            categories=tuple(categories) or (getattr(cls, "puzzle_type", ""),),
            answer_type=answer_type,
            answered_by=answered_by,
        )
        register_kind(kind)
        return cls

    return decorate


def clear() -> None:
    """Drop every registration (tests, or re-discovering a different language)."""
    _REGISTRY.clear()


def all_kinds() -> list[PuzzleKind]:
    """Registered kinds, ordered by name for a stable API surface."""
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def get(name: str) -> PuzzleKind:
    """Look a kind up by name, raising :class:`UnknownKind` when absent."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownKind(
            f"unknown puzzle kind {name!r}; registered: {sorted(_REGISTRY)}"
        ) from None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

#: name -> (title, interaction, actions, answer_type, answered_by)
#:
#: ``answered_by="action"`` marks the kinds whose ``check_answer`` ignores its
#: argument and reads its own state instead (measured 2026-10-16: 2048 compares
#: the board against its target, anagram reads the letters the player arranged,
#: memory compares matched pairs, minesweeper returns its ``win`` flag, hangman
#: asks whether every letter is revealed, colour sequence reads its own phase
#: flag). Those kinds are solved by acting, so the service scores them the moment
#: their state says they are finished rather than waiting for an answer that is
#: never sent.
_MANIFEST: dict[str, tuple[str, str, tuple[str, ...], str, str]] = {
    "math": ("Math", "text", (), "int", "check"),
    "riddle": ("Riddle", "choice", (), "int", "check"),
    "crossword": ("Crossword", "grid", ("set_cell",), "list", "check"),
    "sudoku": ("Sudoku", "grid", ("set_cell",), "list", "check"),
    "guess_number": ("Guess the number", "text", (), "int", "check"),
    "word_ladder": ("Word ladder", "sequence", ("set_step",), "list", "check"),
    "minesweeper": ("Minesweeper", "grid", ("reveal", "toggle_flag"), "list", "action"),
    "nonogram": ("Nonogram", "grid", ("toggle_cell",), "list", "check"),
    "anagram": ("Anagram", "sequence", ("swap_letters",), "str", "action"),
    "memory": ("Memory pairs", "grid", ("flip_card", "hide_unmatched"), "list", "action"),
    "pattern": ("Pattern", "choice", (), "int", "check"),
    "hangman": ("Hangman", "keyboard", ("guess_letter",), "str", "action"),
    "2048": ("2048", "board", ("move",), "int", "action"),
    "color_sequence": ("Colour sequence", "colors", ("press_color",), "list", "action"),
}


def _kind_name(cls: type) -> str:
    """Map a puzzle class onto its manifest key (falls back to the module name)."""
    module = cls.__module__.rsplit(".", 1)[-1]
    for suffix in ("_puzzle",):
        if module.endswith(suffix):
            module = module[: -len(suffix)]
    if module in _MANIFEST:
        return module
    lowered = getattr(cls, "puzzle_name", cls.__name__).lower()
    return lowered


def discover(language: str = "zh", content: Any = None) -> list[PuzzleKind]:
    """Import *language*'s ``gameplay_pool`` and register every kind it exports.

    Idempotent: registering the same class twice is a no-op, while a *different*
    class claiming a taken name raises instead of silently shadowing.

    Args:
        language: ``"zh"`` or ``"en"``.
        content: content pack handed to content kinds (``None`` = built-in banks).
            Passing it here keeps ``PuzzleKind`` immutable: the pack is fixed at
            registration time instead of being patched afterwards.
    """
    if language not in LANGUAGES:
        raise UnknownLanguage(
            f"unknown language {language!r}; known: {sorted(LANGUAGES)}"
        )

    root = bootstrap_import_path(language)
    if root is None:
        raise RuntimeError(
            "project root not found (no pyproject.toml next to a shared/ directory)"
        )

    gameplay_pool = __import__("gameplay_pool", fromlist=["PUZZLE_CLASSES"])
    classes = list(getattr(gameplay_pool, "PUZZLE_CLASSES", ()))
    if not classes:
        raise RuntimeError(
            "gameplay_pool.PUZZLE_CLASSES is empty; the build did not export any kinds"
        )

    for cls in classes:
        name = _kind_name(cls)
        title, interaction, actions, answer_type, answered_by = _MANIFEST.get(
            name, (cls.__name__, "text", (), "str", "check")
        )
        register_kind(
            PuzzleKind(
                name=name,
                cls=cls,
                title=title,
                interaction=interaction,
                actions=actions,
                categories=(getattr(cls, "puzzle_type", ""),),
                answer_type=answer_type,
                answered_by=answered_by,
                language=language,
                content=content,
                meta={"manifest": name in _MANIFEST},
            )
        )
    return all_kinds()
