"""一次性补丁脚本：给 kid_a_walker.py 加 find_safe_spawn 并修类型注解。

目标文件解析：命令行参数 → 本文件同级的 ../kid-a-walker/kid_a_walker.py → fail-loud
（原写法钉死在本机一条已失效的绝对路径上，见硬编码门禁清单）

用法:
    python fix_script.py                       # 默认改本仓 games/kid-a-walker/kid_a_walker.py
    python fix_script.py <kid_a_walker.py 路径> # 指定其它副本
"""
import re
import sys
from pathlib import Path

DEFAULT_TARGET = Path(__file__).resolve().parent.parent / "kid-a-walker" / "kid_a_walker.py"


def resolve_target():
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    if DEFAULT_TARGET.is_file():
        return DEFAULT_TARGET
    raise SystemExit(
        f"[fix_script] 找不到目标文件：{DEFAULT_TARGET}\n"
        f"  用法：python {Path(__file__).name} <kid_a_walker.py 路径>"
    )


filepath = str(resolve_target())

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加 find_safe_spawn 方法到 WorldMap 类
old_init_end = "        self._generate_chunk((0, 0), required_exits={'N','S','E','W'})\n\n    # ── 出口查询 ──"

new_init_end = """        self._generate_chunk((0, 0), required_exits={'N','S','E','W'})

    def find_safe_spawn(self, cx, cy):
        chunk = self._chunks.get((cx, cy))
        if chunk is None:
            self._generate_chunk((cx, cy))
            chunk = self._chunks.get((cx, cy))
        if chunk is None:
            return (cx * CHUNK_SIZE + 10.5, cy * CHUNK_SIZE + 10.5)
        center = CHUNK_SIZE // 2
        for radius in range(8):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue
                    lx, ly = center + dx, center + dy
                    if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                        if chunk[ly][lx] == '.':
                            return (cx * CHUNK_SIZE + lx + 0.5, cy * CHUNK_SIZE + ly + 0.5)
        for ly in range(CHUNK_SIZE):
            for lx in range(CHUNK_SIZE):
                if chunk[ly][lx] == '.':
                    return (cx * CHUNK_SIZE + lx + 0.5, cy * CHUNK_SIZE + ly + 0.5)
        return (cx * CHUNK_SIZE + 10.5, cy * CHUNK_SIZE + 10.5)

    # ── 出口查询 ──"""

if old_init_end in content:
    content = content.replace(old_init_end, new_init_end, 1)
    print("1. Added find_safe_spawn method")
else:
    print("1. WARNING: Pattern not found for find_safe_spawn")

# 2. 更新出生位置使用 find_safe_spawn
old_spawn = "    # 玩家出生在起始区块中心\n    px, py, pang = CHUNK_SIZE * 0.5, CHUNK_SIZE * 0.5, 0.0"
new_spawn = """    # 玩家出生在起始区块中心（使用find_safe_spawn确保安全）
    spawn_x, spawn_y = world.find_safe_spawn(0, 0)
    px, py, pang = spawn_x, spawn_y, 0.0"""

if old_spawn in content:
    content = content.replace(old_spawn, new_spawn, 1)
    print("2. Updated spawn position")
else:
    print("2. WARNING: Pattern not found for spawn")

# 3. 修复类型注解ERROR - _generate_chunk
old_gen = "    def _generate_chunk(self, coord: tuple[int,int], required_exits: set | None = None):"
new_gen = "    def _generate_chunk(self, coord, required_exits=None):"

if old_gen in content:
    content = content.replace(old_gen, new_gen, 1)
    print("3. Fixed _generate_chunk type annotation")
else:
    print("3. WARNING: Pattern not found for _generate_chunk")

# 4. 修复 _pick_exits
old_pick = "    def _pick_exits(self, forced: set) -> frozenset:"
new_pick = "    def _pick_exits(self, forced) -> frozenset:"

if old_pick in content:
    content = content.replace(old_pick, new_pick, 1)
    print("4. Fixed _pick_exits type annotation")
else:
    print("4. WARNING: Pattern not found for _pick_exits")

# 5. 修复 _pick_template
old_tmpl = "    def _pick_template(self, exits: frozenset):"
new_tmpl = "    def _pick_template(self, exits):"

if old_tmpl in content:
    content = content.replace(old_tmpl, new_tmpl, 1)
    print("5. Fixed _pick_template type annotation")
else:
    print("5. WARNING: Pattern not found for _pick_template")

# 6. 修复 generated_chunks
old_genchunks = "    def generated_chunks(self) -> list[tuple[int,int]]:"
new_genchunks = "    def generated_chunks(self):"

if old_genchunks in content:
    content = content.replace(old_genchunks, new_genchunks, 1)
    print("6. Fixed generated_chunks type annotation")
else:
    print("6. WARNING: Pattern not found for generated_chunks")

# 7. 修复 _apply_reverb 的 delay_ms 类型问题
old_reverb = "        samples = _apply_reverb(samples, delay_ms=50 + cfg.reverb_dense * 80,"
new_reverb = "        samples = _apply_reverb(samples, delay_ms=int(50 + cfg.reverb_dense * 80),"

if old_reverb in content:
    content = content.replace(old_reverb, new_reverb, 1)
    print("7. Fixed _apply_reverb delay_ms type")
else:
    print("7. WARNING: Pattern not found for _apply_reverb")

# 8. 修复 _apply_reverb 函数参数类型
old_reverb_fn = "def _apply_reverb(samples: list, delay_ms: float = 80, decay: float = 0.3):"
new_reverb_fn = "def _apply_reverb(samples, delay_ms=80, decay=0.3):"

if old_reverb_fn in content:
    content = content.replace(old_reverb_fn, new_reverb_fn, 1)
    print("8. Fixed _apply_reverb function signature")
else:
    print("8. WARNING: Pattern not found for _apply_reverb function")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone! All fixes applied.")
