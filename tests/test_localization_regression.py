"""A10 附加 — localization.translate() 回归用例。

Rex 演练要求：增加“复合串 / 缺键 / 子串冲突”回归用例，
断言输出为完整中文而非中英混杂（实测 "Seek the Magic Orb" → "寻找 the Magic 法球"）。

基线层（当前即通过）：整词精确匹配、未知键原样返回、全由已知键构成的复合串输出全中文。
目标层（xfail，待 A11 落地翻转）：
  - 词边界匹配：仅含某键为子串的其它词（如 "React" 含 "Act"）不被内部误替换；
  - 缺键上报：缺失键被显式收集/告警，而非静默回退英文；
  - 真实复合串（"Seek the Magic Orb"）最终输出为完整中文。

A11（整词/词边界匹配 + 缺键监控）由 tech-writer(i18n) 负责；落地后 xfail 翻转为 XPASS。
"""

import pytest

from pq2.localization import translate, get_cn

from .conftest import xfail_pre_fix


def _i18n_fixes_landed() -> bool:
    """A11 落地探针：localization 是否提供「词边界翻译 / translate 缺键上报」能力。
    注意：本批次仅落地 get_missing_keys（显式 get_cn 监控），translate() 的
    词边界匹配与缺键上报（translate_with_report）未实现，故探针以它为代理信号，
    避免 get_missing_keys 落地后把词边界用例误翻转为运行失败。
    """
    import pq2.localization as loc
    return hasattr(loc, "translate_with_report")


def _xfail_i18n(reason: str):
    return pytest.mark.xfail(condition=not _i18n_fixes_landed(), reason=reason, strict=False)


# ============================ 基线：当前即正确 ============================

def test_exact_key_match():
    assert translate("Loading") == "加载中"


def test_unknown_key_returns_self():
    assert translate("ZzzQuantum") == "ZzzQuantum"
    assert get_cn("ZzzQuantum") == "ZzzQuantum"


def test_composite_of_known_keys_is_full_chinese():
    """全部由已知键构成的复合串，当前贪婪替换也应已输出全中文。"""
    out = translate("Exterminate Shoelaces")
    assert out == "消灭 鞋带术"
    assert not any(c.isascii() and c.isalpha() for c in out)


# ============================ 目标：词边界匹配 (A11) ============================

@_xfail_i18n("A11 未落地：translate 仍按子串贪婪替换，会误伤含键的其它词")
def test_no_internal_substring_replacement():
    """含某键为子串的其它词不应被内部误替换（词边界匹配）。"""
    assert translate("React") == "React"               # 不应 "R章节"（Act 在内部）
    assert translate("Exterminator") == "Exterminator"  # 不应 "消灭ator"


# ============================ 目标：缺键上报 (A11) ============================

@_xfail_i18n("A11 未落地：缺键仅静默回退英文，无上报/监控")
def test_missing_key_is_reported():
    """缺失键应被显式收集，供 i18n 监控，而非静默丢弃。"""
    import pq2.localization as loc
    translate("Completely Unknown Phrase Zxcv")
    missing = loc.get_missing_keys()
    assert "Completely Unknown Phrase Zxcv" in missing


# ============================ 目标：真实复合串全中文 (A11 + 字典覆盖) ============================

@_xfail_i18n("A11 未落地 + 字典未覆盖 the/Magic：仍中英混杂")
def test_real_world_composite_full_chinese():
    """演练实证串：最终应为完整中文。"""
    out = translate("Seek the Magic Orb")
    assert out == "寻找 魔法 法球"
    assert not any(c.isascii() and c.isalpha() for c in out)
