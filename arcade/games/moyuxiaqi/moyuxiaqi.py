import pygame
import pygame.sysfont as _sysfont
import random
import time
import os

# --- Python 3.14 兼容性补丁 ---
# pygame.sysfont.initsysfonts_win32() 在 Python 3.14 下会因为字体枚举返回非字符串类型而崩溃
_original_initsysfonts_win32 = _sysfont.initsysfonts_win32
def _patched_initsysfonts_win32():
    try:
        return _original_initsysfonts_win32()
    except TypeError:
        return []  # 忽略错误，返回空字体列表
_sysfont.initsysfonts_win32 = _patched_initsysfonts_win32


def _get_chinese_font(size):
    """获取支持中文显示的字体"""
    font_paths = [
        'C:/Windows/Fonts/msyh.ttc',    # 微软雅黑
        'C:/Windows/Fonts/simhei.ttf',   # 黑体
        'C:/Windows/Fonts/simsun.ttc',   # 宋体
        'C:/Windows/Fonts/arial.ttf',    # Arial（英文回退）
    ]
    for path in font_paths:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)  # 默认字体


# 设置环境变量以支持中文路径
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'windib'

# 初始化Pygame
_ = pygame.init()

# 游戏常量
GRID_SIZE = 6  # 6x6 棋盘，比4x4稍大但不过分
CELL_SIZE = 80
MARGIN = 10
WIDTH = HEIGHT = GRID_SIZE * CELL_SIZE + (GRID_SIZE + 1) * MARGIN
FPS = 60  # 降低帧率节省资源

# 颜色定义
COLORS = {
    0: (204, 192, 179),  # 空单元格
    2: (238, 228, 218),
    4: (237, 224, 200),
    8: (242, 177, 121),
    16: (245, 149, 99),
    32: (246, 124, 95),
    64: (246, 94, 59),
    128: (237, 207, 114),
    256: (237, 204, 97),
    512: (237, 200, 80),
    1024: (237, 197, 63),
    2048: (237, 194, 46)
}

# 文字颜色
TEXT_COLORS = {
    2: (119, 110, 101),
    4: (119, 110, 101),
    8: (249, 246, 242),
    16: (249, 246, 242),
    32: (249, 246, 242),
    64: (249, 246, 242),
    128: (249, 246, 242),
    256: (249, 246, 242),
    512: (249, 246, 242),
    1024: (249, 246, 242),
    2048: (249, 246, 242)
}

class Auto2048Chess:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT + 100))  # 底部留空间显示状态
        pygame.display.set_caption("挂机摸鱼2048棋 - 自动运行中...")
        self.clock = pygame.time.Clock()
        self.font = _get_chinese_font(36)
        self.small_font = _get_chinese_font(24)
        
        # 游戏状态
        self.board = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.score = 0
        self.moves = 0
        self.game_over = False
        self.auto_mode = True
        self.last_move_time = time.time()
        self.move_delay = 0.5  # 自动移动间隔(秒)
        self.ai_thinking = False
        
        # 添加起始棋子
        self.add_random_tile()
        self.add_random_tile()
        
        # 游戏记录
        self.history = []
        self.max_tile = 2
        self.streak = 0  # 连击数
        
        # AI策略队列
        self.strategies = ["merge", "consolidate", "corner", "random"]
        self.current_strategy = 0
        
    def add_random_tile(self):
        """添加一个随机棋子"""
        empty_cells = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) if self.board[r][c] == 0]
        if empty_cells:
            r, c = random.choice(empty_cells)
            # 90%概率生成2，10%概率生成4
            self.board[r][c] = 2 if random.random() < 0.9 else 4
            return True
        return False
    
    def move(self, direction):
        """移动棋子
        方向: 0-上, 1-右, 2-下, 3-左
        """
        moved = False
        old_board = [row[:] for row in self.board]
        
        if direction == 0:  # 上
            for c in range(GRID_SIZE):
                column = [self.board[r][c] for r in range(GRID_SIZE) if self.board[r][c] != 0]
                # 合并相同的数字
                i = 0
                while i < len(column) - 1:
                    if column[i] == column[i + 1]:
                        column[i] *= 2
                        self.score += column[i]
                        self.max_tile = max(self.max_tile, column[i])
                        column.pop(i + 1)
                        self.streak += 1
                    i += 1
                # 填充空白
                column += [0] * (GRID_SIZE - len(column))
                for r in range(GRID_SIZE):
                    if self.board[r][c] != column[r]:
                        moved = True
                    self.board[r][c] = column[r]
                    
        elif direction == 1:  # 右
            for r in range(GRID_SIZE):
                row = [cell for cell in self.board[r] if cell != 0]
                # 从右向左合并
                i = len(row) - 1
                while i > 0:
                    if row[i] == row[i - 1]:
                        row[i] *= 2
                        self.score += row[i]
                        self.max_tile = max(self.max_tile, row[i])
                        row.pop(i - 1)
                        i -= 1
                        self.streak += 1
                    i -= 1
                # 填充空白
                row = [0] * (GRID_SIZE - len(row)) + row
                for c in range(GRID_SIZE):
                    if self.board[r][c] != row[c]:
                        moved = True
                    self.board[r][c] = row[c]
                    
        elif direction == 2:  # 下
            for c in range(GRID_SIZE):
                column = [self.board[r][c] for r in range(GRID_SIZE) if self.board[r][c] != 0]
                # 从下向上合并
                i = len(column) - 1
                while i > 0:
                    if column[i] == column[i - 1]:
                        column[i] *= 2
                        self.score += column[i]
                        self.max_tile = max(self.max_tile, column[i])
                        column.pop(i - 1)
                        i -= 1
                        self.streak += 1
                    i -= 1
                # 填充空白
                column = [0] * (GRID_SIZE - len(column)) + column
                for r in range(GRID_SIZE):
                    if self.board[r][c] != column[r]:
                        moved = True
                    self.board[r][c] = column[r]
                    
        elif direction == 3:  # 左
            for r in range(GRID_SIZE):
                row = [cell for cell in self.board[r] if cell != 0]
                # 从左向右合并
                i = 0
                while i < len(row) - 1:
                    if row[i] == row[i + 1]:
                        row[i] *= 2
                        self.score += row[i]
                        self.max_tile = max(self.max_tile, row[i])
                        row.pop(i + 1)
                        self.streak += 1
                    i += 1
                # 填充空白
                row += [0] * (GRID_SIZE - len(row))
                for c in range(GRID_SIZE):
                    if self.board[r][c] != row[c]:
                        moved = True
                    self.board[r][c] = row[c]
        
        if moved:
            self.moves += 1
            self.history.append((old_board, direction, self.score))
            self.add_random_tile()
            self.check_game_over()
            
        return moved
    
    def can_move(self):
        """检查是否还能移动"""
        # 检查是否有空白格子
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if self.board[r][c] == 0:
                    return True
        
        # 检查是否有可合并的相邻格子
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                current = self.board[r][c]
                # 检查右侧
                if c < GRID_SIZE - 1 and self.board[r][c + 1] == current:
                    return True
                # 检查下侧
                if r < GRID_SIZE - 1 and self.board[r + 1][c] == current:
                    return True
        
        return False
    
    def check_game_over(self):
        """检查游戏是否结束"""
        if not self.can_move():
            self.game_over = True
            
    def get_best_move(self):
        """AI选择最佳移动方向"""
        if random.random() < 0.1:  # 10%概率随机移动
            return random.randint(0, 3)
            
        # 检查是否有合并机会
        for direction in range(4):
            # 模拟移动
            test_board = [row[:] for row in self.board]
            test_score = self.score
            
            # 简化模拟
            if self.simulate_move(test_board, test_score, direction):
                # 优先选择能合并的方向
                return direction
        
        # 否则随机选择
        return random.randint(0, 3)
    
    def simulate_move(self, board, score, direction):
        """简化模拟移动"""
        # 这里实现一个简化的模拟逻辑
        # 实际应该更复杂，但为了挂机效率简化
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if board[r][c] != 0:
                    # 检查是否能与相邻格子合并
                    if direction == 0 and r > 0 and board[r-1][c] == board[r][c]:
                        return True
                    elif direction == 1 and c < GRID_SIZE-1 and board[r][c+1] == board[r][c]:
                        return True
                    elif direction == 2 and r < GRID_SIZE-1 and board[r+1][c] == board[r][c]:
                        return True
                    elif direction == 3 and c > 0 and board[r][c-1] == board[r][c]:
                        return True
        return False
    
    def auto_play(self):
        """自动游戏逻辑"""
        if time.time() - self.last_move_time > self.move_delay and not self.game_over:
            direction = self.get_best_move()
            self.move(direction)
            self.last_move_time = time.time()
            
            # 随机切换策略
            if random.random() < 0.05:
                self.current_strategy = (self.current_strategy + 1) % len(self.strategies)
    
    def check_gomoku(self):
        """检查是否有五子连珠"""
        for r in range(GRID_SIZE - 4):
            for c in range(GRID_SIZE - 4):
                # 检查3x3区域内的井字棋
                for rr in range(3):
                    for cc in range(3):
                        if (self.board[r+rr][c+cc] != 0 and
                            self.board[r+rr][c+cc] == self.board[r+rr][c+cc+1] == self.board[r+rr][c+cc+2]):
                            # 三连消除
                            tile_value = self.board[r+rr][c+cc] * 3
                            self.board[r+rr][c+cc] = 0
                            self.board[r+rr][c+cc+1] = 0
                            self.board[r+rr][c+cc+2] = 0
                            # 在随机位置生成新棋子
                            empty_cells = [(rrr, ccc) for rrr in range(GRID_SIZE) for ccc in range(GRID_SIZE) 
                                         if self.board[rrr][ccc] == 0]
                            if empty_cells:
                                rr2, cc2 = random.choice(empty_cells)
                                self.board[rr2][cc2] = tile_value
                                return True
        return False
    
    def draw(self):
        """绘制游戏界面"""
        self.screen.fill((187, 173, 160))  # 背景
        
        # 绘制棋盘
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                value = self.board[r][c]
                color = COLORS.get(value, (60, 58, 50))
                
                rect = pygame.Rect(
                    MARGIN + c * (CELL_SIZE + MARGIN),
                    MARGIN + r * (CELL_SIZE + MARGIN),
                    CELL_SIZE,
                    CELL_SIZE
                )
                
                pygame.draw.rect(self.screen, color, rect, border_radius=6)
                
                if value != 0:
                    font_size = 36 if value < 1000 else 30
                    font_color = TEXT_COLORS.get(value, (255, 255, 255))
                    font = _get_chinese_font(font_size)
                    text = font.render(str(value), True, font_color)
                    text_rect = text.get_rect(center=rect.center)
                    self.screen.blit(text, text_rect)
        
        # 绘制状态信息
        status_rect = pygame.Rect(0, HEIGHT, WIDTH, 100)
        pygame.draw.rect(self.screen, (50, 50, 50), status_rect)
        
        # 分数
        score_text = self.font.render(f"分数: {self.score}", True, (255, 255, 255))
        self.screen.blit(score_text, (20, HEIGHT + 10))
        
        # 步数
        moves_text = self.font.render(f"步数: {self.moves}", True, (255, 255, 255))
        self.screen.blit(moves_text, (20, HEIGHT + 50))
        
        # 最高数字
        max_text = self.font.render(f"最高: {self.max_tile}", True, (255, 255, 255))
        self.screen.blit(max_text, (WIDTH//3, HEIGHT + 10))
        
        # 连击
        streak_text = self.font.render(f"连击: {self.streak}", True, (255, 255, 255))
        self.screen.blit(streak_text, (WIDTH//3, HEIGHT + 50))
        
        # 游戏状态
        status_text = "游戏结束" if self.game_over else "自动游戏中..."
        status_color = (255, 100, 100) if self.game_over else (100, 255, 100)
        status_surf = self.font.render(status_text, True, status_color)
        self.screen.blit(status_surf, (2*WIDTH//3, HEIGHT + 10))
        
        # 策略显示
        strategy_text = self.small_font.render(f"策略: {self.strategies[self.current_strategy]}", True, (200, 200, 255))
        self.screen.blit(strategy_text, (2*WIDTH//3, HEIGHT + 50))
        
        # 控制提示
        hint_text = self.small_font.render("空格: 暂停/继续 | R: 重新开始 | ESC: 退出", True, (200, 200, 200))
        self.screen.blit(hint_text, (WIDTH//2 - 200, HEIGHT + 80))
        
    def reset(self):
        """重置游戏"""
        self.board = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.score = 0
        self.moves = 0
        self.game_over = False
        self.max_tile = 2
        self.streak = 0
        self.history = []
        self.add_random_tile()
        self.add_random_tile()
    
    def run(self):
        """主游戏循环"""
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.auto_mode = not self.auto_mode
                    elif event.key == pygame.K_r:
                        self.reset()
                    elif not self.auto_mode and not self.game_over:
                        # 手动控制
                        if event.key == pygame.K_UP:
                            self.move(0)
                        elif event.key == pygame.K_RIGHT:
                            self.move(1)
                        elif event.key == pygame.K_DOWN:
                            self.move(2)
                        elif event.key == pygame.K_LEFT:
                            self.move(3)
            
            # 自动游戏
            if self.auto_mode and not self.game_over:
                self.auto_play()
                
                # 偶尔检查五子连珠
                if random.random() < 0.1:  # 10%概率检查
                    self.check_gomoku()
            
            # 绘制
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()

# 控制台版本的简化挂机游戏（不需要图形界面）
class ConsoleAuto2048:
    def __init__(self):
        self.board = [[0 for _ in range(4)] for _ in range(4)]
        self.score = 0
        self.moves = 0
        self.game_over = False
        
        # 添加起始棋子
        self.add_random_tile()
        self.add_random_tile()
        
    def add_random_tile(self):
        """添加随机棋子"""
        empty = [(r, c) for r in range(4) for c in range(4) if self.board[r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            self.board[r][c] = 2 if random.random() < 0.9 else 4
            
    def print_board(self):
        """打印棋盘到控制台"""
        print("\n" + "="*40)
        print(f"分数: {self.score} | 步数: {self.moves}")
        print("-"*40)
        for row in self.board:
            print(" ".join(f"{num:4}" if num > 0 else "   ." for num in row))
        print("="*40)
        
    def auto_play_console(self, max_moves=1000):
        """控制台自动运行"""
        print("开始挂机摸鱼2048游戏！")
        print("游戏将自动运行，请坐等看结果...")
        
        moves = 0
        while moves < max_moves and not self.game_over:
            # 随机移动
            direction = random.randint(0, 3)
            
            # 简化移动逻辑
            moved = False
            if direction == 0:  # 上
                for c in range(4):
                    col = [self.board[r][c] for r in range(4) if self.board[r][c] != 0]
                    i = 0
                    while i < len(col) - 1:
                        if col[i] == col[i + 1]:
                            col[i] *= 2
                            self.score += col[i]
                            col.pop(i + 1)
                        i += 1
                    col += [0] * (4 - len(col))
                    for r in range(4):
                        if self.board[r][c] != col[r]:
                            moved = True
                        self.board[r][c] = col[r]
                        
            if moved:
                self.moves += 1
                self.add_random_tile()
                
                # 每10步显示一次
                if self.moves % 10 == 0:
                    self.print_board()
                    time.sleep(0.5)  # 稍微停顿一下
                    
                moves += 1
            else:
                # 如果不能移动，尝试下一个方向
                continue
        
        print("\n" + "="*40)
        print("游戏结束！最终结果：")
        self.print_board()
        print(f"最终分数: {self.score}")
        print(f"总步数: {self.moves}")
        print("="*40)
        
        # 计算最大数字
        max_tile = max(max(row) for row in self.board)
        print(f"最大数字: {max_tile}")
        
        # 评级
        if max_tile >= 2048:
            print("评级: 大神！你合成了2048！")
        elif max_tile >= 512:
            print("评级: 不错！继续努力！")
        else:
            print("评级: 再接再厉！")

def main():
    """主函数"""
    print("选择游戏模式:")
    print("1. 图形界面挂机版 (推荐)")
    print("2. 控制台纯挂机版 (最省资源)")
    print("3. 控制台自动演示版")
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    if choice == "1":
        print("\n启动图形界面挂机版...")
        print("控制说明:")
        print("  - 游戏自动运行")
        print("  - 空格键: 暂停/继续自动运行")
        print("  - R键: 重新开始游戏")
        print("  - ESC键: 退出游戏")
        print("\n最小化窗口即可挂机摸鱼！")
        input("按回车键开始...")
        
        game = Auto2048Chess()
        game.run()
        
    elif choice == "2":
        print("\n启动控制台纯挂机版...")
        print("游戏将在后台自动运行")
        print("完成后显示结果")
        input("按回车键开始挂机...")
        
        game = ConsoleAuto2048()
        game.auto_play_console(max_moves=200)
        
    elif choice == "3":
        print("\n启动控制台自动演示版...")
        print("将逐步显示游戏过程")
        
        # 简单演示
        game = Auto2048Chess()
        running = True
        while running and not game.game_over:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
            
            if not game.game_over:
                game.auto_play()
                game.draw()
                pygame.display.flip()
                game.clock.tick(5)  # 慢速演示
        
        pygame.quit()
        
    else:
        print("无效选择，使用默认控制台挂机版...")
        game = ConsoleAuto2048()
        game.auto_play_console(max_moves=100)

if __name__ == "__main__":
    main()