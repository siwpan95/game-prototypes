"""Registry contract: kinds are discovered, named stably, and never silently shadowed.

Also covers the language keying: the same kind exists once per language, and asking
for a kind in a language that was never discovered must fail rather than quietly
hand back another language's puzzle — that is the defect the M5 merge surfaced (the
first language registered in a process used to win for every later request).
"""

from __future__ import annotations

import pytest

from puzzle_service import registry
from puzzle_service.registry import PuzzleKind, UnknownKind, UnknownLanguage

EXPECTED_ZERO_DUPLICATE_KINDS = 14


def test_every_kind_is_discovered(service, kinds):
    assert len(kinds) == EXPECTED_ZERO_DUPLICATE_KINDS, [k["name"] for k in kinds]
    names = [kind["name"] for kind in kinds]
    assert len(names) == len(set(names)), f"duplicate kind names: {names}"


def test_every_kind_declares_a_usable_interaction(kinds):
    allowed = {"text", "choice", "grid", "sequence", "keyboard", "colors", "board"}
    for kind in kinds:
        assert kind["interaction"] in allowed, kind
        assert kind["title"], kind
        assert kind["answer_type"] in {"str", "int", "list", "dict"}, kind


def test_kind_is_instantiable(service):
    for kind in service.list_kinds():
        puzzle = registry.get(kind["name"], service.language).create(difficulty="easy")
        assert puzzle is not None
        assert puzzle.get_hint(), f"{kind['name']}: empty hint"


def test_unknown_kind_raises():
    with pytest.raises(UnknownKind):
        registry.get("no-such-puzzle", "zh")


def test_unknown_language_raises():
    with pytest.raises(UnknownLanguage):
        registry.discover("de")


def test_registering_a_different_class_under_a_taken_name_is_refused():
    existing = registry.get("math", "zh")

    class Impostor:
        puzzle_type = "content"

    with pytest.raises(ValueError):
        registry.register_kind(PuzzleKind(name="math", cls=Impostor, title="impostor", language="zh"))

    # The original registration must still be intact after the refusal.
    assert registry.get("math", "zh").cls is existing.cls


def test_registering_the_same_class_twice_is_a_noop(service):
    before = len(registry.all_kinds(service.language))
    registry.discover("zh")
    assert len(registry.all_kinds("zh")) == before


def test_kind_public_payload_is_json_safe(service):
    import json

    payload = json.dumps(service.list_kinds())
    assert "PuzzleKind" not in payload and "class " not in payload


# --- language keying (the M5 defect) ---------------------------------------


def test_both_languages_are_registered_and_distinct():
    """Two languages coexist in one process, each with its own pack and names."""
    registry.discover("zh")
    registry.discover("en")
    zh = registry.get("riddle", "zh")
    en = registry.get("riddle", "en")
    assert zh.cls is en.cls, "both languages share the same implementation"
    assert zh.content is not en.content, "each language must carry its own content pack"
    assert zh.title != en.title, f"titles are not translated: {zh.title} / {en.title}"


def test_a_language_that_was_never_discovered_does_not_fall_back():
    """Silently handing back another language's puzzle is the defect to prevent."""
    registry.clear()
    registry.discover("zh")
    with pytest.raises(UnknownKind):
        registry.get("math", "en")
    assert registry.get("math", "zh").language == "zh"


def test_the_registry_reports_each_language_separately():
    registry.discover("zh")
    registry.discover("en")
    assert len(registry.all_kinds("zh")) == EXPECTED_ZERO_DUPLICATE_KINDS
    assert len(registry.all_kinds("en")) == EXPECTED_ZERO_DUPLICATE_KINDS
    assert all(kind.language == "en" for kind in registry.all_kinds("en"))
    assert all(kind.language == "zh" for kind in registry.all_kinds("zh"))
