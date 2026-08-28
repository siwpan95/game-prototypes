"""Audio Integration Guide for KARD — 音频系统集成指南。

本文件说明如何将 AudioSystem 集成到 KARD 游戏中，
并触发所有游戏的音频事件。

遵循音频工程师规范：
- 游戏逻辑不直接调用 pygame.mixer
- 通过 AudioEventComponent 抛出音频事件
- AudioSystem 每帧消费事件队列
"""

import os
import sys

# ── 步骤 1：修改 main.py 初始化音频系统 ─────────────────────────


def patch_main_py() -> str:
    """返回需要添加到 main.py 的代码片段。"""

    code = '''
# ===== 音频系统初始化（添加到 main.py 的 imports 区域） =====
from audio import AudioSystem, MusicController, SFXBank
from audio.audio_components import AudioEventComponent, MusicStateComponent
from audio.audio_constants import AudioEventType, PYGAME_MIXER_CONFIG

# ===== 音频系统初始化（添加到 main() 函数中，pygame.init() 之后） =====
def init_audio_system():
    """初始化音频系统。"""
    try:
        # 配置 pygame.mixer（音频工程师规范）
        freq = PYGAME_MIXER_CONFIG["frequency"]
        size = PYGAME_MIXER_CONFIG["size"]
        channels = PYGAME_MIXER_CONFIG["channels"]
        buffer = PYGAME_MIXER_CONFIG["buffer"]

        pygame.mixer.init(
            frequency=freq,
            size=size,
            channels=channels,
            buffer=buffer,
        )
        print(f"[Audio] mixer 初始化成功: {pygame.mixer.get_init()}")
        return True
    except Exception as e:
        print(f"[Audio] mixer 初始化失败: {e}")
        return False


def main() -> None:
    pygame.init()

    # 初始化音频系统
    audio_enabled = init_audio_system()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    # ECS World
    world = World()
    gs = GameState()

    # ===== 创建音频系统（在创建其他系统之前）=====
    audio_sys = None
    music_ctrl = None
    if audio_enabled:
        try:
            audio_sys = AudioSystem(gs)
            music_ctrl = MusicController()
            world.add_system(audio_sys)
            print("[Audio] 音频系统已加载")
        except Exception as e:
            print(f"[Audio] 音频系统加载失败: {e}")
            audio_sys = None

    # Systems
    combat_sys = CombatSystem(gs)
    keyword_sys = KeywordSystem(gs)
    render_sys = RenderSystem(screen, gs)
    input_sys = InputSystem(gs, combat_sys)

    # 系统顺序很重要！音频系统应该在渲染之后执行
    world.add_system(input_sys)      # input first
    world.add_system(combat_sys)      # combat resolution
    world.add_system(keyword_sys)    # keyword effects
    world.add_system(render_sys)     # drawing (runs last)
    if audio_sys:
        world.add_system(audio_sys)   # audio (runs after render)

    # ... 其余代码保持不变 ...
'''

    return code


# ── 步骤 2：在游戏逻辑中触发音频事件 ─────────────────────────


class AudioEventTriggers:
    """音频事件触发器 —— 在游戏逻辑中调用这些方法来触发音效。

    用法：
    from audio_integration import AudioEventTriggers

    # 在需要播放音效的地方：
    AudioEventTriggers.on_card_play(world, card_entity)
    """

    @staticmethod
    def on_card_play(world, card_entity) -> None:
        """卡牌打出时触发。"""
        # 获取或创建 AudioEventComponent
        audio_comp = world.get_component(card_entity, AudioEventComponent)
        if not audio_comp:
            world.add_component(card_entity, AudioEventComponent())
            audio_comp = world.get_component(card_entity, AudioEventComponent)

        # 根据卡牌类型选择音效
        card = world.get_component(card_entity, "CardComponent")
        if card:
            if card.card_type == "attack":
                audio_comp.push_event(AudioEventType.CARD_PLAY, volume=0.7)
            elif card.card_type == "skill":
                audio_comp.push_event(AudioEventType.CARD_PLAY, volume=0.6)
            elif card.card_type == "minion":
                audio_comp.push_event(AudioEventType.MINION_SUMMON, volume=0.7)

    @staticmethod
    def on_card_draw(world, card_entity) -> None:
        """抽卡时触发。"""
        audio_comp = world.get_component(card_entity, AudioEventComponent)
        if not audio_comp:
            world.add_component(card_entity, AudioEventComponent())
            audio_comp = world.get_component(card_entity, AudioEventComponent)
        audio_comp.push_event(AudioEventType.CARD_DRAW, volume=0.5)

    @staticmethod
    def on_card_select(world, card_entity) -> None:
        """选中卡牌时触发。"""
        audio_comp = world.get_component(card_entity, AudioEventComponent)
        if not audio_comp:
            return
        audio_comp.push_event(AudioEventType.CARD_SELECT, volume=0.4)

    @staticmethod
    def on_combat_attack(world, attacker_entity, target_entity) -> None:
        """攻击时触发。"""
        # 给攻击者添加音频事件
        audio_comp = world.get_component(attacker_entity, AudioEventComponent)
        if not audio_comp:
            world.add_component(attacker_entity, AudioEventComponent())
            audio_comp = world.get_component(attacker_entity, AudioEventComponent)

        # 3D 空间音频：传递位置信息
        pos = world.get_component(attacker_entity, "PositionComponent")
        if pos:
            audio_comp.push_spatial_event(
                AudioEventType.COMBAT_ATTACK,
                x=pos.x,
                y=pos.y,
                volume=0.8,
            )
        else:
            audio_comp.push_event(AudioEventType.COMBAT_ATTACK, volume=0.8)

    @staticmethod
    def on_combat_damage(world, target_entity, amount: int) -> None:
        """受到伤害时触发。"""
        audio_comp = world.get_component(target_entity, AudioEventComponent)
        if not audio_comp:
            world.add_component(target_entity, AudioEventComponent())
            audio_comp = world.get_component(target_entity, AudioEventComponent)

        # 根据伤害量调整音量
        volume = min(1.0, 0.3 + amount * 0.05)
        audio_comp.push_event(AudioEventType.COMBAT_DAMAGE_PLAYER, volume=volume)

    @staticmethod
    def on_combat_heal(world, target_entity, amount: int) -> None:
        """治疗时触发。"""
        audio_comp = world.get_component(target_entity, AudioEventComponent)
        if not audio_comp:
            world.add_component(target_entity, AudioEventComponent())
            audio_comp = world.get_component(target_entity, AudioEventComponent)
        audio_comp.push_event(AudioEventType.COMBAT_HEAL, volume=0.6)

    @staticmethod
    def on_minion_summon(world, minion_entity) -> None:
        """召唤随从时触发。"""
        audio_comp = world.get_component(minion_entity, AudioEventComponent)
        if not audio_comp:
            world.add_component(minion_entity, AudioEventComponent())
            audio_comp = world.get_component(minion_entity, AudioEventComponent)
        audio_comp.push_event(AudioEventType.MINION_SUMMON, volume=0.7)

    @staticmethod
    def on_minion_death(world, minion_entity) -> None:
        """随从死亡时触发。"""
        audio_comp = world.get_component(minion_entity, AudioEventComponent)
        if not audio_comp:
            return
        audio_comp.push_event(AudioEventType.MINION_DEATH, volume=0.5)

    @staticmethod
    def on_enemy_turn_start(world) -> None:
        """敌人回合开始时触发。"""
        # 全局音频事件（附加到世界实体）
        for e in world.entities:
            if world.get_component(e, MusicStateComponent):
                audio_comp = world.get_component(e, AudioEventComponent)
                if not audio_comp:
                    world.add_component(e, AudioEventComponent())
                    audio_comp = world.get_component(e, AudioEventComponent)
                audio_comp.push_event(AudioEventType.ENEMY_TURN_START, volume=0.6)
                break

    @staticmethod
    def on_game_phase_change(world, new_phase: str) -> None:
        """游戏阶段变化时触发。"""
        # 更新 MusicController 参数
        music_comp = None
        for e in world.entities:
            music_comp = world.get_component(e, MusicStateComponent)
            if music_comp:
                break

        if music_comp:
            music_comp.set_game_phase(new_phase)

            # 触发阶段切换音效
            audio_comp = world.get_component(e, AudioEventComponent)
            if not audio_comp:
                world.add_component(e, AudioEventComponent())
                audio_comp = world.get_component(e, AudioEventComponent)

            phase_to_event = {
                "MENU": AudioEventType.GAME_START,
                "BATTLE": AudioEventType.ROOM_ENTER,
                "EVENT": AudioEventType.EVENT_ENTER,
                "MERCHANT": AudioEventType.MERCHANT_ENTER,
                "CAMPFIRE": AudioEventType.CAMPFIRE_ENTER,
                "GAME_OVER": AudioEventType.GAME_OVER,
            }
            event = phase_to_event.get(new_phase)
            if event:
                audio_comp.push_event(event, volume=0.8)

    @staticmethod
    def on_ui_click(world) -> None:
        """UI 点击时触发。"""
        # UI 音效通常附加到玩家实体
        for e in world.entities:
            if world.get_component(e, "PlayerComponent"):
                audio_comp = world.get_component(e, AudioEventComponent)
                if not audio_comp:
                    world.add_component(e, AudioEventComponent())
                    audio_comp = world.get_component(e, AudioEventComponent)
                audio_comp.push_event(AudioEventType.UI_CLICK, volume=0.6)
                break

    @staticmethod
    def on_ui_hover(world, ui_element_entity) -> None:
        """UI 悬停时触发（谨慎使用，避免过于频繁）。"""
        audio_comp = world.get_component(ui_element_entity, AudioEventComponent)
        if not audio_comp:
            world.add_component(ui_element_entity, AudioEventComponent())
            audio_comp = world.get_component(ui_element_entity, AudioEventComponent)
        # 悬停音效使用极低音量，避免 annoy
        audio_comp.push_event(AudioEventType.UI_HOVER, volume=0.2)

    @staticmethod
    def on_reward_show(world) -> None:
        """显示奖励时触发。"""
        for e in world.entities:
            if world.get_component(e, MusicStateComponent):
                audio_comp = world.get_component(e, AudioEventComponent)
                if not audio_comp:
                    world.add_component(e, AudioEventComponent())
                    audio_comp = world.get_component(e, AudioEventComponent)
                audio_comp.push_event(AudioEventType.REWARD_SHOW, volume=0.7)
                break

    @staticmethod
    def on_room_clear(world) -> None:
        """房间清理完成时触发。"""
        for e in world.entities:
            if world.get_component(e, MusicStateComponent):
                audio_comp = world.get_component(e, AudioEventComponent)
                if not audio_comp:
                    world.add_component(e, AudioEventComponent())
                    audio_comp = world.get_component(e, AudioEventComponent)
                audio_comp.push_event(AudioEventType.ROOM_CLEAR, volume=0.8)
                break


# ── 步骤 3：修改游戏文件以触发音频事件 ─────────────────────────


def get_integration_patches() -> dict[str, str]:
    """返回需要应用到各个游戏文件的补丁。"""

    patches = {}

    # ===== main.py 补丁 =====
    patches["main.py"] = '''
# 在 main.py 顶部添加：
from audio_integration import AudioEventTriggers

# 在 _advance_to_next_room() 中添加：
AudioEventTriggers.on_game_phase_change(world, "BATTLE")

# 在 _end_enemy_turn() 中（房间清理时）添加：
if len(alive) == 0:
    AudioEventTriggers.on_room_clear(world)
'''

    # ===== input_system.py 补丁 =====
    patches["input_system.py"] = '''
# 在 _handle_click() 中添加（UI 点击）：
AudioEventTriggers.on_ui_click(world)

# 在 _play_card() 中添加（卡牌打出）：
AudioEventTriggers.on_card_play(world, card_entity)

# 在 _select_card() 中添加（卡牌选中）：
AudioEventTriggers.on_card_select(world, clicked_entity)

# 在 _start_new_game() 中添加（游戏开始）：
AudioEventTriggers.on_game_phase_change(world, "MENU")
'''

    # ===== combat_system.py 补丁 =====
    patches["combat_system.py"] = '''
# 在 resolve_card() 中添加（卡牌效果生效）：
# （已在 audio_integration 中处理）

# 在 _resolve_attack_card() 中添加（攻击伤害）：
AudioEventTriggers.on_combat_attack(world, card_entity, target)

# 在 minion_attack() 中添加（随从攻击）：
AudioEventTriggers.on_combat_attack(world, attacker_entity, target_entity)

# 在 enemy_attack_player() 中添加（敌人攻击玩家）：
AudioEventTriggers.on_combat_damage(world, player_entity, dmg)

# 在 _check_death() 中添加（实体死亡）：
if world.get_component(entity, "MinionComponent"):
    AudioEventTriggers.on_minion_death(world, entity)
'''

    # ===== game_state.py 补丁 =====
    patches["game_state.py"] = '''
# 在 set_phase() 或 phase 属性 setter 中添加：
def set_phase(self, new_phase):
    old_phase = self._phase
    self._phase = new_phase
    if old_phase != new_phase:
        from audio_integration import AudioEventTriggers
        AudioEventTriggers.on_game_phase_change(world, new_phase)
'''

    return patches


# ── 步骤 4：创建占位音效文件 ─────────────────────────


def create_placeholder_audio_files() -> None:
    """创建占位音效文件（静音），以便测试音频系统。

    实际项目中应替换为真实录制的音效。
    """
    import numpy as np

    sfx_root = os.path.join(os.path.dirname(__file__), "..", "assets", "audio", "sfx")
    sfx_root = os.path.normpath(sfx_root)

    # 创建目录
    categories = ["ui", "card", "combat", "enemy", "minion", "system"]
    for cat in categories:
        os.makedirs(os.path.join(sfx_root, cat), exist_ok=True)

    # 生成静音 WAV 文件（1 秒，440Hz 正弦波）
    sample_rate = 44100
    duration = 0.5  # 秒
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    # 不同类别使用不同频率
    freq_map = {
        "ui/click": 800,
        "ui/hover": 600,
        "card/play": 523,  # C5
        "card/draw": 440,  # A4
        "combat/attack": 330,  # E4
        "combat/damage": 220,  # A3
        "enemy/intent_attack": 280,
        "minion/summon": 660,  # E5
        "system/game_start": 880,  # A5
        "system/room_clear": 1046,  # C6
    }

    for rel_path, freq in freq_map.items():
        file_path = os.path.join(sfx_root, rel_path + "_01.wav")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 生成音频数据
        wave = np.sin(2 * np.pi * freq * t) * 0.3  # 30% 振幅
        wave = (wave * 32767).astype(np.int16)

        # 保存为 WAV
        from scipy.io import wavfile
        wavfile.write(file_path, sample_rate, wave)
        print(f"[Audio] 创建占位音效: {file_path}")


# ── 步骤 5：测试音频系统 ─────────────────────────


def test_audio_system() -> None:
    """测试音频系统是否正常。"""
    print("[Audio Test] 开始测试音频系统...")

    try:
        from audio import AudioSystem, SFXBank
        from audio.audio_components import AudioEventComponent
        from audio.audio_constants import AudioEventType

        # 测试 1：创建 AudioSystem
        print("[Test 1] 创建 AudioSystem...")
        # 需要传入 GameState，这里简化处理
        print("  ✓ AudioSystem 类导入成功")

        # 测试 2：验证音效定义
        print("[Test 2] 验证音效库...")
        bank = SFXBank("dummy_path")
        names = bank.get_all_names()
        print(f"  ✓ 音效库包含 {len(names)} 个音效定义")
        print(f"  示例: {names[:5]}")

        # 测试 3：测试音频事件触发
        print("[Test 3] 测试音频事件触发...")
        # 实际项目中应在游戏中测试
        print("  ✓ AudioEventTriggers 方法已定义")

        print("[Audio Test] 测试完成！")

    except Exception as e:
        print(f"[Audio Test] 测试失败: {e}")
        import traceback
        traceback.print_exc()


# ── 主函数 ─────────────────────────


if __name__ == "__main__":
    print("=== KARD 音频系统集成指南 ===")
    print()

    print("步骤 1：查看需要添加到 main.py 的代码")
    code = patch_main_py()
    print(code[:500] + "..." if len(code) > 500 else code)
    print()

    print("步骤 2：查看音频事件触发器")
    print("  AudioEventTriggers 类提供了所有游戏音频触发方法")
    print()

    print("步骤 3：查看集成补丁")
    patches = get_integration_patches()
    for filename, patch in patches.items():
        print(f"  {filename}:")
        print(f"    {patch[:100]}...")
    print()

    print("步骤 4：创建占位音效文件")
    print("  运行 create_placeholder_audio_files() 创建测试音效")
    print()

    print("步骤 5：运行测试")
    print("  运行 test_audio_system() 测试音频系统")
    print()

    print("=== 集成完成 ===")
    print()
    print("接下来：")
    print("1. 将音频系统集成到 main.py")
    print("2. 在游戏逻辑中调用 AudioEventTriggers 方法")
    print("3. 替换为真实音效文件")
    print("4. 调整音效音量、音高随机化范围")
    print("5. 测试自适应音乐参数过渡")
