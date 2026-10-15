# -*- coding: utf-8 -*-
"""Phase 2-C 第二批 天气单测（纯逻辑，零 GL）。

覆盖：确定性（时刻的纯函数）/ 晴雨雪的判据边界 / 强度平滑（不突变）/
雨雪由昼夜分流（夜雪日雨）/ 天光乘子 / 配置口固定天气 / 天气**不进存档**。

跑：`python -m tests.test_weather`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import weather as W
from mcclone3d.kernel import make_offline

test, main = make_suite('ALL_WEATHER_TESTS_PASSED', '天气')


def _wc(seed=2026, slot=W.WEATHER_SLOT):
    return W.WeatherCycle(seed, slot)


# ==================================================================== 确定性
@test('确定性：同一时刻两次查询完全一致（不读系统时钟、不用 random）')
def t_deterministic():
    wc = _wc()
    for t in (0.0, 12.5, 95.0, 361.25, 1234.0):
        assert wc.intensity_at(t) == wc.intensity_at(t)
        assert wc.kind_at(t, day_factor=1.0) == wc.kind_at(t, day_factor=1.0)


@test('确定性：换种子 ⇒ 天气不同（噪声真的用上了）')
def t_seed_matters():
    # ⚠ 取样必须落在**段中**：段首（local≈0）强度恒为 0 ⇒ kind 永远是 clear，
    #   那样比出来的永远是"两个种子都是 clear"（实测踩过）。
    def series(seed):
        wc = _wc(seed)
        return [wc.kind_at(i * W.WEATHER_SLOT + W.WEATHER_SLOT * 0.5,
                           day_factor=1.0)
                for i in range(1, 40)]

    a, b = series(2026), series(777)
    assert a != b, '换种子天气完全一样（种子没起作用）'
    assert set(a) | set(b) & {W.RAIN, W.CLEAR}, (set(a), set(b))


@test('状态与推进无关：advance() 不改变任何查询结果（它是时刻的纯函数）')
def t_stateless():
    wc = _wc()
    before = wc.intensity_at(200.0)
    for _ in range(100):
        wc.advance(0.05)
    assert wc.intensity_at(200.0) == before, 'advance 改了状态'


# ==================================================================== 判据
@test('强度落在 0..1，且晴天的比例大致对得上（约 45% 槽是晴）')
def t_intensity_range():
    wc = _wc()
    vals = [wc.intensity_at(i * 1.0) for i in range(3600)]      # 一小时
    assert all(0.0 <= v <= 1.0 for v in vals), \
        f'强度越界：{min(vals)}..{max(vals)}'
    clear = sum(1 for v in vals if v < 0.15)
    assert 0.2 < clear / len(vals) < 0.85, f'晴天比例 {clear / len(vals):.2f} 不合理'


@test('强度在一段内平滑起落（不突变 ⇒ 天光不会跳变）')
def t_smooth_ramp():
    wc = _wc(31337, slot=90.0)
    # 找一段非晴的
    slot = next(i for i in range(40)
                if wc.intensity_at(i * 90.0 + 45.0) > 0.2)
    base = slot * 90.0
    seq = [wc.intensity_at(base + t * 0.5) for t in range(180)]   # 段内 90 秒
    jump = max(abs(b - a) for a, b in zip(seq, seq[1:]))
    assert jump < 0.05, f'段内强度突变 {jump:.3f}（天光会跳）'


@test('雨雪分流：白天雨、夜里雪（用 day_factor 判，不另设温度系统）')
def t_rain_vs_snow():
    wc = _wc()
    t = next((i * 0.5 for i in range(4000)
              if wc.intensity_at(i * 0.5) > 0.5), None)
    assert t is not None, '扫了 2000 秒没遇到一场雨/雪'
    assert wc.kind_at(t, day_factor=1.0) == W.RAIN, '白天该下雨'
    assert wc.kind_at(t, day_factor=0.2) == W.SNOW, '夜里该下雪'
    assert wc.kind_at(t, day_factor=0.44) == W.SNOW, '昏暗时该下雪'
    assert wc.kind_at(t, day_factor=0.46) == W.RAIN, '明亮时该下雨'


@test('天光乘子：雨 < 雪 < 晴，且都在 0.7~1.0（不压到看不清路）')
def t_light_scale():
    assert W.weather_light_scale(W.CLEAR, 1.0) == 1.0
    rain = W.weather_light_scale(W.RAIN, 1.0)
    snow = W.weather_light_scale(W.SNOW, 1.0)
    assert rain < snow < 1.0, f'乘子关系错：雨{rain} 雪{snow}'
    assert rain > 0.7, f'雨天压得太狠（{rain}）：会看不清路'
    assert W.weather_light_scale(W.RAIN, 0.0) == 1.0, '强度 0 时不该有影响'
    # 强度线性
    assert W.weather_light_scale(W.RAIN, 0.5) > rain


@test('快照字段齐（HUD 直接吃它）')
def t_state_dict():
    st = _wc().state_at(100.0, day_factor=1.0)
    for k in ('kind', 'name', 'intensity', 'light_scale'):
        assert k in st, f'快照缺字段 {k}'
    assert st['name'] in W.WEATHER_NAMES.values(), st
    assert st['kind'] in (W.CLEAR, W.RAIN, W.SNOW), st


# ==================================================================== 内核
@test('内核：weather_state 与 day_factor 同源（雨天真的把天光压暗）')
def t_kernel_dim():
    k = make_offline({'seed': 2026, 'size': 64, 'height': 64, 'light': False})
    k2 = make_offline({'seed': 2026, 'size': 64, 'height': 64, 'light': False,
                       'weather': 'rain'})
    k3 = make_offline({'seed': 2026, 'size': 64, 'height': 64, 'light': False,
                       'weather': 'snow'})
    base = k.cycle.sky()['day_factor']
    assert k.weather_state()['kind'] == W.CLEAR, k.weather_state()
    assert k2.weather_state()['kind'] == W.RAIN
    assert k3.weather_state()['kind'] == W.SNOW
    assert k2.day_factor() < k3.day_factor() < k.day_factor(), \
        f'天光没按雨<雪<晴排序：{k2.day_factor():.3f}/{k3.day_factor():.3f}/{k.day_factor():.3f}'
    assert abs(k2.day_factor() - base * 0.72) < 1e-6, \
        f'雨天乘子不对：{k2.day_factor()} vs {base}×0.72'


@test('内核：天气配置口可固定天气（判据/截图要可复现）')
def t_kernel_fixed_weather():
    for kind in (W.CLEAR, W.RAIN, W.SNOW):
        k = make_offline({'seed': 2026, 'size': 32, 'height': 32, 'light': False,
                          'weather': kind})
        assert k.weather_state()['kind'] == kind, k.weather_state()


@test('内核：同种子同时刻 ⇒ 天气与天光一致（回放对得上）')
def t_kernel_replay():
    k1 = make_offline({'seed': 2026, 'size': 32, 'height': 32, 'light': False,
                       'time': 123.0})
    k2 = make_offline({'seed': 2026, 'size': 32, 'height': 32, 'light': False,
                       'time': 123.0})
    assert k1.weather_state() == k2.weather_state(), '同种子同时刻天气不同'
    assert abs(k1.day_factor() - k2.day_factor()) < 1e-12


@test('纪律：天气不进存档（它是时刻+种子的纯函数，读档重算即可）')
def t_not_in_save():
    k = make_offline({'seed': 2026, 'size': 32, 'height': 32, 'light': False,
                      'time': 200.0})
    data = k.dump()
    blob = repr(data)
    assert 'weather' not in blob.lower() or 'weather' not in data.get('world', {}), \
        '存档里不该有天气字段'
    # 读档后按那一刻重算 ⇒ 天气与存档前一致
    k2 = make_offline({'seed': 2026, 'size': 32, 'height': 32, 'light': False,
                       'time': 200.0})
    k2.load(data)
    assert k2.weather_state()['kind'] == k.weather_state()['kind'], \
        f'读档后天气变了：{k2.weather_state()} vs {k.weather_state()}'


if __name__ == '__main__':
    sys.exit(main())
