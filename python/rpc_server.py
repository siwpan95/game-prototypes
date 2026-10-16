"""JSON-RPC 2.0 over stdio: the bridge between the Cordis host and the puzzles.

The Python side of the split. It owns puzzle state and logic; the Node host owns
orchestration, transport, and rendering. Frames are newline-delimited JSON on
stdin/stdout, so the protocol layer needs nothing but the standard library
(no pip install for the service to be reachable).

Two hard requirements come from the platform it runs on:

* **stdout carries the protocol and nothing else.** Any library that prints to
  stdout corrupts the stream, so this module never prints diagnostics to stdout —
  they go to stderr, which the host forwards to its logger.
* **Encoding is explicit.** On a Chinese Windows console the default encoding is
  a legacy code page; reading or writing UTF-8 without saying so would mangle
  every CJK string that crosses the bridge.

Request/response shapes follow JSON-RPC 2.0: a request carries ``method`` and
optionally ``params``, and the reply is exactly one of ``result`` or ``error``.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, TextIO

if __package__ in (None, ""):  # running as a script: make the project importable
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

from puzzle_service.registry import UnknownKind, UnknownLanguage
from puzzle_service.service import InvalidAction, InvalidAnswer, PuzzleService

__all__ = ["RpcServer", "METHODS"]

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVICE_ERROR = -32000


class RpcError(Exception):
    """An error that is reported to the caller as a JSON-RPC error object."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class RpcServer:
    """Serves the puzzle service over newline-delimited JSON frames."""

    def __init__(self, language: str = "zh", stdin: TextIO | None = None,
                 stdout: TextIO | None = None, stderr: TextIO | None = None):
        self.service = PuzzleService(language=language)
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self._methods: dict[str, Callable[..., Any]] = {
            "puzzle.list": self._list,
            "puzzle.new": self._new,
            "puzzle.submit": self._submit,
            "puzzle.action": self._action,
            "puzzle.hint": self._hint,
            "puzzle.state": self._state,
            "puzzle.reset": self._reset,
            "content.info": self._content_info,
            "session.reset": self._reset,
            "server.ping": self._ping,
            "server.info": self._info,
            "server.shutdown": self._shutdown,
        }
        self._running = True

    # --- method surface ------------------------------------------------------

    def _list(self) -> list[dict[str, Any]]:
        return self.service.list_kinds()

    def _new(self, session_id: str = "default", kind: str | None = None,
             difficulty: str = "medium") -> dict[str, Any]:
        return self.service.new_puzzle(
            session_id=session_id, kind=kind, difficulty=difficulty
        )

    def _submit(self, session_id: str = "default", answer: Any = None) -> dict[str, Any]:
        return self.service.submit(session_id, answer)

    def _action(self, session_id: str = "default", action: str | None = None,
                **params: Any) -> dict[str, Any]:
        if not action:
            raise RpcError(INVALID_PARAMS, "puzzle.action requires 'action'")
        return self.service.perform(session_id, action, **params)

    def _hint(self, session_id: str = "default") -> dict[str, Any]:
        return {"hint": self.service.hint(session_id)}

    def _state(self, session_id: str = "default") -> dict[str, Any]:
        return self.service.snapshot(session_id)

    def _reset(self, session_id: str = "default") -> dict[str, Any]:
        return self.service.reset(session_id)

    def _content_info(self) -> dict[str, Any]:
        return self.service.content_summary()

    def _ping(self) -> dict[str, Any]:
        return {"pong": True}

    def _info(self) -> dict[str, Any]:
        return {
            "language": self.service.language,
            "kinds": len(self.service.list_kinds()),
            "protocol": "jsonrpc-2.0/ndjson",
            "content": self.service.content_summary(),
        }

    def _shutdown(self) -> dict[str, Any]:
        self._running = False
        return {"bye": True}

    # --- dispatch ------------------------------------------------------------

    def handle(self, request: Any) -> dict[str, Any] | None:
        """Answer one decoded frame. Returns ``None`` for notifications."""
        if not isinstance(request, dict):
            return _error_response(None, INVALID_REQUEST, "request must be an object")

        request_id = request.get("id")
        method = request.get("method")
        if not isinstance(method, str) or not method:
            return _error_response(request_id, INVALID_REQUEST, "missing method")

        params = request.get("params") or {}
        if not isinstance(params, dict):
            return _error_response(request_id, INVALID_PARAMS, "params must be an object")

        handler = self._methods.get(method)
        if handler is None:
            return _error_response(
                request_id, METHOD_NOT_FOUND, f"unknown method {method!r}"
            )

        try:
            result = handler(**params)
        except RpcError as exc:
            return _error_response(request_id, exc.code, exc.message, exc.data)
        except (InvalidAnswer, UnknownKind, UnknownLanguage) as exc:
            # Naming a kind or language that does not exist is the caller's
            # mistake, not an internal fault: report -32602, not -32603.
            return _error_response(request_id, INVALID_PARAMS, str(exc))
        except InvalidAction as exc:
            return _error_response(request_id, SERVICE_ERROR, str(exc))
        except TypeError as exc:
            # Wrong keyword names reach the handler as a TypeError; that is the
            # caller's mistake, not an internal fault, so do not report -32603.
            return _error_response(request_id, INVALID_PARAMS, f"bad parameters: {exc}")
        except Exception as exc:  # noqa: BLE001 - a crash must not kill the bridge
            self._log(f"internal error on {method}: {traceback.format_exc()}")
            return _error_response(request_id, INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")

        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def serve_forever(self) -> int:
        """Read frames until stdin closes or ``server.shutdown`` arrives."""
        self._log(f"puzzle rpc ready (language={self.service.language}, "
                  f"kinds={len(self.service.list_kinds())})")
        for line in self.stdin:
            text = line.strip()
            if not text:
                continue
            try:
                request = json.loads(text)
            except json.JSONDecodeError as exc:
                self._write(_error_response(None, PARSE_ERROR, f"invalid JSON: {exc}"))
                continue

            response = self.handle(request)
            if response is not None:
                self._write(response)
            if not self._running:
                break
        self._log("puzzle rpc stopped")
        return 0

    # --- io ------------------------------------------------------------------

    def _write(self, payload: dict[str, Any]) -> None:
        self.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.stdout.flush()

    def _log(self, message: str) -> None:
        self.stderr.write(f"[puzzle-rpc] {message}\n")
        self.stderr.flush()


def _error_response(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


METHODS = (
    "puzzle.list",
    "puzzle.new",
    "puzzle.submit",
    "puzzle.action",
    "puzzle.hint",
    "puzzle.state",
    "puzzle.reset",
    "server.info",
    "server.ping",
    "server.shutdown",
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    language = "zh"
    for index, arg in enumerate(args):
        if arg == "--language" and index + 1 < len(args):
            language = args[index + 1]
        elif arg.startswith("--language="):
            language = arg.split("=", 1)[1]
    try:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover - stdin/stdout may be a pipe without reconfigure
        pass
    return RpcServer(language=language).serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
