"""
极简 YAML 子集加载/发射器（纯标准库）
====================================

只为 engine.yaml / engine.patch.yaml 服务，支持的最小语法：

    注释          行尾 #（引号内除外）
    映射          key: value（嵌套靠缩进，任意一致空格缩进）
    列表          - item  /  - key: value（项为映射时续行缩进更深）
    行内列表      [a, b, 'c']
    标量          str / int / float / bool(true,false) / null

不支持：锚点/别名、多行字符串、flow mapping、tab 缩进。
"""

from __future__ import annotations

from typing import Any, List, Tuple

__all__ = ["loads", "dumps", "load_file", "dump_file", "ConfigSyntaxError"]


class ConfigSyntaxError(ValueError):
    """配置语法错误（带行号）。"""


def _strip_comment(line: str) -> str:
    """去掉行尾注释（引号内的 # 不算）。"""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def _parse_scalar(s: str) -> Any:
    s = s.strip()
    if not s:
        return None
    if s[0] in "'\"" and len(s) >= 2 and s[-1] == s[0]:
        return s[1:-1]
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_commas(inner)]
    return s


def _split_commas(s: str) -> List[str]:
    parts: List[str] = []
    buf = ""
    quote = None
    depth = 0
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            buf += ch
        elif ch in "([":
            depth += 1
            buf += ch
        elif ch in ")]":
            depth -= 1
            buf += ch
        elif ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _split_kv(content: str) -> Tuple[str, bool, str]:
    """切分 'key: value'；返回 (key, found, value)。引号/括号内的冒号不算。"""
    quote = None
    depth = 0
    for i, ch in enumerate(content):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == ":" and depth == 0:
            key = content[:i].strip()
            if not key:
                raise ConfigSyntaxError(f"空键: {content!r}")
            return key, True, content[i + 1:].strip()
    return content, False, ""


def _parse_block(lines: List[Tuple[int, str]], i: int, indent: int):
    """递归下降：解析同一缩进级别的一个块（dict 或 list）。返回 (值, 新下标)。"""
    if i >= len(lines) or lines[i][0] < indent:
        return {}, i
    if lines[i][1].startswith("-"):
        # ── 列表块 ──
        result: List[Any] = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("-"):
            rest = lines[i][1][1:].strip()
            if rest == "":
                i += 1
                if i < len(lines) and lines[i][0] > indent:
                    sub, i = _parse_block(lines, i, lines[i][0])
                else:
                    sub = None
                result.append(sub)
                continue
            key, found, val = _split_kv(rest)
            if found:
                item: dict = {key: _parse_scalar(val) if val else None}
                i += 1
                if not val:
                    if i < len(lines) and lines[i][0] > indent:
                        sub, i = _parse_block(lines, i, lines[i][0])
                        item[key] = sub if sub is not None else None
                # 吸收该项的续行（更深缩进的 kv）
                while i < len(lines) and lines[i][0] > indent:
                    k2, f2, v2 = _split_kv(lines[i][1])
                    if not f2:
                        break
                    i += 1
                    if v2:
                        item[k2] = _parse_scalar(v2)
                    elif i < len(lines) and lines[i][0] > indent:
                        sub, i = _parse_block(lines, i, lines[i][0])
                        item[k2] = sub if sub is not None else None
                    else:
                        item[k2] = None
                result.append(item)
            else:
                result.append(_parse_scalar(rest))
                i += 1
        return result, i
    # ── 映射块 ──
    result: dict = {}
    while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("-"):
        key, found, val = _split_kv(lines[i][1])
        if not found:
            raise ConfigSyntaxError(f"无法解析: {lines[i][1]!r}")
        i += 1
        if val:
            result[key] = _parse_scalar(val)
        elif i < len(lines) and lines[i][0] > indent:
            sub, i = _parse_block(lines, i, lines[i][0])
            result[key] = sub if sub is not None else None
        else:
            result[key] = None
    return result, i


def loads(text: str) -> Any:
    """解析 YAML 子集文本 → Python 对象（dict/list/标量）。"""
    text = text.lstrip("\ufeff")  # 容忍 UTF-8 BOM（PowerShell Set-Content 常见）
    entries: List[Tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw)
        if not line.strip():
            continue
        stripped = line.lstrip()
        if line[: len(line) - len(stripped)].startswith("\t"):
            raise ConfigSyntaxError(f"第 {lineno} 行: 不支持 tab 缩进")
        entries.append((len(line) - len(stripped), stripped))
    if not entries:
        return {}
    root, _ = _parse_block(entries, 0, entries[0][0])
    return root


def _scalar_str(v: Any) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(ch in s for ch in (":", "#")) or s != s.strip() or s == "":
        return "'" + s.replace("'", "''") + "'"
    return s


def _emit(value: Any, indent: int, out: List[str]) -> None:
    pad = " " * indent
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, dict):
                out.append(f"{pad}{k}:")
                _emit(v, indent + 2, out)
            elif isinstance(v, list):
                if not v:
                    out.append(f"{pad}{k}: []")
                elif all(isinstance(x, dict) for x in v):
                    out.append(f"{pad}{k}:")
                    for item in v:
                        first = True
                        for kk, vv in item.items():
                            if isinstance(vv, dict):
                                out.append(f"{pad}- {kk}:" if first else f"{pad}  {kk}:")
                                _emit(vv, indent + 4, out)
                            elif isinstance(vv, list):
                                out.append(f"{pad}- {kk}: [{', '.join(_scalar_str(x) for x in vv)}]" if first else f"{pad}  {kk}: [{', '.join(_scalar_str(x) for x in vv)}]")
                            else:
                                out.append(f"{pad}- {kk}: {_scalar_str(vv)}" if first else f"{pad}  {kk}: {_scalar_str(vv)}")
                            first = False
                else:
                    out.append(f"{pad}{k}: [{', '.join(_scalar_str(x) for x in v)}]")
            else:
                out.append(f"{pad}{k}: {_scalar_str(v)}")
    elif isinstance(value, list):
        for x in value:
            out.append(f"{pad}- {_scalar_str(x)}")
    else:
        out.append(f"{pad}{_scalar_str(value)}")


def dumps(value: Any) -> str:
    """把 Python 对象发射为 YAML 子集文本。"""
    out: List[str] = []
    _emit(value, 0, out)
    return "\n".join(out) + "\n"


def load_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return loads(fh.read())


def dump_file(path: str, value: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(dumps(value))
