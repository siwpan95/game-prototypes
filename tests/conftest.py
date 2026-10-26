"""A10 混沌/固化测试 — 公共 fixtures 与“修复落地”探针。

设计原则（与 Rex 的事故演练 A10 一致）：
- 基线断言（baseline）：对【当前代码】必须可跑且通过，作为回归锚点。
- 目标态断言（target）：断言 A3/A4/A5/A6/A8 落地后的【期望行为】，用 xfail 编码规格；
  一旦对应修复落地（LoadError 增加 Corrupt/VersionMismatch），xfail 会自动翻转为 XPASS，
  提示“该修复已验证有效”，此时移除 xfail 即可。

修复落地探针：fixes_landed() 检测 pq2.types.LoadError 是否新增 Corrupt 成员。
A3/A4/A5/A6/A8 为同一根治批次（code-reviewer + architect），落地后一起翻转。
"""

import os
import gzip
import json
import tempfile

import pytest

from pq2.types import LoadError, SaveError, GameState

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOOD_SAVE = os.path.join(ROOT, "savefile.pq2")  # 仓库内真实完好存档


def fixes_landed() -> bool:
    """A3/A4/A5/A6/A8 根治批次是否落地（以 LoadError.Corrupt 为代理信号）。"""
    return hasattr(LoadError, "Corrupt")


def xfail_pre_fix(reason: str):
    """目标态规格标记：修复未落地时记为预期失败（xfail），落地后变 XPASS。"""
    return pytest.mark.xfail(condition=not fixes_landed(), reason=reason, strict=False)


def good_save_bytes() -> bytes:
    """读取仓库内真实完好存档的原始 gzip 字节。"""
    with gzip.open(GOOD_SAVE, "rb") as f:
        return f.read()


def corrupt_save(kind: str, raw: bytes) -> str:
    """生成三类损坏档，返回临时文件路径（调用方负责清理）。"""
    path = tempfile.mktemp(suffix=".pq2")
    if kind == "truncated":           # 截断 500B（gzip 头损坏/体截断）
        data = raw[:500]
    elif kind == "empty":             # 空档
        data = b""
    elif kind == "half-json":         # gzip 完好但 JSON 被截断
        good = raw.decode("utf-8")
        bad = good[: len(good) // 2]
        data = gzip.compress(bad.encode("utf-8"))
    else:
        raise ValueError(f"unknown corrupt kind: {kind}")
    with open(path, "wb") as f:
        f.write(data)
    return path


@pytest.fixture
def raw_good():
    return good_save_bytes()


@pytest.fixture
def tmp_save():
    path = tempfile.mktemp(suffix=".pq2")
    yield path
    if os.path.exists(path):
        os.remove(path)
    for ext in (".tmp", ".bak"):
        if os.path.exists(path + ext):
            os.remove(path + ext)
