"""一次性补丁脚本（第二轮）：修 kid_a_walker.py 的 frozenset / 类型注解。

目标文件解析：命令行参数 → 本文件同级的 ../kid-a-walker/kid_a_walker.py → fail-loud
（原写法钉死在本机一条已失效的绝对路径上，见硬编码门禁清单）

用法:
    python fix_script2.py                       # 默认改本仓 games/kid-a-walker/kid_a_walker.py
    python fix_script2.py <kid_a_walker.py 路径> # 指定其它副本
"""
import sys
from pathlib import Path

DEFAULT_TARGET = Path(__file__).resolve().parent.parent / "kid-a-walker" / "kid_a_walker.py"


def resolve_target():
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    if DEFAULT_TARGET.is_file():
        return DEFAULT_TARGET
    raise SystemExit(
        f"[fix_script2] 找不到目标文件：{DEFAULT_TARGET}\n"
        f"  用法：python {Path(__file__).name} <kid_a_walker.py 路径>"
    )


filepath = str(resolve_target())

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复 Line 497: frozenset -> set
old_line497 = "        self._exits[coord]  = exits"
new_line497 = "        self._exits[coord]  = set(exits)"

if old_line497 in content:
    content = content.replace(old_line497, new_line497, 1)
    print("Fixed Line 497: frozenset -> set")
else:
    print("WARNING: Pattern not found for Line 497")

# 修复 Line 499: 移除 frozenset 返回类型注解
old_line499 = "    def _pick_exits(self, forced) -> frozenset:"
new_line499 = "    def _pick_exits(self, forced):"

if old_line499 in content:
    content = content.replace(old_line499, new_line499, 1)
    print("Fixed Line 499: removed frozenset return type")
else:
    print("WARNING: Pattern not found for Line 499")

# 修复 Line 575: set -> set[str] 或移除类型注解
old_line575 = "    def exits_of(self, cx, cy) -> set:"
new_line575 = "    def exits_of(self, cx, cy):"

if old_line575 in content:
    content = content.replace(old_line575, new_line575, 1)
    print("Fixed Line 575: removed set return type")
else:
    print("WARNING: Pattern not found for Line 575")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone!")
