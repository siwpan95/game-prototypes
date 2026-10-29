"""自定义事件名常量（命名空间 ``fishtank.*``）。

🔴 准则 L6 / 验收第 8 条：**任何事件都不得触发桌面通知或强制弹窗。**
事件只用于：更新 HUD、点亮图鉴条目、写日志、驱动粒子。
唯一允许主动弹出的 UI 是离线结算卡片（P0-19），且它由启动流程直接调用，
不经过事件总线的通知路径。
"""

NS = "fishtank."

FISH_BORN = NS + "fish_born"
"""购买/初始化产生新鱼。data: {"uid", "species"}"""

FISH_GROWN = NS + "fish_grown"
"""鱼跨越成长阶段。data: {"uid", "species", "from", "to"}"""

FISH_HATCHED = NS + "fish_hatched"
"""繁殖孵化出新鱼。data: {"uid", "species", "parents"}"""

FISH_SOLD = NS + "fish_sold"
"""自动卖出成鱼。data: {"uid", "species", "stage", "sold_milli"}"""

CODEX_UNLOCKED = NS + "codex_unlocked"
"""图鉴解锁新条目。data: {"species"}  —— 只点亮条目，绝不弹窗。"""

GROUP_COMPLETED = NS + "group_completed"
"""集齐某族群。data: {"group"} —— 只在图鉴页亮一行，绝不弹窗。"""

WATER_BAND_CHANGED = NS + "water_band_changed"
"""水质**档位**跨档（不是每帧浮点变化）。data: {"band", "water"}"""

UPGRADE_BOUGHT = NS + "upgrade_bought"
"""升级购买成功。data: {"kind", "level"}"""

DECOR_BOUGHT = NS + "decor_bought"
"""装饰购买成功。data: {"id"}"""

COINS_CHANGED = NS + "coins_changed"
"""金币变化。data: {"coins_milli", "delta_milli"}"""

OFFLINE_SETTLED = NS + "offline_settled"
"""离线结算完成。data: OfflineResult 的摘要字典。"""

SAVED = NS + "saved"
"""存档写入完成。data: {"path", "ok"}"""

ALL_EVENTS = (
    FISH_BORN, FISH_GROWN, FISH_HATCHED, FISH_SOLD, CODEX_UNLOCKED, GROUP_COMPLETED,
    WATER_BAND_CHANGED, UPGRADE_BOUGHT, DECOR_BOUGHT, COINS_CHANGED,
    OFFLINE_SETTLED, SAVED,
)
