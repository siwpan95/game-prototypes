"""路径解析工具"""
import os

# ---------------------------- Path Resolution ----------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(filename: str) -> str:
    """获取脚本目录下的文件绝对路径"""
    return os.path.join(SCRIPT_DIR, filename)
