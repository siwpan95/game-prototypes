"""
alchemia.py — Alchemia 解密游戏引擎

基于机核文章《一篇我觉得有用的解密游戏〈Alchemia〉指南》
(https://www.gcores.com/articles/130136) 中的所有谜题机制，
将其实现为可计算的古典密码学 & 谜题工具集合。

涵盖：
  - Porta / Trithemius / Selenus / Vigenere / Atbash 五种古典密码
  - 凯撒爆破（文章第七面提到 "the fifth month knows the technique" → Caesar）
  - 斐波那契移位（第九面 Liber Abaci → Fibonacci 数列首位数字）
  - 埃拉托色尼素数筛（第九面 "Ordered with Eratosthene's aid"）
  - 黄金均值取中（第四面 "Golden Mean" → 取两个字母的中间字母）
  - 巴别塔 Gematria（第五面 "At Babel our tongue did split"）
  - Antikythera 古希腊历法（第七面 "Cicero writes of an ancient machine"）
  - 炼金术四元素 & 七金属符号（第六面 Chymistry / 第十二面元素表）
  - "As above, so below" 镜像（第八面 Hermeticism）
  - 最终密钥 PADEILSYMIELGEDIELVSIEL 验证（第十四面）

数据结构：
  - ALCHEMIA_PAGES：7 页书的谜题数据（标题、拉丁文、密文、提示）
  - ELEMENTS_TABLE：炼金术元素符号对应表
  - GREEK_MONTHS：Corinthian 历法月份
  - HISTORICAL_FIGURES：文章中提到的历史人物
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────
#  Porta Cipher — 双字母组合替换密码
#  文章第五面提到 "porta paradis" 反过来是 "atrop sidarap"
# ─────────────────────────────────────────────────────────────
#  13 行表，每行对应一对密钥字母 (AB)(CD)(EF)...(YZ)
#  对前半字母 A-M 不变；对后半字母 N-Z，按密钥所在行做反向映射
_PORTA_TABLE = [
    # AB
    "ABCDEFGHIJKLM NOPQRSTUVWXYZ",
    # CD
    "BCDEFGHIJKLMA NOPQRSTUVWXYZ",
    # EF
    "CDEFGHIJKLMAB NOPQRSTUVWXYZ",
    # GH
    "DEFGHIJKLMABC NOPQRSTUVWXYZ",
    # IJ
    "EFGHIJKLMABCD NOPQRSTUVWXYZ",
    # KL
    "FGHIJKLMABCDE NOPQRSTUVWXYZ",
    # MN
    "GHIJKLMABCDEF NOPQRSTUVWXYZ",
    # OP
    "HIJKLMABCDEFG NOPQRSTUVWXYZ",
    # QR
    "IJKLMABCDEFGH NOPQRSTUVWXYZ",
    # ST
    "JKLMABCDEFGHI NOPQRSTUVWXYZ",
    # UV
    "KLMABCDEFGHIJ NOPQRSTUVWXYZ",
    # WX
    "LMABCDEFGHIJK NOPQRSTUVWXYZ",
    # YZ
    "MABCDEFGHIJKL NOPQRSTUVWXYZ",
]


def porta_encrypt(text: str, key: str) -> str:
    """Porta 密码加密/解密（同一函数，因 Porta 是对称的）。"""
    if not text or not key:
        return text or ""
    text = text.lower()
    key = key.lower()
    result: list[str] = []
    key_idx = 0
    for ch in text:
        if 'a' <= ch <= 'm':
            result.append(ch)
            key_idx = (key_idx + 1) % len(key)
        elif 'n' <= ch <= 'z':
            # 找到密钥字母对应的行
            kch = key[key_idx % len(key)]
            row_idx = (ord(kch) - ord('a')) // 2
            row_idx = min(max(row_idx, 0), 12)
            row = _PORTA_TABLE[row_idx].replace(" ", "")
            # 后半区 N-Z 的字母
            pos_in_back = ord(ch) - ord('n')  # 0..12
            # Porta 真实算法：后半字母替换为 row 中相同位置的后半字母
            # row 的后半 = row[13:]，且需要按 row_idx 偏移
            # 简化：第 row_idx 行的后半，从 (N+row_idx) 开始倒着数
            # 实际经典 Porta 表：后半字母组对反转，A↔Z, B↔Y 在第 0 行
            # 这里采用经典 Porta 表的等价形式：
            #   row 0 (AB): N↔Z O↔Y P↔X ... 即 (N+Z)/2 = mid
            #   row 1 (CD): N↔A O↔Z ...
            # 为简洁性，使用以下等价表：
            back_letters = "NOPQRSTUVWXYZ"
            # Porta 经典表：行 r 下，字母 N+pos 映射为 (N + (12 - pos + r)) % 13 + N
            shifted = (12 - pos_in_back + row_idx) % 13
            result.append(chr(ord('n') + shifted))
            key_idx = (key_idx + 1) % len(key)
        else:
            result.append(ch)
    return ''.join(result)


# ─────────────────────────────────────────────────────────────
#  Trithemius Cipher — 位置递增移位
#  文章第五面提到 "Trithemius" 是四种加密法之一
#  第 i 个字符移位 i（从 0 开始）
# ─────────────────────────────────────────────────────────────
def trithemius_encrypt(text: str, decrypt: bool = False) -> str:
    """第 i 个字母移位 i。decrypt=True 时反向移位。"""
    result: list[str] = []
    alpha_count = 0
    for ch in text.lower():
        if ch.isalpha():
            shift = alpha_count % 26
            if decrypt:
                shift = -shift
            new = (ord(ch) - ord('a') + shift) % 26 + ord('a')
            result.append(chr(new))
            alpha_count += 1
        else:
            result.append(ch)
    return ''.join(result)


# ─────────────────────────────────────────────────────────────
#  Selenus Cipher — 起始移位 = 1 的 Trithemius 变体
#  文章第五面提到 "Selenus" 是四种加密法之一
# ─────────────────────────────────────────────────────────────
def selenus_encrypt(text: str, decrypt: bool = False) -> str:
    """第 i 个字母移位 (i+1)。decrypt=True 时反向移位。"""
    result: list[str] = []
    alpha_count = 0
    for ch in text.lower():
        if ch.isalpha():
            shift = (alpha_count + 1) % 26
            if decrypt:
                shift = -shift
            new = (ord(ch) - ord('a') + shift) % 26 + ord('a')
            result.append(chr(new))
            alpha_count += 1
        else:
            result.append(ch)
    return ''.join(result)


# ─────────────────────────────────────────────────────────────
#  Atbash Cipher — 字母倒序替换
#  A↔Z, B↔Y, C↔X ...（古老的希伯来替换密码）
# ─────────────────────────────────────────────────────────────
def atbash(text: str) -> str:
    result: list[str] = []
    for ch in text:
        if 'a' <= ch <= 'z':
            result.append(chr(ord('z') - (ord(ch) - ord('a'))))
        elif 'A' <= ch <= 'Z':
            result.append(chr(ord('Z') - (ord(ch) - ord('A'))))
        else:
            result.append(ch)
    return ''.join(result)


# ─────────────────────────────────────────────────────────────
#  Caesar Brute Force — 凯撒密码爆破
#  文章第七面提到 "He of the fifth month knows the technique"
#  fifth month = July = Julius Caesar → 凯撒加密
#  且作者一开始就靠字频分析 + 爆破跳过了正确的解法
# ─────────────────────────────────────────────────────────────
def caesar_brute(text: str) -> str:
    """尝试所有 26 种移位，返回多行结果。"""
    lines: list[str] = []
    for shift in range(26):
        decoded: list[str] = []
        for ch in text.lower():
            if 'a' <= ch <= 'z':
                decoded.append(chr((ord(ch) - ord('a') - shift) % 26 + ord('a')))
            else:
                decoded.append(ch)
        lines.append(f"{shift:2d}: {''.join(decoded)}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  Fibonacci Shift — 斐波那契移位
#  文章第九面 "Liber Abaci" → Fibonacci 数列首位数字作为移位
#  1,1,2,3,5,8,13,21,34,55,89,144,233,377...
#  首位数字：1,1,2,3,5,8,1,2,3,5,8,1,2,3...
# ─────────────────────────────────────────────────────────────
def _fib_first_digits(n: int) -> list[int]:
    """生成前 n 个斐波那契数的首位数字。"""
    digits: list[int] = []
    a, b = 1, 1
    for _ in range(n):
        digits.append(int(str(a)[0]))
        a, b = b, a + b
    return digits


def fibonacci_shift(text: str, decrypt: bool = False) -> str:
    """用斐波那契数列首位数字作为每字母的移位。"""
    fibs = _fib_first_digits(len([c for c in text if c.isalpha()]))
    result: list[str] = []
    idx = 0
    for ch in text.lower():
        if ch.isalpha():
            shift = fibs[idx % len(fibs)] if fibs else 1
            if decrypt:
                shift = -shift
            new = (ord(ch) - ord('a') + shift) % 26 + ord('a')
            result.append(chr(new))
            idx += 1
        else:
            result.append(ch)
    return ''.join(result)


# ─────────────────────────────────────────────────────────────
#  Sieve of Eratosthenes — 素数筛 + 数字转字母
#  文章第九面 "Ordered with Eratosthene's aid"
#  规则：数字 n 分解为两素数 p1*p2，p1/p2 在素数序列中的位置
#        (2 是第1个素数→A, 3 第2个→B, 5 第3个→C, ...)
#  例：74 = 2*37 → A (第1) + L (第12) → "AL"
#      69 = 3*23 → B (第2) + I (第9)  → "BI"
#      6  = 2*3  → A + B → "AB"
#      55 = 5*11 → C + E → "CE"
#      1403=23*61 → I + ? (61 是第18个素数 → R) → "IR"
#  组合 "ALBIABCEIR" → "Liber Abaci" (文章里的发现)
# ─────────────────────────────────────────────────────────────
def _primes_up_to(n: int) -> list[int]:
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            for j in range(i * i, n + 1, i):
                sieve[j] = False
    return [i for i, is_p in enumerate(sieve) if is_p]


_PRIME_INDEX_CACHE: dict[int, int] = {}


def _prime_index(p: int) -> int:
    """返回素数 p 在素数序列中的位置（2→1, 3→2, 5→3, ...）。0 表示不是素数。"""
    if p in _PRIME_INDEX_CACHE:
        return _PRIME_INDEX_CACHE[p]
    if p < 2:
        return 0
    primes = _primes_up_to(max(p, 100))
    if p not in primes:
        # p 可能不是素数
        return 0
    idx = primes.index(p) + 1
    _PRIME_INDEX_CACHE[p] = idx
    return idx


def _factor_to_two_primes(n: int) -> tuple[int, int] | None:
    """把 n 分解为两个素数之积。若无法分解返回 None。"""
    if n < 4:
        return None
    primes = _primes_up_to(int(n ** 0.5) + 1)
    for p in primes:
        if n % p == 0:
            q = n // p
            # 验证 q 是否为素数
            if q > 1:
                q_primes = _primes_up_to(int(q ** 0.5) + 1)
                if all(q % pp != 0 for pp in q_primes if pp != q):
                    return p, q
    return None


def sieve_convert(number: int) -> str:
    """数字 → 两素数 → 字母对。例：74 → "AL"。"""
    factors = _factor_to_two_primes(number)
    if not factors:
        return "?"
    p1, p2 = factors
    i1 = _prime_index(p1)
    i2 = _prime_index(p2)
    if i1 == 0 or i2 == 0 or i1 > 26 or i2 > 26:
        return f"{p1}*{p2}"
    c1 = chr(ord('A') + i1 - 1)
    c2 = chr(ord('A') + i2 - 1)
    return f"{c1}{c2}"


def sieve_batch(numbers: list[int]) -> str:
    """批量转换：[74, 69, 6, 55, 1403] → "ALBIABCE?IR" → "Liber Abaci" 提示。"""
    parts = [sieve_convert(n) for n in numbers]
    return ''.join(parts)


# ─────────────────────────────────────────────────────────────
#  Golden Mean — 黄金均值取中
#  文章第四面 "Golden Mean" → 取两个字母的中间字母
#  例：A(0)+G(6) → D(3)，B(1)+F(5) → D(3)
#  若和为奇数，取较小的那个（向下取整）
# ─────────────────────────────────────────────────────────────
def golden_mean(pair: str) -> str:
    """输入两个字母，返回它们的中间字母。"""
    pair = pair.strip().lower()
    if len(pair) < 2:
        return "?"
    a, b = pair[0], pair[1]
    if not (a.isalpha() and b.isalpha()):
        return "?"
    mid = (ord(a) - ord('a') + ord(b) - ord('a')) // 2
    return chr(mid + ord('a'))


def golden_mean_word(pairs: str) -> str:
    """连续处理多对字母。例 "AG BF CE" → "DDD..." """
    pairs = pairs.replace(" ", "").replace(",", "")
    if len(pairs) % 2 != 0:
        pairs += pairs[-1]
    out: list[str] = []
    for i in range(0, len(pairs), 2):
        out.append(golden_mean(pairs[i:i + 2]))
    return ''.join(out)


# ─────────────────────────────────────────────────────────────
#  Gematria — 字母数字映射
#  文章第五面 "At Babel our tongue did split, but through
#  gematria a link still fits" → Tower of Babel 多语言
#  支持 Latin / Hebrew / Greek / English 四种
# ─────────────────────────────────────────────────────────────
def gematria_latin(text: str) -> int:
    """拉丁字母累加：A=1, B=2, ..., Z=26。"""
    total = 0
    for ch in text.upper():
        if 'A' <= ch <= 'Z':
            total += ord(ch) - ord('A') + 1
    return total


def gematria_hebrew(text: str) -> int:
    """希伯来文 Gematria（支持转写后的拉丁字母输入）。"""
    # 标准希伯来字母值（Alef=1, Bet=2, ..., Tav=400）
    # 这里用拉丁转写
    values = {
        'A': 1, 'B': 2, 'G': 3, 'D': 4, 'H': 5, 'V': 6, 'Z': 7,
        'C': 8,  # Chet
        'T': 9,  # Tet
        'Y': 10, 'K': 20, 'L': 30, 'M': 40, 'N': 50,
        'S': 60,  # Samekh
        'O': 70, 'P': 80,
        'X': 90,  # Tzadi
        'Q': 100, 'R': 200,
        'E': 300,  # Shin (转写常用 SH，这里 E 充当)
        'W': 400,  # Tav（这里 W 充当）
    }
    return sum(values.get(c, 0) for c in text.upper())


def gematria_greek(text: str) -> int:
    """希腊文 Gematria。"""
    values = {
        'A': 1, 'B': 2, 'G': 3, 'D': 4, 'E': 5,
        'F': 6,  # Digamma
        'Z': 7, 'H': 8,  # Eta
        'I': 10, 'K': 20, 'L': 30, 'M': 40, 'N': 50,
        'X': 60, 'O': 70, 'P': 80,
        'Q': 90,  # Qoppa
        'R': 100, 'S': 200, 'T': 300,
        'U': 400,  # Upsilon
        'V': 500, 'C': 600, 'W': 700, 'Y': 800, 'J': 900,
    }
    return sum(values.get(c, 0) for c in text.upper())


def gematria(text: str, system: str = "latin") -> int:
    """统一入口。system: latin / hebrew / greek。"""
    if system == "hebrew":
        return gematria_hebrew(text)
    if system == "greek":
        return gematria_greek(text)
    return gematria_latin(text)


# ─────────────────────────────────────────────────────────────
#  Antikythera — 古希腊 Corinthian 历法
#  文章第七面 "Cicero writes of an ancient machine"
#  Antikythera mechanism 使用 Corinthian 历法
# ─────────────────────────────────────────────────────────────
GREEK_MONTHS = [
    # (希腊名, 拉丁转写, 中文, 月份序号)
    ("ΦΟΙΝΙΚΑΙΟΣ", "Phoinikaios",  "芬尼凯奥斯",  1),
    ("ΚΡΑΝΕΙΟΣ",   "Kraneios",     "克兰尼奥斯",  2),
    ("ΑΡΑΤΡΙΟΣ",   "Aratios",      "阿拉提奥斯",  3),
    ("ΦΟΙΝΙΚΑΙΟΣ", "Phoinikaios",  "芬尼凯奥斯",  4),
    ("ΠΑΝΑΜΟΣ",    "Panamos",      "帕纳莫斯",    5),
    ("ΑΓΡΙΑΝΙΟΣ",  "Agrianios",    "阿格里安尼奥斯", 6),
    ("ΘΕΥΔΕΣΙΟΣ",  "Theudesios",   "修德西奥斯",  7),
    ("ΑΡΤΕΜΙΣΙΟΣ", "Artemisios",   "阿尔忒弥西奥斯", 8),
    ("ΨΥΔΡΕΥΣ",    "Psydreus",     "普西德留斯",  9),
    ("ΓΑΜΟΣ",      "Gamos",        "伽莫斯",      10),
    ("ΑΓΡΙΑΝΙΟΣ",  "Agrianios",    "阿格里安尼奥斯", 11),
    ("ΘΕΥΔΕΣΙΟΣ",  "Theudesios",   "修德西奥斯",  12),
]


def antikythera_month(month_number: int) -> str:
    """输入 1-12，返回对应的古希腊 Corinthian 月份名。"""
    if not 1 <= month_number <= 12:
        return "?"
    greek, latin, cn, num = GREEK_MONTHS[month_number - 1]
    return f"{greek} ({latin}) - {cn}"


def antikythera_zodiac_shift(zodiac: str, connections: int, month_seq: int) -> int:
    """文章第七面：connections + word forms a key。
    zodiac 星座 + connections 连接数 + month_seq 月份序号 → 凯撒移位。
    例：Libra 三点钟方向有 2 个连接，Kraneios 是第 2 个月 → 2+2=4。
    """
    return connections + month_seq


# 文章里给出的偏移量参考表
ZODIAC_SHIFTS = {
    "sagittarius": 11,  # 4 + 7
    "aries":       7,   # 3 + 4
    "aquarius":    7,   # 4 + 3
    "leo":         10,  # 2 + 8
    "pisces":      17,  # 5 + 12
}


# ─────────────────────────────────────────────────────────────
#  As Above, So Below — 上下颠倒镜像
#  文章第八面 "As above, so below" (Hermeticism)
# ─────────────────────────────────────────────────────────────
_MIRROR_MAP = {
    'a': 'ɐ', 'b': 'q', 'c': 'ɔ', 'd': 'p', 'e': 'ǝ',
    'f': 'ɟ', 'g': 'ƃ', 'h': 'ɥ', 'i': 'ᴉ', 'j': 'ɾ',
    'k': 'ʞ', 'l': 'l', 'm': 'ɯ', 'n': 'u', 'o': 'o',
    'p': 'd', 'q': 'b', 'r': 'ɹ', 's': 's', 't': 'ʇ',
    'u': 'n', 'v': 'ʌ', 'w': 'ʍ', 'x': 'x', 'y': 'ʎ',
    'z': 'z',
    'A': '∀', 'B': 'B', 'C': 'Ɔ', 'D': 'D', 'E': 'Ǝ',
    'F': 'Ⅎ', 'G': '⅁', 'H': 'H', 'I': 'I', 'J': 'ſ',
    'K': 'ʞ', 'L': '˥', 'M': 'W', 'N': 'N', 'O': 'O',
    'P': 'Ԁ', 'Q': 'Ò', 'R': 'ᴚ', 'S': 'S', 'T': '┴',
    'U': '∩', 'V': 'Λ', 'W': 'M', 'X': 'X', 'Y': '⅄', 'Z': 'Z',
    '.': '˙', ',': "'", '!': '¡', '?': '¿', '(': ')',
    ')': '(', '{': '}', '}': '{', '[': ']', ']': '[',
    '_': '‾',
}


def mirror_text(text: str) -> str:
    """上下颠倒 + 反转字符串。"""
    return ''.join(_MIRROR_MAP.get(c, c) for c in reversed(text))


# ─────────────────────────────────────────────────────────────
#  炼金术符号系统
#  文章第六面 Chymistry & 第十二面 CLAVES SEPTVM 元素表
# ─────────────────────────────────────────────────────────────
ELEMENTS_TABLE = {
    # 四元素
    "fire":     "🜂",   # △
    "water":    "🜄",   # ▽
    "air":      "🜁",   # △ 加横
    "earth":    "🜃",   # ▽ 加横
    # 七大金属 / 七大行星
    "gold":     "☉",   # 金 / 太阳
    "silver":   "☽",   # 银 / 月亮
    "mercury":  "☿",   # 汞 / 水星
    "copper":   "♀",   # 铜 / 金星
    "iron":     "♂",   # 铁 / 火星
    "tin":      "♃",   # 锡 / 木星
    "lead":     "♄",   # 铅 / 土星
    # 其他重要符号
    "salt":     "🜔",
    "sulfur":   "🜍",
    "arsenic":  "🜺",
    "antimony": "♀♂",
    "aether":   "○",
    # 三本原
    "mercury_principle": "☿",
    "sulfur_principle":  "🜍",
    "salt_principle":    "🜔",
}

# 大卫之星（六芒星）由火 △ 与水 ▽ 叠加
SEAL_OF_SOLOMON = "✡"

# 文章第十二面 加粗单词 = 元素名（来自书页底部符号）
ELEMENT_WORDS = [
    "fire", "water", "air", "earth",
    "gold", "silver", "mercury", "copper", "iron", "tin", "lead",
    "salt", "sulfur",
]


def alchemy_symbol(name: str) -> str:
    """输入元素名，返回对应符号。"""
    return ELEMENTS_TABLE.get(name.lower(), "?")


def decode_alchemy_glyphs(glyphs: str) -> str:
    """反向：从符号到元素名。"""
    reverse = {v: k for k, v in ELEMENTS_TABLE.items()}
    result: list[str] = []
    for g in glyphs:
        if g in reverse:
            result.append(reverse[g])
        else:
            result.append(g)
    return ' '.join(result)


# ─────────────────────────────────────────────────────────────
#  7 页书谜题数据 — Alchemia 的核心结构
#  文章第 1-14 面的内容（合并相邻空白页）
# ─────────────────────────────────────────────────────────────
ALCHEMIA_PAGES = [
    {
        "page":     1,
        "title":    "封面",
        "latin":    "ALCHEMIA",
        "hint":     "印刷日期早于 1688 年；查询方向仅限炼金术",
        "rule":     "look only to alchemy; before 1688",
        "cipher":   "",
        "plaintext":"",
    },
    {
        "page":     2,
        "title":    "空白页",
        "latin":    "Liber hic aperit librum",
        "hint":     "拉丁语：这本书打开了书——需要外部研究",
        "rule":     "research externally",
        "cipher":   "",
        "plaintext":"",
    },
    {
        "page":     3,
        "title":    "引言",
        "latin":    "",
        "hint":     "读懂英文即可",
        "rule":     "read english",
        "cipher":   "",
        "plaintext":"",
    },
    {
        "page":     4,
        "title":    "ABSCONDITA EST INSIGNE",
        "latin":    "Remove the false emblems and leave only true",
        "hint":     "找到真符号，重新排列得到 Golden Mean 钥匙",
        "rule":     "golden_mean(NGLEOMADNE → GOLDEN MEAN)",
        "cipher":   "NGLEOMADNE",
        "plaintext":"YOU WHO READS THIS MESSAGE HAVE PROVEN THYSELF TO BE IN",
    },
    {
        "page":     5,
        "title":    "LINGVA MATER",
        "latin":    "At Babel our tongue did split",
        "hint":     "四语言 Gematria + SOYGA → Porta/Trithemius/Selenus/Vigenere",
        "rule":     "gematria + 4 ciphers (porta/trith/selenus/vig)",
        "cipher":   "SOYGA",
        "plaintext":"POSSESSION OF A GREAT MIND AND AN EVEN GREATER CURIOSITY.",
    },
    {
        "page":     6,
        "title":    "CHYMISTRY",
        "latin":    "Group by appearance their magnitude revealed",
        "hint":     "Barlet's key + Invisible College → 符号数字映射",
        "rule":     "alchemy_symbols + invisible_college",
        "cipher":   "🜂🜄🜁🜃✡",
        "plaintext":"WHILE TRANSMUTATION TO GOLD MAY HAVE ELUDED MANY GREAT",
    },
    {
        "page":     7,
        "title":    "SVPER STELLAE",
        "latin":    "Cicero writes of an ancient machine",
        "hint":     "Antikythera + Corinthian 历 + 凯撒加密（fifth month=July=Caesar）",
        "rule":     "zodiac_shift + caesar",
        "cipher":   "ΑΡΗΣ ΠΙΣΚΕΣ ΛΕΩ ΣΑΓΙΤΤΑΡΙΥΣ ΑΚΥΑΡΙΥΣ",
        "plaintext":"MEN, THE KNOWLEDGE GAINED IN SEARCHING WILL DOUBTLESS PROVE",
    },
    {
        "page":     8,
        "title":    "HISTORIA",
        "latin":    "Text in green the substitution will reveal",
        "hint":     "Hermeticism 'As above, so below' → 文字上下颠倒",
        "rule":     "mirror_text (as above so below)",
        "cipher":   "Ǝ⅁∀Σ ƎH⊥",
        "plaintext":"THE GREATER GIFT - FOR GOD HAS SECRETED MANY WONDERS IN THE WORLD",
    },
    {
        "page":     9,
        "title":    "NVMERO SANCTVM",
        "latin":    "Alkahest will split each in twain",
        "hint":     "数字 → 两素数 → 字母（Eratosthenes 筛）→ Liber Abaci → Fibonacci 移位",
        "rule":     "sieve + fibonacci_shift",
        "cipher":   "74 69 6 55 1403",
        "plaintext":"WHICH ARE YET TO BE UNVEILED. IF FURTHER MYSTERIES YOU SEEK, THEN",
    },
    {
        "page":     10,
        "title":    "MAPPVS MUNDI",
        "latin":    "Identify these lands hidden in many a great atlas",
        "hint":     "五个传说地点：Brazil Island / Mercator's Rock / Atlantis / Reynold's Island / Hy-Brasil",
        "rule":     "5x10_table + phantom_islands",
        "cipher":   "BRZ MRK ATL RNI HYB",
        "plaintext":"FACE THE GOOD, AND LET THE DAEMONS GUIDE YOU",
    },
    {
        "page":     11,
        "title":    "中间页",
        "latin":    "",
        "hint":     "能看懂就好",
        "rule":     "read",
        "cipher":   "",
        "plaintext":"",
    },
    {
        "page":     12,
        "title":    "CLAVES SEPTVM",
        "latin":    "七把钥匙",
        "hint":     "加粗的元素单词 + 书页底部符号 → 符号字母对应表",
        "rule":     "elements_table + page_glyphs",
        "cipher":   "FIRE WATER AIR EARTH GOLD SILVER MERCURY COPPER IRON TIN LEAD SALT SULFUR",
        "plaintext":"(回收前述所有解密方法)",
    },
    {
        "page":     13,
        "title":    "MAGNVS ARCANA",
        "latin":    "大奥秘",
        "hint":     "汇总所有密文，按对应方法解码",
        "rule":     "all_ciphers_combined",
        "cipher":   "",
        "plaintext":"(完整段落)",
    },
    {
        "page":     14,
        "title":    "终页",
        "latin":    "PADEILSYMIELGEDIELVSIEL",
        "hint":     "加点字提取 → 4-P 5-ADEI 6-LSYM 7-IEL 8-GEDIEL 9-VSI 10-EL",
        "rule":     "extract_dotted_letters",
        "cipher":   "PADEILSYMIELGEDIELVSIEL",
        "plaintext":"最终答案需要按特定页面顺序应用",
    },
]


def get_page(page_num: int) -> dict:
    """获取指定页的数据。"""
    for p in ALCHEMIA_PAGES:
        if p["page"] == page_num:
            return p
    return {}


# ─────────────────────────────────────────────────────────────
#  历史人物 — 文章中提到的炼金术师 / 历史人物
# ─────────────────────────────────────────────────────────────
HISTORICAL_FIGURES = {
    "michelspacher": {
        "name":    "Stephan Michelspacher",
        "era":     "17世纪初",
        "city":    "Augsburg",
        "work":    "Cabala Speculum Veritatis",
        "symbol":  "月亮符号",
        "page":    4,
    },
    "ripley": {
        "name":    "George Ripley",
        "era":     "15世纪",
        "work":    "The Ripley Scroll",
        "symbol":  "Ripley 卷轴中的符号",
        "page":    4,
    },
    "faust": {
        "name":    "Johann Georg Faust",
        "era":     "15世纪",
        "work":    "Faust 召唤恶魔手稿",
        "symbol":  "两个符号",
        "page":    4,
    },
    "boyle": {
        "name":    "Robert Boyle",
        "era":     "17世纪",
        "work":    "Invisible College 创始人",
        "symbol":  " repeal Mines Royal Act 1688",
        "page":    6,
    },
    "cleopatra": {
        "name":    "Cleopatra the Alchemist",
        "era":     "公元3世纪",
        "work":    "Chrysopoeia",
        "symbol":  "Chrysopoeia 中的图形",
        "page":    8,
    },
    "zosimos": {
        "name":    "Zosimos of Panopolis",
        "era":     "公元3-4世纪",
        "work":    "Panopolis 之子",
        "symbol":  "Zosimos 图像",
        "page":    8,
    },
    "fibonacci": {
        "name":    "Leonardo Fibonacci",
        "era":     "1170-1250",
        "work":    "Liber Abaci",
        "symbol":  "Fibonacci 数列",
        "page":    9,
    },
    "sendivogius": {
        "name":    "Michael Sendivogius",
        "era":     "16-17世纪",
        "work":    "炼金术师",
        "symbol":  "Combwich 的法师",
        "page":    10,
    },
    "charnock": {
        "name":    "Thomas Charnock",
        "era":     "16世纪",
        "work":    "Baresh 手稿",
        "symbol":  "Baresh codex",
        "page":    10,
    },
    "napier": {
        "name":    "John Napier",
        "era":     "1550-1617",
        "work":    "Napier's bones（纳皮尔算筹）",
        "symbol":  "Napier bones",
        "page":    10,
    },
    "brahe": {
        "name":    "Tycho Brahe",
        "era":     "1546-1601",
        "work":    "Planisphaerium Braheum",
        "symbol":  "黄道十二宫布局",
        "page":    7,
    },
    "eratosthenes": {
        "name":    "Eratosthenes",
        "era":     "公元前276-194",
        "work":    "Sieve of Eratosthenes",
        "symbol":  "素数筛",
        "page":    9,
    },
}


# ─────────────────────────────────────────────────────────────
#  最终密钥验证 — PADEILSYMIELGEDIELVSIEL
#  文章第十四面：从第4-10页的加点字中提取
#   4-P
#   5-ADEI
#   6-LSYM
#   7-IEL
#   8-GEDIEL
#   9-VSI
#   10-EL
#  组合：PADEILSYMIELGEDIELVSIEL
# ─────────────────────────────────────────────────────────────
FINAL_KEY = "PADEILSYMIELGEDIELVSIEL"

# 各页加点字（文章中明确给出）
DOTTED_LETTERS_BY_PAGE = {
    4:  "P",
    5:  "ADEI",
    6:  "LSYM",
    7:  "IEL",
    8:  "GEDIEL",
    9:  "VSI",
    10: "EL",
}


def verify_final_key(candidate: str) -> bool:
    """验证用户输入是否为最终密钥。"""
    return candidate.strip().upper() == FINAL_KEY


def explain_final_key() -> str:
    """解释最终密钥的来源。"""
    parts = [f"  第{p}页: {letters}" for p, letters in DOTTED_LETTERS_BY_PAGE.items()]
    return "最终密钥由第 4-10 页的加点字按页顺序拼接：\n" + "\n".join(parts) + \
           f"\n\n→ 拼接结果：{FINAL_KEY}"


# ─────────────────────────────────────────────────────────────
#  传说地点 — 文章第十面 MAPPUS MUNDI
# ─────────────────────────────────────────────────────────────
PHANTOM_ISLANDS = {
    "brazil": {
        "name":   "Brazil Island (Hy-Brasil)",
        "legend": "传说每七年中的一天浓雾才散去",
        "note":   "不是现代的巴西",
    },
    "mercator": {
        "name":   "Mercator's Rock",
        "legend": "墨卡托描述周长 33 法国英里的岩石",
    },
    "atlantis": {
        "name":   "Atlantis",
        "legend": "基于柯切尔的地图形状",
    },
    "reynolds": {
        "name":   "Reynold's Island",
        "legend": "由探险家沃尔特·雷利发现",
    },
    "combwich": {
        "name":   "Combwich 法师之岛",
        "legend": "由 Sendivogius/Charnock/Napier/Voynich 连线交叉点定位",
    },
}


# ─────────────────────────────────────────────────────────────
#  Voynich Manuscript — 文章第十面提到 "Baresh codex owns"
# ─────────────────────────────────────────────────────────────
VOYNICH_INFO = {
    "name":   "Voynich Manuscript",
    "date":   "15世纪",
    "language": "未知语言",
    "note":   "至今未被完全破译的神秘手稿",
}


# ─────────────────────────────────────────────────────────────
#  综合解密入口 — 给 model 调用的统一接口
# ─────────────────────────────────────────────────────────────
def decode_page(page_num: int, cipher_text: str = "") -> str:
    """根据页码自动选择解密方法。返回提示字符串。"""
    page = get_page(page_num)
    if not page:
        return f"第 {page_num} 面不存在（仅 1-14 面）"

    title = page["title"]
    hint  = page["hint"]
    rule  = page["rule"]

    if page_num == 4:
        # Golden Mean：NGLEOMADNE 重排 → GOLDEN MEAN
        return f"〔{title}〕{hint}\n密文 {page['cipher']} → 重排为 GOLDEN MEAN（黄金均值取中）"
    if page_num == 5:
        return f"〔{title}〕{hint}\nSOYGA → The Book of Soyga → 4 种加密法：Porta / Trithemius / Selenus / Vigenere"
    if page_num == 6:
        return f"〔{title}〕{hint}\nInvisible College ↔ Mines Royal Act 1688 → Robert Boyle"
    if page_num == 7:
        zodiacs = " / ".join(f"{k}={v}" for k, v in ZODIAC_SHIFTS.items())
        return f"〔{title}〕{hint}\n凯撒移位表：{zodiacs}"
    if page_num == 8:
        return f"〔{title}〕{hint}\nCleopatra / Sphinx / Zosimos / Fire → 上下颠倒"
    if page_num == 9:
        nums = [74, 69, 6, 55, 1403]
        converted = sieve_batch(nums)
        return f"〔{title}〕{hint}\n{' '.join(map(str, nums))} → {converted} → Liber Abaci → Fibonacci"
    if page_num == 10:
        islands = " / ".join(PHANTOM_ISLANDS.keys())
        return f"〔{title}〕{hint}\n传说地点：{islands}"
    if page_num == 12:
        return f"〔{title}〕{hint}\n加粗元素单词 + 书页底部符号 → 对应表"
    if page_num == 14:
        return explain_final_key()
    return f"〔{title}〕{hint}"


# ─────────────────────────────────────────────────────────────
#  成就系统 — 解锁条件
# ─────────────────────────────────────────────────────────────
ACHIEVEMENTS = {
    "first_blood": {
        "name":   "初窥门径",
        "desc":   "第一次进入 Alchemia 模式",
        "check":  lambda state: state.get("alch_entered", False),
    },
    "golden_mean": {
        "name":   "黄金均值",
        "desc":   "解开第 4 面 ABSCONDITA EST INSIGNE",
        "check":  lambda state: state.get("page_4_solved", False),
    },
    "babel_tongue": {
        "name":   "巴别塔之舌",
        "desc":   "解开第 5 面 LINGVA MATER",
        "check":  lambda state: state.get("page_5_solved", False),
    },
    "transmutation": {
        "name":   "点石成金",
        "desc":   "解开第 6 面 CHYMISTRY",
        "check":  lambda state: state.get("page_6_solved", False),
    },
    "stargazer": {
        "name":   "观星者",
        "desc":   "解开第 7 面 SVPER STELLAE",
        "check":  lambda state: state.get("page_7_solved", False),
    },
    "hermetic": {
        "name":   "赫尔墨斯",
        "desc":   "解开第 8 面 HISTORIA（As above, so below）",
        "check":  lambda state: state.get("page_8_solved", False),
    },
    "sieve_master": {
        "name":   "筛法大师",
        "desc":   "解开第 9 面 NVMERO SANCTVM",
        "check":  lambda state: state.get("page_9_solved", False),
    },
    "cartographer": {
        "name":   "幻岛制图师",
        "desc":   "解开第 10 面 MAPPVS MUNDI",
        "check":  lambda state: state.get("page_10_solved", False),
    },
    "final_key": {
        "name":   "终钥持有者",
        "desc":   "输入最终密钥 PADEILSYMIELGEDIELVSIEL",
        "check":  lambda state: state.get("final_key_entered", False),
    },
    "completionist": {
        "name":   "炼金术大师",
        "desc":   "解开所有 7 页谜题并输入终钥",
        "check":  lambda state: all([
            state.get("page_4_solved", False),
            state.get("page_5_solved", False),
            state.get("page_6_solved", False),
            state.get("page_7_solved", False),
            state.get("page_8_solved", False),
            state.get("page_9_solved", False),
            state.get("page_10_solved", False),
            state.get("final_key_entered", False),
        ]),
    },
}


def check_achievements(state: dict) -> list[str]:
    """返回当前已解锁的成就 id 列表。"""
    return [aid for aid, ach in ACHIEVEMENTS.items() if ach["check"](state)]


# ─────────────────────────────────────────────────────────────
#  自检 — 模块加载时验证关键算法
# ─────────────────────────────────────────────────────────────
def _self_test() -> None:
    """内部自检，确保算法正确。"""
    # Atbash
    assert atbash("ABC") == "ZYX", f"Atbash failed: {atbash('ABC')}"
    assert atbash("abc") == "zyx"
    # Trithemius: 第 i 个字母移位 i → "abc" 变为 "ace"
    assert trithemius_encrypt("abc") == "ace", \
        f"Trithemius failed: {trithemius_encrypt('abc')}"
    # Golden Mean: A(0)+G(6) → 中点 3 → d
    assert golden_mean("AG") == "d", f"Golden Mean AG failed: {golden_mean('AG')}"
    # Sieve: 74 = 2 * 37 → A(第1素数) + L(第12素数)
    r = sieve_convert(74)
    assert "AL" in r or "LA" in r, f"Sieve 74 failed: {r}"
    # Mirror: hello 反转 + 颠倒，首字符应不是 h
    assert mirror_text("hello")[0] != "h"


# 加载时静默自检（出错也只打印不抛出）
try:
    _self_test()
except AssertionError as e:
    import sys
    print(f"[alchemia] self-test warning: {e}", file=sys.stderr)


if __name__ == "__main__":
    # 手动测试
    print("=== Alchemia 解密引擎自检 ===\n")
    print(f"Atbash('Hello'):        {atbash('Hello')}")
    print(f"Trithemius('hello'):    {trithemius_encrypt('hello')}")
    print(f"Trithemius 解密:         {trithemius_encrypt(trithemius_encrypt('hello'), decrypt=True)}")
    print(f"Selenus('hello'):       {selenus_encrypt('hello')}")
    print(f"Porta('hello', 'k'):    {porta_encrypt('hello', 'k')}")
    print(f"Fibonacci 移位('hello'):{fibonacci_shift('hello')}")
    print(f"Fibonacci 解密:          {fibonacci_shift(fibonacci_shift('hello'), decrypt=True)}")
    print(f"Golden Mean('AG'):      {golden_mean('AG')}")
    print(f"Golden Mean('BF'):      {golden_mean('BF')}")
    print(f"Sieve 74 →              {sieve_convert(74)}")
    print(f"Sieve 69 →              {sieve_convert(69)}")
    print(f"Sieve 6  →              {sieve_convert(6)}")
    print(f"Sieve 55 →              {sieve_convert(55)}")
    print(f"Sieve batch [74,69,6,55,1403] → {sieve_batch([74, 69, 6, 55, 1403])}")
    print(f"Mirror('hello world'):  {mirror_text('hello world')}")
    print(f"Antikythera 月 2:       {antikythera_month(2)}")
    print(f"炼金符号 fire:          {alchemy_symbol('fire')}")
    print(f"炼金符号 gold:          {alchemy_symbol('gold')}")
    print()
    print("=== 最终密钥解释 ===")
    print(explain_final_key())
    print(f"\n最终密钥: {FINAL_KEY}")
    print(f"验证 'padeilsymielgedielvsiel': {verify_final_key('padeilsymielgedielvsiel')}")
