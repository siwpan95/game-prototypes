"""★ FishTankGame：整局游戏的编排层（无 GUI 依赖，可 headless 跑）。

🔴 禁止 `from __future__ import annotations`（E6）。

职责边界
--------
* **它做**：装数据 → 读档 → 离线结算 → 建 World/系统/实体 → 驱动 update →
  提供商店/投喂等玩家动作 → 自动存档。
* **它不做**：任何 tkinter / 画布 / 窗口相关的事（那些在 `pyapp/` 里）。
  所以本模块可以在纯命令行下被测试与压测。

时间模型（准则 L2：收益永不丢失）
--------------------------------
`GameState.saved_at_utc` = "玩法已模拟到的 UTC 秒"。

* 在线：`TickSystem` 每推进一个固定步就把它 +1 步；
* 掉线/休眠：`now - saved_at_utc` 变大，:meth:`update` 检测到超过
  `offline.fine_step_sec` 就调用**同一个** :func:`~fishtank.offline.settle_offline`
  纯函数补算，然后热替换状态。

于是"启动补算"和"运行中休眠补算"共用一条代码路径，不存在第二套逻辑。

随机源（双端一致性）
--------------------
两条**互不干扰**的确定性流：

* `WD_RNG`   —— 玩法流。只被繁殖消耗，`state.rng_seed` 随档持久化。
* `WD_AI_RNG`—— 表现流。巡游目标、气泡等，不入档；帧率变化不会污染玩法流。
"""

import os

from fishtank.behaviors import AIConfig, build_fish_tree
from fishtank.components import (
    AIState, Animation, Appearance, DecorItem, FishTag, FoodPellet, Growth,
    Motion, RenderCache, Schooling, Transform,
)
from fishtank.constants import (
    MODE_TANK, UPGRADE_CAPACITY, UPGRADE_FEEDER, UPGRADE_FILTER, UPGRADES,
    WD_AI_RNG, WD_AUTOSELL, WD_BALANCE, WD_BONUS, WD_BUS, WD_CFG, WD_DECOR,
    WD_GAME, WD_NOW, WD_RNG, WD_SPECIES, WD_STATE,
)
from fishtank.data_defs import load_all
from fishtank.economy import (
    BonusCache, format_coins, fry_price_milli, max_level, net_rate_milli,
    quality_factor, satiety_factor, stage_scale, upgrade_price_milli,
)
from fishtank.engine_bootstrap import (
    BlackboardComponent, BrainComponent, BrainSystem, EventBus, World,
    get_logger,
)
from fishtank.events import (
    DECOR_BOUGHT, FISH_BORN, FISH_HATCHED, FISH_SOLD, CODEX_UNLOCKED,
    OFFLINE_SETTLED, SAVED, UPGRADE_BOUGHT,
)
from fishtank.offline import settle_offline
from fishtank.rng import DetRandom
from fishtank.save import SaveManager
from fishtank.state import FishState, GameState, now_utc
from fishtank.systems import (
    AutoFeederSystem, AutoSellSystem, BreedingSystem, GrowthSystem,
    IncomeSystem, MovementSystem, ParticleBridgeSystem, TickSystem,
    WaterSystem,
)

_AI_SEED_SALT = 0x9E3779B97F4A7C15
"""表现流种子的扰动常量（黄金比例哈希常数）。只为把两条随机流彻底岔开。"""

_DEFAULT_DATA_DIR = "data"


def default_data_dir():
    """返回项目自带的 `data/` 目录绝对路径。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), _DEFAULT_DATA_DIR)


class ActionResult(object):
    """玩家动作的统一返回值。

    :ivar ok: 是否成功
    :ivar code: 机器可读的结果码（UI 用它去 ui_text.json 取文案，代码里不写中文）
    :ivar data: 附加数据字典
    """

    __slots__ = ("ok", "code", "data")

    def __init__(self, ok=False, code="", data=None):
        self.ok = bool(ok)
        self.code = str(code)
        self.data = dict(data or {})

    def __repr__(self):
        return "<ActionResult ok=%s code=%s data=%r>" % (self.ok, self.code, self.data)

    def __bool__(self):
        return self.ok


class FishTankGame(object):
    """一局游戏。

    典型用法::

        game = FishTankGame()
        game.start()                 # 装数据 + 读档 + 离线结算 + 建世界
        while running:
            game.update(dt)          # 推进一帧
        game.shutdown()              # 收尾存档
    """

    def __init__(self, data_dir="", save_dir="", logger=None,
                 save_enabled=True, fx_enabled=True, clock=None):
        """:param data_dir: data 目录；留空用项目自带的
        :param save_dir: 存档目录；留空用引擎重定向后的目录
        :param save_enabled: False 时不写盘（`--no-save`）
        :param fx_enabled: False 时关闭粒子（省电）
        :param clock: 可注入的取时函数（测试用；默认 :func:`fishtank.state.now_utc`）
        """
        self.log = logger or get_logger("fishtank")
        self.data_dir = data_dir or default_data_dir()
        self.clock = clock or now_utc

        self.bal = None
        self.species = None
        self.decor = None
        self.text = None
        self.balance_problems = []

        self.state = None
        self.world = None
        self.bus = EventBus()
        self.cfg = None
        self.rng = None
        self.ai_rng = None
        self.saver = SaveManager(directory=save_dir, enabled=save_enabled,
                                 logger=self.log)
        self.fx_enabled = bool(fx_enabled)

        self.systems = {}
        self.offline_report = None
        self.resume_reports = []
        """运行中因休眠触发的补算报告（诊断用；不弹窗，准则 L6）。"""

        self._entities = {}
        self._save_accum = 0.0
        self._autosave_sec = 60.0
        self._resume_threshold = 60
        self._started = False
        self.frames = 0
        self.interest = None

    # ══════════════════════════════════════════════════════════
    #  启动
    # ══════════════════════════════════════════════════════════

    def start(self, when=None):
        """装数据 → 读档 → 离线结算 → 建世界。幂等。

        :param when: 注入当前 UTC 秒（测试用）
        :returns: self
        """
        if self._started:
            return self
        self.load_data()
        now = int(when) if when is not None else int(self.clock())
        self.load_state(now)
        self.build_world()
        self._started = True
        self.state.bump_stat("sessions", 1)
        return self

    def load_data(self):
        """加载 data/ 下四份 JSON 并做启动校验。"""
        self.bal, self.species, self.decor, self.text = load_all(
            self.data_dir, logger=self.log)
        self.balance_problems = self.bal.validate()
        if self.balance_problems:
            self.log.warning("[game] balance 校验发现 %d 个问题（已降级运行）"
                             % len(self.balance_problems))
        self.cfg = AIConfig.from_balance(self.bal)
        self._autosave_sec = max(1.0, float(self.bal.get("save.autosave_sec", 60) or 60))
        self._resume_threshold = max(1, int(self.bal.get("offline.fine_step_sec", 60) or 60))
        self.saver.keep_backups = max(0, int(self.bal.get("save.keep_backups", 1) or 0))

    def load_state(self, now):
        """读档（没有就开新档），随后立刻做一次离线结算。"""
        st = self.saver.load()
        if st is None:
            st = GameState.new_game(self.bal, self.species, when=now)
            self.log.info("[game] 未找到存档，已创建新档")
        else:
            fixed = st.repair()
            if fixed:
                self.log.warning("[game] 存档自愈修补了 %d 处" % fixed)

        st, report = settle_offline(st, now, self.bal, self.species, self.decor)
        self.state = st
        self.offline_report = report
        if report.has_content():
            self.log.info("[game] 离线 %.2f 小时，等效 %.2f 小时，入账 %s"
                          % (report.away_hours(), report.equivalent_hours(),
                             format_coins(report.coins_gained_milli, self.bal)))
        self.bus.emit(OFFLINE_SETTLED, report.to_dict())

    def build_world(self):
        """建 World、装系统、按存档铺实体。"""
        world = World()
        self.world = world

        self.rng = DetRandom(self.state.rng_seed)
        self.ai_rng = DetRandom((int(self.state.rng_seed) ^ _AI_SEED_SALT) & 0xFFFFFFFFFFFFFFFF)

        world.set_data(WD_STATE, self.state)
        world.set_data(WD_BALANCE, self.bal)
        world.set_data(WD_SPECIES, self.species)
        world.set_data(WD_DECOR, self.decor)
        world.set_data(WD_BUS, self.bus)
        world.set_data(WD_CFG, self.cfg)
        world.set_data(WD_RNG, self.rng)
        world.set_data(WD_AI_RNG, self.ai_rng)
        world.set_data(WD_BONUS, BonusCache(self.bal, self.species, self.decor))
        world.set_data(WD_GAME, self)
        world.set_data(WD_NOW, int(self.state.saved_at_utc))

        self.systems = {
            "tick": TickSystem(logger=self.log),
            "brain": BrainSystem(event_bus=None),
            "movement": MovementSystem(logger=self.log),
            "growth": GrowthSystem(logger=self.log),
            "water": WaterSystem(logger=self.log),
            "feeder": AutoFeederSystem(logger=self.log),
            "income": IncomeSystem(logger=self.log),
            "breeding": BreedingSystem(logger=self.log),
            "autosell": AutoSellSystem(logger=self.log),
            "particles": ParticleBridgeSystem(logger=self.log, fx_enabled=self.fx_enabled),
        }
        for sys_obj in self.systems.values():
            world.add_system(sys_obj)

        self.rebuild_entities()

    # ══════════════════════════════════════════════════════════
    #  实体
    # ══════════════════════════════════════════════════════════

    def rebuild_entities(self):
        """按当前 GameState 重建全部实体（读档 / 离线补算后调用）。"""
        world = self.world
        if world is None:
            return
        for eid in list(self._entities.values()):
            world.remove_entity(eid)
        self._entities = {}
        for f in self.state.fishes_sorted():
            self.spawn_fish_entity(f)
        self._rebuild_decor_entities()

    def spawn_fish_entity(self, fish):
        """为一条 :class:`~fishtank.state.FishState` 建 ECS 实体（含独立行为树）。

        :param fish: 鱼的持久化状态
        :returns: Entity
        """
        world = self.world
        sp = self.species.get(fish.species)
        rarity = sp.rarity if sp else "R1"
        speed_key = sp.speed_key() if sp else "normal"
        base_speed = self.cfg.speed_of(speed_key)
        tail_hz = self.cfg.tail_hz_of(speed_key)
        layer_y = self.cfg.layer_of(sp.layer_key() if sp else "")
        attract = self.cfg.attract_of(sp.schooling_key() if sp else "")

        ent = world.create_entity("fish:%d" % fish.uid)
        ent.add(FishTag(uid=fish.uid, species=fish.species))
        ent.add(Transform(x=fish.x, y=fish.y, heading=fish.heading,
                          scale=stage_scale(fish.stage, self.bal.stage_scale_table())))
        ent.add(Motion(base_speed=base_speed, target_x=fish.x, target_y=fish.y,
                       turn_rate=self.cfg.turn_rate))
        ent.add(Growth(age_sec=fish.age_sec,
                       cycle_sec=float(self.bal.growth_cycle_sec(rarity)),
                       stage=fish.stage, rarity=rarity))
        ent.add(self._make_appearance(fish, sp, rarity))
        ent.add(Animation(tail_hz=tail_hz))
        ent.add(AIState())
        ent.add(Schooling(attract=attract, radius=self.cfg.school_radius,
                          layer_y=layer_y, layer_bias=self.cfg.layer_bias))
        ent.add(RenderCache())

        tree = build_fish_tree(
            fish.uid, self.cfg, self.ai_rng, x=fish.x, y=fish.y,
            heading=fish.heading, base_speed=base_speed, tail_hz=tail_hz,
            layer_y=layer_y, attract=attract, now=int(self.state.saved_at_utc))
        ent.add(BlackboardComponent())
        # E14：每条鱼一棵树、一块黑板。把树直接绑到实体级黑板上，
        # 免得 BrainSystem 首帧 rebind 时丢掉 build_fish_tree 写好的初始目标点。
        ent.get(BlackboardComponent).blackboard = tree.blackboard
        ent.add(BrainComponent(tree=tree, name="fish:%d" % fish.uid))

        self._entities[fish.uid] = ent.eid
        return ent

    def _make_appearance(self, fish, sp, rarity):
        """从鱼种定义 + 稀有度视觉档烘焙外观组件。"""
        color = sp.color if sp else {}
        shape = sp.shape if sp else {}
        vis = self.bal.get("visual." + rarity) or {}
        return Appearance(
            species=fish.species,
            rarity=rarity,
            body_color=str(color.get("body", "#8899AA")),
            belly_color=str(color.get("belly", color.get("body", "#B8C4CE"))),
            fin_color=str(color.get("fin", color.get("body", "#8899AA"))),
            # fish_data.json 的花纹色键名就叫 pattern
            accent_color=str(color.get("pattern",
                                       color.get("accent", color.get("fin", "#FFFFFF")))),
            tail=str(shape.get("tail", "fork")),
            body_len=float(shape.get("length", 1.0) or 1.0),
            # 🔴 JSON 里的键是 height_ratio，不是 body_ratio
            body_ratio=float(shape.get("height_ratio", 0.4) or 0.4),
            variant=bool(fish.variant),
            gradient=int(vis.get("gradient", 0) or 0),
            outline=int(vis.get("outline", 0) or 0),
            pattern=str(vis.get("pattern", "none")),
            glow=int(vis.get("glow", 0) or 0),
        )

    def _rebuild_decor_entities(self):
        """按存档里的装饰列表铺装饰实体（沿缸底均匀排开）。"""
        world = self.world
        ids = sorted(str(d) for d in self.state.tank.decors)
        n = len(ids)
        for i, did in enumerate(ids):
            d = self.decor.get(did)
            if d is None:
                continue
            ent = world.create_entity("decor:%s" % did)
            ent.add(DecorItem(
                decor_id=did, draw=d.draw,
                x=(i + 0.5) / float(n) if n else 0.5,
                y=self.cfg.y_max, scale=1.0, colors=list(d.color),
            ))

    # ══════════════════════════════════════════════════════════
    #  主循环
    # ══════════════════════════════════════════════════════════

    def update(self, dt, when=None):
        """推进一帧。

        :param dt: 真实帧时长（秒）
        :param when: 注入当前 UTC 秒（测试用）
        :returns: 本帧是否触发了休眠补算
        """
        if not self._started or self.world is None:
            return False
        now = int(when) if when is not None else int(self.clock())
        self.frames += 1

        resumed = self._maybe_resume(now)
        self.world.set_data(WD_NOW, now)
        self.world.set_data("fishtank.interest", self.interest)
        self.world.update(float(dt))

        # 清理自动卖出队列中的实体
        sold_uids = self.world.get_data(WD_AUTOSELL)
        if sold_uids:
            for uid in sold_uids:
                eid = self._entities.pop(uid, None)
                if eid is not None:
                    self.world.remove_entity(eid)
            sold_uids.clear()

        self._save_accum += float(dt)
        if self._save_accum >= self._autosave_sec:
            self._save_accum = 0.0
            self.save()
        return resumed

    def _maybe_resume(self, now):
        """检测休眠 / 长时间卡顿，用同一个纯函数把丢掉的时间补回来。"""
        gap = now - int(self.state.saved_at_utc)
        if gap < self._resume_threshold:
            return False
        st, report = settle_offline(self.state, now, self.bal, self.species, self.decor)
        self.state = st
        self.resume_reports.append(report)
        self.world.set_data(WD_STATE, st)
        self.rng = DetRandom(st.rng_seed)
        self.world.set_data(WD_RNG, self.rng)
        self.rebuild_entities()
        water_sys = self.systems.get("water")
        if water_sys is not None:
            water_sys.resync(st, self.bal)
        self.log.info("[game] 运行中补算 %d 秒（休眠恢复），入账 %s"
                      % (report.away_sec,
                         format_coins(report.coins_gained_milli, self.bal)))
        return True

    def save(self):
        """写盘。锚点用"已模拟到的时刻"，不用墙钟 —— 否则会吞掉未结算的秒数。"""
        if self.state is None:
            return False
        self.state.rng_seed = self.rng.state() if self.rng is not None else self.state.rng_seed
        ok = self.saver.save(self.state, when=int(self.state.saved_at_utc))
        self.bus.emit(SAVED, {"path": self.saver.path(), "ok": ok})
        return ok

    def shutdown(self):
        """收尾：存一次盘。"""
        if not self._started:
            return False
        ok = self.save()
        self._started = False
        return ok

    # ══════════════════════════════════════════════════════════
    #  玩家动作（≤3 次点击，准则 L5）
    # ══════════════════════════════════════════════════════════

    def feed_at(self, x, y):
        """在归一化坐标处丢一颗鱼食。

        :returns: :class:`ActionResult`（code=``fed`` / ``no_world``）
        """
        if self.world is None:
            return ActionResult(False, "no_world")
        life = float(self.bal.get("ai.food_life_sec", 12.0) or 12.0)
        sink = float(self.bal.get("ai.food_sink_speed", 0.045) or 0.045)
        ent = self.world.create_entity()
        ent.add(FoodPellet(
            x=min(max(float(x), self.cfg.x_min), self.cfg.x_max),
            y=min(max(float(y), self.cfg.y_min), self.cfg.y_max),
            life=life, sink_speed=sink, claimed_by=-1,
        ))
        return ActionResult(True, "fed", {"x": x, "y": y})

    def set_interest(self, x=None, y=None):
        """设置/清除玩家兴趣点（鼠标悬停时鱼会好奇地游过来）。"""
        if x is None or y is None:
            self.interest = None
        else:
            self.interest = (float(x), float(y))
        return ActionResult(True, "interest", {"point": self.interest})

    def buy_fry(self, species_id):
        """买一条鱼苗。

        :returns: code ∈ {bought, unknown_species, not_for_sale, tank_full, no_coins}
        """
        sp = self.species.get(str(species_id))
        if sp is None:
            return ActionResult(False, "unknown_species", {"species": species_id})
        sale = self.bal.get("shop.sale_rarities") or []
        if isinstance(sale, list) and sale and sp.rarity not in sale:
            return ActionResult(False, "not_for_sale", {"species": species_id})
        if self.state.is_full(self.bal):
            return ActionResult(False, "tank_full", {"capacity": self.state.capacity(self.bal)})
        price = fry_price_milli(sp.rarity, self.bal)
        if not self.state.spend_milli(price):
            return ActionResult(False, "no_coins", {"price_milli": price})

        now = int(self.state.saved_at_utc)
        fish = FishState(uid=self.state.alloc_uid(), species=sp.id, born_at=now,
                         age_sec=0.0, last_bred_at=now,
                         x=self.ai_rng.uniform(self.cfg.x_min, self.cfg.x_max),
                         y=self.ai_rng.uniform(self.cfg.y_min, self.cfg.y_max),
                         heading=1.0 if self.ai_rng.chance(0.5) else -1.0)
        first = self.state.add_fish(fish, when=now)
        self.state.bump_stat("born", 1)
        self.spawn_fish_entity(fish)
        self.bus.emit(FISH_BORN, {"uid": fish.uid, "species": fish.species})
        if first:
            self.bus.emit(CODEX_UNLOCKED, {"species": fish.species})
        return ActionResult(True, "bought", {"uid": fish.uid, "species": sp.id,
                                             "price_milli": price, "first": first})

    def buy_upgrade(self, kind):
        """买一级升级（扩容 / 过滤 / 自动投食器）。

        :returns: code ∈ {upgraded, unknown_kind, max_level, no_coins}
        """
        kind = str(kind)
        if kind not in UPGRADES:
            return ActionResult(False, "unknown_kind", {"kind": kind})
        cur = self._upgrade_level(kind)
        top = max_level(kind, self.bal)
        if cur >= top:
            return ActionResult(False, "max_level", {"kind": kind, "level": cur})
        price = upgrade_price_milli(kind, cur + 1, self.bal)
        if price < 0 or not self.state.spend_milli(price):
            return ActionResult(False, "no_coins", {"kind": kind, "price_milli": price})

        if kind == UPGRADE_CAPACITY:
            self.state.tank.capacity_level = cur + 1
        elif kind == UPGRADE_FILTER:
            self.state.tank.filter_level = cur + 1
        else:
            self.state.tank.feeder_owned = True
            self.state.tank.feeder_on = True
        new_level = self._upgrade_level(kind)
        self.bus.emit(UPGRADE_BOUGHT, {"kind": kind, "level": new_level})
        return ActionResult(True, "upgraded", {"kind": kind, "level": new_level,
                                               "price_milli": price})

    def upgrade_info(self, kind):
        """某项升级的只读展示信息（供商店页渲染，UI 层不碰经济函数）。

        :returns: {kind, level, max_level, maxed, price_milli, price_text}
        """
        kind = str(kind)
        cur = self._upgrade_level(kind) if kind in UPGRADES else 0
        top = max_level(kind, self.bal) if kind in UPGRADES else 0
        maxed = cur >= top
        price = -1 if maxed else upgrade_price_milli(kind, cur + 1, self.bal)
        return {
            "kind": kind,
            "level": cur,
            "max_level": top,
            "maxed": bool(maxed),
            "price_milli": price,
            "price_text": "" if price < 0 else format_coins(price, self.bal),
        }

    def fry_price_text(self, species_id):
        """鱼苗售价的展示文本（买不到时返回空串）。"""
        sp = self.species.get(str(species_id))
        if sp is None:
            return ""
        price = fry_price_milli(sp.rarity, self.bal)
        if price is None or price < 0:
            return ""
        return format_coins(price, self.bal)

    def _upgrade_level(self, kind):
        """当前某项升级的等级（喂食器用 0/1 表示未买/已买）。"""
        if kind == UPGRADE_CAPACITY:
            return int(self.state.tank.capacity_level)
        if kind == UPGRADE_FILTER:
            return int(self.state.tank.filter_level)
        if kind == UPGRADE_FEEDER:
            return 1 if self.state.tank.feeder_owned else 0
        return 0

    def buy_decor(self, decor_id):
        """买一件装饰。

        :returns: code ∈ {bought, unknown_decor, owned, no_coins}
        """
        d = self.decor.get(str(decor_id))
        if d is None:
            return ActionResult(False, "unknown_decor", {"id": decor_id})
        if d.id in self.state.tank.decors:
            return ActionResult(False, "owned", {"id": d.id})
        price = int(d.price) * self.bal.coin_scale()
        if not self.state.spend_milli(price):
            return ActionResult(False, "no_coins", {"id": d.id, "price_milli": price})
        self.state.tank.decors.append(d.id)
        self.state.tank.decors.sort()
        self.world.set_data(WD_BONUS, BonusCache(self.bal, self.species, self.decor))
        self._rebuild_decor_entities()
        self.bus.emit(DECOR_BOUGHT, {"id": d.id})
        return ActionResult(True, "bought", {"id": d.id, "price_milli": price})

    def toggle_feeder(self, on=None):
        """开关自动投食器。

        :returns: code ∈ {toggled, not_owned}
        """
        if not self.state.tank.feeder_owned:
            return ActionResult(False, "not_owned")
        self.state.tank.feeder_on = (not self.state.tank.feeder_on) if on is None else bool(on)
        return ActionResult(True, "toggled", {"on": self.state.tank.feeder_on})

    def rename_fish(self, uid, nickname):
        """给鱼起昵称。

        :returns: code ∈ {renamed, no_such_fish}
        """
        f = self.state.get_fish(int(uid))
        if f is None:
            return ActionResult(False, "no_such_fish", {"uid": uid})
        f.nickname = str(nickname)[:24]
        return ActionResult(True, "renamed", {"uid": f.uid, "nickname": f.nickname})

    def set_window_mode(self, mode):
        """记录窗口形态（tank / strip / panel）。"""
        self.state.settings["window_mode"] = str(mode or MODE_TANK)
        return ActionResult(True, "mode", {"mode": self.state.settings["window_mode"]})

    # ══════════════════════════════════════════════════════════
    #  只读快照（给 UI / 测试）
    # ══════════════════════════════════════════════════════════

    def hud_snapshot(self):
        """HUD 需要的一切，一次算完。

        :returns: dict
        """
        st = self.state
        bal = self.bal
        cache = self.world.get_data(WD_BONUS) if self.world is not None else None
        bonus = cache.value(st) if cache is not None else None
        rate = net_rate_milli(st, bal, self.species, self.decor, bonus=bonus)
        return {
            "coins_milli": st.coins_milli,
            "coins_text": format_coins(st.coins_milli, bal),
            "rate_milli_per_min": rate,
            "rate_text": format_coins(rate, bal),
            "fish_count": st.fish_count(),
            "capacity": st.capacity(bal),
            "water": st.tank.water,
            "water_factor": quality_factor(st.tank.water, bal),
            "satiety": st.tank.satiety,
            "satiety_factor": satiety_factor(st.tank.satiety, bal),
            "bonus": bonus if bonus is not None else 0.0,
            "codex_count": len(st.codex),
            "species_total": len(self.species.all_items),
            "feeder_owned": st.tank.feeder_owned,
            "feeder_on": st.tank.feeder_on,
            "filter_level": st.tank.filter_level,
            "capacity_level": st.tank.capacity_level,
            "session_gain_milli": self.systems["income"].session_gain_milli
            if "income" in self.systems else 0,
        }

    def fish_views(self):
        """渲染层需要的每条鱼的快照列表（按 uid 升序，保证绘制顺序稳定）。"""
        out = []
        if self.world is None:
            return out
        for uid in sorted(self._entities.keys()):
            ent = self.world.get_entity(self._entities[uid])
            if ent is None:
                continue
            tr = ent.get(Transform)
            app = ent.get(Appearance)
            anim = ent.get(Animation)
            ai = ent.get(AIState)
            g = ent.get(Growth)
            if tr is None or app is None:
                continue
            out.append({
                "uid": uid,
                "x": tr.x, "y": tr.y, "heading": tr.heading, "scale": tr.scale,
                "species": app.species, "rarity": app.rarity,
                "body_color": app.body_color, "belly_color": app.belly_color,
                "fin_color": app.fin_color,
                "accent_color": app.accent_color, "tail": app.tail,
                "body_len": app.body_len,
                "body_ratio": app.body_ratio, "variant": app.variant,
                "gradient": app.gradient, "outline": app.outline,
                "pattern": app.pattern, "glow": app.glow,
                "tail_phase": anim.tail_phase if anim else 0.0,
                "state": ai.state if ai else "",
                "stage": g.stage if g else "",
            })
        return out

    def decor_views(self):
        """渲染层需要的装饰快照列表。"""
        out = []
        if self.world is None:
            return out
        for ent in self.world.each(DecorItem):
            d = ent.get(DecorItem)
            out.append({"id": d.decor_id, "draw": d.draw, "x": d.x, "y": d.y,
                        "scale": d.scale, "colors": list(d.colors)})
        out.sort(key=lambda v: v["id"])
        return out

    def food_views(self):
        """渲染层需要的鱼食快照列表。"""
        out = []
        if self.world is None:
            return out
        for ent in self.world.each(FoodPellet):
            p = ent.get(FoodPellet)
            out.append({"x": p.x, "y": p.y, "life": p.life})
        return out

    def particle_views(self):
        """渲染层需要的粒子快照列表。"""
        sysobj = self.systems.get("particles")
        if sysobj is None:
            return []
        return [{"x": p.x, "y": p.y, "size": p.size, "alpha": p.alpha,
                 "color": p.color} for p in sysobj.particles()]

    def entity_of(self, uid):
        """按 uid 取实体（测试 / 调试用）。"""
        eid = self._entities.get(int(uid))
        return self.world.get_entity(eid) if (eid and self.world) else None
