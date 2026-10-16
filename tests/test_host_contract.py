"""Cross-language contract: the two primitive whitelists must stay identical.

The host validates every view model against ``src/plugins/render.mjs`` before it
is sent, and the browser fails on the same list in ``public/client/primitives.js``.
Two copies of a contract drift; this test is what makes the drift visible in CI
instead of in a browser console.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_RENDER = ROOT / "src" / "plugins" / "render.mjs"
CLIENT_PRIMITIVES = ROOT / "public" / "client" / "primitives.js"
PY_VIEWS = ROOT / "puzzle_service" / "views.py"


def _host_primitives() -> set[str]:
    text = HOST_RENDER.read_text(encoding="utf-8")
    block = text.split("export const PRIMITIVES = {", 1)[1].split("\n}", 1)[0]
    return set(re.findall(r"^\s{2}([a-z_]+):", block, re.MULTILINE))


def _client_primitives() -> set[str]:
    text = CLIENT_PRIMITIVES.read_text(encoding="utf-8")
    block = text.split("export const PRIMITIVES = {", 1)[1].split("\n}", 1)[0]
    return set(re.findall(r"^\s{2}([a-z_]+):", block, re.MULTILINE))


def test_the_two_primitive_lists_are_identical():
    host = _host_primitives()
    client = _client_primitives()
    assert host, "could not parse the host primitive list"
    assert host == client, (
        f"host-only: {sorted(host - client)}; client-only: {sorted(client - host)}"
    )


def test_every_primitive_the_python_side_emits_is_declared():
    """The Python service is the producer: it must not invent primitives."""
    text = PY_VIEWS.read_text(encoding="utf-8")
    emitted = set(re.findall(r'"type":\s*"([a-z_]+)"', text))
    declared = _host_primitives()
    undeclared = emitted - declared
    assert not undeclared, f"python emits undeclared primitives: {sorted(undeclared)}"


def test_each_declared_primitive_is_actually_used_by_some_kind():
    """A primitive nobody emits is dead weight in the contract."""
    text = PY_VIEWS.read_text(encoding="utf-8")
    emitted = set(re.findall(r'"type":\s*"([a-z_]+)"', text))
    unused = _host_primitives() - emitted
    assert not unused, f"declared but never emitted: {sorted(unused)}"


def test_cordis_config_lists_the_services_the_host_needs():
    entries = json.loads((ROOT / "cordis.json").read_text(encoding="utf-8"))["entries"]
    ids = {entry["id"] for entry in entries}
    assert {"puzzles", "web"} <= ids, f"cordis.json entries: {sorted(ids)}"
    for entry in entries:
        assert entry["name"].startswith("./"), entry
        assert (ROOT / entry["name"]).exists(), f"entry file missing: {entry['name']}"


def test_package_json_and_gitignore_agree_about_generated_files():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for required in ("node_modules/", ".venv/", "__pycache__/"):
        assert required in ignore, f"{required} is not ignored"


def test_web_plugin_declares_its_injection():
    """Cordis throws at run time if a service is read without an inject declaration."""
    text = (ROOT / "src" / "plugins" / "web.mjs").read_text(encoding="utf-8")
    assert "static inject = ['puzzles']" in text, "web.mjs lost its inject declaration"


def test_the_two_clients_stay_structurally_equal():
    """Catches drift between the two pygame clients (and any duplicate puzzle pool).

    The clients implement the same game, and nothing else enforces that they keep the
    same shape. The concrete cost of ignoring it: a helper added to the Chinese build
    only was missing in English, which failed the first time the English build was
    played. Since M5 the check also asserts that neither client carries its own
    puzzle pool — one implementation lives at the project root.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_build_consistency.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=300,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "CLIENT CONSISTENCY PASSED" in result.stdout
