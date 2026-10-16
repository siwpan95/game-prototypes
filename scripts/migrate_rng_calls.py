"""Rewrite built-in bank draws to use the puzzle's own (possibly seeded) generator.

Needed by the daily puzzle: every bank draw must come from the puzzle's generator,
so a date seed reproduces the same puzzle, **without** reseeding process-global
``random`` (which would leak into other sessions).

Why this is AST-aware rather than search-and-replace: the first attempt rewrote
``random.shuffle(...)`` inside ``@staticmethod`` bodies to ``self._rng()``, which
raises NameError — there is no ``self`` in a static method. Here:

1. every ``random.X`` call inside a ``@staticmethod`` becomes ``rng.X``, and that
   method gains an ``rng=None`` parameter defaulting to the module ``random``;
2. every remaining ``random.X`` call becomes ``self._rng().X`` (inside instance
   methods, where ``self`` exists).

Pass 1 runs before pass 2 so pass 2 cannot touch the static bodies, and edits are
applied bottom-up so earlier line numbers stay valid.

Usage: ``--apply`` writes (with ``.rng-bak`` backups), ``--clean`` removes backups.
"""

from __future__ import annotations

import ast
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "text_adventure_zh" / "gameplay_pool",
    ROOT / "text_adventure" / "gameplay_pool",
]
# random_pick.py is the legacy pygame selector, not part of the service registry.
SKIP = {"random_pick.py", "base_puzzle.py", "__init__.py"}

CALL = re.compile(r"(?<![\w.])random\.(choice|choices|randint|shuffle|sample|random|uniform)\(")
PARAM = "rng"


@dataclass
class StaticMethod:
    name: str
    start: int
    end: int
    def_line: int
    body_line: int
    indent: str
    #: The full replacement signature line (built with ast.unparse, so annotations,
    #: defaults, *args and keyword-only markers survive intact).
    signature: str = ""


def _signature_with_rng(node: ast.FunctionDef, original_line: str) -> str:
    """Rebuild ``def ...`` as a one-liner that also accepts ``rng``.

    String surgery on the original line was tried first and broke on a return
    annotation (``def f(a: int) -> list[int]:``): the closing parenthesis of the
    annotation's subscript was mistaken for the parameter list's. Unparsing the
    AST avoids the whole class of mistake.
    """
    args = node.args
    new_args = ast.arguments(
        posonlyargs=list(args.posonlyargs),
        args=list(args.args) + [ast.arg(arg=PARAM, annotation=None)],
        vararg=args.vararg,
        kwonlyargs=list(args.kwonlyargs),
        kw_defaults=list(args.kw_defaults),
        kwarg=args.kwarg,
        defaults=list(args.defaults) + [ast.Constant(value=None)],
    )
    # The added parameter is last and has a default, so the appended default is
    # filled with None — exactly what a bare `rng=None` means.
    new_args.defaults[-1] = ast.Constant(value=None)
    stub = ast.FunctionDef(
        name=node.name,
        args=new_args,
        body=[ast.Pass()],
        decorator_list=[],
        returns=node.returns,
        type_comment=None,
        type_params=getattr(node, "type_params", []),
    )
    ast.fix_missing_locations(stub)
    unparsed = ast.unparse(stub)  # "def f(a, rng=None) -> list[int]:\n    pass"
    first_line = unparsed.splitlines()[0]
    indent = original_line[: len(original_line) - len(original_line.lstrip())]
    return f"{indent}{first_line}\n"


def _find_static_methods(tree: ast.Module, source_lines: list[str]) -> list[StaticMethod]:
    found: list[StaticMethod] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        is_static = any(
            (isinstance(d, ast.Name) and d.id == "staticmethod")
            or (isinstance(d, ast.Attribute) and d.attr == "staticmethod")
            for d in node.decorator_list
        )
        if not is_static:
            continue
        original_line = (
            source_lines[node.lineno - 1] if 0 <= node.lineno - 1 < len(source_lines) else ""
        )
        found.append(
            StaticMethod(
                name=node.name,
                start=min([d.lineno for d in node.decorator_list] + [node.lineno]),
                end=node.end_lineno or node.lineno,
                def_line=node.lineno,
                body_line=node.body[0].lineno,
                indent=" " * node.col_offset,
                signature=_signature_with_rng(node, original_line),
            )
        )
    return found


def patch_source(source: str) -> tuple[str, list[str]]:
    lines = source.splitlines(keepends=True)
    log: list[str] = []

    # --- pass 1: static methods take an explicit generator --------------------
    statics = _find_static_methods(ast.parse(source), lines)
    # Bottom-up, so line numbers above an edit stay valid.
    for method in sorted(statics, key=lambda m: m.start, reverse=True):
        hits = 0
        for index in range(method.start - 1, min(method.end, len(lines))):
            lines[index], count = CALL.subn(rf"{PARAM}.\1(", lines[index])
            hits += count
        if not hits:
            continue
        body_indent = " " * (len(lines[method.body_line - 1]) - len(lines[method.body_line - 1].lstrip()))
        lines.insert(
            method.body_line - 1,
            f"{body_indent}if {PARAM} is None:\n{body_indent}    {PARAM} = random\n",
        )
        lines[method.def_line - 1] = method.signature
        log.append(f"static {method.name}(): +{PARAM} parameter, {hits} call(s)")

    # --- pass 2: instance methods draw through self._rng() --------------------
    patched = "".join(lines)
    static_spans = [
        (m.start, m.end + 1)  # +1 for the guard line inserted above the body
        for m in _find_static_methods(ast.parse(patched), patched.splitlines(keepends=True))
    ]
    lines = patched.splitlines(keepends=True)
    instance_hits = 0
    for index, line in enumerate(lines, start=1):
        if any(start <= index <= end for start, end in static_spans):
            continue
        lines[index - 1], hits = CALL.subn(r"self._rng().\1(", line)
        instance_hits += hits
    if instance_hits:
        log.append(f"instance methods: {instance_hits} call(s)")
    return "".join(lines), log


def main(argv: list[str]) -> int:
    if "--clean" in argv:
        removed = 0
        for directory in TARGETS:
            for backup in directory.glob("*.py.rng-bak"):
                backup.unlink()
                removed += 1
        print(f"removed {removed} backup(s)")
        return 0

    apply = "--apply" in argv
    touched = 0
    for directory in TARGETS:
        for path in sorted(directory.glob("*.py")):
            if path.name in SKIP:
                continue
            original = path.read_text(encoding="utf-8")
            updated, log = patch_source(original)
            if updated == original:
                continue
            touched += 1
            print(f"{'patch' if apply else 'would patch'} {path.relative_to(ROOT)}")
            for entry in log:
                print(f"    {entry}")
            if apply:
                shutil.copy2(path, path.with_suffix(".py.rng-bak"))
                path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"\n{touched} file(s) {'patched' if apply else 'to patch'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
