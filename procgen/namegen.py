"""名字生成器：基于音节拼接，支持多种风格。"""
from __future__ import annotations

import numpy as np

_STYLES = {
    "fantasy": {
        "pre": ["A", "Be", "Ca", "Dra", "E", "Fen", "Gal", "Is", "Mor", "Tho", "Vor", "Zy"],
        "mid": ["a", "el", "il", "om", "ar", "ith", "or", "un", "ae", "yn"],
        "suf": ["dor", "wyn", "ric", "thas", "mir", "loth", "wen", "dil", "rion", "vyn"],
    },
    "sci": {
        "pre": ["X", "Kr", "V", "Z", "Q", "N", "T", "Ar", "Cy", "Bl"],
        "mid": ["o", "ex", "ix", "an", "or", "ul", "ev", "in"],
        "suf": ["on", "ix", "ar", "us", "ex", "oid", "an", "yx"],
    },
    "eastern": {
        "pre": ["长", "风", "青", "玄", "白", "墨", "凌", "苏", "沈", "顾"],
        "mid": ["月", "云", "雪", "川", "夜", "羽", "霜", "霄"],
        "suf": ["轩", "瑶", "尘", "澜", "然", "霜", "璃", "辰"],
    },
}

# 马尔可夫训练语料（每种风格若干样例词，用于字符级转移学习）
_CORPUS = {
    "fantasy": ["aiden", "bard", "caelan", "draven", "elwin", "fenris", "galen",
                "isolde", "morgana", "thorin", "vorian", "zyra", "alwin", "briar",
                "cedric", "elena", "freya", "rowan", "tamsin", "wren"],
    "sci": ["xandar", "krell", "vexis", "zorin", "quill", "nyx", "atlas", "cyber",
            "blip", "orbit", "vega", "zenith", "pulsar", "nova", "ion", "cipher"],
    "eastern": ["changfeng", "qingyun", "xuanye", "baishuang", "moyu", "lingshuang",
                "suyue", "guchen", "shenlan", "fengyao", "yunxi", "hanli"],
}


def _build_markov(words, order: int = 2) -> dict:
    """由语料构建 order 阶字符转移表：key -> [next_char, ...]。"""
    trans = {}
    for w in words:
        w = "^" + w + "$"
        for i in range(len(w) - order):
            key = w[i:i + order]
            trans.setdefault(key, []).append(w[i + order])
    return trans


def _markov_name(trans, rng, min_len: int = 4, max_len: int = 10,
                 order: int = 2, _tries: int = 0) -> str:
    """从转移表采样一个名字（首字母大写）。带长度下限与重试上限。"""
    if _tries > 50:
        return rng.choice(list(trans.keys())).strip("^").capitalize()
    starts = [k for k in trans if k.startswith("^")] or list(trans.keys())
    first = rng.choice(starts)
    out = [first[1:]]          # 去掉起始哨兵 '^'
    key = first                # 滑动窗口，长度恒为 order
    while len(out) < max_len:
        nxts = trans.get(key)
        if not nxts:
            break
        c = rng.choice(nxts)
        if c == "$":
            break
        out.append(c)
        key = (key + c)[-order:]
    name = "".join(out).capitalize()
    return name if len(name) >= min_len else _markov_name(
        trans, rng, min_len, max_len, order, _tries + 1)


class NameGenerator:
    """名字生成器（音节拼接 / 马尔可夫两种算法）。

    参数：
        style:    'fantasy' / 'sci' / 'eastern'
        seed:     随机种子
        syllables: 音节数量（默认 2），仅 syllable 方法使用
        method:   'syllable'（默认，音节拼接）或 'markov'（字符级转移学习）

    示例：
        ng = NameGenerator(style='fantasy', syllables=2)
        names = ng.generate(10)
        mk = NameGenerator(style='sci', method='markov')
        names = mk.generate(10)
    """

    def __init__(self, style: str = "fantasy", seed: int = 0, syllables: int = 2,
                 method: str = "syllable"):
        if style not in _STYLES:
            raise ValueError(f"未知风格: {style}，可选 {list(_STYLES)}")
        if method not in ("syllable", "markov"):
            raise ValueError(f"未知方法: {method}，可选 syllable/markov")
        if syllables < 1:
            raise ValueError("syllables 必须 >= 1")
        self.style = style
        self.parts = _STYLES[style]
        self.syllables = syllables
        self.method = method
        self.rng = np.random.RandomState(seed)
        if method == "markov":
            self._trans = _build_markov(_CORPUS.get(style, _CORPUS["fantasy"]))

    def _one_syllable(self) -> str:
        parts = []
        for i in range(self.syllables):
            p = self.rng.choice(self.parts["pre"])
            if i > 0:
                p = p.lower()  # 仅首音节首字母大写，保证 istitle
            m = self.rng.choice(self.parts["mid"]) if self.rng.rand() < 0.6 else ""
            parts.append(p + m)
        s = self.rng.choice(self.parts["suf"])
        return "".join(parts) + s

    def _one(self) -> str:
        if self.method == "markov":
            return _markov_name(self._trans, self.rng)
        return self._one_syllable()

    def generate(self, n: int = 1) -> list[str]:
        return [self._one() for _ in range(n)]
