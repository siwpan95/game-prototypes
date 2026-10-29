"""
CalculatorModel — 纯业务逻辑层
MVVM 中 Model 的职责：维护状态、执行运算、通知观察者。
不包含任何 GUI 代码，不依赖 ViewModel / View。

增强版（基于 Alchemia 解密游戏指南）：
  - 扩展特殊组合：炼金术、古典密码、历史人物、神话地点
  - 新增 12 个 # 模式：#alch、#porta、#trith、#selenus、#atbash、
    #fib、#sieve、#golden、#gematria、#anti、#mirror、#brute、#page、#key2
  - 成就系统：跟踪解开的页数和最终密钥
"""

from typing import Callable
from utils import CryptoUtils


class CalculatorModel:
    """Pure state + business logic. No GUI imports, no widget refs."""

    SPECIAL_COMBOS = {
        # ── classic ──
        "++--××÷÷()()": "cool",
        "110":  "warning",
        "119":  "warning",
        "120":  "warning",
        "911":  "fbi warning",
        "520":  "1314",
        "1314": "520",
        # ── AES 加密 ──
        "128": "aes-128",
        "192": "aes-192",
        "256": "sha-256",
        # ── 哈希函数 ──
        "160": "sha-1",
        "224": "sha-224",
        "384": "sha-384",
        "512": "sha-512",
        # ── RSA 密钥 ──
        "1024": "rsa-1k",
        "2048": "rsa-2048",
        "3072": "rsa-3k",
        "4096": "rsa-4k",
        # ── ECC 椭圆曲线 ──
        "521": "p-521",
        # ── 密钥交换 ──
        "448": "x448",
        # ── 安全协议 ──
        "443": "https",
        "22": "ssh",
        "21": "ftp",
        # ── 加密模式 ──
        "ecb": "危险",
        "cbc": "安全",
        "gcm": "认证",
        "ofb": "流式",
        # ── 填充方案 ──
        "pkcs7": "padding",
        "zero": "zero",
        # ── 密钥派生 ──
        "1000": "pbkdf2",
        "10": "bcrypt",
        # ── 二进制 / 十六进制 ──
        "101": "matrix",
        "010": "binary",
        "16":  "hex",
        "2":   "binary",
        "00":  "null",
        "ff":  "0xff",
        "0x":  "hex",
        "0b":  "bin",
        # ── 熵与随机 ──
        "64":  "salt",
        # ── 数学常数 ──
        "314": "pi",
        "271": "e",
        "161": "golden",
        "618": "phi",
        # ── 安全术语 ──
        "xor": "⊕",
        "rnd": "rand",
        "key": "🔐",
        "enc": "encrypt",
        "dec": "decrypt",
        "sig": "signature",
        "pki": "pki",
        "ca":  "certificate",
        # ── fun ──
        "42":  "answer",
        "007": "bond",
        "404": "not found",
        "666": "beast",
        "777": "jackpot",
        "000": "void",

        # ════════════════════════════════════════════════════════
        #  Alchemia 解密游戏彩蛋（基于机核文章）
        # ════════════════════════════════════════════════════════
        # ── 历史关键年份 ──
        "1688":  "Mines Royal Act",   # 文章第六面： repealed by Robert Boyle
        "1170":  "Fibonacci 出生",     # Fibonacci 1170-1250
        "1250":  "Liber Abaci",
        # ── 文章中的关键词 ──
        "alchemia":  "7 页书",
        "alchemy":   "🜂🜄🜁🜃",          # 四元素
        "soyga":     "Book of Soyga", # 文章第五面 SOYGA
        "porta":     "Porta Cipher",
        "trithemius":"Trithemius Cipher",
        "selenus":   "Selenus Cipher",
        "vigenere":  "Vigenere Cipher",
        "atbash":    "Atbash Cipher",
        "caesar":    "Caesar Cipher",
        # ── 历史人物 ──
        "faust":     "Johann Georg Faust",
        "ripley":    "George Ripley",
        "michelspacher": "Stephan Michelspacher",
        "boyle":     "Robert Boyle (Invisible College)",
        "cleopatra": "Cleopatra the Alchemist",
        "zosimos":   "Zosimos of Panopolis",
        "fibonacci": "Liber Abaci",
        "sendivogius": "Michael Sendivogius",
        "charnock":  "Thomas Charnock",
        "napier":    "Napier's bones",
        "brahe":     "Tycho Brahe",
        "eratosthenes": "Sieve",
        # ── 神话与传说地点 ──
        "atlantis":  "Phantom Island",
        "babel":     "Tower of Babel",
        "antikythera": "ΚΡΑΝΕΙΟΣ",
        "sphinx":    "狮身人面像",
        # ── 炼金术概念 ──
        "fire":      "🜂",
        "water":     "🜄",
        "air":       "🜁",
        "earth":     "🜃",
        "gold":      "☉",
        "silver":    "☽",
        "mercury":   "☿",
        "copper":    "♀",
        "iron":      "♂",
        "tin":       "♃",
        "lead":      "♄",
        "salt":      "🜔",
        "sulfur":    "🜍",
        "aether":    "○",
        # ── 谜题术语 ──
        "golden":    "Mean",
        "goldenmean":"⚖",
        "philosopher": "Stone",
        "elixir":    "长生不老药",
        # ── 文章编号 ──
        "130136":    "Alchemia Guide",
        # ── 最终密钥（不区分大小写）── 由 _evaluate 特殊处理
        # "padeilsymielgedielvsiel" → 触发终钥彩蛋

        # ── Fibonacci 数列前几位 ──
        "1123":      "1,1,2,3,5,8,13,21...",
        "112358":    "Fibonacci",
        # ── 素数相关 ──
        "2357":      "Prime",
        # ── 元素周期表前几个 ──
        "hhe":       "H, He",
        "hhe libe":  "前4元素",

        # ── Alchemia 7 页书页码（直接输入数字）──
        "714":       "7 pages of Alchemia",
    }

    # 最终密钥（输入此值触发终钥彩蛋）
    FINAL_KEY = "PADEILSYMIELGEDIELVSIEL"

    MAX_DIGIT_PRESSES     = 4
    MAX_CHARS             = 13
    TRIPLE_SAME_RESET     = 3
    TRIPLE_BACKSPACE_QUIT = 3
    TRIPLE_EQUALS_SHUFFLE = 3

    def __init__(self):
        self._observers: list[Callable[[], None]] = []
        self._backspace_streak: int = 0
        self._equals_streak:    int = 0
        # public readable state (ViewModel reads these in observer callbacks)
        self.expression:       str  = ""
        self.display_text:     str  = "0"
        self.last_eval_expr:   str  = ""
        self.char_limit:       bool = False
        self.digit_limit:      bool = False
        # last action type
        self.last_action:      str  = "display"  # display|result|reset|quit|shuffle|achievement
        # 密码学模式状态
        self._crypto_mode:     str  = ""
        self._crypto_input:    str  = ""
        self._crypto_param:    str  = ""
        self._crypto_history:  list[str] = []
        # Alchemia 解密游戏状态
        self._alchemia_active: bool = False     # 是否处于 Alchemia 模式
        self._alchemia_state:  dict = {}        # 成就状态字典
        self._last_achievement: str = ""        # 最近解锁的成就 id
        self._reset_expr()

    # ── Observer API ─────────────────────────────────────────────
    def add_observer(self, cb: Callable[[], None]) -> None:
        self._observers.append(cb)

    def _notify(self) -> None:
        for cb in self._observers:
            cb()

    # ── Internal helpers ─────────────────────────────────────────
    def _reset_expr(self):
        self.expression        = ""
        self._last_token: str  = ""
        self._same_count: int  = 0
        self._digit_presses: int = 0
        self._update_limits()

    def _update_limits(self):
        self.char_limit  = len(self.expression) >= self.MAX_CHARS
        self.digit_limit = self._digit_presses >= self.MAX_DIGIT_PRESSES

    def _recalc_digit_presses(self):
        self._digit_presses = sum(
            1 for ch in self.expression if ch.isdigit() or ch == "."
        )
        self._update_limits()

    # ── Evaluation ───────────────────────────────────────────────
    def _evaluate(self) -> str:
        expr = self.expression.strip()
        if not expr:
            return "0"

        # 最终密钥特殊处理（不区分大小写）
        if expr.lower() == self.FINAL_KEY.lower():
            self._alchemia_state["final_key_entered"] = True
            self._last_achievement = "final_key"
            self.last_action = "achievement"
            return "★ 终钥已开启 ★"

        if expr in self.SPECIAL_COMBOS:
            return self.SPECIAL_COMBOS[expr]
        # 大小写不敏感匹配（针对 alchemia 相关彩蛋）
        lower = expr.lower()
        for k, v in self.SPECIAL_COMBOS.items():
            if k.lower() == lower:
                return v

        py_expr = expr.replace("×", "*").replace("÷", "/")
        try:
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in py_expr):
                return "fool"
            result = eval(py_expr)   # noqa: S307 – sanitised
            if isinstance(result, float):
                if result != result:
                    return "fool"
                if result == int(result):
                    return str(int(result))
                return f"{result:.6f}".rstrip("0").rstrip(".")
            return str(result)
        except ZeroDivisionError:
            return "fool"
        except Exception:
            return "fool"

    # ── 密码学评估 ────────────────────────────────────────────────
    def _evaluate_crypto(self, token: str) -> str:
        """处理密码学相关输入并返回结果"""
        crypto_prefixes = {
            # ── 经典密码 ──
            "#caesar":   ("caesar",    "凯撒密码"),
            "#rot":      ("rot13",     "ROT13"),
            "#atbash":   ("atbash",    "Atbash 倒序"),
            "#vig":      ("vigenere",  "维吉尼亚"),
            "#porta":    ("porta",     "Porta 密码"),
            "#trith":    ("trithemius","Trithemius"),
            "#selenus":  ("selenus",   "Selenus"),
            "#brute":    ("brute",     "凯撒爆破"),
            # ── 哈希 / 密钥 ──
            "#hash":     ("hash",      "哈希"),
            "#key":      ("key",       "密钥生成"),
            "#salt":     ("salt",      "盐值生成"),
            "#pwd":      ("password",  "密码哈希"),
            # ── 加密 ──
            "#xor":      ("xor",       "异或加密"),
            "#b64":      ("base64",    "Base64"),
            # ── Alchemia 高级解密 ──
            "#fib":      ("fibonacci", "斐波那契移位"),
            "#sieve":    ("sieve",     "素数筛转换"),
            "#golden":   ("golden",    "黄金均值"),
            "#gem":      ("gematria",  "Gematria"),
            "#anti":     ("antikythera","古希腊历法"),
            "#mirror":   ("mirror",    "As above so below"),
            "#alchemy":  ("alchemy",   "炼金符号"),
            "#page":     ("page",      "Alchemia 页码"),
            "#key2":     ("finalkey",  "最终密钥"),
            # ── 总入口 ──
            "#alch":     ("alchemia",  "Alchemia 解密"),
        }
        if token.startswith("#"):
            # 最长前缀匹配，避免 #key 误匹配 #key2、#vig 误匹配 #vigenere 等
            matched_prefix = ""
            for prefix in crypto_prefixes:
                if token.startswith(prefix) and len(prefix) > len(matched_prefix):
                    matched_prefix = prefix
            if matched_prefix:
                mode, desc = crypto_prefixes[matched_prefix]
                self._crypto_mode  = mode
                self._crypto_input = ""
                if mode == "alchemia":
                    self._alchemia_active = True
                    self._alchemia_state.setdefault("alch_entered", True)
                    if "first_blood" not in self._alchemia_state.get("_unlocked", []):
                        self._last_achievement = "first_blood"
                        self._alchemia_state.setdefault("_unlocked", []).append("first_blood")
                        self.last_action = "achievement"
                        return "★ 初窥门径 ★\n#alch 已激活\n可用: #page 1-14 / #golden / #fib ..."
                    self.last_action = "display"
                    return "Alchemia 已激活\n#page N 查页\n#key2 验证终钥"
                return f"🔐 {desc}模式"
            return "unknown crypto"

        if self._crypto_mode:
            if token == "=":
                return self._finalize_crypto()
            elif token == "←":
                self._crypto_input = self._crypto_input[:-1]
                return self._crypto_input or "0"
            elif token == "C":
                self._crypto_mode  = ""
                self._crypto_input = ""
                return "0"
            else:
                self._crypto_input += token
                return self._crypto_input

        return ""

    def _finalize_crypto(self) -> str:
        """完成密码学操作并返回结果"""
        text   = self._crypto_input
        mode   = self._crypto_mode
        result = ""

        try:
            # ── 经典密码 ──
            if mode == "caesar":
                parts = text.split()
                if len(parts) >= 2:
                    try:
                        shift     = int(parts[-1]) % 26
                        plaintext = " ".join(parts[:-1])
                        result    = CryptoUtils.caesar_cipher(plaintext, shift)
                    except ValueError:
                        result = CryptoUtils.caesar_cipher(text, 3)
                else:
                    result = CryptoUtils.caesar_cipher(text, 3)

            elif mode == "rot13":
                result = CryptoUtils.rot13(text)

            elif mode == "atbash":
                result = CryptoUtils.atbash(text)

            elif mode == "brute":
                # 凯撒爆破：返回所有 26 种移位
                result = CryptoUtils.caesar_bruteforce(text)

            elif mode == "hash":
                parts = text.split()
                if len(parts) >= 2:
                    text_to_hash, algo = parts[0], parts[-1].lower()
                else:
                    text_to_hash, algo = text, "sha256"
                result = CryptoUtils.simple_hash(text_to_hash, algo)

            elif mode == "key":
                try:
                    bits = int(text) if text else 256
                    bits = min(max(bits, 64), 4096)
                except ValueError:
                    bits = 256
                result = CryptoUtils.generate_key(bits)

            elif mode == "xor":
                parts = text.split(":")
                if len(parts) == 2:
                    result = CryptoUtils.xor_encrypt(parts[0], parts[1])
                else:
                    result = CryptoUtils.xor_encrypt(text, "secret")

            elif mode == "vigenere":
                parts = text.split()
                if len(parts) >= 2:
                    result = CryptoUtils.vigenere_encrypt(parts[0], parts[-1])
                else:
                    result = "需要: 文本 密钥"

            elif mode == "porta":
                parts = text.split()
                if len(parts) >= 2:
                    result = CryptoUtils.porta(parts[0], parts[-1])
                else:
                    result = "需要: 文本 密钥"

            elif mode == "trithemius":
                result = CryptoUtils.trithemius(text)

            elif mode == "selenus":
                result = CryptoUtils.selenus(text)

            elif mode == "base64":
                try:
                    result = CryptoUtils.encode_fernet(text)
                except Exception:
                    result = "编码失败"

            elif mode == "salt":
                try:
                    length = int(text) if text else 16
                    length = min(max(length, 4), 64)
                except ValueError:
                    length = 16
                result = CryptoUtils.generate_salt(length)

            elif mode == "password":
                parts = text.split()
                if parts:
                    pwd  = parts[0]
                    salt = parts[1] if len(parts) >= 2 else CryptoUtils.generate_salt(16)
                    hash_val, _ = CryptoUtils.hash_password(pwd, salt)
                    result = f"hash:{hash_val[:16]}... salt:{salt[:8]}"
                else:
                    result = "需要: 密码 [盐值]"

            # ── Alchemia 高级解密 ──
            elif mode == "fibonacci":
                result = CryptoUtils.fibonacci(text)

            elif mode == "sieve":
                # 输入数字（空格分隔）→ 转字母
                nums_str = text.replace(",", " ").split()
                nums = []
                for s in nums_str:
                    try:
                        nums.append(int(s))
                    except ValueError:
                        pass
                if nums:
                    if len(nums) == 1:
                        result = CryptoUtils.sieve(nums[0])
                    else:
                        result = CryptoUtils.sieve_multi(nums)
                else:
                    result = "输入数字，如: 74 69 6 55"

            elif mode == "golden":
                # 输入字母对
                pairs = text.replace(",", " ").replace(".", " ")
                if len(pairs.replace(" ", "")) >= 2:
                    result = CryptoUtils.golden_mean_text(pairs)
                else:
                    result = "输入字母对，如: AG BF"

            elif mode == "gematria":
                parts = text.split()
                if len(parts) >= 2:
                    sys_name = parts[-1].lower()
                    text_val = " ".join(parts[:-1])
                    if sys_name in ("latin", "hebrew", "greek"):
                        result = str(CryptoUtils.gematria_value(text_val, sys_name))
                    else:
                        result = str(CryptoUtils.gematria_value(text, "latin"))
                else:
                    result = str(CryptoUtils.gematria_value(text, "latin"))

            elif mode == "antikythera":
                try:
                    m = int(text) if text else 1
                    result = CryptoUtils.antikythera(m)
                except ValueError:
                    result = "输入 1-12"

            elif mode == "mirror":
                result = CryptoUtils.mirror(text)

            elif mode == "alchemy":
                result = CryptoUtils.alchemy(text)
                if result == "?":
                    # 尝试反向解码
                    decoded = CryptoUtils.alchemy_decode(text)
                    if decoded != text:
                        result = decoded

            elif mode == "page":
                # 输入页码 → 显示该页提示
                try:
                    p = int(text) if text else 1
                    result = CryptoUtils.alchemia_page(p)
                    # 解谜成就检查
                    self._check_page_achievement(p, text)
                except ValueError:
                    result = "输入 1-14 页码"

            elif mode == "finalkey":
                # 验证最终密钥
                if CryptoUtils.verify_key(text):
                    self._alchemia_state["final_key_entered"] = True
                    self._last_achievement = "final_key"
                    self.last_action = "achievement"
                    result = "★ 终钥已开启 ★"
                else:
                    result = CryptoUtils.explain_key()

            elif mode == "alchemia":
                result = "Alchemia 模式\n可用: #page N / #golden / #fib / #sieve / #anti / #mirror / #alchemy / #key2"

        except Exception as e:
            result = f"错误: {e}"

        if result and len(result) < 200 and mode not in ("page", "brute", "finalkey", "alchemia"):
            self._crypto_history.append(f"{mode}: {text} → {result[:50]}")
            if len(self._crypto_history) > 5:
                self._crypto_history.pop(0)

        self._crypto_mode  = ""
        self._crypto_input = ""
        return result

    # ── 成就检查 ────────────────────────────────────────────────
    def _check_page_achievement(self, page_num: int, user_input: str) -> None:
        """检查是否解开了某页的谜题。"""
        # 简化版：输入特定页码 + 正确"答案"即解锁
        # 这里只标记页码访问，真正的解谜由用户在外部完成
        unlocked = self._alchemia_state.setdefault("_unlocked", [])
        # 如果用户输入"page N solve"，标记该页已解
        if "solve" in user_input.lower():
            key = f"page_{page_num}_solved"
            if key not in self._alchemia_state:
                self._alchemia_state[key] = True
                # 对应的成就 id
                ach_map = {
                    4:  "golden_mean",
                    5:  "babel_tongue",
                    6:  "transmutation",
                    7:  "stargazer",
                    8:  "hermetic",
                    9:  "sieve_master",
                    10: "cartographer",
                }
                if page_num in ach_map:
                    self._last_achievement = ach_map[page_num]
                    unlocked.append(self._last_achievement)
                    self.last_action = "achievement"

    # ── 公开 API：获取成就状态 ──────────────────────────────────
    def get_achievements(self) -> list[str]:
        """返回当前已解锁的成就 id 列表。"""
        from alchemia import check_achievements
        return check_achievements(self._alchemia_state)

    def get_last_achievement(self) -> str:
        """返回最近解锁的成就 id（清空后返回 ""）。"""
        a = self._last_achievement
        self._last_achievement = ""
        return a

    @property
    def alchemia_active(self) -> bool:
        return self._alchemia_active

    # ── Main input entry point (called by ViewModel) ─────────────
    def push(self, token: str) -> None:
        """处理一个 token，更新状态，通知所有观察者。"""

        # ── 密码学模式 ────────────────────────────────────────────
        if token.startswith("#") or self._crypto_mode:
            # 记录调用前是否已在密码学模式（_finalize_crypto 会清空 _crypto_mode）
            was_in_crypto = bool(self._crypto_mode)
            crypto_result = self._evaluate_crypto(token)
            # 只要之前在密码学模式或刚进入密码学模式，都直接返回（不进入普通求值）
            if was_in_crypto or token.startswith("#"):
                # _finalize_crypto 可能触发了成就
                if self.last_action != "achievement":
                    self.last_action  = "display"
                self.display_text = crypto_result
                self._notify()
                return

        # ── ← 退格 ───────────────────────────────────────────────
        if token == "←":
            self._equals_streak = 0
            self._backspace_streak += 1
            if self._backspace_streak >= self.TRIPLE_BACKSPACE_QUIT:
                self.last_action  = "quit"
                self.display_text = ""
                self._notify()
                return
            if self.expression:
                self.expression = self.expression[:-1]
                self._recalc_digit_presses()
            self._last_token = ""
            self._same_count = 0
            self._update_limits()
            self.last_action  = "display"
            self.display_text = self.expression or "0"
            self._notify()
            return

        # ── = 等号 ───────────────────────────────────────────────
        if token == "=":
            self._backspace_streak = 0
            self._equals_streak   += 1
            if self._equals_streak >= self.TRIPLE_EQUALS_SHUFFLE:
                self._equals_streak = 0
                self._reset_expr()
                self.last_action  = "shuffle"
                self.display_text = "0"
                self._notify()
                return
            self.last_eval_expr = self.expression
            value = self._evaluate()
            # 检查是否触发了成就（最终密钥等）
            if self.last_action == "achievement":
                self.display_text = value
                self._reset_expr()
                self._notify()
                return
            self._reset_expr()
            self.last_action  = "result"
            self.display_text = value or "0"
            self._notify()
            return

        # ── C 清空 ────────────────────────────────────────────────
        if token == "C":
            self._crypto_mode      = ""
            self._crypto_input     = ""
            self._equals_streak    = 0
            self._backspace_streak = 0
            self._reset_expr()
            self.last_action  = "reset"
            self.display_text = "0"
            self._notify()
            return

        # ── 普通 token ────────────────────────────────────────────
        self._backspace_streak = 0
        self._equals_streak    = 0

        if token == self._last_token:
            self._same_count += 1
        else:
            self._same_count = 1
            self._last_token = token

        if self._same_count >= self.TRIPLE_SAME_RESET:
            self._reset_expr()
            self.last_action  = "reset"
            self.display_text = "0"
            self._notify()
            return

        if len(self.expression) >= self.MAX_CHARS:
            self.last_action  = "display"
            self.display_text = self.expression or "0"
            self._notify()
            return

        if token.isdigit() or token == ".":
            if self._digit_presses >= self.MAX_DIGIT_PRESSES:
                self.last_action  = "display"
                self.display_text = self.expression or "0"
                self._notify()
                return
            self._digit_presses += 1

        self.expression  += token
        self._update_limits()
        self.last_action  = "display"
        self.display_text = self.expression
        self._notify()
