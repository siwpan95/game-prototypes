import os
import textwrap
from game_engine import GameEngine

# ---------- ASCII 常量 ----------
BAR_LEN = 20
BAR_FILL = '█'
BAR_EMPTY = '░'
BOX_H = '─'
BOX_V = '│'
BOX_TL = '╔'
BOX_TR = '╗'
BOX_BL = '╚'
BOX_BR = '╝'
BOX_ML = '╠'
BOX_MR = '╣'

TITLE = r'''
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║                   ⚡  十 二 试 炼  ⚡                         ║
    ║                     神话重构                                  ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
'''

DIVIDER = '·' * 80

def _bar(value: int, maximum: int = 20) -> str:
    ratio = max(0, min(value, maximum)) / maximum
    filled = int(ratio * BAR_LEN)
    empty = BAR_LEN - filled
    return f"{BAR_FILL * filled}{BAR_EMPTY * empty} {value:>3}/{maximum}"

def _bordered_box(title: str, content: str, width: int = 78) -> str:
    inner_width = width - 2
    title_line = f"{BOX_V} {title:<{inner_width-2}} {BOX_V}"
    sep_line = f"{BOX_ML}{BOX_H * inner_width}{BOX_MR}"
    wrapped = textwrap.wrap(content, width=inner_width - 4)
    content_lines = []
    for line in wrapped:
        content_lines.append(f"{BOX_V}  {line:<{inner_width-4}}  {BOX_V}")
    top = f"{BOX_TL}{BOX_H * inner_width}{BOX_TR}"
    bottom = f"{BOX_BL}{BOX_H * inner_width}{BOX_BR}"
    box = [top, title_line, sep_line] + content_lines + [bottom]
    return '\n'.join(box)

class ConsoleUI:
    def run(self, engine: GameEngine):
        ConsoleUI._clear()
        print(TITLE)
        print("        硬核神话重构 · 命运由掷骰决定")
        print("\n" * 2)
        input("按回车踏上试炼之路...")

        prev_chapter_index = -1
        while engine.is_alive():
            ConsoleUI._clear()
            self._draw_status(engine)

            event = engine.get_current_event()
            if event is None:
                if engine.state == "GAME_OVER":
                    print("⚡ 所有试炼已完成，等待命运最终的裁决...")
                    break
                continue  # 章节刚加载完但无事件，重试

            # 检测章节切换并显示过渡提示（get_current_event 内部会推进章节）
            if engine.current_labour_index != prev_chapter_index:
                labour_names = {
                    'chapter_01': '第一试炼：涅墨亚雄狮', 'chapter_02': '第二试炼：勒尔涅九头蛇',
                    'chapter_03': '第三试炼：刻律涅牝鹿', 'chapter_04': '第四试炼：厄律曼托斯野猪',
                    'chapter_05': '第五试炼：奥革阿斯牛棚', 'chapter_06': '第六试炼：斯廷法利斯怪鸟',
                    'chapter_07': '第七试炼：克里特公牛', 'chapter_08': '第八试炼：狄俄墨得斯牝马',
                    'chapter_09': '第九试炼：希波吕忒腰带', 'chapter_10': '第十试炼：革律翁牛群',
                    'chapter_11': '第十一试炼：赫斯珀里得斯金苹果', 'chapter_12': '第十二试炼：地狱三头犬'
                }
                cid = engine.selected_labours[engine.current_labour_index]
                chapter_name = labour_names.get(cid, f'未知试炼：{cid}')
                print(f"\n{'='*50}")
                print(f"  ⚡ {chapter_name}")
                print(f"{'='*50}")
                input("按回车迎接新的试炼...")
                ConsoleUI._clear()
                self._draw_status(engine)

            prev_chapter_index = engine.current_labour_index

            self._draw_event(event)
            choice = self._get_choice(len(event['options']))
            if choice == -1:
                print("你放弃了英雄之路，成为无名之魂。")
                break

            success, text, _ = engine.process_option(event, choice)
            ConsoleUI._clear()
            self._draw_status(engine)
            self._draw_event(event)
            if success:
                print(f"✅ 成功：{text}")
            else:
                print(f"❌ 失败：{text}")
            engine.apply_turn_end_effects()
            if not engine.is_alive():
                print(engine.get_death_reason())
                input("\n按回车面对结局...")
                break
            input("\n按回车继续...")

        ConsoleUI._clear()
        endings = engine.check_endings()
        if endings:
            print(DIVIDER)
            for e in endings:
                print(f"【{e['name']}】")
                print(e['text'])
                print()

        # 隐藏第十三试炼检测
        if engine.check_hidden_labor_trigger():
            print("\n【隐藏触发】")
            print("在通关的光芒中，你似乎听到了第十三个心跳。")
            print("那是深渊的回响，还是命运的预告？")
            print()

        # 终局评分报告
        print(DIVIDER)
        print(engine.generate_post_game_report())
        print(DIVIDER)

        if not endings:
            print("你的故事未被传唱，湮没于黄沙。")
        return endings

    @staticmethod
    def _clear():
        os.system('cls' if os.name == 'nt' else 'clear')

    def _draw_status(self, engine: GameEngine):
        s = engine.stats

        # 试炼路径显示
        themes = []
        for i, cid in enumerate(engine.selected_labours):
            for t, ids in engine.labour_pool.items():
                if cid in ids:
                    themes.append(engine.POOL_CN.get(t, t))
                    break
            else:
                themes.append('?')
        path_str = ' → '.join(themes)
        progress = f"{engine.current_labour_index + 1}/{engine.total_labours}"

        print(f"⚔️  {engine.character_name}  |  试炼 {progress}  |  回合 {engine.turn}")
        print(f"🗺️  试炼之路：{path_str}")
        print(DIVIDER)

        row1 = [
            f"荣耀：{_bar(s['荣耀'], 20)}",
            f"力量：{_bar(s['力量'], 20)}",
            f"智慧：{_bar(s['智慧'], 20)}"
        ]
        row2 = [
            f"神恩：{_bar(s['神恩'], 20)}",
            f"疯狂：{_bar(s['疯狂'], 20)}",
            f"生命：{_bar(s['生命'], 20)}"
        ]
        print("  ".join(row1))
        print("  ".join(row2))
        relics = engine.relics
        if relics:
            relic_names = '、'.join([r['name'] for r in relics])
            print(f"📿 遗物：{relic_names}")
        print(DIVIDER)

    @staticmethod
    def _draw_event(event):
        title = event.get('title', '未知事件')
        text = event.get('text', '')
        box = _bordered_box(title, text)
        print(box)
        print()
        for i, opt in enumerate(event.get('options', []), 1):
            print(f"  [{i}]  {opt['text']}")
        print()

    @staticmethod
    def _get_choice(max_opt: int) -> int:
        while True:
            try:
                c = input("▶ 你的选择 (数字, q=放弃) ").strip()
                if c.lower() == 'q':
                    return -1
                if c.isdigit() and 1 <= int(c) <= max_opt:
                    return int(c) - 1
            except:
                pass
            print("请输入有效选项。")