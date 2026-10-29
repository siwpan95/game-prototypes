"""英语复数化"""


def plural(s: str) -> str:
    """将英文单词转为复数形式"""
    if len(s) > 1 and s.endswith("y"):
        return s[:-1] + "ies"
    if len(s) > 2 and s.endswith("us"):
        return s[:-2] + "i"
    if (len(s) > 2 and s.endswith("ch")) or s.endswith("x") or s.endswith("s"):
        return s + "es"
    if len(s) > 1 and s.endswith("f"):
        return s[:-1] + "ves"
    if len(s) > 3 and (s.endswith("man") or s.endswith("Man")):
        return s[:-2] + "en"
    return s + "s"
