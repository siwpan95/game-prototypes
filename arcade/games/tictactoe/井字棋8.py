import random
import time
import os
import math
from collections import defaultdict

class EnhancedTicTacToe:
    def __init__(self):
        self.base_rows = 3
        self.base_cols = 3
        self.rows = self.base_rows
        self.cols = self.base_cols
        self.board = []
        self.max_enlargements = 3
        self.current_enlargement = 0
        self.has_interference = False
        self.poisson_intensity = 0.1
        self.board_shapes = []
        
        # 特殊棋子定义
        self.special_pieces = {
            '💣': {'name': '炸弹', 'effect': '爆炸消除周围棋子'},
            '❄️': {'name': '冻结', 'effect': '冻结相邻干扰项'},
            '🔄': {'name': '转换', 'effect': '转换相邻棋子'},
            '🛡️': {'name': '护盾', 'effect': '保护己方棋子'},
        }
        
        # 多种干扰项类型
        self.interference_types = {
            '+': {
                'name': '基础干扰',
                'color': '\033[93m',  # 黄色
                'rule': 'same_neighbors_change',
                'description': '两侧相同则变化'
            },
            '*': {
                'name': '星型干扰',
                'color': '\033[95m',  # 紫色
                'rule': 'different_neighbors_change',
                'description': '两侧不同则变化'
            },
            '?': {
                'name': '随机干扰',
                'color': '\033[96m',  # 青色
                'rule': 'random_change',
                'description': '随机变化'
            },
            '!': {
                'name': '延迟干扰',
                'color': '\033[91m',  # 红色
                'rule': 'delayed_change',
                'description': '延迟1回合变化'
            }
        }
        
        # 游戏状态
        self.player_symbols = ['X', 'O']
        self.current_player = 0
        self.move_count = 0
        self.special_piece_count = 2  # 每个玩家的特殊棋子数量
        self.player_special_pieces = {
            'X': list(self.special_pieces.keys())[:self.special_piece_count],
            'O': list(self.special_pieces.keys())[:self.special_piece_count]
        }
        
        # 干扰项状态跟踪
        self.delayed_interferences = []  # 延迟变化的干扰项
        self.frozen_interferences = {}   # 冻结的干扰项
        self.init_board_shapes()
        self.reset()
    
    def init_board_shapes(self):
        """初始化棋盘形状"""
        # 初始形状：3x3
        self.board_shapes.append({
            'name': '初始',
            'rows': 3,
            'cols': 3,
            'board': None
        })
        
        # 其他异形棋盘
        shape1 = [
            [0, 0, 1, 1, 1, 0, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 0, 1, 1, 1, 0, 0]
        ]
        self.board_shapes.append({
            'name': 'T形',
            'rows': 5,
            'cols': 7,
            'shape': shape1
        })
        
        shape2 = [
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0],
            [1, 1, 1, 1, 1],
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0]
        ]
        self.board_shapes.append({
            'name': '十字形',
            'rows': 5,
            'cols': 5,
            'shape': shape2
        })
    
    def get_current_shape(self):
        """获取当前形状"""
        if self.current_enlargement >= len(self.board_shapes):
            return self.board_shapes[0]
        return self.board_shapes[self.current_enlargement]
    
    def create_irregular_board(self, shape_config):
        """创建异形棋盘"""
        rows = shape_config['rows']
        cols = shape_config['cols']
        
        if 'shape' in shape_config and shape_config['shape']:
            shape_matrix = shape_config['shape']
            board = []
            for i in range(rows):
                board_row = []
                for j in range(cols):
                    if shape_matrix[i][j] == 1:
                        board_row.append(' ')
                    else:
                        board_row.append('#')
                board.append(board_row)
            return board, rows, cols
        else:
            board = [[' ' for _ in range(cols)] for _ in range(rows)]
            return board, rows, cols
    
    def poisson_point_process_simple(self, intensity, width, height):
        """简化的泊松点过程生成干扰项"""
        expected_points = intensity * width * height
        
        points = []
        placed_positions = set()
        
        for _ in range(int(expected_points * random.uniform(0.8, 1.2))):
            x = random.uniform(0, width - 1e-6)
            y = random.uniform(0, height - 1e-6)
            
            row = int(y)
            col = int(x)
            
            if 0 <= row < height and 0 <= col < width:
                if (row, col) not in placed_positions:
                    # 简单距离检查
                    too_close = False
                    for (pr, pc) in placed_positions:
                        if ((row - pr) ** 2 + (col - pc) ** 2) < 1.0:
                            too_close = True
                            break
                    
                    if not too_close:
                        points.append((x, y))
                        placed_positions.add((row, col))
        
        return points
    
    def reset(self, is_enlargement=False):
        """重置棋盘"""
        if is_enlargement:
            if self.current_enlargement < len(self.board_shapes) - 1:
                self.current_enlargement += 1
            else:
                self.current_enlargement = 0
                self.has_interference = False
        elif self.current_enlargement > 0:
            self.has_interference = True
        
        shape_config = self.get_current_shape()
        self.board, self.rows, self.cols = self.create_irregular_board(shape_config)
        
        # 重置状态
        self.delayed_interferences = []
        self.frozen_interferences = {}
        
        if self.current_enlargement > 0:
            self.has_interference = True
            self.add_interference_poisson()
        
        return is_enlargement
    
    def add_interference_poisson(self):
        """使用泊松点过程在棋盘上放置多种干扰项"""
        if not self.has_interference:
            return 0
        
        # 获取有效位置
        valid_positions = []
        for i in range(self.rows):
            for j in range(self.cols):
                if self.board[i][j] == ' ':
                    valid_positions.append((i, j))
        
        if not valid_positions:
            return 0
        
        # 计算干扰项数量
        interference_types = list(self.interference_types.keys())
        intensity = self.poisson_intensity * len(valid_positions) / (self.rows * self.cols)
        
        poisson_points = self.poisson_point_process_simple(
            intensity=intensity,
            width=self.cols,
            height=self.rows
        )
        
        placed = 0
        placed_set = set()
        
        for x, y in poisson_points:
            row = int(y)
            col = int(x)
            
            if 0 <= row < self.rows and 0 <= col < self.cols:
                if self.board[row][col] == ' ' and (row, col) not in placed_set:
                    # 随机选择干扰项类型
                    interference_type = random.choice(interference_types)
                    self.board[row][col] = interference_type
                    placed_set.add((row, col))
                    placed += 1
        
        return placed
    
    def update_interference(self, row, col, interference_type):
        """更新特定类型的干扰项"""
        if self.board[row][col] != interference_type:
            return None
        
        # 检查是否被冻结
        if (row, col) in self.frozen_interferences:
            self.frozen_interferences[(row, col)] -= 1
            if self.frozen_interferences[(row, col)] <= 0:
                del self.frozen_interferences[(row, col)]
            return None
        
        # 获取干扰项规则
        rule = self.interference_types[interference_type]['rule']
        
        # 获取相邻位置
        neighbors = self.get_valid_neighbors(row, col)
        
        if rule == 'same_neighbors_change':
            # 基础规则：两侧相同则变化
            for i in range(len(neighbors)):
                for j in range(i + 1, len(neighbors)):
                    if (neighbors[i][2] in ['X', 'O'] and 
                        neighbors[i][2] == neighbors[j][2]):
                        new_symbol = 'O' if neighbors[i][2] == 'X' else 'X'
                        self.board[row][col] = new_symbol
                        return (row, col, interference_type, new_symbol, neighbors[i][2])
        
        elif rule == 'different_neighbors_change':
            # 星型规则：两侧不同则变化
            for i in range(len(neighbors)):
                for j in range(i + 1, len(neighbors)):
                    if (neighbors[i][2] in ['X', 'O'] and 
                        neighbors[j][2] in ['X', 'O'] and
                        neighbors[i][2] != neighbors[j][2]):
                        # 随机选择一个相邻的符号
                        adjacent_symbol = random.choice([neighbors[i][2], neighbors[j][2]])
                        new_symbol = 'O' if adjacent_symbol == 'X' else 'X'
                        self.board[row][col] = new_symbol
                        return (row, col, interference_type, new_symbol, 'different')
        
        elif rule == 'random_change':
            # 随机规则：随机变化
            if neighbors:
                # 检查是否有相邻的棋子
                adjacent_pieces = [n[2] for n in neighbors if n[2] in ['X', 'O']]
                if adjacent_pieces:
                    # 随机变成另一个符号
                    adjacent_symbol = random.choice(adjacent_pieces)
                    new_symbol = 'O' if adjacent_symbol == 'X' else 'X'
                    self.board[row][col] = new_symbol
                    return (row, col, interference_type, new_symbol, 'random')
        
        elif rule == 'delayed_change':
            # 延迟规则：记录延迟变化
            if (row, col, interference_type) not in self.delayed_interferences:
                self.delayed_interferences.append((row, col, interference_type))
                return None
        
        return None
    
    def process_delayed_interferences(self):
        """处理延迟干扰项"""
        changes = []
        to_remove = []
        
        for i, (row, col, interference_type) in enumerate(self.delayed_interferences):
            if self.board[row][col] == interference_type:
                # 延迟1回合后变化
                neighbors = self.get_valid_neighbors(row, col)
                if neighbors:
                    adjacent_pieces = [n[2] for n in neighbors if n[2] in ['X', 'O']]
                    if adjacent_pieces:
                        adjacent_symbol = random.choice(adjacent_pieces)
                        new_symbol = 'O' if adjacent_symbol == 'X' else 'X'
                        self.board[row][col] = new_symbol
                        changes.append((row, col, interference_type, new_symbol, 'delayed'))
                        to_remove.append(i)
        
        # 移除已处理的延迟干扰项
        for i in reversed(to_remove):
            if i < len(self.delayed_interferences):
                del self.delayed_interferences[i]
        
        return changes
    
    def get_valid_neighbors(self, row, col):
        """获取有效的相邻位置"""
        neighbors = []
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        
        for dr, dc in directions:
            r, c = row + dr, col + dc
            if 0 <= r < self.rows and 0 <= c < self.cols and self.board[r][c] != '#':
                neighbors.append((r, c, self.board[r][c]))
        
        return neighbors
    
    def update_all_interference(self):
        """更新所有干扰项"""
        changes = []
        
        # 先处理延迟干扰项
        delayed_changes = self.process_delayed_interferences()
        changes.extend(delayed_changes)
        
        # 处理其他干扰项
        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.board[row][col]
                if cell in self.interference_types:
                    result = self.update_interference(row, col, cell)
                    if result:
                        changes.append(result)
        
        return changes
    
    def place_special_piece(self, piece_type, position, current_symbol):
        """放置特殊棋子并应用效果"""
        x, y = position
        
        if self.board[x][y] != ' ':
            return False, "位置已被占用"
        
        if piece_type not in self.player_special_pieces[current_symbol]:
            return False, f"没有可用的{piece_type}棋子"
        
        # 应用特殊效果
        if piece_type == '💣':
            # 炸弹：消除周围3x3区域的棋子
            effect = self.apply_bomb_effect(x, y, current_symbol)
        elif piece_type == '❄️':
            # 冻结：冻结相邻的干扰项
            effect = self.apply_freeze_effect(x, y, current_symbol)
        elif piece_type == '🔄':
            # 转换：转换相邻的棋子
            effect = self.apply_convert_effect(x, y, current_symbol)
        elif piece_type == '🛡️':
            # 护盾：放置护盾
            effect = self.apply_shield_effect(x, y, current_symbol)
        else:
            return False, "未知的特殊棋子"
        
        # 移除使用的特殊棋子
        self.player_special_pieces[current_symbol].remove(piece_type)
        
        return True, effect
    
    def apply_bomb_effect(self, x, y, current_symbol):
        """应用炸弹效果"""
        affected_cells = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.rows and 0 <= ny < self.cols:
                    if self.board[nx][ny] != '#' and self.board[nx][ny] != ' ':
                        affected_cells.append((nx, ny, self.board[nx][ny]))
                        self.board[nx][ny] = ' '
        
        # 炸弹自身也消失
        self.board[x][y] = ' '
        
        return f"炸弹清除了 {len(affected_cells)} 个格子"
    
    def apply_freeze_effect(self, x, y, current_symbol):
        """应用冻结效果"""
        frozen_count = 0
        
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.rows and 0 <= ny < self.cols:
                if self.board[nx][ny] in self.interference_types:
                    self.frozen_interferences[(nx, ny)] = 3  # 冻结3回合
                    frozen_count += 1
        
        # 冻结棋子自身消失
        self.board[x][y] = ' '
        
        return f"冻结了 {frozen_count} 个干扰项"
    
    def apply_convert_effect(self, x, y, current_symbol):
        """应用转换效果"""
        converted_count = 0
        
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.rows and 0 <= ny < self.cols:
                if self.board[nx][ny] in ['X', 'O'] and self.board[nx][ny] != current_symbol:
                    self.board[nx][ny] = current_symbol
                    converted_count += 1
        
        # 转换棋子自身消失
        self.board[x][y] = ' '
        
        return f"转换了 {converted_count} 个敌方棋子"
    
    def apply_shield_effect(self, x, y, current_symbol):
        """应用护盾效果"""
        # 在当前回合，护盾会保护放置位置
        # 简单实现：将护盾放在棋盘上
        self.board[x][y] = '🛡️'
        
        return "放置了护盾"
    
    def display_board(self):
        """显示棋盘"""
        os.system('cls' if os.name == 'nt' else 'clear')
        shape_config = self.get_current_shape()
        
        print(f"\n{'='*50}")
        print(f"当前棋盘: {shape_config['name']} ({self.rows}×{self.cols})")
        print(f"形状序号: {self.current_enlargement}/{len(self.board_shapes)-1}")
        print(f"当前玩家: {self.player_symbols[self.current_player]}")
        print(f"回合数: {self.move_count}")
        print(f"干扰项: {'有' if self.has_interference else '无'}")
        
        # 显示玩家特殊棋子
        for symbol, pieces in self.player_special_pieces.items():
            if pieces:
                piece_names = [self.special_pieces[p]['name'] for p in pieces]
                print(f"玩家{symbol}的特殊棋子: {', '.join(piece_names)}")
        
        # 统计棋盘状态
        stats = defaultdict(int)
        for row in self.board:
            for cell in row:
                stats[cell] += 1
        
        print("\n棋盘统计:")
        for symbol, count in sorted(stats.items()):
            if symbol == ' ':
                print(f"  空格: {count}")
            elif symbol == '#':
                print(f"  障碍: {count}")
            elif symbol in self.interference_types:
                info = self.interference_types.get(symbol, {})
                print(f"  {info.get('name', symbol)}: {count}")
            elif symbol in self.special_pieces:
                info = self.special_pieces.get(symbol, {})
                print(f"  {info.get('name', symbol)}: {count}")
            else:
                print(f"  {symbol}: {count}")
        
        print("-" * (self.cols * 4 + 1))
        
        for row in self.board:
            row_str = "|"
            for cell in row:
                if cell in self.interference_types:
                    # 干扰项使用对应颜色
                    color = self.interference_types[cell]['color']
                    row_str += f"{color} {cell} \033[0m|"
                elif cell == 'X':
                    row_str += f" \033[91m{cell}\033[0m |"  # 红色X
                elif cell == 'O':
                    row_str += f" \033[94m{cell}\033[0m |"  # 蓝色O
                elif cell in self.special_pieces:
                    row_str += f" {cell} |"  # 特殊棋子
                elif cell == '#':
                    row_str += f" \033[90m{cell}\033[0m |"  # 灰色#
                else:
                    row_str += f"   |"  # 空格
            print(row_str)
            print("-" * (self.cols * 4 + 1))
    
    def get_empty_positions(self):
        """获取所有空位置"""
        empty = []
        for i in range(self.rows):
            for j in range(self.cols):
                if self.board[i][j] == ' ':
                    empty.append((i, j))
        return empty
    
    def get_random_position(self):
        """获取随机空位置"""
        empty = self.get_empty_positions()
        if empty:
            return random.choice(empty)
        return None
    
    def place_symbol(self, symbol, position):
        """放置普通符号"""
        x, y = position
        if 0 <= x < self.rows and 0 <= y < self.cols and self.board[x][y] == ' ':
            self.board[x][y] = symbol
            return True
        return False
    
    def check_three_in_a_row(self, symbol, position=None):
        """检查是否形成三连"""
        if position:
            x, y = position
            positions_to_check = [(x, y)]
        else:
            positions_to_check = []
            for i in range(self.rows):
                for j in range(self.cols):
                    if self.board[i][j] == symbol:
                        positions_to_check.append((i, j))
        
        for x, y in positions_to_check:
            # 检查行
            for start_col in range(max(0, y-2), min(self.cols-2, y+1)):
                if all(0 <= x < self.rows and 0 <= start_col + offset < self.cols and 
                       self.board[x][start_col + offset] == symbol for offset in range(3)):
                    return True
            
            # 检查列
            for start_row in range(max(0, x-2), min(self.rows-2, x+1)):
                if all(0 <= start_row + offset < self.rows and 0 <= y < self.cols and 
                       self.board[start_row + offset][y] == symbol for offset in range(3)):
                    return True
            
            # 检查主对角线
            for start_offset in range(-2, 1):
                if all(0 <= x + start_offset + offset < self.rows and 
                       0 <= y + start_offset + offset < self.cols and
                       self.board[x + start_offset + offset][y + start_offset + offset] == symbol 
                       for offset in range(3)):
                    return True
            
            # 检查副对角线
            for start_offset in range(-2, 1):
                if all(0 <= x + start_offset + offset < self.rows and 
                       0 <= y - start_offset - offset < self.cols and
                       self.board[x + start_offset + offset][y - start_offset - offset] == symbol 
                       for offset in range(3)):
                    return True
        
        return False
    
    def is_board_full(self):
        """检查棋盘是否已满"""
        for i in range(self.rows):
            for j in range(self.cols):
                if self.board[i][j] == ' ':
                    return False
        return True
    
    def get_player_input(self):
        """获取玩家输入"""
        current_symbol = self.player_symbols[self.current_player]
        
        print(f"\n玩家 {current_symbol} 的回合")
        print("可用选项:")
        print("  1. 放置普通棋子")
        
        # 显示可用的特殊棋子
        special_pieces = self.player_special_pieces[current_symbol]
        if special_pieces:
            print("  2. 使用特殊棋子")
            for i, piece in enumerate(special_pieces, 1):
                info = self.special_pieces[piece]
                print(f"     {i+1}. 使用{info['name']} ({piece}): {info['effect']}")
        
        print("  0. 退出游戏")
        
        choice = input("请选择操作: ").strip()
        
        if choice == '0':
            return 'quit', None
        elif choice == '1':
            # 自动选择随机位置
            position = self.get_random_position()
            if position:
                return 'place_normal', position
            else:
                print("没有可用位置!")
                return 'skip', None
        elif choice == '2' and special_pieces:
            # 使用特殊棋子
            if len(special_pieces) == 1:
                piece = special_pieces[0]
            else:
                print("请选择特殊棋子:")
                for i, piece in enumerate(special_pieces, 1):
                    info = self.special_pieces[piece]
                    print(f"  {i}. {info['name']} ({piece})")
                
                piece_choice = input("选择棋子编号: ").strip()
                if piece_choice.isdigit() and 1 <= int(piece_choice) <= len(special_pieces):
                    piece = special_pieces[int(piece_choice) - 1]
                else:
                    print("无效选择!")
                    return 'skip', None
            
            position = self.get_random_position()
            if position:
                return f'place_special_{piece}', position
            else:
                print("没有可用位置!")
                return 'skip', None
        else:
            print("无效选择!")
            return 'skip', None
    
    def play_turn(self):
        """进行一回合游戏"""
        current_symbol = self.player_symbols[self.current_player]
        action_result = None
        
        # 获取玩家输入
        action_type, position = self.get_player_input()
        
        if action_type == 'quit':
            return 'quit'
        
        if position is None:
            # 没有可用位置，跳过
            self.current_player = (self.current_player + 1) % len(self.player_symbols)
            return 'continue'
        
        if action_type == 'place_normal':
            # 放置普通棋子
            if self.place_symbol(current_symbol, position):
                action_result = f"放置 {current_symbol} 在 ({position[0]}, {position[1]})"
                self.move_count += 1
            else:
                print("放置失败!")
                return 'continue'
        
        elif action_type.startswith('place_special_'):
            # 放置特殊棋子
            piece_type = action_type.split('_')[-1]
            success, result = self.place_special_piece(piece_type, position, current_symbol)
            if success:
                action_result = result
                self.move_count += 1
            else:
                print(result)
                return 'continue'
        
        # 更新干扰项
        interference_changes = self.update_all_interference()
        
        # 显示棋盘
        self.display_board()
        
        if action_result:
            print(f"\n操作结果: {action_result}")
        
        # 显示干扰项变化
        if interference_changes:
            print("\n干扰项变化:")
            for row, col, old_type, new_symbol, reason in interference_changes:
                old_info = self.interference_types.get(old_type, {'name': old_type})
                print(f"  ({row}, {col}): {old_info['name']} -> {new_symbol} ({reason})")
        
        # 检查是否形成三连
        if self.check_three_in_a_row(current_symbol, position):
            print(f"\n\033[92m发现三连! 玩家 {current_symbol} 获胜!\033[0m")
            time.sleep(2)
            
            was_enlarged = self.reset(True)
            shape_config = self.get_current_shape()
            print(f"切换到棋盘形状: {shape_config['name']} ({self.rows}×{self.cols})")
            
            # 补充特殊棋子
            for symbol in self.player_special_pieces:
                if len(self.player_special_pieces[symbol]) < self.special_piece_count:
                    available_pieces = [p for p in self.special_pieces.keys() 
                                      if p not in self.player_special_pieces[symbol]]
                    if available_pieces:
                        self.player_special_pieces[symbol].append(random.choice(available_pieces))
            
            time.sleep(2)
            self.move_count = 0
            return 'win'
        
        # 检查干扰项变化后是否形成三连
        for row, col, old_type, new_symbol, reason in interference_changes:
            if new_symbol in ['X', 'O'] and self.check_three_in_a_row(new_symbol, (row, col)):
                print(f"\n\033[92m干扰项形成三连! 符号: {new_symbol}\033[0m")
                time.sleep(2)
                
                was_enlarged = self.reset(True)
                shape_config = self.get_current_shape()
                print(f"切换到棋盘形状: {shape_config['name']} ({self.rows}×{self.cols})")
                
                time.sleep(2)
                self.move_count = 0
                return 'interference_win'
        
        # 检查棋盘是否已满
        if self.is_board_full():
            print("\n\033[93m棋盘已满，平局!\033[0m")
            time.sleep(2)
            
            was_enlarged = self.reset(True)
            shape_config = self.get_current_shape()
            print(f"切换到棋盘形状: {shape_config['name']} ({self.rows}×{self.cols})")
            
            time.sleep(2)
            self.move_count = 0
            return 'draw'
        
        # 切换到下一个玩家
        self.current_player = (self.current_player + 1) % len(self.player_symbols)
        
        return 'continue'
    
    def play_game(self):
        """主游戏循环"""
        print("\033[1m异形井字棋增强版\033[0m")
        print("="*50)
        print("游戏特色:")
        print("1. 多种棋盘形状")
        print("2. 多种干扰项类型:")
        for key, info in self.interference_types.items():
            print(f"   {key} - {info['name']}: {info['description']}")
        print("3. 特殊棋子:")
        for key, info in self.special_pieces.items():
            print(f"   {key} - {info['name']}: {info['effect']}")
        print("4. 双人对战模式")
        print("="*50)
        input("按Enter键开始游戏...")
        
        while True:
            result = self.play_turn()
            
            if result == 'quit':
                print("\n游戏结束!")
                break
            
            time.sleep(1.0)

def main():
    """主函数"""
    try:
        game = EnhancedTicTacToe()
        game.play_game()
    except KeyboardInterrupt:
        print("\n\n游戏结束！")
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()