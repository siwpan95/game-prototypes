#!/usr/bin/env python3
"""Headless self-check for mcclone3d (no GL, no window, no 3dworld engine).

``mcclone3d.world`` / ``kernel`` / ``mesh`` need the ``3dworld`` engine and a
GL context, so this check stays on the engine-free gameplay modules:

* enchantment XP curve: closed-form level inverse, level spans, progress and
  the "spend exactly N levels" invariant,
* deterministic weather state machine (same time -> same state, rain/snow by
  day factor, light-scale multipliers),
* procedural texture atlas: exact byte size, determinism, valid UV rects,
* brewing effect queries (speed / damage / resistance / poison / heal).

Run from the project root:

    python selfcheck.py

Prints ``selfcheck ok: ...`` and returns 0 on success, ``FAIL: ...`` and 1
on failure.
"""
from __future__ import annotations

from mcclone3d import brewing as BW
from mcclone3d import enchant as EN
from mcclone3d import textures as TX
from mcclone3d import weather as W

CHECKS: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name}: {detail or 'condition is false'}")
    CHECKS.append(name)


def check_enchant() -> None:
    check("enchant.base", EN.xp_total(0) == 0 and EN.level_for(0) == 0)
    pairs = [(lv, EN.level_for(EN.xp_total(lv))) for lv in range(0, 41)]
    check("enchant.inverse", all(lv == got for lv, got in pairs),
          [p for p in pairs if p[0] != p[1]][:3])
    check("enchant.span",
          all(EN.xp_span(lv) == 2 * lv + 7 for lv in range(0, 30)))
    check("enchant.progress",
          EN.level_progress(EN.xp_total(5) + 3) == (5, 3, EN.xp_span(5)),
          EN.level_progress(EN.xp_total(5) + 3))
    spends = [(lv, EN.level_for(EN.spend_xp(EN.xp_total(lv) + 3, 1)))
              for lv in range(1, 25)]
    check("enchant.spend_levels", all(got == lv - 1 for lv, got in spends),
          [p for p in spends if p[1] != p[0] - 1][:3])
    check("enchant.spend_floor", EN.spend_xp(EN.xp_total(0), 1) is None)
    check("enchant.offer_cap",
          EN.offer_cap(1, "efficiency") == 1 and EN.offer_cap(3, "efficiency") == 5,
          (EN.offer_cap(1, "efficiency"), EN.offer_cap(3, "efficiency")))


def check_weather() -> None:
    cyc = W.WeatherCycle(seed=2026)
    values = [0.0, 37.3, 90.0, 453.0, 1234.5]
    same = all(cyc.state_at(t) == cyc.state_at(t) for t in values)
    check("weather.deterministic", same)
    check("weather.range",
          all(0.0 <= cyc.intensity_at(t) <= 1.0 for t in range(0, 2000, 5)))
    check("weather.clear", cyc.kind_at(0.0) == W.CLEAR, cyc.kind_at(0.0))
    check("weather.rain_day", cyc.kind_at(453.0, day_factor=1.0) == W.RAIN,
          cyc.kind_at(453.0, day_factor=1.0))
    check("weather.snow_night", cyc.kind_at(453.0, day_factor=0.1) == W.SNOW,
          cyc.kind_at(453.0, day_factor=0.1))
    check("weather.light_scale",
          abs(W.weather_light_scale(W.CLEAR, 1.0) - 1.0) < 1e-9
          and abs(W.weather_light_scale(W.RAIN, 0.5) - 0.86) < 1e-9
          and abs(W.weather_light_scale(W.SNOW, 0.5) - 0.90) < 1e-9)
    state = cyc.state_at(453.0)
    check("weather.state_keys",
          {"kind", "name", "intensity", "light_scale"} <= set(state), state)
    check("weather.advance_noop", cyc.advance(1.0) is None)


def check_textures() -> None:
    layout = TX.LAYOUT
    atlas = TX.build_atlas()
    check("textures.size", layout.size == 128 and len(atlas) == layout.size ** 2 * 4,
          (layout.size, len(atlas)))
    check("textures.tiles", len(layout.names) >= 40, len(layout.names))
    check("textures.deterministic", atlas == TX.build_atlas())
    check("textures.nonempty", any(atlas), "atlas is all zero bytes")
    check("textures.stone_index", "stone" in TX.TILE_INDEX)
    u0, v0, u1, v1 = TX.tile_uv_rect("stone")
    check("textures.uv", 0.0 <= u0 < u1 <= 1.0 and 0.0 <= v0 < v1 <= 1.0,
          (u0, v0, u1, v1))
    check("textures.uv_same_across_res",
          TX.tile_uv_rect("stone", layout) == TX.tile_uv_rect("stone"))


def check_brewing() -> None:
    check("brew.count", len(BW.BREWS) >= 5, len(BW.BREWS))
    check("brew.lookup",
          BW.brew_by_ingredient("sugar").output == "swiftness_potion",
          BW.brew_by_ingredient("sugar").output)
    check("brew.output_lookup",
          BW.brew_by_output("healing_potion").ingredient == "gold_ingot",
          BW.brew_by_output("healing_potion").ingredient)
    check("brew.speed", abs(BW.speed_mult({"swiftness": 5}) - 1.4) < 1e-9)
    check("brew.damage", abs(BW.damage_bonus({"strength": 5}) - 2.0) < 1e-9)
    check("brew.resist", abs(BW.damage_scale({"resistance": 1}) - 0.6) < 1e-9)
    check("brew.poison", abs(BW.dot_rate({"poison": 1}) - 1.0) < 1e-9)
    check("brew.heal",
          abs(BW.instant_heal("healing") - 6.0) < 1e-9
          and abs(BW.instant_heal("swiftness")) < 1e-9)
    check("brew.active_order",
          [n for n, _s in BW.active_order({"poison": 3.0, "healing": 0.0})] == ["poison"],
          BW.active_order({"poison": 3.0, "healing": 0.0}))


def run() -> None:
    check_enchant()
    check_weather()
    check_textures()
    check_brewing()


def main() -> int:
    try:
        run()
    except Exception as exc:  # noqa: BLE001 - self-check must report, not traceback
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(f"selfcheck ok: mcclone3d engine-free core "
          f"({len(CHECKS)} checks: enchant/weather/textures/brewing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
