"""
生成恶搞版风扇音效
灵感来自 project1/generate_joke_sfx.py，使用 Python wave 模块程序化合成
每个音效都是对真实风扇声音的恶搞替代
"""
import os
import struct
import wave
import math
import random

# 音效输出目录：默认落在本脚本同级的 fan_sounds/（原为本机一条已失效的绝对路径，见硬编码门禁清单）
SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fan_sounds")
os.makedirs(SOUNDS_DIR, exist_ok=True)

SAMPLE_RATE = 44100


def make_wav(filepath, samples):
    with wave.open(filepath, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        raw = b''
        for s in samples:
            v = max(-1.0, min(1.0, s))
            raw += struct.pack('<h', int(v * 32767))
        wf.writeframes(raw)


def gen_tone(freq, duration, volume=0.5, fade=True):
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = 1.0
        if fade:
            if i < n * 0.05:
                env = i / (n * 0.05)
            elif i > n * 0.85:
                env = (n - i) / (n * 0.15)
        samples.append(volume * env * math.sin(2 * math.pi * freq * t))
    return samples


def gen_noise(duration, volume=0.2, fade=True):
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        env = 1.0
        if fade:
            if i < n * 0.05:
                env = i / (n * 0.05)
            elif i > n * 0.8:
                env = (n - i) / (n * 0.2)
        samples.append(volume * env * (random.random() * 2 - 1))
    return samples


# ═══════════════════════════════════════════════════════════════
#  恶搞音效 —— 替代真实风扇声的搞笑版本
# ═══════════════════════════════════════════════════════════════

print("生成恶搞风扇音效...")

# 1. idle - 猫打呼噜（25Hz 振幅调制 + 呼噜感）
n = int(SAMPLE_RATE * 2.0)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    # 基础低频嗡嗡
    base = math.sin(2 * math.pi * 25 * t)
    # 呼噜的振幅调制 (约每秒3次)
    purr = 0.5 + 0.5 * math.sin(2 * math.pi * 3.5 * t)
    # 加入一些高频谐波模拟喉音
    harmonic = 0.3 * math.sin(2 * math.pi * 80 * t) + 0.1 * math.sin(2 * math.pi * 150 * t)
    env = 1.0
    if i > n * 0.9:
        env = (n - i) / (n * 0.1)
    s.append(0.25 * env * (base * purr + harmonic * purr))
make_wav(os.path.join(SOUNDS_DIR, "idle_purr.wav"), s)
print("  ✓ idle_purr.wav - 猫打呼噜")

# 2. low - 蜜蜂嗡嗡（200Hz + 30Hz 调制）
n = int(SAMPLE_RATE * 2.0)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    buzz = math.sin(2 * math.pi * 200 * t) + 0.4 * math.sin(2 * math.pi * 400 * t)
    mod = 0.6 + 0.4 * math.sin(2 * math.pi * 30 * t)
    env = 1.0
    if i > n * 0.9:
        env = (n - i) / (n * 0.1)
    s.append(0.2 * env * buzz * mod)
make_wav(os.path.join(SOUNDS_DIR, "low_buzz.wav"), s)
print("  ✓ low_buzz.wav - 蜜蜂嗡嗡")

# 3. medium - 警笛（200-800Hz 来回摆动）
n = int(SAMPLE_RATE * 2.0)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    freq = 500 + 300 * math.sin(2 * math.pi * 0.8 * t)
    env = 1.0
    if i > n * 0.9:
        env = (n - i) / (n * 0.1)
    s.append(0.2 * env * math.sin(2 * math.pi * freq * t))
make_wav(os.path.join(SOUNDS_DIR, "medium_siren.wav"), s)
print("  ✓ medium_siren.wav - 警笛")

# 4. high - 喷气放屁（白噪声 + 低频震动 + 指数衰减脉冲）
n = int(SAMPLE_RATE * 2.0)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    # 白噪声基底
    noise = random.random() * 2 - 1
    # 低频震动
    rumble = math.sin(2 * math.pi * 60 * t)
    # 周期性喷气脉冲
    pulse = math.exp(-((t % 0.5) * 8)) * 0.5
    env = 1.0
    if i > n * 0.9:
        env = (n - i) / (n * 0.1)
    s.append(0.15 * env * (0.4 * noise + 0.4 * rumble * pulse + 0.2 * pulse * math.sin(2 * math.pi * 120 * t)))
make_wav(os.path.join(SOUNDS_DIR, "high_jetfart.wav"), s)
print("  ✓ high_jetfart.wav - 喷气放屁")

# 5. startup - 上升哔声（200 -> 800Hz）
n = int(SAMPLE_RATE * 1.0)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    frac = i / n
    freq = 200 + 600 * frac
    env = min(1.0, i / (n * 0.05)) * max(0, 1.0 - max(0, (i - n * 0.85)) / (n * 0.15))
    s.append(0.3 * env * math.sin(2 * math.pi * freq * t))
make_wav(os.path.join(SOUNDS_DIR, "startup_beep.wav"), s)
print("  ✓ startup_beep.wav - 上升哔声")

# 6. shutdown - 下滑号（800 -> 100Hz 滑音 + 颤抖）
n = int(SAMPLE_RATE * 1.5)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    frac = i / n
    freq = 800 * math.exp(-3 * frac) + 100
    tremolo = 1.0 + 0.1 * math.sin(2 * math.pi * 12 * t)
    env = max(0, 1.0 - frac * 0.8)
    s.append(0.25 * env * tremolo * math.sin(2 * math.pi * freq * t))
make_wav(os.path.join(SOUNDS_DIR, "shutdown_trombone.wav"), s)
print("  ✓ shutdown_trombone.wav - 下滑号")

# 7. click - 短促噪声脉冲（0.1秒）
n = int(SAMPLE_RATE * 0.1)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    env = math.exp(-t * 40)
    s.append(0.35 * env * (random.random() * 2 - 1))
make_wav(os.path.join(SOUNDS_DIR, "click.wav"), s)
print("  ✓ click.wav - 短促咔哒")

# 8. wobble - 金属叮当（1200+2400Hz 衰减）
n = int(SAMPLE_RATE * 0.8)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    env = math.exp(-t * 4)
    ding = math.sin(2 * math.pi * 1200 * t) + 0.5 * math.sin(2 * math.pi * 2400 * t)
    # 周期性叮当
    repeat = max(0, 1.0 - ((t + 0.3) % 0.4) * 10)
    s.append(0.2 * (env + repeat * 0.5) * ding)
make_wav(os.path.join(SOUNDS_DIR, "wobble_ding.wav"), s)
print("  ✓ wobble_ding.wav - 金属叮当")

# 9. scrape - 黑板刮擦（3000Hz + FM 调制）
n = int(SAMPLE_RATE * 0.6)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    freq = 3000 + 1500 * math.sin(2 * math.pi * 15 * t)
    env = math.exp(-t * 3)
    s.append(0.2 * env * math.sin(2 * math.pi * freq * t))
make_wav(os.path.join(SOUNDS_DIR, "scrape_squeak.wav"), s)
print("  ✓ scrape_squeak.wav - 黑板刮擦")

# 10. bearing_fail - 低沉爆炸（60Hz + 噪声）
n = int(SAMPLE_RATE * 1.0)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    env = math.exp(-t * 2)
    boom = math.sin(2 * math.pi * 60 * t) + 0.3 * math.sin(2 * math.pi * 30 * t)
    noise = random.random() * 2 - 1
    s.append(0.3 * env * (0.6 * boom + 0.4 * noise))
make_wav(os.path.join(SOUNDS_DIR, "bearing_boom.wav"), s)
print("  ✓ bearing_boom.wav - 低沉爆炸")

# 11. wind_howl - 风声嚎叫（双音拍频 180+185Hz）
n = int(SAMPLE_RATE * 2.0)
s = []
for i in range(n):
    t = i / SAMPLE_RATE
    beat = math.sin(2 * math.pi * 180 * t) + 0.8 * math.sin(2 * math.pi * 185 * t)
    # 加入一些噪声
    noise = 0.2 * (random.random() * 2 - 1)
    env = 1.0
    if i > n * 0.9:
        env = (n - i) / (n * 0.1)
    s.append(0.12 * env * (beat + noise))
make_wav(os.path.join(SOUNDS_DIR, "wind_howl.wav"), s)
print("  ✓ wind_howl.wav - 风声嚎叫")

print(f"\n完成！共生成 11 个恶搞风扇音效 → {SOUNDS_DIR}")
