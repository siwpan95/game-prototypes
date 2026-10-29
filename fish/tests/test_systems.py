"""T03 系统与编排层测试。

最重要的一条是 :func:`test_online_matches_advance_step`：
它逐秒比对"在线跑系统" 与 "离线 advance_step"，任何一处顺序/公式偏差都会被抓住。
这是双端（Python ↔ XJ380 C++）一致性的守门测试。
"""

import math
import os
import tempfile

import pytest

from fishtank.behaviors import AIConfig
from fishtank.components import (
    AIState, Animation, Appearance, FishTag, FoodPellet, Growth, Motion,
    Transform,
)
from fishtank.constants import (
    AI_SEEK_FOOD, BB_HAS_FOOD, BB_TARGET_X, BB_TARGET_Y, UPGRADE_CAPACITY,
    UPGRADE_FEEDER, UPGRADE_FILTER, WD_NOW, WD_STATE, WD_STEP,
)
from fishtank.economy import water_band
from fishtank.engine_bootstrap import BlackboardComponent, BrainComponent
from fishtank.events import (
    COINS_CHANGED, FISH_BORN, FISH_GROWN, WATER_BAND_CHANGED,
)
from fishtank.game import ActionResult, FishTankGame, default_data_dir
from fishtank.offline import advance_step
from fishtank.rng import DetRandom
from fishtank.state import FishState

from conftest import T0

_LOGIC_DT = 1.0 / 20.0

_FAST_DT = 0.25
"""长时程测试用的步长 = `loop.max_frame_time`。

固定步累加器（TickSystem.accum）保证"同样的模拟秒数"无论用多大 dt 推进
都会落到同样的整数步数上，所以换成 0.25 只是少跑 5 倍帧，**不丢时间、不改结果**。
再大就会被 `_clamp_dt` 砍掉，反而真的丢时间——所以上限就卡在 max_frame_time。
"""
"""20 Hz 逻辑步长（与 balance.loop.logic_hz 一致）。"""


# ══════════════════════════════════════════════════════════════
#  夹具
# ══════════════════════════════════════════════════════════════

@pytest.fixture()
def game(tmp_save_dir):
    """一局全新的、写盘到临时目录的游戏（时钟固定在 T0）。"""
    g = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                     save_enabled=True, fx_enabled=True,
                     clock=lambda: T0)
    g.start(when=T0)
    yield g
    g._started = False


def _run(game, seconds, start=T0, dt=_LOGIC_DT):
    """以固定 dt 推进 `seconds` 秒（墙钟同步前进，避免触发休眠补算）。"""
    steps = int(round(seconds / dt))
    for i in range(steps):
        now = start + int((i + 1) * dt)
        game.update(dt, when=now)
    return steps


# ══════════════════════════════════════════════════════════════
#  ★ 在线 == 离线（双端一致性守门）
# ══════════════════════════════════════════════════════════════

def test_online_matches_advance_step(tmp_save_dir, bal, species, decor):
    """在线跑系统 N 秒，必须与 N 次 advance_step 得到**逐字段相同**的状态。

    🔴 这条测试锁死了五阶段顺序（成长→水质→饱食→收益→繁殖）与取整策略。
       任何一处偏差都会让在线/离线/C++ 端结果分叉。
    """
    g = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                     save_enabled=False, fx_enabled=False, clock=lambda: T0)
    g.start(when=T0)

    # 让缸里有点内容：装上过滤与喂食器，塞几条成鱼
    g.state.tank.filter_level = 2
    g.state.tank.feeder_owned = True
    g.state.tank.feeder_on = True
    for i in range(3):
        f = FishState(uid=g.state.alloc_uid(), species="neon_tetra",
                      born_at=T0, age_sec=100000.0, stage="mature",
                      last_bred_at=0, x=0.3 + 0.1 * i, y=0.5)
        g.state.add_fish(f, when=T0)
    g.rebuild_entities()

    # 参照：纯 advance_step 逐秒推进同一份状态
    ref = g.state.deep_copy()
    ref_rng = DetRandom(ref.rng_seed)

    seconds = 120
    _run(g, seconds, start=T0)

    for i in range(seconds):
        advance_step(ref, 1.0, T0 + i + 1, bal, species, decor, ref_rng,
                     efficiency=1.0, offline=False, do_breed=True)
    ref.saved_at_utc = T0 + seconds
    ref.rng_seed = ref_rng.state()

    live = g.state
    assert live.coins_milli == ref.coins_milli
    assert live.tank.water == pytest.approx(ref.tank.water, abs=1e-9)
    assert live.tank.satiety == pytest.approx(ref.tank.satiety, abs=1e-9)
    assert live.breed_timer == pytest.approx(ref.breed_timer, abs=1e-9)
    assert live.saved_at_utc == ref.saved_at_utc
    assert live.rng_seed == ref.rng_seed
    assert len(live.fishes) == len(ref.fishes)
    for a, b in zip(live.fishes_sorted(), ref.fishes_sorted()):
        assert a.uid == b.uid
        assert a.species == b.species
        assert a.age_sec == pytest.approx(b.age_sec, abs=1e-9)
        assert a.stage == b.stage


def test_gameplay_is_dt_independent(tmp_save_dir):
    """★ 同样的模拟秒数，用不同帧长推进必须得到**完全相同**的玩法状态。

    这是固定步累加器的核心保证，也是双端一致的前提之一：
    Python 端 20Hz、XJ380 端 15Hz，两边的玩法数值不能因为帧率不同而分叉。
    """
    def run(dt):
        g = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                         save_enabled=False, fx_enabled=False, clock=lambda: T0)
        g.start(when=T0)
        for i in range(int(round(600 / dt))):
            g.update(dt, when=T0 + int((i + 1) * dt))
        s = g.state
        return (s.coins_milli, round(s.tank.water, 9), round(s.tank.satiety, 9),
                s.saved_at_utc, s.fish_count(), s.rng_seed)

    # 20Hz（Python 逻辑帧）/ 15Hz（XJ380 渲染帧）/ 4Hz（省电帧）
    assert run(1.0 / 20.0) == run(1.0 / 15.0) == run(_FAST_DT)


def test_income_only_on_whole_steps(game):
    """半个固定步内不应入账（避免高帧率把收益切碎后取整放大）。"""
    before = game.state.coins_milli
    game.update(0.04, when=T0)          # 远小于 online_step_sec=1s
    assert game.state.coins_milli == before
    assert game.world.get_data(WD_STEP) == 0.0


def test_fixed_step_accumulator_no_time_loss(game):
    """20Hz 跑满 60 秒，锚点必须正好前进 60 秒（累加器不能丢小数）。"""
    _run(game, 60)
    assert game.state.saved_at_utc == T0 + 60
    assert game.systems["tick"].sim_seconds == pytest.approx(60.0, abs=1e-9)


# ══════════════════════════════════════════════════════════════
#  TickSystem
# ══════════════════════════════════════════════════════════════

def test_tick_clamps_dt(game):
    """超长帧被钳到 max_frame_time，防止一帧跳几十秒。"""
    max_ft = float(game.bal.get("loop.max_frame_time"))
    game.update(99.0, when=T0 + 1)
    assert game.world.get_data("fishtank.dt") == pytest.approx(max_ft)


def test_tick_negative_dt_is_zero(game):
    """负的 dt（系统时钟抖动）被吃成 0，不会倒推。"""
    game.update(-5.0, when=T0)
    assert game.world.get_data("fishtank.dt") == 0.0


def test_tick_anchor_never_passes_now(game):
    """锚点绝不越过"现在"（否则再补算会算出负时长）。"""
    for _ in range(100):
        game.update(_LOGIC_DT, when=T0)
    assert game.state.saved_at_utc <= T0


def test_food_pellet_sinks_and_expires(game):
    """鱼食会下沉，寿命到点自动消失。"""
    game.state.fishes = []       # 清空鱼，免得被吃掉
    game.rebuild_entities()
    game.feed_at(0.5, 0.1)
    assert len(game.food_views()) == 1
    y0 = game.food_views()[0]["y"]
    _run(game, 2)
    views = game.food_views()
    assert views and views[0]["y"] > y0

    life = float(game.bal.get("ai.food_life_sec"))
    _run(game, int(life) + 2, start=T0 + 2)
    assert game.food_views() == []


def test_fish_sees_and_eats_food(game):
    """投喂后鱼会切到 seek_food 状态，游到后吃掉并涨饱食度。"""
    fish = game.state.fishes_sorted()[0]
    fish.x, fish.y = 0.5, 0.5
    game.rebuild_entities()
    game.state.tank.satiety = 0.2

    game.feed_at(0.52, 0.5)
    game.update(_LOGIC_DT, when=T0 + 1)
    ent = game.entity_of(fish.uid)
    bb = ent.get(BlackboardComponent).blackboard
    assert bb.get(BB_HAS_FOOD) is True
    assert ent.get(AIState).state == AI_SEEK_FOOD

    _run(game, 30, start=T0 + 1)
    assert game.systems["feeder"].eaten >= 1
    assert game.state.tank.satiety > 0.2


def test_school_center_computed(game):
    """同鱼种的质心会被算出来并写进黑板。"""
    for i in range(3):
        f = FishState(uid=game.state.alloc_uid(), species="neon_tetra",
                      born_at=T0, x=0.2 + 0.2 * i, y=0.5)
        game.state.add_fish(f, when=T0)
    game.rebuild_entities()
    game.update(_LOGIC_DT, when=T0 + 1)
    centers = game.systems["tick"]._school_centers(game.world)
    assert "neon_tetra" in centers
    cx, cy = centers["neon_tetra"]
    assert 0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0


# ══════════════════════════════════════════════════════════════
#  MovementSystem
# ══════════════════════════════════════════════════════════════

def test_fish_stays_in_bounds(game):
    """跑满 5 分钟，所有鱼始终在活动区内。"""
    cfg = game.cfg
    for _ in range(20 * 300):
        game.update(_LOGIC_DT, when=T0)
        for f in game.state.fishes:
            assert cfg.x_min - 1e-9 <= f.x <= cfg.x_max + 1e-9
            assert cfg.y_min - 1e-9 <= f.y <= cfg.y_max + 1e-9


def test_fish_actually_moves(game):
    """鱼不能是静止的雕塑。"""
    before = [(f.x, f.y) for f in game.state.fishes_sorted()]
    _run(game, 10)
    after = [(f.x, f.y) for f in game.state.fishes_sorted()]
    assert any(abs(a[0] - b[0]) + abs(a[1] - b[1]) > 1e-4
               for a, b in zip(before, after))


def test_movement_writes_back_to_state(game):
    """Transform 与 FishState 的坐标必须一致（存档是唯一真相）。"""
    _run(game, 5)
    for f in game.state.fishes_sorted():
        tr = game.entity_of(f.uid).get(Transform)
        assert tr.x == pytest.approx(f.x)
        assert tr.y == pytest.approx(f.y)
        assert tr.heading == pytest.approx(f.heading)


def test_heading_is_unit_sign(game):
    """朝向永远是 ±1，不会出现 0 或小数。"""
    _run(game, 30)
    for f in game.state.fishes:
        assert f.heading in (1.0, -1.0)


def test_tail_phase_wraps(game):
    """摆尾相位保持在 [0, 2π) 内，不会无限增长导致精度爆炸。"""
    _run(game, 120)
    for f in game.state.fishes_sorted():
        phase = game.entity_of(f.uid).get(Animation).tail_phase
        assert 0.0 <= phase < math.pi * 2.0 + 1e-9


def test_turns_recorded(game):
    """掉头会被记录（供粒子系统用）。"""
    _run(game, 120)
    assert game.systems["movement"].turns >= 1


# ══════════════════════════════════════════════════════════════
#  GrowthSystem
# ══════════════════════════════════════════════════════════════

def test_growth_ages_and_promotes(game):
    """年龄增长并在跨阈值时升阶 + 发事件。"""
    events = []
    game.bus.subscribe(FISH_GROWN, lambda d: events.append(d))
    f = game.state.fishes_sorted()[0]
    sp = game.species.get(f.species)
    cycle = game.bal.growth_cycle_sec(sp.rarity)
    th = game.bal.thresholds()
    # 停在 fry→juvenile 阈值前 2 秒
    f.age_sec = cycle * float(th["fry"]) - 2.0
    f.stage = "fry"

    _run(game, 5)
    assert f.stage == "juvenile"
    assert any(e["uid"] == f.uid and e["to"] == "juvenile" for e in events)


def test_growth_never_regresses(game):
    """准则 L1：鱼只会长大，绝不退化。"""
    order = list(game.bal.get("growth.stage_order"))
    f = game.state.fishes_sorted()[0]
    idx = order.index(f.stage)
    for _ in range(600):
        game.update(_LOGIC_DT, when=T0)
        new_idx = order.index(f.stage)
        assert new_idx >= idx
        idx = new_idx


def test_growth_syncs_scale(game):
    """成长阶段变化会同步到 Transform.scale。"""
    f = game.state.fishes_sorted()[0]
    ent = game.entity_of(f.uid)
    table = game.bal.stage_scale_table()
    game.update(_LOGIC_DT, when=T0 + 1)
    assert ent.get(Transform).scale == pytest.approx(float(table[f.stage]))
    assert ent.get(Growth).stage == f.stage


# ══════════════════════════════════════════════════════════════
#  WaterSystem
# ══════════════════════════════════════════════════════════════

def test_water_decays_and_has_floor(game):
    """水质会下降，但永不低于 water.min（准则 L4）。"""
    lo = float(game.bal.get("water.min"))
    game.state.tank.water = lo + 0.5
    _run(game, 600)
    assert game.state.tank.water >= lo - 1e-9


def test_water_band_event_only_on_cross(game):
    """E11：只有跨档才发事件，不是每帧都发。"""
    events = []
    game.bus.subscribe(WATER_BAND_CHANGED, lambda d: events.append(d))
    bands = game.bal.get("water.bands")
    # 把水质放在某个档位边界上方一点点，让它很快跨下去
    game.state.tank.water = float(bands[-2]) + 0.05
    game.systems["water"].resync(game.state, game.bal)
    start_band = water_band(game.state.tank.water, game.bal)

    _run(game, 600)
    end_band = water_band(game.state.tank.water, game.bal)
    crossed = abs(end_band - start_band)
    assert len(events) == crossed
    assert len(events) < 600 * 20        # 绝不是每帧一次


def test_water_filter_offsets_decay(game):
    """高等级过滤器能把水质拉回上限。"""
    game.state.tank.water = 70.0
    game.state.tank.filter_level = len(game.bal.get("water.filter_gain")) - 1
    _run(game, 1800)
    assert game.state.tank.water > 70.0
    assert game.state.tank.water <= float(game.bal.get("water.max")) + 1e-9


# ══════════════════════════════════════════════════════════════
#  AutoFeederSystem
# ══════════════════════════════════════════════════════════════

def test_satiety_decays_with_floor(game):
    """饱食度会掉，但产出系数有下限（准则 L4：鱼不会饿死）。"""
    game.state.tank.satiety = 0.05
    game.state.tank.feeder_owned = False
    _run(game, 600)
    lo = float(game.bal.get("feeder.satiety_min"))
    floor = float(game.bal.get("feeder.output_floor"))
    assert game.state.tank.satiety >= lo - 1e-9
    assert game.systems["feeder"].factor >= floor - 1e-9


def test_auto_feeder_refills(game):
    """自动投食器会在饱食度低于阈值时补上（准则 L3：自动优先）。"""
    game.state.tank.feeder_owned = True
    game.state.tank.feeder_on = True
    game.state.tank.satiety = 0.1
    _run(game, 60)
    assert game.systems["feeder"].auto_feeds >= 1
    assert game.state.tank.satiety > 0.1


def test_feeder_off_does_not_feed(game):
    """关掉开关就不再自动投食（也不再扣维护费）。"""
    game.state.tank.feeder_owned = True
    game.state.tank.feeder_on = False
    game.state.tank.satiety = 0.1
    _run(game, 60)
    assert game.systems["feeder"].auto_feeds == 0
    assert game.systems["feeder"].upkeep_rate_milli(game.state, game.bal) == 0


# ══════════════════════════════════════════════════════════════
#  IncomeSystem
# ══════════════════════════════════════════════════════════════

def test_income_accumulates_and_emits(game):
    """收益会累加并发 COINS_CHANGED 事件。"""
    events = []
    game.bus.subscribe(COINS_CHANGED, lambda d: events.append(d))
    before = game.state.coins_milli
    _run(game, 120)
    assert game.state.coins_milli > before
    assert events
    assert events[-1]["coins_milli"] == game.state.coins_milli
    assert game.systems["income"].session_gain_milli == game.state.coins_milli - before


def test_coins_never_negative(game):
    """准则 L2：金币永不为负，哪怕维护费远超产出。"""
    game.state.coins_milli = 0
    game.state.tank.feeder_owned = True
    game.state.tank.feeder_on = True
    for i in range(40):
        f = FishState(uid=game.state.alloc_uid(), species="neon_tetra",
                      born_at=T0, age_sec=0.0, stage="fry")
        game.state.add_fish(f, when=T0)
    game.rebuild_entities()
    _run(game, 300)
    assert game.state.coins_milli >= 0


def test_income_rate_reported(game):
    """HUD 用的速率字段是活的。"""
    _run(game, 2)
    assert game.systems["income"].rate_milli >= 0
    assert 0.0 <= game.systems["income"].bonus <= game.bal.bonus_cap() + 1e-9


# ══════════════════════════════════════════════════════════════
#  BreedingSystem
# ══════════════════════════════════════════════════════════════

def test_breeding_uses_gameplay_rng_not_ai_rng(game):
    """繁殖必须消耗玩法随机流；表现流的消耗不能影响它。"""
    ai_state_before = game.ai_rng.state()
    _run(game, 5)
    assert game.ai_rng.state() != ai_state_before   # 表现流确实在被消耗
    # 玩法流只在繁殖检查时消耗；5 秒内 breed_timer 还没到 interval
    assert game.state.rng_seed == game.rng.state()


def test_breeding_fires_on_interval(game):
    """跨过 check_interval_sec 才会做繁殖判定。"""
    interval = int(game.bal.get("breeding.check_interval_sec"))
    game.state.breed_timer = interval - 1.0
    _run(game, 3)
    assert game.systems["breeding"].checks >= 1


def test_breeding_respects_capacity(game):
    """缸满时静默跳过，绝不超容量（准则 L1：不驱逐、不排队、不提示）。"""
    cap = game.state.capacity(game.bal)
    while game.state.fish_count() < cap:
        f = FishState(uid=game.state.alloc_uid(), species="neon_tetra",
                      born_at=T0, age_sec=999999.0, stage="mature",
                      last_bred_at=0)
        game.state.add_fish(f, when=T0)
    game.rebuild_entities()
    game.state.breed_timer = 0.0
    _run(game, 3600, dt=_FAST_DT)
    assert game.state.fish_count() == cap


def test_breeding_can_produce_offspring(game):
    """给足条件与时间，繁殖能真的出鱼，并且实体也建出来了。"""
    game.state.tank.capacity_level = len(game.bal.get("shop.capacity")) - 1
    for _ in range(4):
        f = FishState(uid=game.state.alloc_uid(), species="neon_tetra",
                      born_at=T0, age_sec=999999.0, stage="mature",
                      last_bred_at=0)
        game.state.add_fish(f, when=T0)
    game.rebuild_entities()
    n0 = game.state.fish_count()

    # 事件驱动建实体：BreedingSystem 只发事件，实体由 game 负责补
    born = []
    game.bus.subscribe("fishtank.fish_hatched", lambda d: born.append(d))
    # 同种冷却 3h，所以时程必须够长；用 _FAST_DT 把帧数压到 1/5（结果不变）
    _run(game, 3600 * 6, dt=_FAST_DT)
    assert game.state.fish_count() > n0
    assert born
    for rec in born:
        assert game.state.get_fish(rec["uid"]) is not None


# ══════════════════════════════════════════════════════════════
#  ParticleBridgeSystem
# ══════════════════════════════════════════════════════════════

def test_particles_spawn_and_respect_cap(game):
    """气泡会生成，且不超过 fx.max_particles。"""
    cap = int(game.bal.get("fx.max_particles"))
    _run(game, 120)
    ps = game.systems["particles"]
    assert ps.spawned >= 1
    assert len(ps.particles()) <= cap


def test_particles_float_upward(game):
    """E16：浮力用负重力实现，气泡的 y 应该在减小。"""
    _run(game, 5)
    ps = game.systems["particles"]
    parts = ps.particles()
    if not parts:
        pytest.skip("这 5 秒没生成气泡")
    assert any(p.vy < 0.0 for p in parts)


def test_particles_disabled_is_noop(tmp_save_dir):
    """关掉特效后一颗粒子都不生成。"""
    g = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                     save_enabled=False, fx_enabled=False, clock=lambda: T0)
    g.start(when=T0)
    _run(g, 30)
    assert g.systems["particles"].spawned == 0
    assert g.particle_views() == []


# ══════════════════════════════════════════════════════════════
#  FishTankGame 编排
# ══════════════════════════════════════════════════════════════

def test_start_is_idempotent(game):
    """重复 start 不会重建世界。"""
    w = game.world
    game.start()
    assert game.world is w


def test_new_game_from_config(game):
    """新档的初始值全部来自 balance.start.*（零硬编码）。"""
    assert game.state.coins_milli == int(game.bal.get("start.coins_milli"))
    assert game.state.fish_count() == len(game.bal.get("start.fishes"))
    assert game.balance_problems == []


def test_entities_match_state(game):
    """每条鱼都有实体，且组件齐全。"""
    for f in game.state.fishes_sorted():
        ent = game.entity_of(f.uid)
        assert ent is not None
        for comp in (FishTag, Transform, Motion, Growth, Appearance,
                     Animation, AIState, BlackboardComponent, BrainComponent):
            assert ent.has(comp), "%s 缺少 %s" % (f.uid, comp.__name__)


def test_brain_bound_to_entity_blackboard(game):
    """行为树的黑板必须就是实体黑板（否则 TickSystem 写的数据行为树读不到）。"""
    for f in game.state.fishes_sorted():
        ent = game.entity_of(f.uid)
        assert ent.get(BrainComponent).tree.blackboard is \
            ent.get(BlackboardComponent).blackboard


def test_buy_fry(game):
    """买鱼：扣钱、加鱼、建实体、发事件。"""
    events = []
    game.bus.subscribe(FISH_BORN, lambda d: events.append(d))
    game.state.coins_milli = 10 ** 9
    n0 = game.state.fish_count()
    res = game.buy_fry("zebra_danio")
    assert res.ok and res.code == "bought"
    assert game.state.fish_count() == n0 + 1
    assert game.entity_of(res.data["uid"]) is not None
    assert events and events[0]["species"] == "zebra_danio"


def test_buy_fry_failures(game):
    """买鱼的四种失败路径都返回结果码，不抛异常。"""
    assert game.buy_fry("no_such_fish").code == "unknown_species"
    game.state.coins_milli = 0
    assert game.buy_fry("neon_tetra").code == "no_coins"

    game.state.coins_milli = 10 ** 9
    cap = game.state.capacity(game.bal)
    while game.state.fish_count() < cap:
        game.state.add_fish(FishState(uid=game.state.alloc_uid(),
                                      species="neon_tetra", born_at=T0), when=T0)
    assert game.buy_fry("neon_tetra").code == "tank_full"


def test_buy_upgrade_all_kinds(game):
    """三种升级都能买，等级正确递增，买到顶返回 max_level。"""
    game.state.coins_milli = 10 ** 12
    assert game.buy_upgrade(UPGRADE_FEEDER).ok
    assert game.state.tank.feeder_owned is True
    assert game.buy_upgrade(UPGRADE_FEEDER).code == "max_level"

    for expect in range(1, len(game.bal.get("water.filter_gain"))):
        res = game.buy_upgrade(UPGRADE_FILTER)
        assert res.ok and res.data["level"] == expect
    assert game.buy_upgrade(UPGRADE_FILTER).code == "max_level"

    for expect in range(1, len(game.bal.get("shop.capacity"))):
        res = game.buy_upgrade(UPGRADE_CAPACITY)
        assert res.ok and res.data["level"] == expect
    assert game.buy_upgrade(UPGRADE_CAPACITY).code == "max_level"
    assert game.buy_upgrade("nonsense").code == "unknown_kind"


def test_buy_decor(game):
    """买装饰：扣钱、进列表、加成变大、重复购买被拒。"""
    game.state.coins_milli = 10 ** 12
    did = game.decor.ids()[0]
    b0 = game.hud_snapshot()["bonus"]
    res = game.buy_decor(did)
    assert res.ok
    assert did in game.state.tank.decors
    assert game.hud_snapshot()["bonus"] >= b0
    assert game.buy_decor(did).code == "owned"
    assert game.buy_decor("no_such_decor").code == "unknown_decor"
    assert any(v["id"] == did for v in game.decor_views())


def test_toggle_feeder(game):
    """没买投食器时开关无效。"""
    assert game.toggle_feeder().code == "not_owned"
    game.state.tank.feeder_owned = True
    assert game.toggle_feeder(False).data["on"] is False
    assert game.toggle_feeder().data["on"] is True


def test_rename_and_mode(game):
    """改名与窗口形态。"""
    uid = game.state.fishes_sorted()[0].uid
    assert game.rename_fish(uid, "小蓝").ok
    assert game.state.get_fish(uid).nickname == "小蓝"
    assert game.rename_fish(99999, "x").code == "no_such_fish"
    assert game.set_window_mode("strip").ok
    assert game.state.settings["window_mode"] == "strip"


def test_interest_point(game):
    """设置/清除兴趣点。"""
    assert game.set_interest(0.3, 0.4).ok
    assert game.interest == (0.3, 0.4)
    game.set_interest()
    assert game.interest is None


def test_hud_snapshot_fields(game):
    """HUD 快照字段齐全、类型正确。"""
    snap = game.hud_snapshot()
    for key in ("coins_milli", "coins_text", "rate_milli_per_min", "fish_count",
                "capacity", "water", "water_factor", "satiety", "satiety_factor",
                "bonus", "codex_count", "species_total"):
        assert key in snap
    assert snap["fish_count"] <= snap["capacity"]
    assert 0.0 < snap["water_factor"] <= 1.0
    assert 0.0 < snap["satiety_factor"] <= 1.0


def test_fish_views_sorted_and_complete(game):
    """渲染快照按 uid 升序（绘制顺序稳定），字段齐全。"""
    _run(game, 2)
    views = game.fish_views()
    assert [v["uid"] for v in views] == sorted(v["uid"] for v in views)
    assert len(views) == game.state.fish_count()
    for v in views:
        assert v["body_color"].startswith("#")
        assert v["tail"] in ("fan", "fork", "round", "long")
        assert 0.0 <= v["x"] <= 1.0 and 0.0 <= v["y"] <= 1.0


# ══════════════════════════════════════════════════════════════
#  存档 / 休眠恢复
# ══════════════════════════════════════════════════════════════

def test_autosave_and_reload(tmp_save_dir):
    """自动存档写盘，重开一局能读回来且金币不倒退。"""
    g1 = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                      save_enabled=True, fx_enabled=False, clock=lambda: T0)
    g1.start(when=T0)
    _run(g1, 120)
    assert g1.save()
    coins = g1.state.coins_milli
    anchor = g1.state.saved_at_utc

    g2 = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                      save_enabled=True, fx_enabled=False,
                      clock=lambda: anchor)
    g2.start(when=anchor)
    assert g2.state.coins_milli >= coins
    assert g2.state.fish_count() == g1.state.fish_count()


def test_save_anchor_is_simulated_time(game):
    """存档锚点用"已模拟到的时刻"，不能被墙钟抬走未结算的秒数（准则 L2）。"""
    _run(game, 30)
    anchor = game.state.saved_at_utc
    game.clock = lambda: T0 + 10 ** 6      # 墙钟猛跳
    game.save()
    assert game.state.saved_at_utc == anchor


def test_resume_after_sleep_settles_offline(tmp_save_dir):
    """运行中休眠 1 小时，用同一个 settle_offline 补回来，一秒收益都不丢。"""
    g = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                     save_enabled=False, fx_enabled=False, clock=lambda: T0)
    g.start(when=T0)
    _run(g, 10)
    coins = g.state.coins_milli

    resumed = g.update(_LOGIC_DT, when=T0 + 10 + 3600)
    assert resumed is True
    assert g.resume_reports
    rep = g.resume_reports[0]
    assert rep.away_sec == pytest.approx(3600, abs=2)
    assert g.state.coins_milli > coins
    assert g.state.saved_at_utc == T0 + 10 + 3600
    # 实体被重建且仍然一一对应
    for f in g.state.fishes_sorted():
        assert g.entity_of(f.uid) is not None


def test_resume_does_not_double_count(tmp_save_dir):
    """补算后锚点被推到 now，不会再次补算同一段时间。"""
    g = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                     save_enabled=False, fx_enabled=False, clock=lambda: T0)
    g.start(when=T0)
    g.update(_LOGIC_DT, when=T0 + 7200)
    n = len(g.resume_reports)
    coins = g.state.coins_milli
    g.update(_LOGIC_DT, when=T0 + 7200)
    assert len(g.resume_reports) == n
    assert g.state.coins_milli == coins


def test_offline_report_on_start(tmp_save_dir):
    """启动时的离线结算报告存在且自洽。"""
    g1 = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                      save_enabled=True, fx_enabled=False, clock=lambda: T0)
    g1.start(when=T0)
    g1.save()

    later = T0 + 86400
    g2 = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                      save_enabled=False, fx_enabled=False, clock=lambda: later)
    g2.start(when=later)
    rep = g2.offline_report
    assert rep.away_sec == 86400
    assert rep.coins_gained_milli > 0
    assert rep.has_content() is True
    assert g2.state.saved_at_utc == later


def test_shutdown_saves(tmp_save_dir):
    """shutdown 会落一次盘。"""
    g = FishTankGame(data_dir=default_data_dir(), save_dir=tmp_save_dir,
                     save_enabled=True, fx_enabled=False, clock=lambda: T0)
    g.start(when=T0)
    _run(g, 5)
    assert g.shutdown() is True
    assert os.path.isfile(g.saver.path())
    assert g.shutdown() is False       # 幂等：第二次不再写


def test_no_save_mode_writes_nothing(tmp_save_dir):
    """--no-save 模式一个文件都不产生。"""
    sub = tempfile.mkdtemp(dir=tmp_save_dir)
    g = FishTankGame(data_dir=default_data_dir(), save_dir=sub,
                     save_enabled=False, fx_enabled=False, clock=lambda: T0)
    g.start(when=T0)
    _run(g, 5)
    g.shutdown()
    assert os.listdir(sub) == []


# ══════════════════════════════════════════════════════════════
#  健壮性
# ══════════════════════════════════════════════════════════════

def test_unknown_species_survives(game):
    """存档里混进未知鱼种也不能崩（准则：数据问题绝不崩溃）。"""
    game.state.add_fish(FishState(uid=game.state.alloc_uid(),
                                  species="ghost_fish_that_does_not_exist",
                                  born_at=T0), when=T0)
    game.rebuild_entities()
    _run(game, 30)
    assert game.state.fish_count() >= 1
    assert game.hud_snapshot()["fish_count"] >= 1


def test_empty_tank_runs(game):
    """空缸也能正常跑。"""
    game.state.fishes = []
    game.rebuild_entities()
    _run(game, 60)
    assert game.state.fish_count() == 0
    assert game.state.coins_milli >= 0


def test_long_run_is_stable(game):
    """连跑 10 分钟逻辑帧，状态全程有限且合法。"""
    _run(game, 600)
    assert math.isfinite(game.state.tank.water)
    assert math.isfinite(game.state.tank.satiety)
    assert game.state.coins_milli >= 0
    for f in game.state.fishes:
        assert math.isfinite(f.x) and math.isfinite(f.y)
        assert f.age_sec >= 0.0


def test_action_result_repr():
    """ActionResult 的布尔语义与 repr。"""
    ok = ActionResult(True, "x", {"a": 1})
    bad = ActionResult(False, "y")
    assert bool(ok) is True and bool(bad) is False
    assert "ok=True" in repr(ok)


def test_system_priority_order(game):
    """🔴 系统执行顺序必须是 10→20→30→40→45→47→50→60→70。"""
    priorities = [type(s).priority for s in game.world._systems] \
        if hasattr(game.world, "_systems") else None
    if priorities is None:
        priorities = [type(s).priority for s in game.world.systems]
    assert priorities == sorted(priorities)
    assert priorities == [10, 20, 30, 40, 45, 47, 50, 60, 70]
