"""Registry contract: kinds are discovered, named stably, and never silently shadowed."""

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
        puzzle = registry.get(kind["name"]).create(difficulty="easy")
        assert puzzle is not None
        assert puzzle.get_hint(), f"{kind['name']}: empty hint"


def test_unknown_kind_raises():
    with pytest.raises(UnknownKind):
        registry.get("no-such-puzzle")


def test_unknown_language_raises():
    with pytest.raises(UnknownLanguage):
        registry.discover("de")


def test_registering_a_different_class_under_a_taken_name_is_refused():
    existing = registry.get("math")

    class Impostor:
        puzzle_type = "content"

    with pytest.raises(ValueError):
        registry.register_kind(PuzzleKind(name="math", cls=Impostor, title="impostor"))

    # The original registration must still be intact after the refusal.
    assert registry.get("math").cls is existing.cls


def test_registering_the_same_class_twice_is_a_noop(service):
    before = len(registry.all_kinds())
    registry.discover("zh")
    assert len(registry.all_kinds()) == before


def test_kind_public_payload_is_json_safe(service):
    import json

    payload = json.dumps(service.list_kinds())
    assert "PuzzleKind" not in payload and "class " not in payload
