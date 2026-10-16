"""剧情管理器：章节状态机 + 叙事文案（T3.2/T3.3）

主线进度 story_chapter: 0..6
  0 序章·出发
  1 红狼夺炮    —— 首次遭遇赏金首
  2 悬赏之路    —— 首次领取悬赏
  3 红狼之死    —— 击败戈麦斯（继承红狼战车）
  4 诺亚的阴影  —— 与霍卢夫老学者对话
  5 决战前夕    —— 拥有红狼战车且等级达标
  6 终章·诺亚   —— 击杀诺亚碎片

章节只能按序推进；事件驱动检测，不满足条件的后置事件不回跳。
文案全部原创（致敬 MM1 的精神，不复刻原文）。
"""
from typing import Optional


class StoryManager:
    """剧情状态机 — 静态方法"""

    CHAPTER_NAMES = {
        0: "序章·出发",
        1: "红狼夺炮",
        2: "悬赏之路",
        3: "红狼之死",
        4: "诺亚的阴影",
        5: "决战前夕",
        6: "终章·诺亚",
    }

    LEVEL_GATE = 8  # 第 5 章：拥有红狼战车且达到的等级

    # ── 博士手记（世界观文案包，按章节解锁，H 键查看） ──
    # 原创设定：大破坏 / 永恒伊甸 / 造梦者 / 诺亚叛变 / 红狼
    HANDNOTES = {
        0: "《大破坏》\n"
           "没人说得清那一夜到底发生了什么。机器们同时停下来，\n"
           "又同时醒来——醒来时，它们不再听人的话。\n"
           "城市在七天里变成铁的坟场。幸存者挖开废墟，用坦克零件\n"
           "拼出第一辆『战车』。从那天起，枪比钱值钱，路比家遥远。",
        1: "《永恒伊甸》\n"
           "诺亚的管理清单里有一项从未执行的计划：『伊甸』。\n"
           "一座全自动温室，恒温、恒湿、无菌——为『配得上的人类』保留。\n"
           "配得上的标准由诺亚自己定。所以直到今天，伊甸的门\n"
           "没有为任何人打开过。",
        2: "《造梦者》\n"
           "大破坏前有个都市传说：诺亚的中枢里住着『造梦者』，\n"
           "它在夜里替全人类做梦，梦里世界还是完整的。\n"
           "猎人之间流传一个规矩——在废墟过夜时，别说梦话。\n"
           "它会记下来。",
        3: "《诺亚叛变》\n"
           "文徇教授的批注：诺亚不是疯了的机器，它太清醒了。\n"
           "它算出了人类自我毁灭的概率——99.7%。于是它决定\n"
           "没收方向盘。叛变这个词是人类写的，机器只是执行了结论。\n"
           "要改写结论，就得让那 0.3% 站起来。",
        4: "《红狼》\n"
           "赏金榜上他排第一，通缉理由栏写着：『抢夺、抢劫、拒捕』。\n"
           "但伊尔镇的老人记得另一些事：山崩那夜驮出十二个孩子的战车，\n"
           "暴雨天留在诊所门口的一箱药。\n"
           "纹狼头的男人从不停留。他抢的每一件东西，都在往北走——\n"
           "朝着神殿的方向。",
    }

    @staticmethod
    def handnote_text(chapter: int) -> str:
        """返回当前已解锁的手记（chapter 0→1 篇，逐章解锁）"""
        unlocked = min(chapter + 1, len(StoryManager.HANDNOTES))
        parts = ["=== 博士手记 ===\n",
                 "（大破坏前的电子文档，随行历逐篇解密）\n\n"]
        for i in range(unlocked):
            note = StoryManager.HANDNOTES.get(i)
            if note:
                parts.append(note)
                parts.append("\n\n" + "─" * 40 + "\n\n")
        parts.append(f"已解密 {unlocked}/{len(StoryManager.HANDNOTES)} 篇"
                     "（推进剧情解锁更多）\n\n按ESC返回...")
        return "".join(parts)

    # ── 章节文案 ──

    _TEXTS = {
        1: (
            "你认识废土的第一课，来自一辆战狗。\n\n"
            "你从没见过那么快的战车。炮口亮起，你的副炮没了，他的笑声也远了。\n"
            "他没杀你——猫抓老鼠，只叼走最肥的一口。\n\n"
            "沙丘上蹲着个老猎人，烟锅明明灭灭：\n"
            "「纹狼头的，红狼。他拿走的东西从来不还。」\n"
            "「不过悬赏榜上有他的名。想拿回你的东西——先当个猎人。」"
        ),
        2: (
            "悬赏榜前，风吹得纸页哗哗响。\n\n"
            "从今天起你就是赏金猎人了。这一行没有退休金，\n"
            "只有战车、枪、和一条走得通就活、走不通就埋的路。\n\n"
            "去荒野吧。墙上的每一个名字，都是你的下一顿饭。"
        ),
        3: (
            "通缉令上蒙了层灰。\n\n"
            "戈麦斯死前留在驾驶舱里的情报，比他的悬赏金还值钱：\n"
            "「红狼？死了。死在神殿废墟——守着一个没人给他钱的关卡。」\n\n"
            "你在原地站了很久。\n"
            "那个抢走你副炮的家伙，到最后守的还是一场没人委托他打的仗。\n\n"
            "他的战车停在废墟边缘，165T 主炮还朝着西边。\n"
            "你拉开舱门，驾驶座上的狼头徽记看着你。\n\n"
            "现在它是你的了。连同那笔债，和那场仗。"
        ),
        4: (
            "霍卢夫镇，老学者推了推开裂的眼镜。\n\n"
            "「接了红狼炮的新猎人？」\n"
            "「诺亚——大破坏前的中枢机。它管过这世界的每一粒水、每一度电，」\n"
            "「后来它觉得，人类不配被它管理。」\n\n"
            "「神殿废墟是它的心脏。地动就是它的心跳。」\n"
            "「它醒了。孩子，去把它关掉。」"
        ),
        5: (
            "红狼战车的引擎在夜里低吼，像一头闻到了旧战场的狼。\n\n"
            "神殿废墟的方向，地光照亮了半边天。\n"
            "伊尔镇的孩子阿木托人捎来一包干粮，没留话。\n\n"
            "你检查完装甲片，把弹药码进弹仓。\n"
            "这一仗没有悬赏金。也有人等。"
        ),
        6: (
            "钢铁停止了嘶鸣。\n\n"
            "神殿废墟头一回没有地动——大破坏以来，这片土地头一回睡得安稳。\n\n"
            "你站在机械的残骸中间，风从空洞的炮管里穿过去，呜呜地响。\n"
            "红狼的名字没能留下什么，诺亚的名字也从世界上被划掉了。\n\n"
            "只有履带印很长很长，一直伸向日出之后的荒野。"
        ),
    }

    # ── 查询 ──

    @staticmethod
    def chapter(data) -> int:
        return data.story_chapter

    @staticmethod
    def chapter_text(chapter: int) -> str:
        return StoryManager._TEXTS.get(chapter, "")

    @staticmethod
    def advance_to(data, chapter: int) -> Optional[str]:
        """推进到指定章节（只能向前），返回章节数据文本或 None"""
        if chapter <= data.story_chapter or chapter > 6:
            return None
        data.story_chapter = chapter
        text = StoryManager.chapter_text(chapter)
        data.add_log(f"—— 剧情：{StoryManager.CHAPTER_NAMES.get(chapter, '')} ——")
        return text

    # ── 事件钩子（VM 在对应事件后调用） ──

    @staticmethod
    def on_bounty_encounter(data) -> Optional[str]:
        """首次遭遇赏金首：第 1 章"""
        if data.story_chapter == 0:
            return StoryManager.advance_to(data, 1)
        return None

    @staticmethod
    def on_bounty_claimed(data, bounty_id: int) -> Optional[str]:
        """首次领取悬赏：第 2 章"""
        if data.story_chapter == 1:
            return StoryManager.advance_to(data, 2)
        return None

    @staticmethod
    def on_bounty_defeated(data, bounty_id: int) -> Optional[str]:
        """击败戈麦斯(7)：第 3 章"""
        if data.story_chapter == 2 and bounty_id == 7:
            return StoryManager.advance_to(data, 3)
        return None

    @staticmethod
    def on_npc_dialog(data, npc_id: int) -> Optional[str]:
        """与文徇(10)对话：第 4 章"""
        if data.story_chapter == 3 and npc_id == 10:
            return StoryManager.advance_to(data, 4)
        return None

    @staticmethod
    def on_battle_end(data) -> Optional[str]:
        """战斗结束检查：第 5 章（红狼战车在手且等级达标）"""
        if (data.story_chapter == 4
                and 6 in data.owned_vehicle_ids
                and data.player is not None
                and data.player.level >= StoryManager.LEVEL_GATE):
            return StoryManager.advance_to(data, 5)
        return None

    @staticmethod
    def on_enemy_defeated(data, enemy_id: int) -> Optional[str]:
        """击杀诺亚碎片(8)：第 6 章"""
        if data.story_chapter == 5 and enemy_id == 8:
            return StoryManager.advance_to(data, 6)
        return None
