# -*- coding: utf-8 -*-
"""test_m2_daynight — 昼夜循环：light_factor / is_night / time_str / 序列化（headless，T-M2-03）。"""

from __future__ import annotations

from mcclone.core.daynight import DayNight


def test_light_factor_noon_is_one():
    d = DayNight()
    d._t = 0.5
    assert abs(d.light_factor() - 1.0) < 1e-9


def test_light_factor_midnight_is_zero():
    d = DayNight()
    d._t = 0.0
    assert d.light_factor() == 0.0
    d._t = 1.0
    assert d.light_factor() == 0.0


def test_light_factor_in_range():
    d = DayNight()
    for i in range(0, 100):
        d._t = i / 100.0
        lf = d.light_factor()
        assert 0.0 <= lf <= 1.0


def test_is_night():
    d = DayNight()
    d._t = 0.0
    assert d.is_night() is True
    d._t = 0.5
    assert d.is_night() is False
    d._t = 0.8
    assert d.is_night() is True
    d._t = 0.24
    assert d.is_night() is True    # <0.25 夜
    d._t = 0.25
    assert d.is_night() is False   # 边界：>=0.25 昼
    d._t = 0.749
    assert d.is_night() is False
    d._t = 0.75
    assert d.is_night() is True


def test_time_str():
    d = DayNight()
    d._t = 0.0
    assert d.time_str() == "00:00"
    d._t = 0.5
    assert d.time_str() == "12:00"
    d._t = 0.25
    assert d.time_str() == "06:00"


def test_update_wraps():
    d = DayNight(day_length_sec=600)
    d._t = 0.99
    d.update(600 * 0.02)          # 推进 0.02 → 1.01 mod 1 = 0.01
    assert abs(d.t() - 0.01) < 1e-9


def test_to_dict_from_dict_roundtrip():
    d = DayNight(300)
    d._t = 0.37
    d2 = DayNight.from_dict(d.to_dict())
    assert abs(d2.t() - 0.37) < 1e-9
    assert d2.day_length_sec == 300


def test_default_roundtrip():
    d = DayNight()
    d._t = 0.6
    d2 = DayNight.from_dict(d.to_dict())
    assert d2.t() == 0.6
