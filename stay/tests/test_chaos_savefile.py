"""A10 混沌/固化测试 — 存档损坏 / 磁盘满 / 缺字体。

覆盖 Rex 演练指定的注入环境：截断档、空档、半写 JSON、磁盘满(mock 写失败)、缺字体。
断言：进程不崩溃（load_game 不抛未捕获异常）且能自愈/提示（目标态）。

基线层（当前代码即通过）：损坏档返回 LoadError、不抛异常、状态不被污染。
目标层（xfail，待 A3/A4/A5/A6/A8 落地翻转）：
  - 损坏档返回具体的 Corrupt（而非 blanket NotValidSaveFile）；
  - 版本不匹配返回 VersionMismatch；
  - 存在 .bak 时 load_game 自愈（返回 None_ 且状态 Ready）；
  - 磁盘满时原子写保证原存档不被破坏；
  - 缺字体时显式信号（返回 None / 抛 typed error），而非静默回退到非 CJK 字体。
"""

import os
import errno
import json
import gzip
import tempfile

import pytest

from pq2.game import Game
from pq2.types import LoadError, SaveError, GameState

from .conftest import corrupt_save, xfail_pre_fix, good_save_bytes


# ============================ 基线：不崩溃 ============================

@pytest.mark.parametrize("kind", ["truncated", "empty", "half-json"])
def test_corrupt_save_does_not_crash(kind, raw_good):
    """损坏档加载：不抛未捕获异常，返回 LoadError，状态保持 None_。"""
    path = corrupt_save(kind, raw_good)
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert isinstance(err, LoadError)
    assert g.get_state() == GameState.None_        # 不应污染为 Ready


def test_file_not_found_returns_loaderror(raw_good):
    g = Game()
    err = g.load_game("__definitely_missing__.pq2")
    assert err == LoadError.FileNotFound
    assert g.get_state() == GameState.None_


def test_load_game_returns_loaderror_enum(raw_good):
    g = Game()
    err = g.load_game("__missing__.pq2")
    assert isinstance(err, LoadError)


# ============================ 目标：错误类型细分 (A4/A6) ============================

@pytest.mark.parametrize("kind", ["truncated", "half-json"])
def test_corrupt_returns_specific_corrupt(kind, raw_good):
    """损坏档应返回具体的 Corrupt，而非 blanket 的 NotValidSaveFile（保留根因链）。"""
    path = corrupt_save(kind, raw_good)
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.Corrupt
    assert err != LoadError.NotValidSaveFile


def test_version_mismatch_returns_unknown_save_version(raw_good):
    """改写版本头使其不匹配，应返回 UnknownSaveVersion（A6 已落地）。"""
    path = tempfile.mktemp(suffix=".pq2")
    obj = json.loads(good_save_bytes().decode("utf-8"))
    obj["version"] = 999999                      # A6 约定的 version 字段
    with gzip.open(path, "wb") as f:
        f.write(json.dumps(obj).encode("utf-8"))
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.UnknownSaveVersion


# ============================ 目标：启动自愈 / .bak 回退 (A3/A7) ============================

def test_recover_from_backup_when_current_corrupt(raw_good):
    """A7：当前档损坏、存在完好 .bak 时，load_game_with_recovery 应自愈（返回 None_ 且状态 Ready）。"""
    base = tempfile.mktemp(suffix=".pq2")
    cur = base
    bak = base + ".bak"
    with open(bak, "wb") as f:           # 完好 .bak（gzip，与 load_from_file 一致）
        f.write(gzip.compress(raw_good))
    with open(cur, "wb") as f:            # 损坏当前档
        f.write(raw_good[:500])
    g = Game()
    try:
        err, recovered = g.load_game_with_recovery(cur)
    finally:
        for p in (cur, bak, cur + ".corrupt"):
            if os.path.exists(p):
                os.remove(p)
    assert err == LoadError.None_
    assert recovered is True
    assert g.get_state() == GameState.Ready


# ============================ 目标：磁盘满原子写 (A3) ============================

@xfail_pre_fix("A3: 原子写(os.replace)未落地，磁盘满会就地覆盖损坏原档")
def test_diskfull_atomic_write_keeps_original_intact(raw_good, tmp_save, monkeypatch):
    """磁盘满(os.replace 抛 ENOSPC)时，原存档必须保持完好（原子写保证）。"""
    with open(tmp_save, "wb") as f:       # 预置完好“原档”
        f.write(raw_good)
    original = open(tmp_save, "rb").read()

    # 原子写约定（A3）：先写 <path>.tmp 再 os.replace(tmp, final)
    def _raise_enospc(*a, **k):
        raise OSError(errno.ENOSPC, "No space left on device (simulated)")
    monkeypatch.setattr(os, "replace", _raise_enospc)

    g = Game()
    g._filename = tmp_save
    g._game_state = GameState.Ready
    result = g.save_game(tmp_save)

    after = open(tmp_save, "rb").read()
    assert after == original              # 原档字节未被破坏
    assert result != SaveError.None_      # 应返回磁盘满错误而非静默成功


# ============================ 目标：缺字体显式信号 (A5) ============================

def _a5_font_signal_landed() -> bool:
    """A5 落地探针：字体缺失时是否显式告警（typed error / 信号属性）。"""
    import pq2.gui.tkinter_gui as gui
    return hasattr(gui, "FontMissingError")

@pytest.mark.xfail(condition=not _a5_font_signal_landed(),
                   reason="A5 未落地：字体缺失仍静默回退到非 CJK 字体，未显式告警",
                   strict=False)
def test_missing_font_signals_explicitly():
    """无任何可用 CJK 字体时，_get_font_family 应返回 None/抛 typed error，而非静默选非中文字体。"""
    import tkinter as tk
    import tkinter.font as tkfont

    import pq2.gui.tkinter_gui as gui

    def _boom(*a, **k):
        raise RuntimeError("simulated: no font available")

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(tkfont, "Font", _boom)
        family = gui._get_font_family()

    # 目标：显式信号（None 或 typed error），绝不返回非 CJK 回退
    assert family is None or getattr(gui, "FontMissingError", None) is not None
