"""CLI client: the terminal front end must be playable, scriptable and honest.

Tests drive the real entry point as a subprocess over **piped stdin**, because
that is the mode the user actually gets on a terminal-less machine and the mode
in which encoding defects show up. A pure in-process unit test would never see a
mojibake CJK string or a missing `reconfigure`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from puzzle_service.cli import render_snapshot
from puzzle_service.registry import all_kinds
from puzzle_service.service import PuzzleService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def registered():
    """Make sure the registry is populated — *with* the content pack.

    The registry is process-global and discovered once. Registering here without
    content would leave a later module (which asserts kinds carry a pack) staring
    at pack-less registrations, so this fixture goes through PuzzleService, which
    is exactly what the real CLI does.
    """
    PuzzleService(language="zh")
    return all_kinds()


def run_cli(*args: str, stdin: str | None = None, language: str = "zh") -> subprocess.CompletedProcess:
    """Run the CLI exactly as a user would, with UTF-8 pipes on both ends."""
    command = [sys.executable, "-m", "puzzle_service.cli", "--language", language, *args]
    return subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )


# --- one-shot commands ------------------------------------------------------


def test_kinds_lists_every_kind_with_its_protocol():
    result = run_cli("kinds")
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines[0].split("\t")[:3] == ["种类", "交互", "判定"]
    names = {line.split("\t")[0] for line in lines[1:]}
    assert len(names) == 14, sorted(names)


def test_content_reports_the_loaded_pack():
    result = run_cli("content")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["source"] in {"content pack", "built-in banks"}
    assert "root" not in payload, "the CLI must not print a machine path"


def test_new_then_state_renders_a_puzzle():
    result = run_cli("new", "math", "easy")
    assert result.returncode == 0, result.stderr
    assert "math" in result.stdout
    assert "[输入]" in result.stdout, result.stdout
    assert "答案" in result.stdout, "a Chinese client must not show an English label"


def test_spoken_language_is_chinese_in_the_terminal_client():
    """The service names fields in English; this client must localise what it shows."""
    result = run_cli("new", "word_ladder", "easy")
    assert result.returncode == 0, result.stderr
    assert "下一个单词" in result.stdout, result.stdout
    assert "next word" not in result.stdout


def test_hint_comes_back_in_chinese():
    result = run_cli("new", "math", ";", "hint")
    assert result.returncode == 0, result.stderr
    assert "提示：" in result.stdout
    assert any("\u4e00" <= char <= "\u9fff" for char in result.stdout), "CJK was mangled"


def test_several_commands_in_one_invocation_share_the_session():
    """`;` separates commands so a scripted run keeps its puzzle, not just its state."""
    result = run_cli("new", "math", "easy", ";", "state", ";", "content")
    assert result.returncode == 0, result.stderr
    assert "math" in result.stdout
    assert "built-in banks" in result.stdout or "content pack" in result.stdout


def test_a_bad_command_exits_non_zero_so_scripts_can_branch():
    result = run_cli("frobnicate")
    assert result.returncode == 1
    assert "未知命令" in result.stdout


def test_unknown_kind_is_reported_not_crashed():
    result = run_cli("new", "no-such-kind")
    assert result.returncode == 1
    assert "×" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_bad_parameter_syntax_is_reported():
    result = run_cli("new", "minesweeper", ";", "act", "reveal", "row0")
    assert result.returncode == 1
    assert "key=value" in result.stdout


def test_actions_reach_the_puzzle_from_the_terminal():
    # Nonogram toggles a known cell, so the assertion does not depend on the board.
    result = run_cli("new", "nonogram", "easy", ";", "act", "toggle_cell", "row=1", "col=2")
    assert result.returncode == 0, result.stderr
    assert "■" in result.stdout, f"toggled cell not rendered:\n{result.stdout}"


def test_acting_without_a_puzzle_fails_with_a_localised_message():
    result = run_cli("act", "reveal", "row=0", "col=0")
    assert result.returncode == 1
    assert "当前没有进行中的谜题" in result.stdout


def test_json_output_is_machine_readable():
    result = run_cli("new", "sudoku", "easy", ";", "json")
    assert result.returncode == 0, result.stderr
    # The `new` output comes first; the JSON document follows it.
    start = result.stdout.index("{")
    snapshot = json.loads(result.stdout[start:])
    assert snapshot["view"]["kind"] == "sudoku"
    assert snapshot["view"]["nodes"]
    assert "solution" not in result.stdout, "the JSON snapshot leaked the solution"


# --- interactive / piped mode ----------------------------------------------


def test_piped_session_plays_a_whole_puzzle():
    """The user's stated workflow: commands on stdin, no TTY involved."""
    session = subprocess.run(
        [sys.executable, "-m", "puzzle_service.cli", "--language", "zh"],
        input="new math easy\nstate\nhint\nquit\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    assert session.returncode == 0, session.stderr
    assert "输入 help 查看命令" in session.stdout
    assert "提示：" in session.stdout
    assert "再见。" in session.stdout
    assert "> " not in session.stdout, "a prompt must not be printed on a pipe"


def test_piped_session_survives_bad_input_and_keeps_going():
    session = subprocess.run(
        [sys.executable, "-m", "puzzle_service.cli"],
        input="bogus\nnew math\nsubmit not-a-number\nkinds\nquit\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    assert session.returncode == 0, session.stderr
    assert "未知命令" in session.stdout
    assert "种类" in session.stdout, "the session stopped after a bad command"
    assert "Traceback" not in session.stdout + session.stderr


def test_stdin_eof_ends_the_session_cleanly():
    session = subprocess.run(
        [sys.executable, "-m", "puzzle_service.cli"],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    assert session.returncode == 0, session.stderr
    assert "输入 help" in session.stdout


def test_english_language_option_works():
    result = run_cli("new", "math", language="en")
    assert result.returncode == 0, result.stderr
    assert "math" in result.stdout


# --- rendering --------------------------------------------------------------


def test_render_snapshot_is_a_pure_function_over_the_view_model():
    service = PuzzleService(language="zh")
    service.new_puzzle(session_id="t", kind="minesweeper", difficulty="easy")
    text = render_snapshot(service.snapshot("t"))
    assert "雷区" in text
    assert text.count("\n") > 3


def test_render_snapshot_handles_an_empty_session():
    text = render_snapshot(PuzzleService(language="zh").snapshot("empty"))
    assert "没有进行中的谜题" in text


def test_every_kind_renders_in_the_terminal(registered):
    """A new kind must not blow up this client: it renders view models, not kinds."""
    service = PuzzleService(language="zh")
    problems: list[str] = []
    for kind in service.list_kinds():
        try:
            snapshot = service.new_puzzle(session_id="k", kind=kind["name"], difficulty="easy")
            text = render_snapshot(snapshot)
            if not text.strip():
                problems.append(f"{kind['name']}: rendered nothing")
        except Exception as exc:  # noqa: BLE001 - collect all, then report
            problems.append(f"{kind['name']}: {type(exc).__name__}: {exc}")
    assert not problems, problems


def test_terminal_rendering_does_not_leak_the_solution(registered):
    """The same rule the web client is held to: the answer is not in the payload."""
    service = PuzzleService(language="zh")
    snapshot = service.new_puzzle(session_id="leak", kind="sudoku", difficulty="easy")
    solution = service._session("leak").puzzle.data["solution"]
    rendered = render_snapshot(snapshot)
    assert json.dumps(solution) not in rendered
    for row in solution:
        assert "".join(str(value) for value in row) not in rendered.replace(" ", "")
