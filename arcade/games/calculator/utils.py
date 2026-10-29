"""
CryptoUtils — 密码学演示工具函数集合

包含：
  - 古典密码：凯撒 / 维吉尼亚 / Atbash / Porta / Trithemius / Selenus
  - 现代：XOR / 哈希 / Base64 / 密钥生成 / 盐值 / PBKDF2
  - Alchemia 解密：斐波那契移位 / 素数筛转换 / 黄金均值 / Gematria
  - 凯撒爆破

无外部依赖，纯静态方法。具体算法在 alchemia.py 中实现，这里做转发。
"""

import hashlib
import random

# 从 alchemia 模块转发具体实现，避免重复代码
from alchemia import (
    porta_encrypt,
    trithemius_encrypt,
    selenus_encrypt,
    atbash,
    caesar_brute,
    fibonacci_shift,
    sieve_convert,
    sieve_batch,
    golden_mean,
    golden_mean_word,
    gematria,
    gematria_latin,
    gematria_hebrew,
    gematria_greek,
    mirror_text,
    antikythera_month,
    alchemy_symbol,
    decode_alchemy_glyphs,
    decode_page,
    verify_final_key,
    explain_final_key,
    ALCHEMIA_PAGES,
    HISTORICAL_FIGURES,
    ACHIEVEMENTS,
    check_achievements,
    FINAL_KEY,
    ZODIAC_SHIFTS,
    ELEMENTS_TABLE,
)


class CryptoUtils:
    """简单的密码学演示工具，含 Alchemia 解密游戏扩展。"""

    # ── 古典密码 ────────────────────────────────────────────────
    @staticmethod
    def caesar_cipher(text: str, shift: int = 3) -> str:
        """凯撒密码加密"""
        result = []
        for char in text.lower():
            if char.isalpha():
                shifted = ord(char) - ord('a') + shift
                result.append(chr(shifted % 26 + ord('a')))
            else:
                result.append(char)
        return ''.join(result)

    @staticmethod
    def caesar_decipher(text: str, shift: int = 3) -> str:
        """凯撒密码解密"""
        return CryptoUtils.caesar_cipher(text, -shift)

    @staticmethod
    def caesar_bruteforce(text: str) -> str:
        """凯撒密码爆破：26 种移位全部列出。"""
        return caesar_brute(text)

    @staticmethod
    def rot13(text: str) -> str:
        """ROT13 加密（凯撒密码特例）"""
        return CryptoUtils.caesar_cipher(text, 13)

    @staticmethod
    def atbash(text: str) -> str:
        """Atbash 字母倒序替换（古希伯来密码）。"""
        return atbash(text)

    @staticmethod
    def vigenere_encrypt(text: str, key: str) -> str:
        """维吉尼亚密码加密"""
        result = []
        key = key.lower()
        ki = 0
        for char in text.lower():
            if char.isalpha():
                shift = ord(key[ki % len(key)]) - ord('a')
                shifted = ord(char) - ord('a') + shift
                result.append(chr(shifted % 26 + ord('a')))
                ki += 1
            else:
                result.append(char)
        return ''.join(result)

    @staticmethod
    def vigenere_decrypt(text: str, key: str) -> str:
        """维吉尼亚密码解密"""
        result = []
        key = key.lower()
        ki = 0
        for char in text.lower():
            if char.isalpha():
                shift = ord(key[ki % len(key)]) - ord('a')
                shifted = ord(char) - ord('a') - shift
                result.append(chr(shifted % 26 + ord('a')))
                ki += 1
            else:
                result.append(char)
        return ''.join(result)

    @staticmethod
    def porta(text: str, key: str) -> str:
        """Porta 密码（对称，加密=解密）。"""
        return porta_encrypt(text, key)

    @staticmethod
    def trithemius(text: str, decrypt: bool = False) -> str:
        """Trithemius 密码：第 i 个字母移位 i。"""
        return trithemius_encrypt(text, decrypt)

    @staticmethod
    def selenus(text: str, decrypt: bool = False) -> str:
        """Selenus 密码：第 i 个字母移位 (i+1)。"""
        return selenus_encrypt(text, decrypt)

    # ── Alchemia 高级解密 ───────────────────────────────────────
    @staticmethod
    def fibonacci(text: str, decrypt: bool = False) -> str:
        """斐波那契移位：用数列首位数字作移位（1,1,2,3,5,8...）。"""
        return fibonacci_shift(text, decrypt)

    @staticmethod
    def sieve(number: int) -> str:
        """数字 → 两素数 → 字母对（埃拉托色尼筛法）。"""
        return sieve_convert(number)

    @staticmethod
    def sieve_multi(numbers: list[int]) -> str:
        """批量素数筛转换。"""
        return sieve_batch(numbers)

    @staticmethod
    def golden_mean(pair: str) -> str:
        """两个字母取中间字母（黄金均值）。"""
        return golden_mean(pair)

    @staticmethod
    def golden_mean_text(pairs: str) -> str:
        """对多对字母连续取中间字母。"""
        return golden_mean_word(pairs)

    @staticmethod
    def gematria_value(text: str, system: str = "latin") -> int:
        """Gematria 字母数字映射。system: latin/hebrew/greek。"""
        return gematria(text, system)

    @staticmethod
    def mirror(text: str) -> str:
        """As above, so below — 文字上下颠倒 + 反转。"""
        return mirror_text(text)

    @staticmethod
    def antikythera(month: int) -> str:
        """Antikythera 古希腊 Corinthian 历法月份查询。"""
        return antikythera_month(month)

    @staticmethod
    def alchemy(name: str) -> str:
        """炼金术符号查询。"""
        return alchemy_symbol(name)

    @staticmethod
    def alchemy_decode(glyphs: str) -> str:
        """炼金术符号 → 元素名。"""
        return decode_alchemy_glyphs(glyphs)

    @staticmethod
    def alchemia_page(page_num: int) -> str:
        """查询 Alchemia 7 页书的某一页的解密提示。"""
        return decode_page(page_num)

    @staticmethod
    def verify_key(candidate: str) -> bool:
        """验证最终密钥 PADEILSYMIELGEDIELVSIEL。"""
        return verify_final_key(candidate)

    @staticmethod
    def explain_key() -> str:
        """解释最终密钥的来源。"""
        return explain_final_key()

    # ── 哈希 / 加密 / 编码 ─────────────────────────────────────
    @staticmethod
    def simple_hash(text: str, algorithm: str = "sha256") -> str:
        """简单哈希计算"""
        data = text.encode('utf-8')
        if algorithm == "md5":
            return hashlib.md5(data).hexdigest()[:16]
        elif algorithm == "sha1":
            return hashlib.sha1(data).hexdigest()[:20]
        elif algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()[:32]
        elif algorithm == "sha512":
            return hashlib.sha512(data).hexdigest()[:64]
        return hashlib.sha256(data).hexdigest()[:32]

    @staticmethod
    def xor_encrypt(text: str, key: str) -> str:
        """简单的 XOR 加密"""
        key_bytes = key.encode()
        text_bytes = text.encode()
        result = []
        for i, byte in enumerate(text_bytes):
            result.append(chr(byte ^ key_bytes[i % len(key_bytes)]))
        return ''.join(result)

    @staticmethod
    def generate_key(bits: int = 128) -> str:
        """生成随机密钥（十六进制）"""
        num_bytes = bits // 8
        key = bytes(random.randint(0, 255) for _ in range(num_bytes))
        return key.hex()[:32]

    @staticmethod
    def generate_salt(length: int = 16) -> str:
        """生成盐值"""
        return bytes(random.randint(33, 126) for _ in range(length)).decode('latin-1')

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        """带盐值哈希密码"""
        if salt is None:
            salt = CryptoUtils.generate_salt()
        salted = password + salt
        hash_val = hashlib.pbkdf2_hmac(
            'sha256', salted.encode('utf-8'), salt.encode('utf-8'), 100000
        )
        return hash_val.hex()[:32], salt

    @staticmethod
    def check_password(password: str, hash_val: str, salt: str) -> bool:
        """验证密码"""
        new_hash, _ = CryptoUtils.hash_password(password, salt)
        return new_hash == hash_val

    @staticmethod
    def encode_fernet(text: str) -> str:
        """简单的 Base64 编码演示"""
        import base64
        return base64.b64encode(text.encode()).decode()[:32]

    @staticmethod
    def decode_fernet(encoded: str) -> str:
        """简单的 Base64 解码演示"""
        import base64
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += '=' * padding
        try:
            return base64.b64decode(encoded.encode()).decode()[:32]
        except Exception:
            return "invalid"


if __name__ == "__main__":
    # 工具类自检
    print("=== CryptoUtils 自检 ===")
    print(f"Caesar('hello', 3):       {CryptoUtils.caesar_cipher('hello', 3)}")
    print(f"Caesar 解密:               {CryptoUtils.caesar_decipher(CryptoUtils.caesar_cipher('hello', 3), 3)}")
    print(f"ROT13('hello'):           {CryptoUtils.rot13('hello')}")
    print(f"Atbash('hello'):          {CryptoUtils.atbash('hello')}")
    print(f"Vigenere('hello', 'key'): {CryptoUtils.vigenere_encrypt('hello', 'key')}")
    print(f"Porta('hello', 'k'):      {CryptoUtils.porta('hello', 'k')}")
    print(f"Trithemius('hello'):      {CryptoUtils.trithemius('hello')}")
    print(f"Selenus('hello'):         {CryptoUtils.selenus('hello')}")
    print(f"Fibonacci('hello'):       {CryptoUtils.fibonacci('hello')}")
    print(f"Sieve(74):                {CryptoUtils.sieve(74)}")
    print(f"GoldenMean('AG'):         {CryptoUtils.golden_mean('AG')}")
    print(f"Mirror('hello'):          {CryptoUtils.mirror('hello')}")
    print(f"Antikythera(2):           {CryptoUtils.antikythera(2)}")
    print(f"Alchemy('fire'):          {CryptoUtils.alchemy('fire')}")
    print(f"Alchemia page 4:          {CryptoUtils.alchemia_page(4)[:60]}...")
    print(f"Verify final key:         {CryptoUtils.verify_key('PADEILSYMIELGEDIELVSIEL')}")
