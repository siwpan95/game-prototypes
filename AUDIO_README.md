# KARD 游戏音频系统 —— 使用说明

## 📁 文件结构

```
kard_CN/
├── audio/                      # 音频系统包
│   ├── __init__.py             # 包导出
│   ├── audio_constants.py      # 音频常量（预算、路径、参数规范）
│   ├── audio_components.py     # ECS 组件（AudioEventComponent 等）
│   ├── audio_system.py         # 核心 ECS 系统（消费音频事件）
│   ├── music_controller.py     # 自适应音乐控制器
│   └── sfx_bank.py            # 音效资源库（定义所有音效）
├── audio_integration.py        # 集成指南（如何接入游戏）
├── assets/
│   └── audio/                # 音频资源目录
│       ├── sfx/               # 音效文件
│       │   ├── ui/
│       │   ├── card/
│       │   ├── combat/
│       │   ├── enemy/
│       │   ├── minion/
│       │   └── system/
│       └── music/              # 音乐文件
└── ...
```

---

## 🎯 核心设计理念

### 1. 事件驱动架构（音频工程师规范）

```
游戏逻辑 ────────┐
                 │
                 ▼
        AudioEventComponent（事件队列）
                 │
                 ▼
           AudioSystem（每帧消费）
                 │
                 ▼
            pygame.mixer / FMOD / Wwise
```

**游戏逻辑永远不直接调用音频 API。**

---

### 2. 音频事件触发示例

#### ❌ 错误做法（游戏逻辑直接播放音效）

```python
# 不要这样做！
pygame.mixer.Sound("click.wav").play()
```

#### ✅ 正确做法（通过 AudioEventComponent 抛出事件）

```python
# 在 combat_system.py 的 _resolve_attack_card() 中：
def _resolve_attack_card(self, world, card, target):
    # ... 伤害计算逻辑 ...

    # 触发音效：向目标实体的 AudioEventComponent 追加事件
    audio_comp = world.get_component(target, AudioEventComponent)
    if not audio_comp:
        world.add_component(target, AudioEventComponent())
        audio_comp = world.get_component(target, AudioEventComponent)

    audio_comp.push_event(
        event_name=AudioEventType.COMBAT_DAMAGE_ENEMY,
        volume=0.7,
        pitch=1.0,
    )

    # 如果是 3D 空间音效，使用：
    pos = world.get_component(attacker, PositionComponent)
    if pos:
        audio_comp.push_spatial_event(
            event_name=AudioEventType.COMBAT_ATTACK,
            x=pos.x,
            y=pos.y,
            volume=0.8,
        )
```

---

## 🚀 快速集成步骤

### 步骤 1：修改 `main.py`

在 `pygame.init()` 之后添加：

```python
from audio import AudioSystem
from audio.audio_constants import PYGAME_MIXER_CONFIG

def init_audio():
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
    print(f"[Audio] mixer 初始化: {pygame.mixer.get_init()}")
    return True

# 在 main() 中：
pygame.init()
init_audio()  # <-- 添加这里

# ... 创建系统 ...
audio_sys = AudioSystem(gs)
world.add_system(audio_sys)  # <-- 添加到系统列表（渲染之后）
```

---

### 步骤 2：在游戏逻辑中触发音效

在 `combat_system.py`、`input_system.py`、`main.py` 等文件中，
导入 `AudioEventTriggers` 并调用对应方法：

```python
from audio_integration import AudioEventTriggers

# 示例 1：卡牌打出
def resolve_card(self, world, card_entity, target_entity=None):
    # ... 原有逻辑 ...
    AudioEventTriggers.on_card_play(world, card_entity)

# 示例 2：敌人攻击玩家
def enemy_attack_player(self, world, enemy_entity):
    # ... 伤害计算 ...
    AudioEventTriggers.on_combat_damage(world, player_entity, damage)
    AudioEventTriggers.on_enemy_turn_start(world)

# 示例 3：随从召唤
def _resolve_minion_card(self, world, card_entity, card):
    minion_entity = create_minion_from_card(world, card_entity)
    AudioEventTriggers.on_minion_summon(world, minion_entity)
```

---

### 步骤 3：创建占位音效文件

运行以下代码生成测试音效（静音正弦波）：

```python
from audio_integration import create_placeholder_audio_files
create_placeholder_audio_files()
```

然后在 `assets/audio/sfx/` 目录中替换为您自己录制的音效文件。

---

### 步骤 4：测试

```bash
python -c "from audio_integration import test_audio_system; test_audio_system()"
```

---

## 🎵 自适应音乐系统

### 参数驱动

音乐过渡由以下参数驱动（在 `audio_constants.py` 中定义）：

| 参数 | 范围 | 说明 |
|---|---|---|
| `CombatIntensity` | 0.0 - 1.0 | 0.0=探索, 0.3=警戒, 0.6=战斗, 1.0=首领战 |
| `PlayerHealth` | 0.0 - 1.0 | <0.2 时激活低通滤波器（闷音效果） |
| `GamePhase` | 枚举 | MENU / BATTLE / EVENT / MERCHANT / CAMPFIRE / GAME_OVER |

### 音乐过渡规则（音频工程师规范）

- **必须节拍同步**：所有音乐过渡都对齐到最近的节拍边界
- **淡入淡出时长**：默认 2.0 秒
- **优先 stem-based 横向重排序**（内存效率），而非纵向分层

---

## 📊 音频预算（遵循音频工程师规范）

### 语音数限制

| 平台 | 真实语音 | 虚拟语音 |
|---|---|---|
| PC | 32 | 64 |
| Console | 24 | 48 |
| Mobile | 16 | 32 |

### 内存预算

| 类别 | 预算 | 格式 |
|---|---|---|
| SFX Pool | 16 MB | ADPCM（解压到内存） |
| Music | 8 MB | Vorbis（流式播放） |
| Ambience | 8 MB | Vorbis（流式播放） |

### CPU 预算

- FMOD DSP 最大 **1.5ms/帧**（在最低目标硬件上测量）

---

## 🔊 3D 空间音频

### 启用条件

所有**世界空间音效**必须使用 3D 空间化，永不播放 2D。

### 配置参数

```python
SPATIAL_AUDIO = {
    "min_distance": 1.0,    # 米，全音量距离
    "max_distance": 50.0,  # 米，静音距离
    "rolloff": "LOGARITHMIC",  # 真实衰减
    "occlusion_enabled": True,  # 遮挡检测
    "occlusion_max_cutoff": 800,  # Hz，最大遮挡时的低通截止频率
    "max_raycasts_per_frame": 4,  # 分散到多帧
}
```

### 遮挡检测

- 方法：从监听器（玩家）到音源发射射线
- 参数：`Occlusion`（0.0=无遮挡，1.0=完全遮挡）
- 效果：低通滤波器截止频率降至 800Hz

---

## 📝 音效定义示例

在 `sfx_bank.py` 中定义音效：

```python
self.register(SFXDef(
    name="combat_attack",
    file_paths=self._files("combat", "attack", ["attack_01.wav", "attack_02.wav", "attack_03.wav"]),
    volume=0.8,
    pitch_range=(0.95, 1.05),     # 随机化音高（避免重复感）
    priority=2,                      # 优先级（0=最高）
    max_voices=8,                   # 最大同时播放数
    steal_mode="STEAL_FARTHEST",    # 抢占策略
    is_3d=True,                    # 启用 3D 空间音频
    min_distance=2.0,
    max_distance=30.0,
))
```

**关键点**：
- 所有音效必须是**随机化容器**（pitch + volume variation）
- 每个音效必须配置 `max_voices` 和 `steal_mode`
- 默认值不允许发货

---

## 🛠️ 调试

### 启用调试日志

```python
# 在创建 AudioSystem 后
audio_sys.debug_audio = True
```

### 验证音频文件

```python
missing = audio_sys.validate_audio_files()
if missing:
    print("缺失的音频文件：")
    for name, files in missing.items():
        print(f"  {name}: {files}")
```

---

## 🚧 常见问题

### Q1：音频系统初始化失败？

**A**：检查 `pygame.mixer` 是否正确初始化。确保 `pygame.init()` 在 `AudioSystem()` 之前调用。

---

### Q2：音效没有播放？

**A**：
1. 检查 `AudioEventComponent` 是否已附加到正确的实体
2. 检查音效文件是否存在（运行 `validate_audio_files()`）
3. 检查语音预算是否已满（降低 `max_voices` 或调整优先级）

---

### Q3：音乐没有过渡？

**A**：
1. 确保在 `GameState` 中正确设置了 `phase`
2. 检查 `MusicController.set_game_phase()` 是否被调用
3. 启用 `debug_audio = True` 查看参数变化

---

### Q4：如何替换为 FMOD/Wwise？

**A**：`AudioSystem` 是中间件无关的。只需：
1. 将 `pygame.mixer` 调用替换为 FMOD/Wwise API
2. 在 `AudioEventComponent` 中使用 FMOD 事件路径（如 `event:/SFX/Card/Play_Attack`）
3. 其余游戏逻辑**无需修改**

---

## 📖 进一步阅读

- **音频工程师规范**：参见 `audio/audio_constants.py` 文件头部的注释
- **ECS 架构说明**：参见 `ecs.py`
- **游戏阶段说明**：参见 `game_state.py`

---

## ✅ 验收标准（音频工程师规范）

- [ ] 音频导致的帧卡顿 = 0（在目标硬件上测量）
- [ ] 所有事件配置了 `max_voices` 和 `steal_mode`（无默认值发货）
- [ ] 音乐过渡在测试中**全部**无缝切换
- [ ] 音频内存在所有关卡、最大内容密度下**不超标**
- [ ] 遮挡和混响在所有世界空间 Diegetic 音效上**激活**

---

**祝您的游戏音频大获成功！** 🎉
