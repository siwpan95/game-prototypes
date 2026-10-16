"""Bridge contract: frames, error mapping, and a UTF-8 round trip through stdio.

Runs the real server in a child process (no mocking) because the defects this
guards against are transport defects: an encoding that mangles CJK, diagnostics
printed onto the protocol stream, or an unhandled exception that kills the child
instead of answering.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "python" / "rpc_server.py"


def call(frames: list[dict], expect_frames: int | None = None) -> list[dict]:
    """Send *frames* to a fresh server process and collect its replies."""
    payload = "".join(json.dumps(frame, ensure_ascii=False) + "\n" for frame in frames)
    process = subprocess.run(
        [sys.executable, str(SERVER), "--language", "zh"],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    assert process.returncode == 0, process.stderr
    replies = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    if expect_frames is not None:
        assert len(replies) == expect_frames, replies
    return replies


def test_ping_and_info():
    replies = call(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "server.ping", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "server.info", "params": {}},
        ],
        expect_frames=2,
    )
    assert replies[0]["result"] == {"pong": True}
    info = replies[1]["result"]
    assert info["language"] == "zh"
    assert info["kinds"] == 14


def test_list_returns_json_safe_kinds():
    (reply,) = call([{"jsonrpc": "2.0", "id": 1, "method": "puzzle.list", "params": {}}], 1)
    kinds = reply["result"]
    assert len(kinds) == 14
    json.dumps(kinds)


def test_a_whole_round_trip_in_chinese():
    """create → view → answer → score, with CJK text surviving the pipe both ways."""
    replies = call(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "puzzle.new",
             "params": {"session_id": "s", "kind": "math", "difficulty": "easy"}},
            {"jsonrpc": "2.0", "id": 2, "method": "puzzle.hint", "params": {"session_id": "s"}},
            {"jsonrpc": "2.0", "id": 3, "method": "puzzle.state", "params": {"session_id": "s"}},
        ],
        3,
    )
    view = replies[0]["result"]["view"]
    assert view["kind"] == "math"
    hint = replies[1]["result"]["hint"]
    assert hint.strip(), "hint came back empty"
    assert replies[2]["result"]["kind"] == "math"


def test_unknown_method_is_reported_not_ignored():
    (reply,) = call([{"jsonrpc": "2.0", "id": 1, "method": "puzzle.explode", "params": {}}], 1)
    assert reply["error"]["code"] == -32601
    assert "unknown method" in reply["error"]["message"]


def test_malformed_json_yields_a_parse_error_and_the_server_keeps_going():
    process = subprocess.run(
        [sys.executable, str(SERVER)],
        input='{"jsonrpc": "2.0", "id": 1, "method": \n'
              '{"jsonrpc": "2.0", "id": 2, "method": "server.ping", "params": {}}\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    assert process.returncode == 0, "a bad frame must not kill the bridge"
    replies = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    assert replies[0]["error"]["code"] == -32700
    assert replies[1]["result"] == {"pong": True}, "the server stopped answering after a bad frame"


def test_invalid_params_are_a_caller_error():
    (reply,) = call(
        [{"jsonrpc": "2.0", "id": 1, "method": "puzzle.new",
          "params": {"session_id": "s", "kind": "no-such-kind"}}],
        1,
    )
    # Naming a kind that does not exist is the caller's mistake (-32602),
    # not an internal fault (-32603).
    assert reply["error"]["code"] == -32602
    assert "no-such-kind" in reply["error"]["message"]


def test_wrong_keyword_names_are_reported_as_invalid_params():
    (reply,) = call(
        [{"jsonrpc": "2.0", "id": 1, "method": "puzzle.new",
          "params": {"bogus_keyword": 1}}],
        1,
    )
    assert reply["error"]["code"] == -32602
    assert "bad parameters" in reply["error"]["message"]


def test_a_non_numeric_answer_is_a_structured_error():
    replies = call(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "puzzle.new",
             "params": {"session_id": "s", "kind": "math", "difficulty": "easy"}},
            {"jsonrpc": "2.0", "id": 2, "method": "puzzle.submit",
             "params": {"session_id": "s", "answer": "definitely not a number"}},
            {"jsonrpc": "2.0", "id": 3, "method": "puzzle.state", "params": {"session_id": "s"}},
        ],
        3,
    )
    assert replies[1]["error"]["code"] == -32602
    assert replies[2]["result"]["score"] == 0, "a rejected answer must not score"


def test_actions_reach_the_puzzle_over_the_wire():
    replies = call(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "puzzle.new",
             "params": {"session_id": "s", "kind": "minesweeper", "difficulty": "easy"}},
            {"jsonrpc": "2.0", "id": 2, "method": "puzzle.action",
             "params": {"session_id": "s", "action": "reveal", "row": 0, "col": 0}},
        ],
        2,
    )
    snapshot = replies[1]["result"]
    grid = next(node for node in snapshot["view"]["nodes"] if node["type"] == "grid")
    assert grid["cells"][0][0]["revealed"] is True


def test_string_coordinates_from_json_are_coerced():
    replies = call(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "puzzle.new",
             "params": {"session_id": "s", "kind": "nonogram", "difficulty": "easy"}},
            {"jsonrpc": "2.0", "id": 2, "method": "puzzle.action",
             "params": {"session_id": "s", "action": "toggle_cell", "row": "1", "col": "2"}},
        ],
        2,
    )
    grid = next(node for node in replies[1]["result"]["view"]["nodes"] if node["type"] == "grid")
    assert grid["cells"][1][2]["value"] == 1


def test_shutdown_stops_the_server_cleanly():
    replies = call(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "server.shutdown", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "server.ping", "params": {}},
        ]
    )
    assert replies[0]["result"] == {"bye": True}
    assert len(replies) == 1, "frames after shutdown must not be answered"


def test_diagnostics_never_reach_stdout():
    """stdout is the protocol stream: any stray text would corrupt a reply."""
    process = subprocess.run(
        [sys.executable, str(SERVER)],
        input='{"jsonrpc": "2.0", "id": 1, "method": "server.ping", "params": {}}\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    for line in process.stdout.splitlines():
        if line.strip():
            json.loads(line)  # would raise if a log line had landed on stdout
    assert "[puzzle-rpc]" in process.stderr, "diagnostics should be on stderr"
