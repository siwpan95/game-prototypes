#!/usr/bin/env python3
"""Import smoke test + dependency reachability gate.

WHY THIS EXISTS
---------------
Prevents "import-crash" regressions like:
  * data/enemies.py once forgot `from typing import Dict`, so
    `systems/movement` (which imports data.enemies) blew up at import time.
  * an earlier F1-startup crash caused by a missing module.
A CI that imports the pygame-free modules on every push catches these
before they ever reach a player.

SCOPE (deliberate)
------------------
Only modules that do NOT depend on pygame are imported:
    core/  systems/  models/  save/  data/
main.py and ui/** are EXCLUDED on purpose -- they `import pygame` and
cannot run on a headless host (no display / no pygame installed).

DEPENDENCY REACHABILITY GATE
----------------------------
Every package listed in requirements.txt is imported by its *module* name.
This catches phantom / misspelled dependencies (e.g. `pygam-ce` would
fail to import even after `pip install`). A MISSING non-exempt package
causes a non-zero exit.

NOTE / KNOWN MISLEADING ITEM (do not edit requirements.txt here; docs = Docu):
  requirements.txt lists `pygame-ce` (the *distribution* name, hyphen).
  The *import* name is `pygame_ce` (underscore). We map hyphen->underscore
  automatically. pygame-ce is also a headless-exempt dependency (needs SDL /
  a display), so on a host without pygame it is reported as a WARNING, not a
  hard failure -- in CI it is installed via pip and imports fine.
"""

import importlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_DIRS = ["core", "systems", "models", "save", "data"]
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"

# Distribution names that legitimately cannot be imported on a headless
# (no-display, no-pygame) dev host. They are WARNINGs, not hard failures,
# because CI installs them via pip. Anything else missing IS a hard fail
# (covers typo / phantom dependency). Set SMOKE_STRICT=1 to force strict.
HEADLESS_EXEMPT = {"pygame", "pygame-ce", "pygame_ce", "sdl2", "pygame-sdl2"}


def collect_modules():
    """Return list of (module_name, file_path) for all .py in SMOKE_DIRS."""
    modules = []
    for d in SMOKE_DIRS:
        base = REPO_ROOT / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT)
            module = ".".join(rel.with_suffix("").parts)
            modules.append((module, path))
    return modules


def run_import_smoke():
    """Import every pygame-free module; return list of (module, path, err)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    failed = []
    for module, path in collect_modules():
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - catch ALL import failures
            failed.append((module, path, repr(exc)))
    return failed


def parse_requirements():
    """Parse bare package (distribution) names from requirements.txt."""
    if not REQUIREMENTS_FILE.is_file():
        return []
    names = []
    for raw in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split("#", 1)[0].strip()      # inline comment
        line = line.split(";", 1)[0].strip()      # env markers
        line = line.split("[", 1)[0].strip()      # extras [..]
        for op in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            line = line.split(op, 1)[0].strip()   # version specifiers
        if line:
            names.append(line)
    return names


def import_candidates(dist_name):
    """Distribution name -> ordered list of possible module import names."""
    if dist_name in ("pygame-ce", "pygame_ce"):
        return ["pygame_ce", "pygame"]
    base = dist_name.replace("-", "_")
    return [base, dist_name]


def run_dependency_gate():
    """Verify each requirement is importable.

    Returns (missing, warnings, ok) where:
      missing  -> hard failures: (dist_name, err)
      warnings -> exempt deps absent on headless host: (dist_name, err)
      ok       -> (dist_name, imported_as)
    """
    strict = os.environ.get("SMOKE_STRICT") == "1"
    missing, warnings, ok = [], [], []
    for name in parse_requirements():
        imported = None
        last_err = None
        for cand in import_candidates(name):
            try:
                importlib.import_module(cand)
                imported = cand
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
        if imported:
            ok.append((name, imported))
        elif name in HEADLESS_EXEMPT and not strict:
            warnings.append((name, repr(last_err)))
        else:
            missing.append((name, repr(last_err)))
    return missing, warnings, ok


def main():
    print("=" * 62)
    print("IMPORT SMOKE + DEPENDENCY REACHABILITY GATE")
    print(f"repo root : {REPO_ROOT}")
    print(f"python    : {sys.version.split()[0]}")
    print("=" * 62)

    # ---- [1/2] Dependency reachability gate ----
    print("\n[1/2] Dependency reachability gate (requirements.txt)")
    missing, warnings, ok = run_dependency_gate()
    for name, imp in ok:
        print(f"  OK   {name} -> import '{imp}'")
    for name, err in warnings:
        print(f"  WARN {name} -> not importable on headless host: {err}")
        print(f"        (exempt: installed via pip in CI; not part of smoke)")
    for name, err in missing:
        print(f"  MISS {name} -> {err}")
    if not parse_requirements():
        print("  (requirements.txt empty or missing)")

    # ---- [2/2] Import smoke (pygame-free modules) ----
    print("\n[2/2] Import smoke (pygame-free modules)")
    failed = run_import_smoke()
    if failed:
        for module, path, err in failed:
            print(f"  FAIL {module} ({path.name}) -> {err}")
    else:
        print(f"  OK: all {len(collect_modules())} pygame-free modules imported.")

    # ---- Verdict ----
    if missing or failed:
        print("\nRESULT: GATE_FAIL")
        sys.exit(1)
    print("\nRESULT: IMPORT_SMOKE_OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
