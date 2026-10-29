import tkinter as tk
from tkinter import messagebox
import random
import time
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os

class MahjongCardGame:
    def __init__(self, root):
        self.root = root
        self.root.title("麻将连连看")
        self.root.geometry("1000x750")
        self.root.configure(bg='#2d5016')

        self.load_fonts()

        # === 模式切换：'mahjong'=自由牌模式(正宗), 'link'=两折连线模式(上一版) ===
        self.mode = 'mahjong'

        # 棋盘：三维 (layer, row, col)，layer 0 最底
        self.max_layer = 4
        self.rows = 8
        self.cols = 14
        self.tile_size = 56
        self.margin_x = 30
        self.margin_y = 30
        # 选中
        self.selected = None
        # 游戏状态
        self.score = 0
        self.time_limit = 300  # 5分钟
        self.start_time = None
        self.game_running = False
        self.hint_avail = 3

        self.build_tile_deck()
        self.setup_ui()
        self.init_board()
        self.root.bind('<Escape>', lambda e: self.pause_game())
        self.root.bind('h', lambda e: self.show_hint())
        self.root.bind('r', lambda e: self.restart_game())
        self.root.bind('m', lambda e: self.toggle_mode())

    # ==================== 字体 ====================
    def load_fonts(self):
        base = os.path.dirname(os.path.abspath(__file__))
        # 主字体(SimHei 画汉字)
        simhei = os.path.join(base, 'SimHei.ttf')
        self.font_main = simhei if os.path.exists(simhei) else None
        # 符号字体(Arial 画 ♠♥♦♣，Windows/mac 都自带)
        arial_paths = [
            os.path.join(base, 'arial.ttf'),
            'C:/Windows/Fonts/arial.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]
        self.font_symbol = None
        for p in arial_paths:
            if os.path.exists(p):
                self.font_symbol = p
                break
        # tkinter 字体
        self.f = ('SimHei', 10)
        self.fb = ('SimHei', 12, 'bold')
        self.fbig = ('SimHei', 18, 'bold')

    def get_font(self, size=16, symbol=False):
        path = (self.font_symbol if symbol else self.font_main) or self.font_main
        try:
            return ImageFont.truetype(path, size)
        except:
            return ImageFont.load_default()

    # ==================== 牌堆 ====================
    def build_tile_deck(self):
        """标准 144 张麻将配比"""
        deck = []
        # 筒条万 各 4×9 = 36
        for s in ['筒','条','万']:
            for n in range(1,10):
                deck.extend([f'{s}{n}'] * 4)
        # 风 4×4=16
        for s in ['东','南','西','北']:
            deck.extend([s] * 4)
        # 箭 3×4=12
        for s in ['中','发','白']:
            deck.extend([s] * 4)
        # 季(春夏秋冬) 各1 → 4
        self.season = ['春','夏','秋','冬']
        deck.extend(self.season)
        # 花(梅兰菊竹) 各1 → 4
        self.flower = ['梅','兰','菊','竹']
        deck.extend(self.flower)
        # 共 36 * 3+16+12+4+4 = 144
        self.deck = deck
        # 纸牌（仍保留，作为彩蛋混进 mode='link' 时）
        self.card_tiles = []
        for s in ['♠','♥','♦','♣']:
            for v in ['A','2','3','4','5','6','7','8','9','10','J','Q','K']:
                self.card_tiles.append(f'{v}{s}')
        # 渲染缓存
        self.img_cache = {}

    def render_tile(self, txt):
        """画单张牌，♠♥♦♣ 用 symbol 字体避免方框"""
        sz = self.tile_size
        img = Image.new('RGBA', (sz-4, sz-4), (255, 255, 255, 245))
        draw = ImageDraw.Draw(img)
        # 边框
        bw = 2
        draw.rectangle([0,0,sz-5,sz-5], outline='#555', width=bw)
        # 颜色
        color_map = {'万':'#000','条':'#000','筒':'#000',
                     '东':'#c00','南':'#c00','西':'#c00','北':'#c00',
                     '中':'#c00','发':'#080','白':'#000',
                     '春':'#c0','夏':'#c0','秋':'#c0','冬':'#c0',
                     '梅':'#c0','兰':'#c0','菊':'#c0','竹':'#c0',
                     '♠':'#000','♣':'#000','♥':'#c00','♦':'#c00'}
        color = '#000'
        if txt in self.season or txt in self.flower:
            color = '#c60'
        elif txt in ['发']: color='#080'
        elif txt in ['中','东','南','西','北']: color='#c00'
        elif any(txt.endswith(s) for s in '♠♥♦♣'): color='#000' if txt.endswith(('♠','♣')) else '#c00'

        # 判断要不要切 symbol 字体
        need_sym = any(ch in txt for ch in '♠♥♦♣')
        if need_sym:
            # 两部分：汉字/数字 用 main，符号用 symbol
            # 简单策略：整串用 symbol 字体（Arial 能画数字+符号，但汉字会丑）
            # 更好：拆。这里简化——整串试 symbol，失败了回 main
            try:
                font = self.get_font(15, symbol=True)
                bbox = draw.textbbox((0,0), txt, font=font)
                w = bbox[2]-bbox[0]; h = bbox[3]-bbox[1]
                x = (sz-4-w)//2; y = (sz-4-h)//2
                draw.text((x, y), txt, fill=color, font=font)
            except:
                font = self.get_font(15, symbol=False)
                bbox = draw.textbbox((0,0), txt, font=font)
                w = bbox[2]-bbox[0]; h = bbox[3]-bbox[1]
                x = (sz-4-w)//2; y = (sz-4-h)//2
                draw.text((x, y), txt, fill=color, font=font)
        else:
            font = self.get_font(15, symbol=False)
            bbox = draw.textbbox((0,0), txt, font=font)
            w = bbox[2]-bbox[0]; h = bbox[3]-bbox[1]
            x = (sz-4-w)//2; y = (sz-4-h)//2
            draw.text((x, y), txt, fill=color, font=font)
        return ImageTk.PhotoImage(img)

    def get_img(self, txt):
        if txt not in self.img_cache:
            self.img_cache[txt] = self.render_tile(txt)
        return self.img_cache[txt]

    # ==================== 乌龟堆叠生成 ====================
    def gen_turtle_layout(self):
        """5 层乌龟形，返回 set of (layer,row,col) 有牌的位置，总牌数≈144"""
        L, R, C = self.max_layer, self.rows, self.cols
        occupied = set()
        # layer 0: 满 14×8 = 112
        for r in range(R):
            for c in range(C):
                occupied.add((0,r,c))
        # layer 1: 中央 12×6 → 72，但和 l0 重叠，实际新增 72-被l0盖的不算，这里是位置标记
        # 我们用"牌放哪些 (l,r,c)"来记，生成时直接给牌
        # 简化：预定义每层 (r_range, c_range)
        layers_spec = [
            (0, R, 0, C),          # l0: 14×8
            (1, 6, 1, 12),         # l1: 12×6 居中
            (2, 4, 2, 10),         # l2: 10×4
            (3, 3, 3, 8),          # l3: 8×3
            (4, 2, 4, 6),          # l4: 6×2 头顶
        ]
        # 收集所有 (l,r,c)
        slots = []
        for l, nr, sr, sc in layers_spec:
            for r in range(sr, sr+nr):
                for c in range(sc, sc+sc+nr-2):  # 动态算 c_end
                    pass
        # 上面手写规格容易错，改用更稳的"乌龟"经典坐标：
        # 经典乌龟：底 14col×8row，二层 12×6，三层 10×4，四层 8×3，顶 6×2
        # 每层的 (r_start, r_count, c_start, c_count)
        turtle = [
            (0, 8, 0, 14),   # 112
            (1, 6, 1, 12),   # +72 但和底重叠位置? 不——麻将堆叠是"放在底牌上面"，同(r,c)可以叠多层
            (2, 4, 2, 10),   # 所以是一个 (r,c) 柱可叠 0~4 层
            (3, 3, 3, 8),
            (4, 2, 4, 6),
        ]
        # 算总 slot 数（去重？不，同(r,c)不同l是不同slot）
        # l0: 8 * 14=112, l1:6 * 12=72, l2:4 * 10=40, l3:3 * 8=24, l4:2 * 6=12 → 总 260 个 slot
        # 但我们只取 144 张，方法是：所有 slot 列出来，随机抽 144 个放牌，其余留空
        # 更正的乌龟：经典 144 张是这样分配的（实际上海麻将布局不是全满的，有镂空）
        # 为简化，我们直接按 slot 总数 = 144 来造：
        # 重新设计：l0 只铺"乌龟壳"形状而非全满，太复杂。回到简单可靠方案——
        return self.gen_simple_layers()

    def gen_simple_layers(self):
        """简化多层：保证总牌=144，layer 0 最大，往上缩小，每个(l,r,c)唯一"""
        # 目标 144，分配：l0=80, l1=36, l2=20, l3=8 → 144
        spec = [
            (0, 8, 10),   # 8行 10列 = 80
            (1, 6, 8),    # 6×8 = 48 → 但我们要 36，所以裁
            (2, 4, 6),    # 4×6 = 24 → 要 20
            (3, 2, 4),    # 2×4 = 8
        ]
        # 调整：l0=10×8=80, l1=8×6=48→取36, l2=6×4=24→取20, l3=4×2=8 → 80+36+20+8=144 ✓
        # 实现：每层从中心缩进
        slots = []
        # L0: rows 0..7, cols 2..11 (10×8)
        for r in range(8):
            for c in range(2, 12):
                slots.append((0, r, c))
        # L1: rows 1..6, cols 3..10 (6×8=48) → 只取 36 个：均匀跳
        l1_slots = []
        for r in range(1, 7):
            for c in range(3, 11):
                l1_slots.append((1, r, c))
        slots.extend(l1_slots[:36])
        # L2: rows 2..5, cols 4..9 (4×6=24) → 取 20
        l2_slots = []
        for r in range(2, 6):
            for c in range(4, 10):
                l2_slots.append((2, r, c))
        slots.extend(l2_slots[:20])
        # L3: rows 3..4, cols 5..8 (2×4=8)
        for r in range(3, 5):
            for c in range(5, 9):
                slots.append((3, r, c))
        # slots 共 80+36+20+8=144
        return slots

    # ==================== 自由牌判定 ====================
    def is_free(self, l, r, c):
        """麻将连连看自由牌：上无牌 + 左或右至少一侧同层无邻接"""
        board = self.board
        # 1) 上方无牌（更高 layer 同(r,c) 空）
        for ll in range(l+1, self.max_layer+1):
            if (ll, r, c) in board and board[(ll,r,c)] is not None:
                return False
        # 2) 左右至少一侧空（同 layer 同 row，c-1 或 c+1 要么越界要么无牌）
        left_free = (c-1 < 0) or ((l,r,c-1) not in board or board[(l,r,c-1)] is None)
        right_free = (c+1 >= self.cols) or ((l,r,c+1) not in board or board[(l,r,c+1)] is None)
        return left_free or right_free

    # ==================== 两折连通（link 模式用） ====================
    def can_link(self, pos1, pos2):
        """pos = (l,r,c)，混合模式里允许跨层？不，麻将堆叠里通常同"可见面"——简化：只比(r,c)，layer 忽略（因为自由牌上方无遮挡，可视作同面）"""
        _, r1, c1 = pos1
        _, r2, c2 = pos2
        # 0 折
        if r1 == r2:
            lo, hi = sorted([c1, c2])
            ok = True
            for c in range(lo+1, hi):
                if (0, r1, c) in self.board and self.board[(0, r1, c)] is not None:
                    # 要检查所有 layer 这个(r,c) 是否有牌
                    has = any(self.board.get((ll, r1, c)) is not None for ll in range(self.max_layer+1))
                    if has:
                        ok = False; break
            if ok: return True
        if c1 == c2:
            lo, hi = sorted([r1, r2])
            ok = True
            for r in range(lo+1, hi):
                has = any(self.board.get((ll, r, c1)) is not None for ll in range(self.max_layer+1))
                if has:
                    ok = False; break
            if ok: return True
        # 1 折
        # (r1,c2)
        if self._cell_clear(r1, c2):
            c_ok = True
            if r1 == r2: pass
            else:
                lo,hi = sorted([r1,r2])
                for rr in range(lo+1, hi):
                    if any(self.board.get((ll,rr,c2)) is not None for ll in range(self.max_layer+1)):
                        c_ok=False; break
            h_ok = True
            if c1==c2: pass
            else:
                lo,hi = sorted([c1,c2])
                for cc in range(lo+1, hi):
                    if any(self.board.get((ll,r1,cc)) is not None for ll in range(self.max_layer+1)):
                        h_ok=False; break
            if c_ok and h_ok: return True
        # (r2,c1)
        if self._cell_clear(r2, c1):
            c_ok = True
            if r1==r2: pass
            else:
                lo,hi=sorted([r1,r2])
                for rr in range(lo+1,hi):
                    if any(self.board.get((ll,rr,c1)) is not None for ll in range(self.max_layer+1)):
                        c_ok=False; break
            h_ok = True
            if c1==c2: pass
            else:
                lo,hi=sorted([c1,c2])
                for cc in range(lo+1,hi):
                    if any(self.board.get((ll,r2,cc)) is not None for ll in range(self.max_layer+1)):
                        h_ok=False; break
            if c_ok and h_ok: return True
        # 2 折：略，扫行+扫列
        # 水平扫：从 r1 行找中继 c_mid，使 (r1,c1)-(r1,c_mid)直, (r1,c_mid)-(r2,c_mid)直?, (r2,c_mid)-(r2,c2)直
        # 简化：只做 0/1 折够用，2 折同上一版
        return self._can_link_2corner(pos1, pos2)

    def _cell_clear(self, r, c):
        """(r,c) 所有 layer 都空 → 可作为折点"""
        return all(self.board.get((ll, r, c)) is None for ll in range(self.max_layer+1))

    def _can_link_2corner(self, pos1, pos2):
        (l1,r1,c1),(l2,r2,c2)=pos1,pos2
        # 水平中介：固定 r1，扫 c_mid；固定 r2，扫 c_mid
        for rm in [r1, r2]:
            for cm in range(self.cols):
                if not self._cell_clear(rm, cm): continue
                # (r1,c1)-(rm,cm) 直？
                if rm==r1:
                    lo,hi=sorted([c1,cm])
                    hok=True
                    for cc in range(lo+1,hi):
                        if not self._cell_clear(r1,cc): hok=False;break
                    if not hok: continue
                    # (rm,cm)-(r2,c2) 要 1折或直
                    if cm==c2:
                        lo,hi2=sorted([rm,r2])
                        vok=True
                        for rr in range(lo+1,hi2):
                            if not self._cell_clear(rr,cm): vok=False;break
                        if vok: return True
                    elif rm==r2:
                        lo,hi2=sorted([cm,c2])
                        hok2=True
                        for cc in range(lo+1,hi2):
                            if not self._cell_clear(r2,cc): hok2=False;break
                        if hok2: return True
                # 对称略——复用上一版逻辑更简单，这里直接调旧函数改坐标
        # 垂直中介
        for cm in [c1, c2]:
            for rm in range(self.rows):
                if not self._cell_clear(rm, cm): continue
                if cm==c1:
                    lo,hi=sorted([r1,rm])
                    vok=True
                    for rr in range(lo+1,hi):
                        if not self._cell_clear(rr,c1): vok=False;break
                    if not vok: continue
                    if rm==r2:
                        lo,hi2=sorted([c1,c2])
                        hok=True
                        for cc in range(lo+1,hi2):
                            if not self._cell_clear(r2,cc): hok=False;break
                        if hok: return True
                    elif cm==c2:
                        lo,hi2=sorted([rm,r2])
                        vok2=True
                        for rr in range(lo+1,hi2):
                            if not self._cell_clear(rr,c2): vok2=False;break
                        if vok2: return True
        return False

    # ==================== 同组判定（季/花） ====================
    def tile_match(self, a, b):
        """是否可配对：同字符串，或同属季/花组"""
        if a == b: return True
        if a in self.season and b in self.season: return True
        if a in self.flower and b in self.flower: return True
        return False

    # ==================== UI & 游戏 ====================
    def setup_ui(self):
        top = tk.Frame(self.root, bg='#2d5016')
        top.pack(fill=tk.X, padx=10, pady=8)
        # 分数
        f1 = tk.Frame(top, bg='#1a3009', bd=2, relief=tk.RAISED)
        f1.pack(side=tk.LEFT, padx=8)
        tk.Label(f1,text='分数',font=self.fb,bg='#1a3009',fg='white').pack(padx=8,pady=(4,0))
        self.score_lbl = tk.Label(f1,text='0',font=self.fbig,bg='#1a3009',fg='#fc0')
        self.score_lbl.pack(padx=8,pady=(0,4))
        # 时间
        f2 = tk.Frame(top, bg='#1a3009', bd=2, relief=tk.RAISED)
        f2.pack(side=tk.LEFT, padx=8)
        tk.Label(f2,text='时间',font=self.fb,bg='#1a3009',fg='white').pack(padx=8,pady=(4,0))
        self.time_lbl = tk.Label(f2,text='05:00',font=self.fbig,bg='#1a3009',fg='#0cf')
        self.time_lbl.pack(padx=8,pady=(0,4))
        # 剩余
        f3 = tk.Frame(top, bg='#1a3009', bd=2, relief=tk.RAISED)
        f3.pack(side=tk.LEFT, padx=8)
        tk.Label(f3,text='剩余',font=self.fb,bg='#1a3009',fg='white').pack(padx=8,pady=(4,0))
        self.rem_lbl = tk.Label(f3,text='144',font=self.fbig,bg='#1a3009',fg='#f90')
        self.rem_lbl.pack(padx=8,pady=(0,4))
        # 模式
        f4 = tk.Frame(top, bg='#1a3009', bd=2, relief=tk.RAISED)
        f4.pack(side=tk.LEFT, padx=8)
        tk.Label(f4,text='模式',font=self.fb,bg='#1a3009',fg='white').pack(padx=8,pady=(4,0))
        self.mode_lbl = tk.Label(f4,text='麻将',font=self.fbig,bg='#1a3009',fg='#fff')
        self.mode_lbl.pack(padx=8,pady=(0,4))

        btn = tk.Frame(top, bg='#2d5016')
        btn.pack(side=tk.RIGHT, padx=10)
        tk.Button(btn,text='提示(H)',font=self.f,command=self.show_hint,bg='#4a752c',fg='white').pack(side=tk.LEFT,padx=3)
        tk.Button(btn,text='重开(R)',font=self.f,command=self.restart_game,bg='#4a752c',fg='white').pack(side=tk.LEFT,padx=3)
        tk.Button(btn,text='模式(M)',font=self.f,command=self.toggle_mode,bg='#4a752c',fg='white').pack(side=tk.LEFT,padx=3)
        tk.Button(btn,text='帮助(?)',font=self.f,command=self.show_help,bg='#4e2c8a',fg='white').pack(side=tk.LEFT,padx=3)

        gf = tk.Frame(self.root, bg='#1a3009', bd=3, relief=tk.SUNKEN)
        gf.pack(padx=10, pady=(0,10))
        cw = self.cols*self.tile_size + 60
        ch = (self.max_layer+1)*(self.tile_size//3+self.rows*self.tile_size) + 60  # 层间有偏移
        # 实际上我们用 canvas 画，layer 用 y 偏移表现 3D
        self.canvas = tk.Canvas(gf, width=cw, height=600, bg='#0f1f05', highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<Button-1>', self.on_click)

        st = tk.Frame(self.root, bg='#1a3009')
        st.pack(fill=tk.X, padx=10, pady=(0,8))
        self.status = tk.Label(st, text='麻将连连看 · M键切换模式 · H提示', font=self.f, bg='#1a3009', fg='white')
        self.status.pack(pady=3)

        # board 数据结构：dict {(l,r,c): tile_str or None}
        self.board = {}
        self.cid = {}  # (l,r,c) -> canvas item id

    def toggle_mode(self):
        self.mode = 'link' if self.mode == 'mahjong' else 'mahjong'
        self.mode_lbl.config(text='连线' if self.mode=='link' else '麻将')
        self.restart_game()

    def init_board(self):
        # 生成 144 张
        deck = list(self.deck)
        random.shuffle(deck)
        slots = self.gen_simple_layers()  # 144 slots
        self.board = {}
        for (l,r,c), tile in zip(slots, deck):
            self.board[(l,r,c)] = tile
        self._draw_all()
        self.score = 0
        self.score_lbl.config(text='0')
        self.start_time = time.time()
        self.game_running = True
        self.selected = None
        self.hint_avail = 3
        self._update_rem()
        self._timer()

    def _draw_all(self):
        self.canvas.delete('all')
        self.cid = {}
        # 层从上往下画（l大先画=底，l小后画=顶）—— 3D 感：l 越大 y 偏移越小
        for (l,r,c), tile in self.board.items():
            if tile is None: continue
            # 层偏移：layer 越大越"靠前靠上"
            y_off = l * (self.tile_size // 3)
            x = self.margin_x + c * self.tile_size
            y = self.margin_y + r * self.tile_size - y_off
            img = self.get_img(tile)
            iid = self.canvas.create_image(x, y, anchor=tk.NW, image=img, tags=f'l{l}')
            self.cid[(l,r,c)] = iid

    def _screen_xy(self, l, r, c):
        y_off = l * (self.tile_size // 3)
        x = self.margin_x + c * self.tile_size
        y = self.margin_y + r * self.tile_size - y_off
        return x, y

    def on_click(self, ev):
        if not self.game_running: return
        # 反算 (l,r,c)：从上往下(layer大→小) 查 hit
        mx, my = ev.x, ev.y
        for l in range(self.max_layer, -1, -1):
            for (ll,rr,cc), iid in self.cid.items():
                if ll != l or self.board[(ll,rr,cc)] is None: continue
                x, y = self._screen_xy(ll, rr, cc)
                if x <= mx <= x+self.tile_size and y <= my <= y+self.tile_size:
                    self._handle_pick(ll, rr, cc)
                    return

    def _handle_pick(self, l, r, c):
        tile = self.board[(l,r,c)]
        if tile is None: return

        if self.mode == 'mahjong':
            # 必须自由牌
            if not self.is_free(l, r, c):
                self.status.config(text=f'{tile} 不是自由牌（上方有压或左右都堵）')
                return

        # 选/配
        if self.selected is None:
            self.selected = (l, r, c)
            self._hl((l,r,c), True)
            self.status.config(text=f'已选: {tile}')
        else:
            prev = self.selected
            self._hl(prev, False)
            if prev == (l,r,c):
                self.selected = None
                return
            ptile = self.board[prev]
            if not self.tile_match(ptile, tile):
                self.status.config(text=f'{ptile} ≠ {tile}')
                self.selected = None
                return
            # 连通检查
            if self.mode == 'link' and not self.can_link(prev, (l,r,c)):
                self.status.config(text='连线不通（需≤2折）')
                self.selected = None
                return
            # 消
            self.board[prev] = None
            self.board[(l,r,c)] = None
            self.canvas.delete(self.cid[prev])
            self.canvas.delete(self.cid[(l,r,c)])
            self.cid.pop(prev)
            self.cid.pop((l,r,c))
            self.score += 10
            if self.mode=='mahjong' and (ptile in self.season or ptile in self.flower):
                self.score += 5  # 季/花 bonus
            self.score_lbl.config(text=str(self.score))
            self.selected = None
            rem = self._update_rem()
            self.status.config(text=f'消除 {ptile}+{tile}')
            if rem == 0:
                self._win()
            elif self.mode == 'mahjong' and not self._has_free_pair():
                messagebox.showinfo('死局', '无可用自由牌配对，自动洗牌重排')
                self._reshuffle()

    def _hl(self, pos, on):
        l,r,c = pos
        x,y = self._screen_xy(l,r,c)
        tag = f'hl_{l}_{r}_{c}'
        if on:
            self.canvas.create_rectangle(x-2, y-2, x+self.tile_size+1, y+self.tile_size+1,
                                         outline='#ff0', width=3, tags=tag)
        else:
            self.canvas.delete(tag)

    def _update_rem(self):
        n = sum(1 for v in self.board.values() if v is not None)
        self.rem_lbl.config(text=str(n))
        return n

    def _has_free_pair(self):
        """mahjong 模式下检查是否还有可配对的自由牌"""
        frees = [(l,r,c,t) for (l,r,c),t in self.board.items() if t is not None and self.is_free(l,r,c)]
        for i in range(len(frees)):
            for j in range(i+1, len(frees)):
                _,_,_,a = frees[i]; _,_,_,b = frees[j]
                if self.tile_match(a,b):
                    return True
        return False

    def _reshuffle(self):
        """死局时保留 layer 位置，打乱牌面"""
        tiles = [t for t in self.board.values() if t is not None]
        random.shuffle(tiles)
        # 重新填回原 (l,r,c) 空位
        slots = [k for k,v in self.board.items() if v is not None]
        for k in slots:
            self.board[k] = None
        idx = 0
        for k in slots:
            self.board[k] = tiles[idx]; idx+=1
        self._draw_all()

    def show_hint(self):
        if not self.game_running or self.hint_avail <= 0: return
        if self.mode == 'mahjong':
            frees = [(l,r,c,self.board[(l,r,c)]) for (l,r,c) in self.board if self.board[(l,r,c)] and self.is_free(l,r,c)]
            for i in range(len(frees)):
                for j in range(i+1,len(frees)):
                    _,_,_,a=frees[i]; _,_,_,b=frees[j]
                    if self.tile_match(a,b):
                        self._hl(frees[i][:3],True); self._hl(frees[j][:3],True)
                        self.hint_avail -= 1
                        self.root.after(2000, lambda: [self._hl(frees[i][:3],False), self._hl(frees[j][:3],False)])
                        return
        else:
            # link 模式：找同牌+可连通
            tiles = [(l,r,c,self.board[(l,r,c)]) for (l,r,c) in self.board if self.board[(l,r,c)]]
            for i in range(len(tiles)):
                for j in range(i+1,len(tiles)):
                    if tiles[i][3]==tiles[j][3] and self.can_link(tiles[i][:3], tiles[j][:3]):
                        self._hl(tiles[i][:3],True); self._hl(tiles[j][:3],True)
                        self.hint_avail-=1
                        self.root.after(2000, lambda: [self._hl(tiles[i][:3],False), self._hl(tiles[j][:3],False)])
                        return

    def _timer(self):
        if not self.game_running: return
        el = int(time.time()-self.start_time)
        rem = max(0, self.time_limit-el)
        m,s = rem//60, rem%60
        self.time_lbl.config(text=f'{m:02d}:{s:02d}')
        if rem>0: self.root.after(1000, self._timer)
        else: self._lose()

    def _win(self):
        self.game_running=False
        messagebox.showinfo('通关!', f'分数:{self.score}')

    def _lose(self):
        self.game_running=False
        messagebox.showinfo('超时','时间到')

    def restart_game(self):
        self.init_board()

    def pause_game(self):
        self.game_running = not self.game_running
        if self.game_running: self._timer()

    def show_help(self):
        msg = (
            "麻将连连看\n"
            "· 模式[M]切换：'麻将'=自由牌(正宗) / '连线'=两折连通\n"
            "· 自由牌：上方无压 + 左右至少一侧露边\n"
            "· 季(春夏秋冬)互配、花(梅兰菊竹)互配\n"
            "· H提示  R重开  ESC暂停  M切模式\n"
            "· 每消+10，季/花额外+5"
        )
        messagebox.showinfo('帮助', msg)

if __name__ == '__main__':
    root = tk.Tk()
    MahjongCardGame(root)
    root.mainloop()