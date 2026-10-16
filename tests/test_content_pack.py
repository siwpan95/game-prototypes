"""Content-pack contract: the shipped pack is valid, and the puzzles read from it.

The interesting failure modes here are not "does loading work" but:

* the pack drifts from the puzzle modules it was derived from;
* a puzzle keeps using its embedded bank even though a pack is present;
* a real content defect (measured: two 5-letter words inside the 4-letter ladder
  pool) survives migration because nothing checks it;
* a broken pack silently degrades to the built-in banks without anyone noticing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from puzzle_service.content import (
    ContentPack,
    ContentPackError,
    PACK_FORMAT_VERSION,
    default_pack_path,
    load_pack,
    validate_pack,
)
from puzzle_service.registry import get
from puzzle_service.service import PuzzleService

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "content" / "packs" / "core-zh"
CONTENT_KINDS = ("riddle", "hangman", "anagram", "word_ladder", "crossword")


@pytest.fixture(scope="module", autouse=True)
def registered_kinds():
    """The registry is process-global; make sure this module's tests have kinds.

    Depending on another test module happening to run first would make these
    tests order-dependent, which is how "passes locally, fails in CI" starts.
    """
    from puzzle_service.registry import all_kinds, discover

    if not all_kinds():
        discover("zh", content=load_pack(PACK_DIR))
    return all_kinds()


@pytest.fixture(scope="module")
def pack() -> ContentPack:
    return load_pack(PACK_DIR)


# --- the shipped pack -------------------------------------------------------


def test_shipped_pack_is_valid(pack):
    report = validate_pack(pack)
    assert report["ok"], report["problems"]
    assert report["counts"], "pack declares no content"


def test_manifest_carries_both_version_fields(pack):
    """A pack must state its own format and the oldest engine that can read it."""
    manifest = pack.manifest
    assert manifest["format_version"] == PACK_FORMAT_VERSION
    assert manifest["min_engine_version"], "min_engine_version is what protects old engines"
    for kind, entry in manifest["content"].items():
        assert (PACK_DIR / entry["file"]).is_file(), f"{kind}: declared file is missing"
        assert entry["count"] == len(pack.items(kind)), f"{kind}: manifest count is wrong"


def test_default_pack_path_points_at_the_shipped_pack():
    assert default_pack_path() == PACK_DIR
    assert default_pack_path().is_dir()


def test_every_content_kind_declares_a_pack_kind():
    """A content puzzle without content_kind would silently ignore the pack."""
    for name in CONTENT_KINDS:
        kind = get(name)
        assert getattr(kind.cls, "content_kind", None), f"{name} has no content_kind"
        assert kind.content is not None, f"{name}: kind was registered without the pack"


def _item_key(item: dict) -> str:
    """Stable identity of a pack item, per kind.

    Crosswords carry no single ''word'' field, so their identity is the placed
    words and coordinates — which also proves the *layout* came from the pack and
    not just the word list.
    """
    if "question" in item:
        return str(item["question"])
    if "word" in item:
        return str(item["word"])
    if "start" in item:
        return f"{item['start']}->{item['end']}"
    if "words" in item:
        return "|".join(
            f"{entry['word']}@{entry['row']},{entry['col']},{entry['dir']}"
            for entry in item["words"]
        )
    raise AssertionError(f"pack item has no identity: {sorted(item)}")


def _puzzle_key(puzzle) -> str:
    """Same identity, computed from a live puzzle instance."""
    data = puzzle.data
    if "question" in data:
        return str(data["question"])
    if "start" in data:
        return f"{data['start']}->{data['end']}"
    if "words" in data:
        return "|".join(
            f"{entry['word']}@{entry['row']},{entry['col']},{entry['dir']}"
            for entry in data["words"]
        )
    return str(data.get("word"))


def test_puzzles_actually_draw_from_the_pack(pack):
    """Every content kind must produce an item the pack contains.

    Repeated draws, because a single draw from a bank that overlaps the pack could
    pass by luck.
    """
    for name in CONTENT_KINDS:
        kind = get(name)
        content_kind = kind.cls.content_kind
        expected = {_item_key(item) for item in pack.items(content_kind)}
        assert expected, f"{content_kind} is empty in the pack"
        seen = set()
        for _ in range(25):
            key = _puzzle_key(kind.create(difficulty="easy"))
            seen.add(key)
            assert key in expected, f"{name}: drew {key!r} which is not in the pack"
        assert len(seen) > 1, f"{name}: 25 draws produced a single item, selection looks frozen"


def test_word_ladders_only_use_words_of_the_ladder_length(pack):
    """Measured defect: the built-in 4-letter pool contained 'knife' and 'flame'."""
    for item in pack.items("word_ladders"):
        length = len(item["start"])
        wrong = [word for word in item["pool"] if len(word) != length]
        assert not wrong, f"{item['id']}: pool has words of the wrong length: {wrong}"
        assert item["start"] in item["pool"], f"{item['id']}: start word is not in its pool"


def test_crosswords_declare_their_blocked_cells(pack):
    """A hole must be stated, or a coordinate typo is indistinguishable from design."""
    for item in pack.items("crosswords"):
        size = item["size"]
        covered = set()
        for entry in item["words"]:
            for offset in range(len(entry["word"])):
                row = entry["row"] + (offset if entry["dir"] == "down" else 0)
                col = entry["col"] + (offset if entry["dir"] == "across" else 0)
                covered.add((row, col))
        blocked = {(row, col) for row, col in item["blocks"]}
        assert covered | blocked == {(r, c) for r in range(size) for c in range(size)}
        assert not (covered & blocked), f"{item['id']}: a cell is both blocked and used"


def test_pack_contains_no_executable_content(pack):
    """A pack is data: no code, no expressions, whatever a future author tries."""
    for kind in pack.content:
        text = (PACK_DIR / f"{kind}.json").read_text(encoding="utf-8")
        for forbidden in ("eval(", "__import__", "exec(", "lambda"):
            assert forbidden not in text, f"{kind}.json contains {forbidden!r}"


def test_pack_is_not_stale_relative_to_the_puzzle_modules():
    """The pack is derived from the modules; editing a bank without regenerating must fail."""
    pack_file_count = len(list(PACK_DIR.glob("*.json")))
    if pack_file_count == 0:
        pytest.skip("no shipped pack to compare against")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_content_pack.py"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    assert result.returncode == 0, (
        "content pack is out of date with the puzzle modules; run "
        f"python scripts/build_content_pack.py\n{result.stdout}{result.stderr}"
    )


# --- loading failures are loud ---------------------------------------------


def _write_pack(root: Path, manifest: dict, files: dict[str, list[dict]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    for kind, items in files.items():
        (root / f"{kind}.json").write_text(
            json.dumps({"kind": kind, "items": items}, ensure_ascii=False), encoding="utf-8"
        )


def _base_manifest(**overrides) -> dict:
    manifest = {
        "name": "test-pack",
        "version": "0.0.1",
        "format_version": PACK_FORMAT_VERSION,
        "min_engine_version": "0.1.0",
        "languages": ["zh"],
        "content": {"riddles": {"file": "riddles.json", "count": 1}},
    }
    manifest.update(overrides)
    return manifest


def _riddle(**overrides) -> dict:
    item = {
        "id": "r1",
        "difficulty": "easy",
        "question": "什么问题？",
        "options": ["甲", "乙"],
        "answer": 0,
    }
    item.update(overrides)
    return item


def test_missing_directory_is_reported(tmp_path):
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path / "nope")
    assert "not found" in str(excinfo.value)


def test_missing_manifest_is_reported(tmp_path):
    (tmp_path / "riddles.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "manifest.json" in str(excinfo.value)


def test_newer_format_version_is_refused_not_half_read(tmp_path):
    _write_pack(tmp_path, _base_manifest(format_version=PACK_FORMAT_VERSION + 1), {"riddles": [_riddle()]})
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "newer than this engine" in str(excinfo.value)


def test_pack_requiring_a_newer_engine_is_refused(tmp_path):
    _write_pack(tmp_path, _base_manifest(min_engine_version="99.0.0"), {"riddles": [_riddle()]})
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "requires engine" in str(excinfo.value)


def test_declared_file_that_does_not_exist_is_reported(tmp_path):
    _write_pack(tmp_path, _base_manifest(), {})
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "is missing" in str(excinfo.value)


def test_invalid_json_names_the_file(tmp_path):
    _write_pack(tmp_path, _base_manifest(), {"riddles": [_riddle()]})
    (tmp_path / "riddles.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "riddles.json" in str(excinfo.value)


def test_answer_index_outside_the_options_is_caught(tmp_path):
    _write_pack(tmp_path, _base_manifest(), {"riddles": [_riddle(answer=7)]})
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "outside the" in str(excinfo.value)


def test_duplicate_entries_are_caught(tmp_path):
    _write_pack(tmp_path, _base_manifest(), {"riddles": [_riddle(), _riddle()]})
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "duplicate entry" in str(excinfo.value)


def test_unknown_content_kind_is_caught(tmp_path):
    manifest = _base_manifest(content={"telepathy": {"file": "telepathy.json", "count": 1}})
    _write_pack(tmp_path, manifest, {"telepathy": [{"id": "x"}]})
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "unknown content kind" in str(excinfo.value)


def test_crossword_with_an_uncovered_cell_is_caught(tmp_path):
    """The check that found a real hole in a hand-written template."""
    item = {
        "id": "cw",
        "difficulty": "easy",
        "size": 3,
        "words": [
            {"word": "ABC", "row": 0, "col": 0, "dir": "across", "clue": "1"},
            {"word": "AD", "row": 0, "col": 0, "dir": "down", "clue": "2"},
        ],
        "blocks": [],
    }
    _write_pack(tmp_path, _base_manifest(content={"crosswords": {"file": "crosswords.json", "count": 1}}),
                {"crosswords": [item]})
    with pytest.raises(ContentPackError) as excinfo:
        load_pack(tmp_path)
    assert "neither blocked nor covered" in str(excinfo.value)


# --- degradation and reporting ---------------------------------------------


def test_a_broken_pack_degrades_loudly_to_builtin_banks(tmp_path, monkeypatch, capsys):
    """Losing the pack must not stop the game, and must not be silent either."""
    broken = tmp_path / "broken"
    _write_pack(broken, _base_manifest(format_version=PACK_FORMAT_VERSION + 1), {"riddles": [_riddle()]})
    monkeypatch.setenv("TEXT_ADVENTURE_CONTENT_PACK", str(broken))
    service = PuzzleService(language="zh")
    captured = capsys.readouterr()
    assert service.content is None
    assert "content pack unusable" in captured.err, "a broken pack was swallowed silently"
    assert "built-in banks" in service.content_summary()["source"]


def test_content_summary_does_not_leak_a_machine_path(pack, service):
    summary = service.content_summary()
    assert "root" not in summary
    assert summary["source"] == "content pack"
    assert "\\" not in json.dumps(summary, ensure_ascii=False)


def test_custom_pack_directory_is_honoured(tmp_path, monkeypatch):
    _write_pack(tmp_path, _base_manifest(), {"riddles": [_riddle()]})
    monkeypatch.setenv("TEXT_ADVENTURE_CONTENT_PACK", str(tmp_path))
    loaded = load_pack()
    assert loaded.name == "test-pack"
    assert len(loaded.items("riddles")) == 1


def test_english_build_carries_the_same_content_protocol():
    """Both builds must expose the same content kinds, or they drift apart.

    Mirrors SPEC-101 §阶段 M5's precondition: converging the two implementations
    starts by making their content seams identical.
    """
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, json\n"
                f"sys.path.insert(0, r'{ROOT}')\n"
                "from shared.paths import bootstrap_import_path\n"
                "bootstrap_import_path('en')\n"
                "from gameplay_pool import PUZZLE_CLASSES\n"
                "print(json.dumps({c.__name__: getattr(c, 'content_kind', None) "
                "for c in PUZZLE_CLASSES}))\n"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    assert probe.returncode == 0, probe.stderr
    english = json.loads(probe.stdout.strip().splitlines()[-1])
    zh_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, json\n"
                f"sys.path.insert(0, r'{ROOT}')\n"
                "from shared.paths import bootstrap_import_path\n"
                "bootstrap_import_path('zh')\n"
                "from gameplay_pool import PUZZLE_CLASSES\n"
                "print(json.dumps({c.__name__: getattr(c, 'content_kind', None) "
                "for c in PUZZLE_CLASSES}))\n"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    assert zh_probe.returncode == 0, zh_probe.stderr
    chinese = json.loads(zh_probe.stdout.strip().splitlines()[-1])

    assert set(english) == set(chinese), (
        f"class sets differ: en-only {sorted(set(english) - set(chinese))}, "
        f"zh-only {sorted(set(chinese) - set(english))}"
    )
    mismatched = {
        name: (english[name], chinese[name])
        for name in english
        if english[name] != chinese[name]
    }
    assert not mismatched, f"content_kind differs between builds: {mismatched}"
    assert sum(1 for value in english.values() if value) == len(CONTENT_KINDS)


def test_service_reports_the_pack_it_loaded(service):
    summary = service.content_summary()
    assert summary["counts"], "the service reported no content"
    assert summary["name"], "the pack has no name"
