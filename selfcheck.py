"""Headless self-check for qiandao（签到 · 斯金纳箱）.

The Tkinter entry ``qiandao.pyw`` is loaded with an explicit file loader, so
its module-level helpers (reinforcement formula, reward weighting, JSON/Excel
config loading, history persistence) are exercised without ever calling
``tk.Tk()`` — no window is created.  Every file write is redirected to a
temporary directory through the module's path globals; project data files are
only read.

Run from the project root:  .venv\\Scripts\\python.exe selfcheck.py
"""
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from unittest import mock

ROOT = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(ROOT, "qiandao.pyw")

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_entry():
    """Import qiandao.pyw without triggering its Tk main block."""
    loader = SourceFileLoader("qiandao_entry", ENTRY)
    spec = importlib.util.spec_from_loader("qiandao_entry", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["qiandao_entry"] = module
    loader.exec_module(module)
    return module


mod = load_entry()


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def check_probability():
    """Bounded reinforcement probability: endpoints, bounds, monotonicity."""
    prob = mod.reinforcement_prob
    g = mod.DEFAULT_GLOBAL
    a_min, a_max = g["alpha_min"], g["alpha_max"]

    _check(prob(0, 0) == a_min, f"prob(0,0)={prob(0, 0)} != alpha_min {a_min}")
    for n, c in ((1, 1), (10, 3), (100, 10), (1000, 100)):
        value = prob(n, c)
        _check(a_min <= value < a_max,
               f"prob({n},{c})={value} outside [{a_min}, {a_max})")
    extreme = prob(10**6, 10**6)
    _check(a_max - 1e-6 <= extreme <= a_max,
           f"prob(1e6,1e6)={extreme} did not approach alpha_max {a_max}")

    fixed_c = 5
    previous = prob(0, fixed_c)
    for n in range(1, 60):
        current = prob(n, fixed_c)
        _check(current > previous, f"prob not increasing in n at n={n}")
        previous = current
    fixed_n = 20
    previous = prob(fixed_n, 0)
    for c in range(1, 60):
        current = prob(fixed_n, c)
        _check(current > previous, f"prob not increasing in c at c={c}")
        previous = current

    custom = {"alpha_min": 0.10, "alpha_max": 0.20, "lam_n": 0.5, "gamma_c": 0.5}
    _check(prob(0, 0, custom) == 0.10, "custom alpha_min ignored")
    _check(0.10 <= prob(7, 7, custom) < 0.20, "custom bounds ignored")
    _check(prob(7, 7, custom) != prob(7, 7), "custom parameters had no effect")


def check_reward_weights():
    """choose_reward weights follow the bounded formula, with g fallbacks."""
    g = {"reward_lam_n": 0.04, "reward_gamma_c": 0.02,
         "alpha_min": 0.03, "alpha_max": 0.35,
         "lam_n": 0.04, "gamma_c": 0.025}
    rewards = [
        {"name": "A", "base": 1.0, "gamma": 0.01, "delta": 0.02},
        {"name": "B", "base": 0.5, "gamma": 0.03},
        {"name": "C", "base": 0.25},
    ]
    n, c = 6, 4
    seen = {}

    def fake_choices(population, weights=None, k=1):
        seen["population"] = list(population)
        seen["weights"] = list(weights)
        seen["k"] = k
        return [population[0]]

    with mock.patch.object(mod.random, "choices", fake_choices):
        chosen = mod.choose_reward(n, c, rewards, g)

    _check(chosen == "A", f"choose_reward returned {chosen!r}")
    _check(seen["population"] == ["A", "B", "C"], "candidate names mangled")
    _check(seen["k"] == 1, "choose_reward drew more than one item")
    expected = []
    for rw in rewards:
        gamma = rw.get("gamma", g["reward_gamma_c"])
        delta = rw.get("delta", g["reward_lam_n"])
        expected.append(rw["base"]
                        * (1 - math.exp(-gamma * c))
                        * (1 - math.exp(-delta * n)))
    _check(len(seen["weights"]) == len(expected), "weight count mismatch")
    for got, want in zip(seen["weights"], expected):
        _check(math.isclose(got, want, rel_tol=1e-12),
               f"weight {got} != expected {want}")
    _check(all(w > 0 for w in seen["weights"]),
           "positive n/c produced a zero weight")


def check_config_round_trip():
    """rewards.json (new/legacy/list formats) and the Excel→JSON fallback."""
    real_json = os.path.join(ROOT, "rewards.json")
    with tempfile.TemporaryDirectory() as tmp:
        copy = os.path.join(tmp, "rewards.json")
        shutil.copyfile(real_json, copy)

        with mock.patch.object(mod, "JSON_PATH", copy):
            globals_, rewards = mod.load_config_from_json()
        _check(len(rewards) >= 5, f"only {len(rewards)} rewards parsed")
        _check(globals_["alpha_min"] == 0.03 and globals_["alpha_max"] == 0.35,
               f"global params not loaded: {globals_}")
        for key in ("name", "base", "gamma", "delta"):
            _check(key in rewards[0], f"reward missing {key!r}")

        # Round trip through sync_config_to_json.
        out = os.path.join(tmp, "round_trip.json")
        with mock.patch.object(mod, "JSON_PATH", out):
            mod.sync_config_to_json(globals_, rewards)
            globals2, rewards2 = mod.load_config_from_json()
        _check(globals2 == globals_, "global params lost in the JSON round trip")
        _check(rewards2 == rewards, "rewards lost in the JSON round trip")
        with open(out, encoding="utf-8") as fh:
            written = json.load(fh)
        _check(written["global"] == globals_ and written["rewards"] == rewards,
               "sync_config_to_json wrote the wrong structure")

        # Legacy {"name": {...}} format.
        legacy = os.path.join(tmp, "legacy.json")
        with open(legacy, "w", encoding="utf-8") as fh:
            json.dump({"global": {"alpha_min": 0.05, "alpha_max": 0.4},
                       "金币+10": {"base": 1.0, "gamma": 0.05, "delta": 0.03},
                       "金币+50": {"base": 0.5}}, fh, ensure_ascii=False)
        with mock.patch.object(mod, "JSON_PATH", legacy):
            g_legacy, r_legacy = mod.load_config_from_json()
        _check(g_legacy["alpha_min"] == 0.05, "legacy global ignored")
        _check(len(r_legacy) == 2, f"legacy parse kept {len(r_legacy)} rewards")
        _check(r_legacy[0]["name"] == "金币+10"
               and r_legacy[0]["delta"] == 0.03, "legacy reward mangled")
        _check(r_legacy[1]["gamma"] == g_legacy["reward_gamma_c"]
               and r_legacy[1]["delta"] == g_legacy["reward_lam_n"],
               "legacy defaults were not taken from global params")

        # Bare list format.
        listed = os.path.join(tmp, "list.json")
        with open(listed, "w", encoding="utf-8") as fh:
            json.dump([{"name": "X", "base": 0.2}], fh, ensure_ascii=False)
        with mock.patch.object(mod, "JSON_PATH", listed):
            _, r_list = mod.load_config_from_json()
        _check(len(r_list) == 1 and r_list[0]["name"] == "X",
               "list-format config not parsed")

        # load_config(): missing Excel -> JSON fallback, no project writes.
        missing_excel = os.path.join(tmp, "no_such.xlsx")
        with mock.patch.object(mod, "JSON_PATH", copy), \
                mock.patch.object(mod, "EXCEL_PATH", missing_excel):
            g_fallback, r_fallback = mod.load_config()
        _check(r_fallback == rewards,
               "load_config() JSON fallback returned different rewards")
        _check(g_fallback == globals_, "load_config() fallback globals differ")


def check_history():
    """History persistence plus the no-reward coalescing state machine."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "history.json")
        records = [
            {"time": "2026-01-01 00:00:00", "n": 1, "streak_c": 1,
             "prob": "3.00%", "result": "1次无奖励", "reward": "",
             "reinforced": False, "no_streak": 1},
            {"time": "2026-01-02 00:00:00", "n": 2, "streak_c": 2,
             "prob": "3.20%", "result": "获得奖励", "reward": "金币+10",
             "reinforced": True, "no_streak": 0},
        ]
        with mock.patch.object(mod, "HISTORY_PATH", path):
            mod.save_history(records)
            loaded = mod.load_history()
            _check(loaded == records, "history round trip changed the records")

            missing = os.path.join(tmp, "absent.json")
            with mock.patch.object(mod, "HISTORY_PATH", missing):
                _check(mod.load_history() == [],
                       "missing history file did not return []")

        # _add_history without a Tk window: build a bare instance.
        game = object.__new__(mod.SkinnerGame)
        game.history = []
        game.n = 1
        game.c = 1
        game._refresh_history_table = lambda: None
        with mock.patch.object(mod, "HISTORY_PATH", path):
            game._add_history(0.0314, False, None)
            _check(len(game.history) == 1, "first no-reward was not recorded")
            first = game.history[0]
            _check(first["result"] == "1次无奖励" and first["no_streak"] == 1,
                   f"first no-reward record wrong: {first}")

            game.n = 2
            game._add_history(0.0317, False, None)
            _check(len(game.history) == 1,
                   "consecutive no-rewards were not coalesced")
            _check(game.history[0]["no_streak"] == 2
                   and game.history[0]["result"] == "连续2次无奖励"
                   and game.history[0]["n_end"] == 2,
                   f"coalesced record wrong: {game.history[0]}")

            game.n = 3
            game.c = 3
            game._add_history(0.0330, True, "金币+10")
            _check(len(game.history) == 2, "rewarded sign-in not appended")
            hit = game.history[1]
            _check(hit["reinforced"] is True and hit["reward"] == "金币+10"
                   and hit["no_streak"] == 0 and hit["streak_c"] == 3,
                   f"rewarded record wrong: {hit}")

            persisted = mod.load_history()
        _check(persisted == game.history,
               "coalesced history was not persisted to disk")


CHECKS = (
    ("reinforcement probability", check_probability),
    ("reward weighting", check_reward_weights),
    ("config round trip", check_config_round_trip),
    ("history state machine", check_history),
)


def main():
    passed = []
    for name, func in CHECKS:
        try:
            func()
        except AssertionError as exc:
            print(f"FAIL: {name}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001 - report any unexpected error
            print(f"FAIL: {name}: {type(exc).__name__}: {exc}")
            return 1
        passed.append(name)
    print("selfcheck ok: " + ", ".join(passed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
