"""程序化生成 8-bit 风格战斗音效（纯标准库，自有版权）

用法：python scripts/gen_sfx.py
产物：assets/sfx/{encounter,victory,defeat,levelup}.wav
"""
import math
import os
import struct
import wave

RATE = 22050


def _write_wav(path, samples):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = b"".join(
            struct.pack("<h", max(-32767, min(32767, int(s * 32767))))
            for s in samples
        )
        w.writeframes(frames)
    print(f"生成 {path} ({len(samples) / RATE:.2f}s)")


def _tone(freqs, dur, vol=0.5, decay=True):
    """一串频率依次发声（方波，8-bit 味道）"""
    seg = []
    per = dur / len(freqs)
    n_per = int(RATE * per)
    for f in freqs:
        for i in range(n_per):
            t = i / RATE
            v = 1.0 if math.sin(2 * math.pi * f * t) >= 0 else -1.0
            if decay:
                v *= 1.0 - i / n_per
            seg.append(v * vol)
    return seg


def _noise(dur, vol=0.4):
    """白噪声突发（打击感）"""
    import random
    rnd = random.Random(42)
    n = int(RATE * dur)
    out = []
    for i in range(n):
        env = 1.0 - i / n
        out.append((rnd.random() * 2 - 1) * vol * env)
    return out


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sfx_dir = os.path.join(root, "assets", "sfx")

    # 遇敌：急促上行双音（警报感）
    _write_wav(os.path.join(sfx_dir, "encounter.wav"),
               _tone([880, 1174], 0.28, vol=0.55))
    # 命中：短噪声
    _write_wav(os.path.join(sfx_dir, "hit.wav"), _noise(0.09, vol=0.5))
    # 胜利：上行三连音
    _write_wav(os.path.join(sfx_dir, "victory.wav"),
               _tone([523, 659, 784, 1046], 0.55, vol=0.5))
    # 战败：下行三音（低落）
    _write_wav(os.path.join(sfx_dir, "defeat.wav"),
               _tone([392, 311, 233], 0.7, vol=0.5))
    # 升级：清脆双音
    _write_wav(os.path.join(sfx_dir, "levelup.wav"),
               _tone([1046, 1318], 0.3, vol=0.45))

    print("全部音效生成完毕（8-bit 风格，程序化生成，自有版权）")


if __name__ == "__main__":
    main()
