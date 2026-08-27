"""Text Formatter — 文本格式化工具。"""

from __future__ import annotations

import re
import textwrap


class TextFormatter:
    """文本格式化静态工具类。"""

    @staticmethod
    def wrap(text: str, width: int = 80, indent: str = "") -> str:
        lines = text.split("\n")
        result = []
        for line in lines:
            if line.strip():
                wrapped = textwrap.wrap(line, width=width - len(indent))
                for wline in wrapped or [""]:
                    result.append(indent + wline)
            else:
                result.append("")
        return "\n".join(result)

    @staticmethod
    def highlight(text: str, keyword: str, mark: str = "[]") -> str:
        pattern = compile(re.escape(keyword), re.IGNORECASE)
        return pattern.sub(f"{mark}{keyword}{mark}", text)

    @staticmethod
    def truncate(text: str, max_len: int = 200, ellipsis: str = "...") -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - len(ellipsis)] + ellipsis

    @staticmethod
    def title_case(text: str) -> str:
        return text.title()

    @staticmethod
    def progress_bar(current: int, total: int, width: int = 20,
                     filled: str = "█", empty: str = "░") -> str:
        if total == 0:
            return f"[{empty * width}]"
        ratio = current / total
        filled_count = int(width * ratio)
        bar = filled * filled_count + empty * (width - filled_count)
        percent = int(ratio * 100)
        return f"[{bar}] {percent}%"

    @staticmethod
    def format_sanity(sanity: int, max_sanity: int) -> str:
        pct = sanity / max(max_sanity, 1)
        if pct > 0.6:
            color = "#2ecc71"
        elif pct > 0.3:
            color = "#f39c12"
        else:
            color = "#e74c3c"
        return f"清晰度: {sanity}/{max_sanity}"

    @staticmethod
    def format_corruption(corruption: int) -> str:
        return f"浑浊度: {corruption}/100"
