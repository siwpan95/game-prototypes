import os
import sys

# 输出路径与测试目录均基于脚本位置推导（scripts/ 的上级即项目根），
# 脚本被挪动后（2026-07-27 归档至 scripts/）仍可正确运行。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(_ROOT, "pytest_out.txt")

buf = open(OUT, "w", encoding="utf-8")
old_stdout = sys.stdout
sys.stdout = buf

try:
    import pytest
except ImportError as e:
    buf.write("PYTEST_NOT_INSTALLED: %r\n" % e)
    sys.stdout = old_stdout
    buf.close()
    sys.exit(3)

tests_dir = os.path.join(_ROOT, "tests")
rc = pytest.main([tests_dir, "-q", "--no-header", "-p", "no:cacheprovider", "-rA"])
sys.stdout = old_stdout
buf.write("\nRETCODE=%d\n" % rc)
buf.close()
