"""[遗留·单文件版] ASCII 滑雪游戏 - 早期单文件实现，仅作历史参考。

⚠️ 本文件为项目最初的单文件版本，逻辑与 UI 耦合，性能较弱。
   不再维护。请使用模块化版本：
     - python main.py

模块化版本（engine.py + ui.py + main.py + config.py + storage.py）
包含：雪人追击、跳跃、加速、暂停、三模式、高分持久化等完整特性。
"""

import tkinter as tk
import random
import time

class ASCIISkiGame:
    def __init__(self, root):
        self.root = root
        self.root.title("ASCII滑雪游戏")
        
        # 游戏配置
        self.width = 80
        self.height = 30
        self.skier_x = self.width // 2
        self.skier_y = 5
        self.tree_char = "♣"
        self.flag_char = "¶"
        self.road_char = "·"
        self.score = 0
        self.distance = 0
        self.game_over = False
        self.game_started = False
        
        # 滑雪者方向状态
        self.skier_direction = 0
        self.skier_chars = {
            -2: "◀◀",  # 向左急转
            -1: "◀",   # 向左转
            0: "▲",    # 向前
            1: "▶",    # 向右转
            2: "▶▶"    # 向右急转
        }
        self.speed_x = 0
        
        # 障碍物
        self.obstacles = []  # 每个障碍物是[x, y, type, passed]
        
        # 创建游戏界面
        self.setup_ui()
        
        # 绑定键盘事件
        self.root.bind('<Left>', lambda e: self.turn(-1))
        self.root.bind('<Right>', lambda e: self.turn(1))
        self.root.bind('<a>', lambda e: self.turn(-1))
        self.root.bind('<d>', lambda e: self.turn(1))
        self.root.bind('<Key>', self.start_game)
        
        # 显示开始界面
        self.show_start_screen()
    
    def setup_ui(self):
        """设置UI界面"""
        # 游戏区域
        self.game_frame = tk.Frame(self.root)
        self.game_frame.pack(pady=10)
        
        # 分数显示
        self.score_label = tk.Label(self.root, text="分数: 0", font=("Courier", 14))
        self.score_label.pack()
        
        # 距离显示
        self.distance_label = tk.Label(self.root, text="距离: 0", font=("Courier", 12))
        self.distance_label.pack()
        
        # 控制说明
        self.controls_label = tk.Label(self.root, text="控制: ←/A 左转, →/D 右转", font=("Courier", 10))
        self.controls_label.pack()
        
        # 游戏画布（用Text控件模拟游戏区域）
        self.game_canvas = tk.Text(self.game_frame, width=self.width, height=self.height, 
                                   font=("Courier", 12), bg="white", fg="black")
        self.game_canvas.pack()
        
        # 配置颜色标签
        self.game_canvas.tag_configure("red", foreground="red")
        self.game_canvas.tag_configure("blue", foreground="blue")
        self.game_canvas.tag_configure("green", foreground="green")
        self.game_canvas.tag_configure("gray", foreground="gray")
        self.game_canvas.tag_configure("black", foreground="black")
    
    def show_start_screen(self):
        """显示开始界面"""
        self.clear_canvas()
        
        title = "ASCII滑雪游戏"
        subtitle = "按任意键开始游戏"
        controls = "控制: 左右方向键或A/D键转弯"
        
        # 计算居中位置
        title_x = (self.width - len(title)) // 2
        subtitle_x = (self.width - len(subtitle)) // 2
        controls_x = (self.width - len(controls)) // 2
        start_y = self.height // 2 - 2
        
        # 显示标题
        self.display_text(title, title_x, start_y, "red")
        self.display_text(subtitle, subtitle_x, start_y + 2, "blue")
        self.display_text(controls, controls_x, start_y + 4, "green")
        
        # 显示示例
        self.display_text("▲ 滑雪者", 10, start_y + 7, "blue")
        self.display_text("♣ 树木(避开: -50分)", 10, start_y + 8, "green")
        self.display_text("¶ 旗子(收集: +10分)", 10, start_y + 9, "red")
    
    def clear_canvas(self):
        """清空游戏画布"""
        self.game_canvas.delete("1.0", tk.END)
    
    def display_text(self, text, x, y, color="black"):
        """在指定位置显示文本"""
        # 定位到指定行
        self.game_canvas.mark_set("insert", f"{y+1}.{x}")
        # 插入带颜色的文本
        self.game_canvas.insert("insert", text, color)
    
    def draw_game(self):
        """绘制游戏画面"""
        self.clear_canvas()
        
        # 绘制道路背景
        for y in range(self.height):
            for x in range(self.width):
                if y > 0:  # 第一行显示分数
                    self.display_text(self.road_char, x, y, "gray")
        
        # 绘制障碍物
        for obstacle in self.obstacles:
            x, y, obstacle_type, _ = obstacle
            if 0 <= y < self.height and 0 <= x < self.width:
                char = self.tree_char if obstacle_type == "tree" else self.flag_char
                color = "green" if obstacle_type == "tree" else "red"
                self.display_text(char, x, y, color)
        
        # 绘制滑雪者
        if 0 <= self.skier_x < self.width and 0 <= self.skier_y < self.height:
            char = self.skier_chars.get(self.skier_direction, "▲")
            self.display_text(char, self.skier_x, self.skier_y, "blue")
        
        # 更新分数和距离显示
        self.score_label.config(text=f"分数: {self.score}")
        self.distance_label.config(text=f"距离: {self.distance}")
        
        # 更新显示
        self.root.update()
    
    def create_obstacles(self, start_row, end_row, num=15):
        """创建障碍物"""
        obstacles = []
        for _ in range(num):
            row = random.randint(start_row, end_row)
            col = random.randint(0, self.width - 1)
            obstacle_type = random.choice(["tree", "flag"])
            obstacles.append([col, row, obstacle_type, False])
        return obstacles
    
    def turn(self, direction_change):
        """改变滑雪者方向"""
        if self.game_over or not self.game_started:
            return
        
        self.skier_direction += direction_change
        self.skier_direction = max(-2, min(2, self.skier_direction))
        
        # 根据方向调整横向速度
        self.speed_x = self.skier_direction
    
    def move_skier(self):
        """移动滑雪者"""
        if self.game_over or not self.game_started:
            return
        
        # 横向移动
        self.skier_x += self.speed_x
        self.skier_x = max(0, min(self.skier_x, self.width - 1))
        
        # 纵向自动向下移动
        # 滑雪者位置固定，障碍物向上移动
    
    def move_obstacles(self):
        """移动障碍物"""
        # 更新障碍物位置
        for obstacle in self.obstacles:
            # 障碍物向上移动
            obstacle[1] -= 1
            
            # 如果障碍物移出屏幕，重新放置
            if obstacle[1] < 0:
                obstacle[1] = self.height - 1
                obstacle[0] = random.randint(0, self.width - 1)
                obstacle[2] = random.choice(["tree", "flag"])
                obstacle[3] = False
        
        # 更新距离
        self.distance += 1
        
        # 每移动一定距离，生成新障碍物
        if self.distance % 20 == 0:
            new_obstacles = self.create_obstacles(self.height - 5, self.height - 1, 5)
            self.obstacles.extend(new_obstacles)
    
    def check_collisions(self):
        """检查碰撞"""
        to_remove = []
        for obstacle in self.obstacles:
            x, y, obstacle_type, passed = obstacle
            
            # 检查是否碰撞
            if (abs(x - self.skier_x) <= 1 and abs(y - self.skier_y) <= 1) and not passed:
                if obstacle_type == "tree":
                    self.score -= 50
                    obstacle[3] = True
                    
                    # 摔倒效果
                    self.game_canvas.delete("1.0", tk.END)
                    self.display_text("✗ 撞到树了! -50分", self.width//2-10, self.height//2, "red")
                    self.root.update()
                    time.sleep(0.5)
                    
                elif obstacle_type == "flag":
                    self.score += 10
                    # 标记旗子待移除
                    to_remove.append(obstacle)
        
        # 统一移除已收集的旗子
        for obstacle in to_remove:
            if obstacle in self.obstacles:
                self.obstacles.remove(obstacle)
    
    def start_game(self, event=None):
        """开始游戏"""
        if self.game_started:
            return
        
        # 重置游戏状态
        self.game_started = True
        self.game_over = False
        self.score = 0
        self.distance = 0
        self.skier_x = self.width // 2
        self.skier_y = 5
        self.skier_direction = 0
        self.speed_x = 0
        
        # 清空障碍物
        self.obstacles = self.create_obstacles(10, self.height - 1, 20)
        
        # 开始游戏循环
        self.game_loop()
    
    def game_loop(self):
        """游戏主循环"""
        if self.game_over or not self.game_started:
            return
        
        # 移动滑雪者
        self.move_skier()
        
        # 移动障碍物
        self.move_obstacles()
        
        # 检查碰撞
        self.check_collisions()
        
        # 绘制游戏
        self.draw_game()
        
        # 检查游戏结束条件
        if self.score < -100:
            self.game_over = True
            self.show_game_over()
        else:
            # 继续游戏循环
            self.root.after(100, self.game_loop)
    
    def show_game_over(self):
        """显示游戏结束画面"""
        self.clear_canvas()
        
        game_over_text = "游戏结束!"
        score_text = f"最终分数: {self.score}"
        distance_text = f"滑行距离: {self.distance}"
        restart_text = "按任意键重新开始"
        
        # 居中显示
        self.display_text(game_over_text, (self.width - len(game_over_text))//2, self.height//2 - 2, "red")
        self.display_text(score_text, (self.width - len(score_text))//2, self.height//2, "blue")
        self.display_text(distance_text, (self.width - len(distance_text))//2, self.height//2 + 1, "green")
        self.display_text(restart_text, (self.width - len(restart_text))//2, self.height//2 + 3, "black")
        
        # 重新绑定开始事件
        self.game_started = False
        self.root.bind('<Key>', self.start_game)

def main():
    root = tk.Tk()
    game = ASCIISkiGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()