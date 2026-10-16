"""Terminal client: play the puzzles from a command line, with no pygame and no browser.

This is a renderer for the same view models the web client renders, which is the
point of the view-model contract: a third client needs no changes to the service.
It works both interactively (a TTY: numbered menu, prompts, convenience aliases)
and non-interactively (piped stdin: plain commands, no prompts, JSON available),
so the same code path serves a human and a test.

Commands::

    kinds                      list the puzzle kinds this service offers
    content                    report which content pack is loaded
    new [kind] [difficulty]    start a puzzle (kind omitted = service picks)
    submit <answer>            answer the current puzzle
    act <action> [k=v ...]     run a kind action (reveal row=0 col=1, move direction=left, ...)
    hint                       show the current puzzle's hint
    state                      re-render the current puzzle
    json                       dump the raw snapshot (scripting)
    help | quit

Exit codes: 0 fine · 1 a command failed · 2 usage error · 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable, Iterator, TextIO

from puzzle_service.registry import UnknownKind
from puzzle_service.service import InvalidAction, InvalidAnswer, PuzzleService

__all__ = ["main_cli", "render_snapshot", "TerminalSession"]

DIFFICULTIES = ("easy", "medium", "hard")
INTERACTIVE_ALIASES = {"": "state", "s": "submit", "n": "new", "h": "hint", "q": "quit", "?": "help"}

BOARD_MASK = "·"
FLAG_MARK = "⚑"


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def _cell_text(cell: dict[str, Any], width: int) -> str:
    if cell.get("flagged"):
        text = FLAG_MARK
    elif cell.get("matched"):
        text = cell.get("symbol") or cell.get("text") or ""
    else:
        text = cell.get("text", "")
    return str(text).center(width)


def _render_grid(node: dict[str, Any], out: list[str]) -> None:
    cells = node.get("cells") or []
    if not cells:
        return
    width = max(3, max((len(str(cell.get("text", ""))) for row in cells for cell in row), default=1) + 2)
    for row in cells:
        out.append("  " + "".join(_cell_text(cell, width) for cell in row).rstrip())
    labels = "".join(
        str(cell.get("label", "")).ljust(width)[:width] for cell in cells[0]
    )
    if labels.strip():
        out.append("  " + labels.rstrip())


#: Presentation-only translations for labels the view model carries. The service
#: names fields in English because it does not know which client is rendering it;
#: a client that speaks Chinese supplies its own wording. (The cleaner fix — the
#: service emitting a label *key* instead of a label — is recorded in
#: docs/spec/SPEC-101-platform-roadmap.md as an M2 follow-up.)
_LABEL_ZH = {
    "Answer": "答案",
    "next word (one step at a time)": "下一个单词（一次一步）",
    "or type the word": "或直接输入单词",
}


def _render_node(node: dict[str, Any], out: list[str]) -> None:
    kind = node["type"]
    if kind == "text":
        out.append(str(node.get("text", "")))
    elif kind == "field":
        label = _LABEL_ZH.get(str(node.get("label", "")), node.get("label", "答案"))
        out.append(f"[输入] {label}（类型：{node.get('answer_type', 'str')}）")
    elif kind == "options":
        out.append("[选项]")
        for item in node.get("items", []):
            out.append(f"  {item['index'] + 1}) {item['text']}")
    elif kind in {"list", "clues"}:
        for entry in node.get("items", []):
            out.append(f"  - {entry}")
    elif kind == "grid":
        _render_grid(node, out)
    elif kind == "sequence":
        tokens = node.get("tokens", [])
        out.append("[序列] " + "  ".join(f"{i + 1}:{token}" for i, token in enumerate(tokens)))
        if node.get("clickable"):
            out.append("  用 act " + str(node.get("action")) + " idx1=<序号> idx2=<序号> 交换")
    elif kind == "keyboard":
        states = {"unused": ".", "correct": "+", "wrong": "-"}
        line = " ".join(
            f"{key['letter']}{states.get(key['state'], '?')}" for key in node.get("keys", [])
        )
        out.append("[字母] " + line)
        out.append("  用 act guess_letter letter=<字母>")
    elif kind == "colors":
        swatches = "  ".join(f"{swatch['label']}" for swatch in node.get("swatches", []))
        out.append("[颜色] " + swatches)
        out.append("  用 act press_color color=<颜色>")
    elif kind == "board":
        out.append("[棋盘] 方向：up/down/left/right（act move direction=left）")
        _render_grid(node, out)
    else:  # pragma: no cover - the service validates primitives before they arrive
        out.append(f"[未知原语 {kind}]")


def render_snapshot(snapshot: dict[str, Any], *, show_scoreboard: bool = True) -> str:
    """Turn a snapshot into terminal text (pure function: easy to assert on)."""
    out: list[str] = []
    if show_scoreboard:
        out.append(
            f"— 得分 {snapshot.get('score', 0)} · 连击 {snapshot.get('streak', 0)} · "
            f"已完成 {snapshot.get('solved', 0)} · 用时 {snapshot.get('elapsed', 0)}s"
        )
    view = snapshot.get("view")
    if not view:
        out.append("（当前没有进行中的谜题：用 new [种类] 开始）")
        return "\n".join(out)

    if snapshot.get("kind"):
        out.append(f"== {snapshot['kind']}（第 {snapshot.get('puzzles_started', 1)} 题）")
    for node in view.get("nodes", []):
        _render_node(node, out)
    if view.get("solved"):
        out.append("✔ 已完成 —— 用 new 开下一题")
    result = snapshot.get("last_result") or {}
    if "correct" in result:
        if result["correct"]:
            out.append(
                f"✔ 正确：+{result.get('points', 0)} 分"
                f"（时间奖励 {result.get('time_bonus', 0)}、连击奖励 {result.get('streak_bonus', 0)}）"
            )
        else:
            out.append("✘ 错误：连击已重置")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------


class TerminalSession:
    """Command interpreter over a :class:`PuzzleService`."""

    def __init__(self, service: PuzzleService, session_id: str = "cli"):
        self.service = service
        self.session_id = session_id
        self.last_kind: str | None = None

    def run_command(self, line: str) -> tuple[bool, bool, str]:
        """Execute one command line.

        Returns ``(keep_going, ok, output)``. The success flag is explicit rather
        than inferred from the text: a caller that decides the exit code by
        string-matching the output breaks as soon as the wording changes.
        """
        parts = line.strip().split()
        if not parts:
            return True, True, render_snapshot(self.service.snapshot(self.session_id))
        verb, args = parts[0], parts[1:]

        try:
            if verb == "quit":
                return False, True, "再见。"
            if verb == "help":
                return True, True, (__doc__ or "").split("Commands::")[-1].strip()
            if verb == "kinds":
                return True, True, self._kinds()
            if verb == "content":
                return True, True, json.dumps(
                    self.service.content_summary(), ensure_ascii=False, indent=2
                )
            if verb == "new":
                return True, True, self._new(args)
            if verb == "submit":
                return True, True, self._submit(args)
            if verb == "act":
                return True, True, self._act(args)
            if verb == "hint":
                return True, True, f"提示：{self.service.hint(self.session_id)}"
            if verb == "state":
                return True, True, render_snapshot(self.service.snapshot(self.session_id))
            if verb == "json":
                return True, True, json.dumps(
                    self.service.snapshot(self.session_id), ensure_ascii=False, indent=2
                )
            # Interactive convenience: a bare number answers a multiple-choice puzzle.
            if verb.isdigit():
                return True, True, self._submit([str(int(verb) - 1)])
        except (InvalidAction, InvalidAnswer) as exc:
            return True, False, f"× {_localise(exc)}"
        except KeyError as exc:
            return True, False, f"× 缺少参数或未知种类：{exc}"

        return True, False, f"× 未知命令 {verb!r}；输入 help 看可用命令"

    # --- commands -----------------------------------------------------------

    def _kinds(self) -> str:
        rows = ["种类\t交互\t判定\t可用动作"]
        for kind in self.service.list_kinds():
            rows.append(
                f"{kind['name']}\t{kind['interaction']}\t{kind['answered_by']}\t"
                + (", ".join(kind["actions"]) or "-")
            )
        return "\n".join(rows)

    def _new(self, args: list[str]) -> str:
        kind = args[0] if args else None
        difficulty = args[1] if len(args) > 1 else "medium"
        if difficulty not in DIFFICULTIES:
            raise InvalidAction(f"难度必须是 {'/'.join(DIFFICULTIES)}，收到 {difficulty!r}")
        try:
            snapshot = self.service.new_puzzle(
                session_id=self.session_id, kind=kind, difficulty=difficulty
            )
        except UnknownKind as exc:
            # The registry raises a LookupError carrying the full English list of
            # valid names; the client turns that into one line naming what is wrong.
            known = ", ".join(item["name"] for item in self.service.list_kinds())
            raise InvalidAction(f"没有叫 {kind!r} 的谜题；可选：{known}") from exc
        self.last_kind = snapshot.get("kind")
        return render_snapshot(snapshot)

    def _submit(self, args: list[str]) -> str:
        if not args:
            raise InvalidAction("用法：submit <答案>")
        return render_snapshot(
            self.service.submit(self.session_id, " ".join(args)),
            show_scoreboard=False,
        )

    def _act(self, args: list[str]) -> str:
        if not args:
            raise InvalidAction("用法：act <动作> [key=value ...]")
        action, params = args[0], _parse_params(args[1:])
        snapshot = self.service.perform(self.session_id, action, **params)
        text = render_snapshot(snapshot, show_scoreboard=False)
        if snapshot.get("action_result") is not None:
            text += f"\n  动作返回：{snapshot['action_result']}"
        return text


def _parse_params(args: Iterable[str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for token in args:
        if "=" not in token:
            raise InvalidAction(f"动作参数要写成 key=value，收到 {token!r}")
        key, value = token.split("=", 1)
        params[key] = value
    return params


#: Exact service messages mapped to this client's wording.
_MESSAGE_ZH = {
    "no active puzzle in this session": "当前没有进行中的谜题（先 new）",
}


def _localise(exc: Exception) -> str:
    text = str(exc)
    if text in _MESSAGE_ZH:
        return _MESSAGE_ZH[text]
    # e.g. "kind 'x' does not accept action 'y'; it accepts [...]" — the tail names
    # the valid actions, which is the useful part, so only the prefix is replaced.
    if text.startswith("no active puzzle"):
        return "当前没有进行中的谜题（先 new）"
    return text


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def _iter_input(stream: TextIO, prompt: str) -> Iterator[str]:
    """Yield lines, prompting only when a human is actually there."""
    interactive = getattr(stream, "isatty", lambda: False)()
    while True:
        try:
            if interactive:
                sys.stdout.write(prompt)
                sys.stdout.flush()
            line = stream.readline()
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            return
        if not line:
            return
        yield line


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="text-adventure-cli",
        description="命令行玩文字解谜（复用 Python 谜题服务，不需要 pygame 与浏览器）",
    )
    parser.add_argument("command", nargs="*", help="一条命令；省略则进入交互模式（可从管道读）")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    parser.add_argument("--session", default="cli")
    args = parser.parse_args(argv)

    # UTF-8 on the way out: a Chinese Windows console defaults to a legacy code
    # page, which turns every CJK string into mojibake.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:  # pragma: no cover - stream may not support it
                pass

    try:
        service = PuzzleService(language=args.language)
    except Exception as exc:  # pragma: no cover - environment failure
        print(f"环境错误：无法启动谜题服务：{exc}", file=sys.stderr)
        return 3

    session = TerminalSession(service, session_id=args.session)

    if args.command:
        # `python -m puzzle_service.cli new math easy ';' hint` runs several
        # commands in one process, so a scripted run can keep session state.
        exit_code = 0
        for command in _split_commands(args.command):
            keep_going, ok, output = session.run_command(command)
            if output:
                print(output)
            if not ok:
                exit_code = 1
            if not keep_going:
                break
        return exit_code

    print(render_snapshot(service.snapshot(args.session)))
    print("输入 help 查看命令；quit 退出。")
    for line in _iter_input(sys.stdin, "> "):
        keep_going, _ok, output = session.run_command(line)
        if output:
            print(output)
        if not keep_going:
            return 0
    return 0


def _split_commands(tokens: list[str]) -> list[str]:
    """Split an argv command list on ``;`` into separate command lines."""
    commands: list[list[str]] = [[]]
    for token in tokens:
        if token == ";":
            commands.append([])
        else:
            commands[-1].append(token)
    return [" ".join(command) for command in commands if command]


if __name__ == "__main__":  # python -m puzzle_service.cli
    raise SystemExit(main_cli())
