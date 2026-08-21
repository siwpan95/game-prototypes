# -*- coding: utf-8 -*-
"""均匀网格空间哈希：尸潮碰撞检测的命根子。

把敌人按 cell(64px) 分桶，投射物/脉冲只查询自己覆盖到的桶，
把 O(弹数×敌数) 的两两检测压成 O(弹数×邻域数)。
"""


class SpatialHash:
    __slots__ = ("cell", "buckets")

    def __init__(self, cell=64.0):
        self.cell = cell
        self.buckets = {}

    def clear(self):
        self.buckets.clear()

    def _key(self, x, y):
        return (int(x // self.cell), int(y // self.cell))

    def insert(self, obj):
        """obj 需有 .x .y 属性。"""
        k = self._key(obj.x, obj.y)
        b = self.buckets.get(k)
        if b is None:
            self.buckets[k] = [obj]
        else:
            b.append(obj)

    def insert_many(self, objs):
        for o in objs:
            self.insert(o)

    def query(self, x, y, radius):
        """返回覆盖 (x,y,radius) 圆的所有桶中对象（未做精确距离过滤）。"""
        c = self.cell
        x0 = int((x - radius) // c)
        x1 = int((x + radius) // c)
        y0 = int((y - radius) // c)
        y1 = int((y + radius) // c)
        out = []
        buckets = self.buckets
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                b = buckets.get((gx, gy))
                if b:
                    out.extend(b)
        return out

    def query_pairs_cellwise(self):
        """逐桶内两两配对，用于敌人相互推挤（只在同桶内做，代价可控）。"""
        for b in self.buckets.values():
            n = len(b)
            if n > 1:
                for i in range(n):
                    for j in range(i + 1, n):
                        yield b[i], b[j]
