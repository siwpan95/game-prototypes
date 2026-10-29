"""Generate synthesized sound effects for facial expressions."""
import os
import struct
import wave
import math
import random

# 音效输出目录：默认落在本脚本同级的 sounds/（原为本机一条已失效的绝对路径，见硬编码门禁清单）
SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
os.makedirs(SOUNDS_DIR, exist_ok=True)

def make_wav(filepath, samples, sample_rate=44100):
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        raw = b""
        for s in samples:
            v = max(-1.0, min(1.0, s))
            raw += struct.pack("<h", int(v * 32767))
        wf.writeframes(raw)

def gen_tone(freq, duration, sample_rate=44100, volume=0.5, fade=True):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        env = 1.0
        if fade:
            if i < n * 0.05:
                env = i / (n * 0.05)
            elif i > n * 0.8:
                env = (n - i) / (n * 0.2)
        samples.append(volume * env * math.sin(2 * math.pi * freq * t))
    return samples

def gen_chord(freqs, duration, sample_rate=44100, volume=0.3):
    n = int(sample_rate * duration)
    samples = [0.0] * n
    for freq in freqs:
        tone = gen_tone(freq, duration, sample_rate, volume / len(freqs), fade=True)
        for i in range(n):
            samples[i] += tone[i]
    return samples

def gen_noise(duration, sample_rate=44100, volume=0.2, fade=True):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        env = 1.0
        if fade:
            if i < n * 0.05:
                env = i / (n * 0.05)
            elif i > n * 0.7:
                env = (n - i) / (n * 0.3)
        samples.append(volume * env * (random.random() * 2 - 1))
    return samples

def gen_sweep(f1, f2, duration, sample_rate=44100, volume=0.4):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        frac = i / n
        freq = f1 + (f2 - f1) * frac
        env = 1.0
        if i < n * 0.05:
            env = i / (n * 0.05)
        elif i > n * 0.8:
            env = (n - i) / (n * 0.2)
        samples.append(volume * env * math.sin(2 * math.pi * freq * t))
    return samples

def concat(*sample_lists):
    result = []
    for s in sample_lists:
        result.extend(s)
    return result

SR = 44100

print("Generating sound effects...")

# 1. default
make_wav(os.path.join(SOUNDS_DIR, "default.wav"), gen_tone(440, 0.15, volume=0.3))
print("  + default.wav")

# 2. happy
make_wav(os.path.join(SOUNDS_DIR, "happy.wav"), concat(
    gen_chord([523, 659, 784], 0.3, volume=0.4),
    gen_tone(1047, 0.15, volume=0.3),
))
print("  + happy.wav")

# 3. sad
make_wav(os.path.join(SOUNDS_DIR, "sad.wav"), concat(
    gen_chord([440, 523, 659], 0.5, volume=0.35),
    gen_tone(392, 0.4, volume=0.3),
))
print("  + sad.wav")

# 4. surprised
make_wav(os.path.join(SOUNDS_DIR, "surprised.wav"), concat(
    gen_sweep(300, 1200, 0.15, volume=0.4),
    gen_noise(0.05, volume=0.3),
))
print("  + surprised.wav")

# 5. angry
make_wav(os.path.join(SOUNDS_DIR, "angry.wav"), concat(
    gen_tone(80, 0.3, volume=0.5),
    gen_noise(0.2, volume=0.25),
))
print("  + angry.wav")

# 6. laugh
laugh_notes = []
for _ in range(3):
    laugh_notes.extend(gen_tone(700, 0.08, volume=0.4))
    laugh_notes.extend(gen_tone(900, 0.08, volume=0.4))
make_wav(os.path.join(SOUNDS_DIR, "laugh.wav"), laugh_notes)
print("  + laugh.wav")

# 7. wink
make_wav(os.path.join(SOUNDS_DIR, "wink.wav"), gen_tone(1200, 0.08, volume=0.3))
print("  + wink.wav")

# 8. love
pulse = gen_tone(200, 0.1, volume=0.5)
gap = [0.0] * int(SR * 0.05)
make_wav(os.path.join(SOUNDS_DIR, "love.wav"), concat(
    pulse, gap, pulse, [0.0] * int(SR * 0.15), gen_tone(523, 0.2, volume=0.3)
))
print("  + love.wav")

# 9. cool
make_wav(os.path.join(SOUNDS_DIR, "cool.wav"), concat(
    gen_noise(0.04, volume=0.4),
    gen_tone(150, 0.2, volume=0.35),
))
print("  + cool.wav")

# 10. sleepy
make_wav(os.path.join(SOUNDS_DIR, "sleepy.wav"), concat(
    gen_tone(500, 0.3, volume=0.25),
    gen_tone(450, 0.3, volume=0.2),
    gen_tone(400, 0.4, volume=0.15),
))
print("  + sleepy.wav")

# 11. confused - wobbly vibrato
n = int(SR * 0.5)
s = []
for i in range(n):
    t = i / SR
    freq = 400 + 200 * math.sin(2 * math.pi * 5 * t)
    env = 1.0
    if i > n * 0.7:
        env = (n - i) / (n * 0.3)
    s.append(0.3 * env * math.sin(2 * math.pi * freq * t))
make_wav(os.path.join(SOUNDS_DIR, "confused.wav"), s)
print("  + confused.wav")

# 12. shy
make_wav(os.path.join(SOUNDS_DIR, "shy.wav"), concat(
    gen_tone(330, 0.15, volume=0.15),
    gen_tone(392, 0.15, volume=0.15),
    gen_tone(523, 0.2, volume=0.12),
))
print("  + shy.wav")

# 13. excited
notes = [440, 554, 659, 880, 1047]
s = []
for freq in notes:
    s.extend(gen_tone(freq, 0.08, volume=0.4))
s.extend(gen_tone(1319, 0.2, volume=0.35))
make_wav(os.path.join(SOUNDS_DIR, "excited.wav"), s)
print("  + excited.wav")

# 14. thinking
n = int(SR * 0.6)
s = []
for i in range(n):
    t = i / SR
    freq = 300 + 50 * math.sin(2 * math.pi * 2 * t)
    env = 1.0
    if i > n * 0.7:
        env = (n - i) / (n * 0.3)
    s.append(0.25 * env * math.sin(2 * math.pi * freq * t))
make_wav(os.path.join(SOUNDS_DIR, "thinking.wav"), s)
print("  + thinking.wav")

# 15. scared
make_wav(os.path.join(SOUNDS_DIR, "scared.wav"), concat(
    gen_sweep(800, 200, 0.15, volume=0.5),
    gen_noise(0.1, volume=0.3),
))
print("  + scared.wav")

# 16. silly - boing
n = int(SR * 0.4)
s = []
for i in range(n):
    t = i / SR
    freq = 300 + 600 * math.exp(-t * 8) * abs(math.sin(2 * math.pi * 8 * t))
    env = math.exp(-t * 3)
    s.append(0.35 * env * math.sin(2 * math.pi * freq * t))
make_wav(os.path.join(SOUNDS_DIR, "silly.wav"), s)
print("  + silly.wav")

# 17. proud - fanfare
make_wav(os.path.join(SOUNDS_DIR, "proud.wav"), concat(
    gen_chord([523, 659, 784], 0.2, volume=0.4),
    gen_chord([659, 784, 988], 0.2, volume=0.4),
    gen_chord([784, 988, 1175], 0.4, volume=0.4),
))
print("  + proud.wav")

# 18. bored
make_wav(os.path.join(SOUNDS_DIR, "bored.wav"), concat(
    gen_noise(0.05, volume=0.1),
    gen_sweep(500, 250, 0.5, volume=0.2),
))
print("  + bored.wav")

# 19. embarrassed
make_wav(os.path.join(SOUNDS_DIR, "embarrassed.wav"), concat(
    gen_tone(400, 0.06, volume=0.3),
    gen_tone(350, 0.06, volume=0.25),
    gen_tone(280, 0.1, volume=0.2),
    gen_noise(0.05, volume=0.15),
))
print("  + embarrassed.wav")

# 20. determined
make_wav(os.path.join(SOUNDS_DIR, "determined.wav"), concat(
    gen_tone(130, 0.15, volume=0.5),
    gen_chord([262, 330, 392], 0.3, volume=0.4),
))
print("  + determined.wav")

# 21. blush
make_wav(os.path.join(SOUNDS_DIR, "blush.wav"), concat(
    gen_tone(440, 0.2, volume=0.15),
    gen_tone(554, 0.2, volume=0.15),
    gen_tone(659, 0.3, volume=0.12),
))
print("  + blush.wav")

# 22. smirk
make_wav(os.path.join(SOUNDS_DIR, "smirk.wav"), concat(
    gen_tone(600, 0.06, volume=0.3),
    gen_sweep(600, 800, 0.1, volume=0.25),
))
print("  + smirk.wav")

# 23. worried - tremolo
n = int(SR * 0.5)
s = []
for i in range(n):
    t = i / SR
    trem = 0.5 + 0.5 * math.sin(2 * math.pi * 15 * t)
    env = 1.0
    if i > n * 0.7:
        env = (n - i) / (n * 0.3)
    s.append(0.25 * env * trem * math.sin(2 * math.pi * 350 * t))
make_wav(os.path.join(SOUNDS_DIR, "worried.wav"), s)
print("  + worried.wav")

# 24. grateful
make_wav(os.path.join(SOUNDS_DIR, "grateful.wav"), concat(
    gen_chord([440, 554], 0.2, volume=0.3),
    gen_chord([523, 659, 784], 0.4, volume=0.35),
))
print("  + grateful.wav")

# 25. mischievous
make_wav(os.path.join(SOUNDS_DIR, "mischievous.wav"), concat(
    gen_tone(400, 0.08, volume=0.25),
    [0.0] * int(SR * 0.04),
    gen_tone(500, 0.08, volume=0.25),
    [0.0] * int(SR * 0.04),
    gen_tone(650, 0.12, volume=0.3),
))
print("  + mischievous.wav")

# 26. disappointed
make_wav(os.path.join(SOUNDS_DIR, "disappointed.wav"), gen_sweep(500, 200, 0.6, volume=0.2))
print("  + disappointed.wav")

# 27. relieved
n = int(SR * 0.5)
s = []
for i in range(n):
    t = i / SR
    env = math.exp(-t * 3)
    noise = random.random() * 2 - 1
    s.append(0.15 * env * (0.5 * noise + 0.5 * math.sin(2 * math.pi * 300 * t)))
make_wav(os.path.join(SOUNDS_DIR, "relieved.wav"), s)
print("  + relieved.wav")

# 28. annoyed
make_wav(os.path.join(SOUNDS_DIR, "annoyed.wav"), concat(
    gen_tone(150, 0.1, volume=0.4),
    gen_noise(0.05, volume=0.3),
    gen_tone(200, 0.15, volume=0.35),
))
print("  + annoyed.wav")

# 29. amazed
freqs = [800, 1000, 1200, 1500, 1800]
s = []
for f in freqs:
    s.extend(gen_tone(f, 0.06, volume=0.25))
s.extend(gen_tone(2000, 0.15, volume=0.2))
make_wav(os.path.join(SOUNDS_DIR, "amazed.wav"), s)
print("  + amazed.wav")

# 30. nervous
s = []
for _ in range(4):
    s.extend(gen_tone(180, 0.05, volume=0.4))
    s.extend([0.0] * int(SR * 0.03))
    s.extend(gen_tone(160, 0.05, volume=0.3))
    s.extend([0.0] * int(SR * 0.08))
make_wav(os.path.join(SOUNDS_DIR, "nervous.wav"), s)
print("  + nervous.wav")

print(f"\nDone! 30 sound effects in {SOUNDS_DIR}")
