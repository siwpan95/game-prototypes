"""
探险日志 - 宣传视频生成 v6
改进:
  1. ✅ 场景间淡入淡出过渡
  3. ✅ 文字动画（逐条淡入）
  4. 待实现：真实游戏截图替换
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont
import numpy as np

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promo_frames")
VIDEO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "探险日志_宣传视频.mp4")
W, H = 1280, 720
FPS = 30
TRANSITION_FRAMES = 15  # 0.5秒过渡

os.makedirs(OUTPUT_DIR, exist_ok=True)

BG_COLOR = (245, 230, 210)
BROWN = (101, 67, 33)
DARK_BROWN = (80, 50, 20)
GOLD = (212, 175, 55)
RED = (180, 50, 50)
GREEN = (50, 150, 50)
BLUE = (50, 100, 180)
WHITE = (255, 255, 255)
BLACK = (30, 20, 10)
TAB_BG = (220, 200, 170)
TAB_ACTIVE = (180, 140, 90)


def get_font(size):
    for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def blend_images(img_a, img_b, alpha):
    a = np.array(img_a.convert("RGB"), dtype=np.float32)
    b = np.array(img_b.convert("RGB"), dtype=np.float32)
    return Image.fromarray(np.clip(a * (1-alpha) + b * alpha, 0, 255).astype(np.uint8))


def crossfade_frames(img_a, img_b, n=TRANSITION_FRAMES):
    return [blend_images(img_a, img_b, i/(n-1)) for i in range(n)]


def render_text_layer(lines_with_style, w=W, h=H):
    """
    渲染文字图层（RGBA）
    lines_with_style: [(text, x, y, fontsize, color, alpha)]
    """
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for text, x, y, fontsize, color, alpha in lines_with_style:
        try:
            f = ImageFont.truetype(get_font(fontsize), fontsize)
        except:
            f = ImageFont.load_default()
        c = list(color) + [int(alpha * 255)]
        draw.text((x, y), text, font=f, fill=tuple(c), anchor="mm" if x == w//2 else "lm")
    return layer


def composite_with_text(bg_img, text_layer):
    """将文字图层合成到背景上"""
    return Image.alpha_composite(bg_img.convert("RGBA"), text_layer).convert("RGB")


# ========== 动画场景生成器 ==========
# 每个场景返回一个列表 of (frame_image, duration_in_frames)
# 或者：生成一个完整的动画帧序列

def make_animated_scene(scene_draw_fn, text_timeline, total_frames):
    """
    通用动画场景生成器
    scene_draw_fn: 函数(visible_text_indices) -> 背景图片（不含动画文字）
    text_timeline: [(text, x, y, fontsize, color)] 列表，按出现顺序
    total_frames: 场景总帧数
    """
    frames = []
    n_texts = len(text_timeline)
    # 每个文字项在 total_frames 的前 2/3 内均匀分布出现
    appear_frames = [int(total_frames * 0.1 + i * total_frames * 0.6 / n_texts) for i in range(n_texts)]
    fade_frames = 8  # 淡入用时
    
    for f_idx in range(total_frames):
        # 绘制背景（不含动画文字）
        visible = [i for i in range(n_texts) if f_idx >= appear_frames[i]]
        bg = scene_draw_fn(visible)
        
        # 绘制文字图层（带淡入）
        text_items = []
        for i, (text, x, y, fontsize, color) in enumerate(text_timeline):
            if f_idx >= appear_frames[i]:
                progress = min(1.0, (f_idx - appear_frames[i]) / fade_frames)
                alpha = progress
                text_items.append((text, x, y, fontsize, color, alpha))
        
        if text_items:
            text_layer = render_text_layer(text_items)
            frame = composite_with_text(bg, text_layer)
        else:
            frame = bg.convert("RGB")
        
        frames.append(frame)
    
    return frames


# ========== 场景背景绘制（不含动画文字） ==========

def draw_base_ui(draw, title, active_tab=None):
    """绘制通用UI框架"""
    draw.rectangle([0, 0, W, H], fill=BG_COLOR)
    draw.rectangle([0, 0, W-1, H-1], outline=BROWN, width=3)
    draw.rectangle([4, 4, W-5, H-5], outline=(180,150,110), width=1)
    draw.rectangle([0, 0, W, 36], fill=DARK_BROWN)
    draw.text((W//2, 18), title, font=get_font(18), fill=GOLD, anchor="mm")
    if active_tab is not None:
        tab_names = ["酒馆", "郊外", "旅店", "商店", "仓库"]
        tab_w = W // 5
        for i, name in enumerate(tab_names):
            x0, x1 = i*tab_w, i*tab_w+tab_w-2
            color = TAB_ACTIVE if i==active_tab else TAB_BG
            draw.rectangle([x0,40,x1,70], fill=color, outline=BROWN, width=1)
            draw.text((x0+tab_w//2, 55), name, font=get_font(14), fill=BLACK, anchor="mm")

def draw_narrative_bar(img, text):
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, H-32, W, H], fill=DARK_BROWN)
    draw.text((W//2, H-16), text, font=get_font(12), fill=GOLD, anchor="mm")


def scene0_title_frames(total_frames=120):
    """标题卡动画帧"""
    frames = []
    narrative_text = "~ 每一次冒险，都是一段新的传说 ~"
    
    for f in range(total_frames):
        img = Image.new("RGB", (W, H), (30, 20, 10))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, W-20, H-20], outline=GOLD, width=3)
        
        # 标题淡入
        title_alpha = min(1.0, max(0, (f - 5) / 15))
        if title_alpha > 0:
            c = tuple(int(GOLD[i] * title_alpha) for i in range(3))
            draw.text((W//2, H//2-60), "探 险 日 志", font=get_font(72), fill=c, anchor="mm")
        
        # 副标题淡入
        sub_alpha = min(1.0, max(0, (f - 25) / 15))
        if sub_alpha > 0:
            c = tuple(int((200,180,140)[i] * sub_alpha) for i in range(3))
            draw.text((W//2, H//2+20), "Progress Quest 风格桌面放置 RPG", font=get_font(28), fill=c, anchor="mm")
        
        # 特性文字逐条出现
        features = ["酒馆 · 郊外 · 旅店 · 商店 · 仓库", "招募 · 探索 · 战斗 · 收集"]
        for i, feat in enumerate(features):
            alpha = min(1.0, max(0, (f - 50 - i*15) / 10))
            if alpha > 0:
                c = tuple(int((180,160,120)[i] * alpha) for i in range(3))
                draw.text((W//2, H//2+70+i*40), feat, font=get_font(18), fill=c, anchor="mm")
        
        # 叙事条
        nar_alpha = min(1.0, max(0, (f - 90) / 15))
        if nar_alpha > 0:
            draw.rectangle([0, H-32, W, H], fill=DARK_BROWN)
            c = tuple(int(GOLD[i] * nar_alpha) for i in range(3))
            draw.text((W//2, H-16), narrative_text, font=get_font(12), fill=c, anchor="mm")
        
        frames.append(img)
    return frames


def scene1_tavern_frames(total_frames=150):
    """酒馆场景动画帧"""
    frames = []
    heroes = [("艾莉丝","战士",5,80,80,40,40,22,15),
              ("格勒","法师",4,65,65,55,55,18,12),
              ("瑟兰","游侠",3,50,50,30,30,15,10)]
    
    for f in range(total_frames):
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        draw_base_ui(draw, "探险日志 v1.0", active_tab=0)
        
        # 输入区
        draw.rectangle([20,80,450,130], fill=(255,248,235), outline=BROWN, width=2)
        draw.text((30,88), "输入冒险者名字:", font=get_font(13), fill=DARK_BROWN)
        draw.rectangle([200,85,380,125], fill=WHITE, outline=BROWN, width=1)
        draw.text((210,95), "艾莉丝", font=get_font(13), fill=BLACK)
        draw_button(draw, 390,85,55,35,"掷骰")
        draw_button(draw, 20,135,100,35,"招募", color=GREEN)
        
        # 队伍标题
        draw.rectangle([20,180,600,680], fill=(255,248,235), outline=BROWN, width=2)
        draw.text((30,188), "我的队伍:", font=get_font(13), fill=DARK_BROWN)
        
        # 角色卡片逐张出现（带淡入）
        for i, hdata in enumerate(heroes):
            appear = 10 + i * 25
            if f >= appear:
                alpha = min(1.0, (f - appear) / 8)
                # 绘制卡片到临时图片然后blend
                card_img = Image.new("RGB", (W,H), BG_COLOR)
                cd = ImageDraw.Draw(card_img)
                draw_base_ui(cd, "探险日志 v1.0", active_tab=0)
                cd.rectangle([20,80,450,130], fill=(255,248,235), outline=BROWN, width=2)
                cd.text((30,88), "输入冒险者名字:", font=get_font(13), fill=DARK_BROWN)
                draw_hero_card_on(cd, 30, 215+i*150, *hdata)
                # blend
                if alpha < 1:
                    blended = blend_images(img, card_img, alpha)
                    # 只保留卡片区域
                    mask = Image.new("L", (W,H), 0)
                    mdraw = ImageDraw.Draw(mask)
                    mdraw.rectangle([30, 215+i*150, 230, 215+i*150+130], fill=255)
                    img.paste(blended, (0,0), mask)
                else:
                    draw_hero_card_on(draw, 30, 215+i*150, *hdata)
        
        # 右侧说明（淡入）
        draw.rectangle([620,80,1260,680], fill=(255,248,235), outline=BROWN, width=2)
        right_alpha = min(1.0, max(0, (f - 60) / 15))
        if right_alpha > 0:
            items = ["战士: 高HP高防御，队伍的前排坦克","法师: 高MP高魔力，强大的法术输出",
                     "游侠: 高速度，擅长先手和闪避","牧师: 治疗与辅助，队伍的后盾"]
            for i, t in enumerate(items):
                item_alpha = min(1.0, max(0, (f - 60 - i*10) / 8))
                if item_alpha > 0:
                    c = tuple(int(BLACK[i] * min(item_alpha, 1.0)) for i in range(3))
                    if item_alpha >= 1:
                        c = BLACK
                    draw.text((630, 115+i*25), f"· {t}", font=get_font(11), fill=c)
        
        draw_narrative_bar(img, "~ 酒馆里热闹非凡，勇敢的冒险者们正在集结 ~")
        frames.append(img)
    
    return frames


def draw_hero_card_on(draw, x, y, name, job, level, hp, mhp, mp, mmp, atk, defense):
    cw, ch = 200, 130
    draw.rectangle([x,y,x+cw,y+ch], fill=(255,248,235), outline=BROWN, width=2)
    draw.text((x+10,y+8), name, font=get_font(13), fill=DARK_BROWN)
    draw.text((x+10,y+26), f"职业: {job}  Lv.{level}", font=get_font(11), fill=BLACK)
    draw.rectangle([x+10,y+44,x+cw-10,y+56], outline=BLACK, width=1)
    draw.rectangle([x+10,y+44,x+10+int(hp/mhp*(cw-20)),y+56], fill=RED)
    draw.text((x+10,y+58), f"HP: {hp}/{mhp}", font=get_font(11), fill=BLACK)
    draw.rectangle([x+10,y+74,x+cw-10,y+84], outline=BLACK, width=1)
    draw.rectangle([x+10,y+74,x+10+int(mp/mmp*(cw-20)),y+84], fill=BLUE)
    draw.text((x+10,y+86), f"MP: {mp}/{mmp}", font=get_font(11), fill=BLACK)
    draw.text((x+10,y+102), f"ATK:{atk}  DEF:{defense}", font=get_font(11), fill=BLACK)


def draw_button(draw, x0, y0, w, h, text, color=None):
    color = color or (180,140,90)
    draw.rectangle([x0,y0,x0+w,y0+h], fill=color, outline=BROWN, width=2)
    draw.text((x0+w//2,y0+h//2), text, font=get_font(12), fill=WHITE, anchor="mm")


def scene2_wilderness_frames(total_frames=150):
    """郊外场景动画帧"""
    frames = []
    logs = ["=== 进入 新手森林 B1F ===", "队伍向前推进...", "遭遇了 哥布林！",
            "--- 战斗开始 ---", "艾莉丝 攻击了 哥布林", "造成 14 点伤害",
            "哥布林 被击倒了！", "获得 25 金币", "--- 战斗结束 ---",
            "", "继续探索...", "发现了一个宝箱！", "获得了 治疗药水", "", "到达楼梯，前往 B2F"]
    
    for f in range(total_frames):
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        draw_base_ui(draw, "探险日志 v1.0", active_tab=1)
        
        # 地下城列表
        draw.rectangle([20,80,450,350], fill=(255,248,235), outline=BROWN, width=2)
        draw.text((30,88), "可探索的地下城:", font=get_font(12), fill=DARK_BROWN)
        for i,(n,d,ok) in enumerate([("新手森林",1,True),("幽暗洞穴",3,True),("遗忘遗迹",5,True),("火焰山脉",7,False),("冰霜深渊",9,False)]):
            y=115+i*42; col=(240,230,210) if ok else (200,200,200)
            draw.rectangle([28,y,442,y+38], fill=col, outline=BROWN, width=1)
            draw.text((36,y+5), f"{n}  {'★'*d}", font=get_font(12), fill=BLACK if ok else (150,150,150))
        
        # 探索控制
        draw.rectangle([20,440,450,620], fill=(255,248,235), outline=BROWN, width=2)
        draw.text((30,448), "探索: 新手森林 B1F/5F", font=get_font(12), fill=DARK_BROWN)
        draw_button(draw, 30,475,80,35,"继续", color=GREEN)
        draw_button(draw, 120,475,80,35,"撤退")
        draw_button(draw, 210,475,80,35,"扎营")
        draw.rectangle([20,560,220,620], fill=(255,248,235), outline=BROWN, width=1)
        draw.text((30,568), "速度:", font=get_font(12), fill=DARK_BROWN)
        draw_button(draw, 30,585,50,28,"1x")
        draw_button(draw, 85,585,50,28,"2x")
        draw_button(draw, 140,585,50,28,"5x")
        
        # 探索日志（逐行出现）
        draw.rectangle([480,80,1260,680], fill=(20,15,10), outline=BROWN, width=2)
        draw.text((490,88), "探索日志:", font=get_font(12), fill=GOLD)
        max_lines = min(len(logs), 1 + max(0, (f - 10) // 8))
        for i, log in enumerate(logs[:max_lines]):
            if not log: continue
            c = GOLD if ("==" in log or "---" in log) else (180,180,180)
            if "获得" in log or "宝箱" in log: c = (100,255,100)
            if "击倒" in log: c = (100,255,100)
            draw.text((490, 115+i*18), log, font=get_font(11), fill=c)
        
        draw_narrative_bar(img, "~ 冒险者们的脚步，在黑暗中留下光芒 ~")
        frames.append(img)
    return frames


def scene3_battle_frames(total_frames=150):
    """战斗场景动画帧"""
    frames = []
    battle_logs = ["=== 战斗开始！ ===", "艾莉丝 使用了 火球术！", "对 哥布林 造成了 28 点伤害",
                   "哥布林 剩余 HP: 12/40", "", "哥布林 发动攻击！", "格勒 受到 8 点伤害",
                   "格勒 剩余 HP: 57/65", "", "格勒 使用了 治疗术！", "格勒 恢复了 15 点 HP"]
    
    for f in range(total_frames):
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        draw_base_ui(draw, "探险日志 v1.0 - 战斗中", active_tab=1)
        
        # 队伍（逐张出现）
        draw.rectangle([20,50,580,370], fill=(255,248,235), outline=BROWN, width=2)
        draw.text((30,58), "我方队伍", font=get_font(14), fill=DARK_BROWN)
        heroes = [("艾莉丝","战士",5,65,80,35,40,22,15),
                  ("格勒","法师",4,58,65,40,55,18,12),
                  ("瑟兰","游侠",3,42,50,25,30,15,10)]
        for i, hdata in enumerate(heroes):
            if f >= 5+i*10:
                draw_hero_card_on(draw, 30, 80+i*120, *hdata)
        
        # VS
        if f > 30:
            vs_alpha = 0.7 + 0.3 * abs(np.sin(f/5))
            c = tuple(int(RED[i]*vs_alpha) for i in range(3))
            draw.text((W//2,200), "VS", font=get_font(64), fill=c, anchor="mm")
        
        # 怪物
        draw.rectangle([600,50,1260,370], fill=(40,20,20), outline=BROWN, width=2)
        draw.text((610,58), "敌人", font=get_font(14), fill=(200,100,100))
        for i,(n,hp,mhp) in enumerate([("哥布林",12,40),("哥布林投手",25,30)]):
            if f >= 20+i*15:
                y=85+i*120
                draw.rectangle([610,y,1240,y+110], fill=(60,30,30), outline=(150,80,80), width=2)
                draw.text((620,y+8), n, font=get_font(14), fill=(255,150,150))
                draw.rectangle([620,y+52,1100,y+64], outline=BLACK, width=1)
                draw.rectangle([620,y+52,620+int(hp/mhp*480),y+64],
                              fill=GREEN if hp>mhp*0.5 else (255,200,0) if hp>mhp*0.2 else RED)
                draw.text((620,y+68), f"HP: {hp}/{mhp}", font=get_font(11), fill=WHITE)
        
        # 战斗日志
        if f > 40:
            draw.rectangle([20,380,580,680], fill=(20,15,10), outline=BROWN, width=2)
            draw.text((30,388), "战斗日志:", font=get_font(12), fill=GOLD)
            max_l = min(len(battle_logs), 1+max(0,(f-40)//8))
            for i, log in enumerate(battle_logs[:max_l]):
                c = GOLD if "==" in log else (200,200,200)
                if "火球" in log or "治疗" in log: c = (255,200,100)
                if "受到" in log: c = (255,120,120)
                draw.text((30,415+i*16), log, font=get_font(11), fill=c)
        
        # 技能
        if f > 60:
            draw.rectangle([600,380,1260,680], fill=(255,248,235), outline=BROWN, width=2)
            draw.text((610,388), "技能（自动释放）:", font=get_font(12), fill=DARK_BROWN)
            for i in range(4):
                sx=610+(i%2)*310; sy=420+(i//2)*60
                draw.rectangle([sx,sy,sx+290,sy+50], fill=(100,60,20), outline=GOLD, width=1)
                draw.text((sx+10,sy+15), f"技能{i+1} (CD: 0)", font=get_font(12), fill=(255,220,150))
        
        draw_narrative_bar(img, "~ 每一次战斗，都是勇气与智慧的较量 ~")
        frames.append(img)
    return frames


def scene4_features_frames(total_frames=180):
    """特性展示动画帧"""
    frames = []
    features = [("酒馆系统","招募冒险者，掷骰决定属性"),
                ("自动战斗","回合制全自动，1x/2x/5x加速"),
                ("地牢探索","7座地下城，难度递增"),
                ("装备收集","武器/防具/饰品，打造最强队伍"),
                ("随机事件","探索中遭遇事件，选择影响结果"),
                ("数据驱动","JSON配置，Excel可编辑，轻松MOD")]
    
    for f in range(total_frames):
        img = Image.new("RGB", (W, H), (30,20,10))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20,20,W-20,H-20], outline=GOLD, width=3)
        
        # 标题
        title_alpha = min(1.0, max(0, f/10))
        if title_alpha > 0:
            c = tuple(int((255,220,150)[i]*title_alpha) for i in range(3))
            draw.text((W//2,60), "游戏特色", font=get_font(36), fill=c, anchor="mm")
        
        # 特性逐条飞入（从右往左）
        for i, (title, desc) in enumerate(features):
            appear = 10 + i * 20
            if f >= appear:
                progress = min(1.0, (f - appear) / 10)
                # 从右侧滑入
                offset_x = int((1 - progress) * 200)
                alpha = progress
                c_title = tuple(int(min(255, 255*alpha)) for _ in range(3))
                c_desc = tuple(int(min(180, 180*alpha)) for _ in range(3))
                if progress >= 1:
                    c_title = WHITE
                    c_desc = (180,180,180)
                y = 130 + i * 85
                draw.rectangle([100+offset_x, y, 170+offset_x, y+50], fill=GOLD, outline=DARK_BROWN, width=2)
                draw.text((135+offset_x, y+25), str(i+1), font=get_font(20), fill=DARK_BROWN, anchor="mm")
                draw.text((200+offset_x, y+10), title, font=get_font(22), fill=c_title)
                draw.text((200+offset_x, y+40), desc, font=get_font(16), fill=c_desc)
        
        # CTA按钮
        if f > 150:
            progress = min(1.0, (f-150)/15)
            alpha = int(255*progress)
            draw.rectangle([W//2-200,H-120,W//2+200,H-70],
                          fill=tuple(min(255,int(GOLD[i]*progress)) for i in range(3)),
                          outline=DARK_BROWN, width=2)
            if progress >= 1:
                draw.text((W//2,H-95), "立即下载 探险日志", font=get_font(24), fill=DARK_BROWN, anchor="mm")
        
        draw_narrative_bar(img, "~ 你的冒险，即将开始 ~")
        frames.append(img)
    return frames


# ========== 主流程 ==========

def main():
    print("=" * 60)
    print("探险日志 - 宣传视频 v6（过渡+文字动画）")
    print("=" * 60)
    
    scenes = [
        ("00_title", scene0_title_frames, 120),
        ("01_tavern", scene1_tavern_frames, 150),
        ("02_wilderness", scene2_wilderness_frames, 150),
        ("03_battle", scene3_battle_frames, 150),
        ("04_features", scene4_features_frames, 180),
    ]
    
    all_frames = []
    
    for idx, (name, fn, n_frames) in enumerate(scenes):
        print(f"生成: {name} ({n_frames}帧)...")
        scene_frames = fn(n_frames)
        print(f"  实际: {len(scene_frames)}帧")
        
        if idx == 0:
            all_frames.extend(scene_frames)
        else:
            # 场景间交叉淡入淡出
            source_start = len(all_frames) - TRANSITION_FRAMES
            source_frames = all_frames[source_start:]
            target_frames = scene_frames[:TRANSITION_FRAMES]
            
            cf = [blend_images(source_frames[j], target_frames[j], j/(TRANSITION_FRAMES-1))
                  for j in range(TRANSITION_FRAMES)]
            
            all_frames = all_frames[:source_start]
            all_frames.extend(cf)
            all_frames.extend(scene_frames[TRANSITION_FRAMES:])
            print(f"  添加过渡: {TRANSITION_FRAMES}帧交叉淡入淡出")
        
        # 保存最后一张作为场景缩略图
        if scene_frames:
            scene_frames[-1].save(os.path.join(OUTPUT_DIR, f"{name}_final.png"))
    
    # 末尾定格帧（停留1秒）
    if all_frames:
        last_frame = all_frames[-1]
        hold_frames = FPS
        print(f"末尾定格: {hold_frames}帧")
        all_frames.extend([last_frame.copy() for _ in range(hold_frames)])
    
    print(f"\n总帧数: {len(all_frames)} ({len(all_frames)/FPS:.1f}秒)")
    
    # 合成视频
    print("合成视频...")
    try:
        import imageio
    except ImportError:
        import subprocess
        subprocess.run([sys.executable,"-m","pip","install","imageio","imageio-ffmpeg"], check=True)
        import imageio
    
    writer = imageio.get_writer(VIDEO_PATH, fps=FPS, codec="libx264", pixelformat="yuv420p")
    for i, frame in enumerate(all_frames):
        arr = np.array(frame)
        writer.append_data(arr)
        if (i+1) % 90 == 0:
            print(f"  进度: {i+1}/{len(all_frames)}")
    writer.close()
    
    print(f"\n[完成] {VIDEO_PATH}")
    print(f"  时长: {len(all_frames)/FPS:.1f}秒")

if __name__ == "__main__":
    main()
