"""L6「零打扰 / 零催促」铁律的自动化守门测试（任务 4.16）。

这份测试是**懒人准则 L6 的机器执行版**。它做三件事：

1. 扫描 `data/ui_text.json` 的全部文案，命中 guilt/FOMO 词汇即失败；
2. 扫描项目全部 `.py` 源码，禁止出现面向用户的中文字面量
   （文案唯一来源必须是 ui_text.json，否则改文案要改代码）；
3. 扫描项目全部 `.py` 源码，禁止出现任何桌面通知 / 声音打扰 API（P0-23）。

🔴 禁止 `from __future__ import annotations`（E6）。

为什么要写成测试而不是靠人工 review：
文案是最容易被"顺手加一句"侵蚀的地方。一句"你的鱼饿了快来看看"
就能把整个懒人定位破坏掉，而 code review 很难每次都逮到。
"""

import ast
import json
import os
import re

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_ROOT, "data")
_UI_TEXT = os.path.join(_DATA_DIR, "ui_text.json")

# 扫描这些包/文件；tests/ 自己不扫（测试里必须能写这些禁用词才能测）
_SCAN_DIRS = ("fishtank", "pyapp")
_SCAN_FILES = ("main.py",)

# 中文字面量只扫**能碰到 Tk 控件的层**。
# `fishtank/` 是无头领域内核，由 `test_domain_layer_is_gui_free` 保证它
# 连 tkinter 都不 import —— 它里面的中文（日志标签、数据表词汇如 '中'/'低'）
# 在物理上不可能变成界面文案，扫它只会制造噪声。
_GUI_DIRS = ("pyapp",)
_GUI_FILES = ("main.py",)


# ---------------------------------------------------------------------------
# 禁用词表
# ---------------------------------------------------------------------------

GUILT_WORDS = (
    # 催促 / 命令
    "快来", "赶紧", "赶快", "速来", "马上来", "别忘", "记得来", "该来",
    "你该", "必须", "务必", "抓紧",
    # 负罪感 / 责备
    "饿", "饿了", "饿死", "没喂", "忘了喂", "疏于", "冷落", "可怜",
    "生病", "病了", "死了", "死掉", "枯萎", "凋零", "受苦", "难受",
    "都怪", "怪你", "你不管", "无人照料", "没人管",
    # FOMO / 稀缺
    "错过", "限时", "仅剩", "最后机会", "即将结束", "倒计时", "过期",
    "抓住机会", "立即", "手慢无", "稍纵即逝", "不再有",
    # 流失挽回话术
    "好久不见", "已经", "天没", "多久没", "终于回来", "还记得",
    # 惩罚
    "惩罚", "扣除", "损失", "清零", "失去", "作废",
)
"""guilt / FOMO / 催促词。命中即判定违反 L6。

⚠️ 有几个词看起来很无辜，但必须禁：
- "饿"：懒人准则 L1「鱼永不饿死」的前提是**根本不提饿**，
  提示"有点饿了"依然是在制造照料焦虑。
- "已经"：几乎只出现在"你已经 3 天没来了"这种句式里。
- "损失"：L2「收益永不丢失」，出现这个词说明有地方在扣东西。
"""

# 特批白名单：某些禁用词在中性语境里是合法的（键 -> 允许的完整文案）
GUILT_ALLOWLIST = {
    # 空状态里的"啦"结尾是纯鼓励，不含催促；此处无需豁免，保留结构以备扩展
}

# 桌面通知 / 声音打扰的**模块**（P0-23：代码中不得导入）
NOTIFY_MODULES = frozenset((
    "win10toast", "win11toast", "plyer", "notify2", "winsound", "playsound",
    "pynotifier", "desktop_notifier", "toasts", "pygame",
))

# 桌面通知 / 声音打扰的**调用名**（属性或函数名，禁止调用）
NOTIFY_CALLS = frozenset((
    "show_toast", "Shell_NotifyIcon", "shell_notifyicon", "MessageBeep",
    "PlaySound", "playsound", "notify", "toast", "bell", "Beep", "beep",
    "send_notification", "desktop_notify",
))
"""禁止出现的打扰型 API。

注意 `tkinter.messagebox` 不在此列：它是**用户主动操作后的同步确认**
（例如点"退出程序"），不是主动推送。但离线卡片明确禁止用它做二次确认（L5）。

`bell` / `Beep` 也在禁列：tkinter 的 `widget.bell()` 是系统提示音，
属于典型的"抓注意力"行为，违反 P0-23。
"""

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# —— 中文字面量豁免规则 ——
# 这些调用的实参是给**开发者**看的（日志 / 诊断），不会流到界面上
_DIAG_CALLS = frozenset((
    "log", "logger", "print", "debug", "info", "warn", "warning",
    "error", "exception", "critical", "_log", "log_error", "log_warn",
))
# 诊断信息收集器：`problems.append("...")` 这类
_DIAG_SINKS = frozenset(("problems", "issues", "errors", "warnings", "bad", "diagnostics"))
# argparse 的这些关键字实参是命令行帮助文本，不是 GUI 文案
_CLI_KWARGS = frozenset(("help", "description", "prog", "metavar", "epilog", "usage"))


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _iter_py_files(dirs=_SCAN_DIRS, files=_SCAN_FILES):
    """遍历需要扫描的全部 .py 文件，产出 (相对路径, 绝对路径)。"""
    for name in files:
        p = os.path.join(_ROOT, name)
        if os.path.isfile(p):
            yield name, p
    for d in dirs:
        base = os.path.join(_ROOT, d)
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for fn in sorted(files):
                if fn.endswith(".py"):
                    ap = os.path.join(root, fn)
                    yield os.path.relpath(ap, _ROOT).replace("\\", "/"), ap


def _walk_json_strings(node, path=""):
    """深度遍历 JSON，产出 (json 路径, 字符串值)。"""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_json_strings(v, "%s.%s" % (path, k) if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_json_strings(v, "%s[%d]" % (path, i))
    elif isinstance(node, str):
        yield path, node


def _parse(abs_path):
    """解析源码为 AST。"""
    with open(abs_path, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        return ast.parse(src, filename=abs_path)
    except SyntaxError as exc:  # pragma: no cover
        pytest.fail("无法解析 %s：%s" % (abs_path, exc))


def _callee_name(node):
    """取 Call 节点的被调用名（`a.b.c()` -> "c"，`f()` -> "f"）。"""
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return ""


def _sink_name(node):
    """取 `xxx.append(...)` 里 xxx 的名字，不是 append 调用则返回空串。"""
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr == "append":
        base = fn.value
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            return base.attr
    return ""


def _user_facing_literals(abs_path):
    """抽取**可能流向界面**的字符串字面量，返回 [(行号, 文本)]。

    用 AST 而不是正则/tokenize，是为了精确豁免下面这些
    「中文完全合法」的场景，否则测试会被日志噪声淹没而失去意义：

    - **docstring / 裸字符串表达式**：给开发者看的；
    - **日志调用实参**（`log.info("[app] ...")`）：给开发者看的；
    - **raise / assert 的信息**：给开发者看的；
    - **诊断收集器**（`problems.append("...")`）：最终也是进日志；
    - **argparse 的 help/description**：命令行帮助，不是 GUI。

    剩下的中文字面量，就是真正需要挪进 `ui_text.json` 的界面文案。
    """
    tree = _parse(abs_path)
    exempt = set()

    def mark_subtree(node):
        for n in ast.walk(node):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                exempt.add(id(n))

    for node in ast.walk(tree):
        # 裸字符串表达式：模块/类/函数 docstring，以及字段后的说明串
        if (isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            exempt.add(id(node.value))
        elif isinstance(node, ast.Raise):
            mark_subtree(node)
        elif isinstance(node, ast.Assert):
            if node.msg is not None:
                mark_subtree(node.msg)
        elif isinstance(node, ast.Call):
            if _callee_name(node) in _DIAG_CALLS or _sink_name(node) in _DIAG_SINKS:
                mark_subtree(node)
            for kw in node.keywords:
                if kw.arg in _CLI_KWARGS:
                    mark_subtree(kw.value)

    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in exempt:
            out.append((n.lineno, n.value))
    return out


def _hits(text, words):
    """返回 text 中命中的禁用词列表。"""
    return [w for w in words if w in text]


# ---------------------------------------------------------------------------
# 1. ui_text.json 文案扫描
# ---------------------------------------------------------------------------

def test_ui_text_has_no_guilt_or_fomo_words():
    """ui_text.json 全部文案不得含 guilt / FOMO / 催促词（L6）。"""
    with open(_UI_TEXT, "r", encoding="utf-8") as f:
        data = json.load(f)

    problems = []
    for jpath, value in _walk_json_strings(data):
        if jpath.startswith("_meta"):
            continue  # _meta.note 本身在描述这条规则，会自我命中
        if GUILT_ALLOWLIST.get(jpath) == value:
            continue
        bad = _hits(value, GUILT_WORDS)
        if bad:
            problems.append("%s = %r 命中 %s" % (jpath, value, bad))

    assert not problems, "ui_text.json 违反 L6：\n" + "\n".join(problems)


def test_ui_text_offline_copy_is_guilt_free():
    """离线卡片文案必须明确「无惩罚」，且不得暗示玩家做错了什么（L7）。"""
    with open(_UI_TEXT, "r", encoding="utf-8") as f:
        data = json.load(f)
    card = data["offline_card"]

    # 结构完整性：这些键 offline_card.py 会直接取
    for key in ("title", "body", "earned", "sub", "elapsed", "variants", "button"):
        assert key in card, "offline_card 缺少键 %s" % key

    assert card["variants"], "offline_card.variants 不能为空"
    # 收益为 0 时的空状态必须存在（不能弹一张空卡片让人以为坏了）
    assert data["empty_states"]["offline_zero"], "缺少 empty_states.offline_zero"

    # 领取按钮必须是"接受"语气，不能是"立即领取/限时领取"这类催促
    assert not _hits(card["button"], GUILT_WORDS)


def test_ui_text_all_keys_used_by_code_exist():
    """代码里 text.get(...) 引用的键必须在 ui_text.json 里真实存在。

    防止界面上出现 `??hints.xxx??` 这类占位符 —— 用户看到的是 bug，
    而 L6 的前提是文案本身可信。
    """
    with open(_UI_TEXT, "r", encoding="utf-8") as f:
        data = json.load(f)

    flat = {k for k, _ in _walk_json_strings(data)}
    # 列表项 a.b[0] 也要能命中 a.b
    flat |= {re.sub(r"\[\d+\]$", "", k) for k in flat}

    pat = re.compile(r"""(?:self\.)?(?:ui)?text\.(?:get|pick)\(\s*["']([a-z_0-9.]+)["']""", re.I)
    missing = []
    for rel, ap in _iter_py_files():
        with open(ap, "r", encoding="utf-8") as f:
            src = f.read()
        for key in pat.findall(src):
            if key.endswith("."):
                # 动态拼接键，如 text.get("tabs." + key)：只校验前缀存在
                if not any(k.startswith(key) for k in flat):
                    missing.append("%s 引用的文案前缀 %r 下没有任何键" % (rel, key))
            elif key not in flat:
                missing.append("%s 引用了不存在的文案键 %r" % (rel, key))

    assert not missing, "文案键缺失：\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# 2. 源码中文字面量扫描
# ---------------------------------------------------------------------------

def test_no_chinese_literals_in_source():
    """面向用户的字符串字面量中不得出现中文（豁免见 `_user_facing_literals`）。

    中文只能待在三个地方：注释 / docstring（给开发者看）、日志与异常
    （给开发者看）、`ui_text.json`（给用户看）。写死在界面代码里的中文
    既改不动也测不到，还会绕过本文件的 L6 词表审查 —— 这才是真正的风险。
    """
    problems = []
    for rel, ap in _iter_py_files(_GUI_DIRS, _GUI_FILES):
        for lineno, text in _user_facing_literals(ap):
            if _CJK_RE.search(text):
                problems.append("%s:%d %r" % (rel, lineno, text[:90]))

    assert not problems, (
        "源码中出现面向用户的中文字面量（应移入 data/ui_text.json）：\n"
        + "\n".join(problems)
    )


def test_domain_layer_is_gui_free():
    """`fishtank/` 不得 import 任何 GUI 模块 —— 这是上一条测试的前提。

    领域内核必须能在无显示环境里跑（`--headless` / pytest / XJ380 对偶），
    同时这条边界也顺带证明了：`fishtank/` 里的中文字面量物理上不可能
    变成界面文案，所以上一条测试只扫 `pyapp/` 是充分的。
    """
    banned = {"tkinter", "pyapp"}
    problems = []
    for rel, ap in _iter_py_files(("fishtank",), ()):
        for node in ast.walk(_parse(ap)):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in banned:
                        problems.append("%s:%d import %s" % (rel, node.lineno, a.name))
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in banned:
                    problems.append("%s:%d from %s" % (rel, node.lineno, node.module))

    assert not problems, "领域层泄漏了 GUI 依赖：\n" + "\n".join(problems)


def test_no_guilt_words_anywhere_in_source():
    """源码任何位置（含注释）都不得出现催促话术成品句。

    只查最露骨的几个成句，避免误伤技术性注释
    （比如注释里写"水质会损失"是在描述数值，不是 UI 文案）。
    """
    hard_banned = ("快来看看", "别忘了喂", "你的鱼饿了", "错过了", "限时活动", "手慢无")
    problems = []
    for rel, ap in _iter_py_files():
        with open(ap, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                bad = _hits(line, hard_banned)
                if bad:
                    problems.append("%s:%d 命中 %s" % (rel, i, bad))

    assert not problems, "源码含催促话术：\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# 3. 打扰型 API 扫描（P0-23）
# ---------------------------------------------------------------------------

def test_no_desktop_notification_api():
    """代码中不得导入或调用任何桌面通知 / 提示音 API（P0-23 零打扰）。

    用 AST 判定「真的 import 了 / 真的调用了」，而不是文本搜索 ——
    否则 docstring 里写一句"本文件不使用 win10toast"都会误报，
    最后逼着开发者删注释来讨好测试，规则就废了。
    """
    problems = []
    for rel, ap in _iter_py_files():
        tree = _parse(ap)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    if top in NOTIFY_MODULES:
                        problems.append("%s:%d 导入了 %s" % (rel, node.lineno, a.name))
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if top in NOTIFY_MODULES:
                    problems.append("%s:%d 导入自 %s" % (rel, node.lineno, node.module))
            elif isinstance(node, ast.Call):
                name = _callee_name(node)
                if name in NOTIFY_CALLS:
                    problems.append("%s:%d 调用了 %s()" % (rel, node.lineno, name))

    assert not problems, "出现打扰型 API：\n" + "\n".join(problems)


def test_sound_defaults_to_false():
    """`balance.ui.sound`（或 settings 默认）必须为 false（P0-23）。"""
    with open(os.path.join(_DATA_DIR, "balance.json"), "r", encoding="utf-8") as f:
        bal = json.load(f)

    ui = bal.get("ui", {})
    if "sound" in ui:
        assert ui["sound"] is False, "balance.ui.sound 必须默认 false"

    from fishtank.state import GameState
    fields = GameState.__dataclass_fields__
    assert "settings" in fields, "GameState 缺少 settings"


def test_only_offline_card_pops_up_actively():
    """全程只允许离线卡片一次主动弹窗：其余 Toplevel 必须由用户操作触发。

    做法：统计 pyapp 下 `Toplevel(` 的出现位置，要求它们只出现在
    `offline_card.py`（离线卡片）与 `panel_window.py`（用户点击打开）中。
    """
    allowed = {"pyapp/offline_card.py", "pyapp/panel_window.py"}
    found = set()
    for rel, ap in _iter_py_files():
        with open(ap, "r", encoding="utf-8") as f:
            for line in f:
                s = line.lstrip()
                if s.startswith("#"):
                    continue
                if "Toplevel(" in s:
                    found.add(rel)

    extra = found - allowed
    assert not extra, "非预期的弹窗来源：%s" % sorted(extra)


# ---------------------------------------------------------------------------
# 4. 懒人准则的结构性检查
# ---------------------------------------------------------------------------

def test_no_death_or_sickness_vocabulary_in_data():
    """三份数据表都不得出现「死亡 / 生病」词汇（L1：鱼永不死亡、不生病）。"""
    death_words = ("死亡", "死掉", "病死", "患病", "生病", "尸体", "消失不见")
    problems = []
    for fn in ("balance.json", "fish_data.json", "decor_data.json", "ui_text.json"):
        p = os.path.join(_DATA_DIR, fn)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        for jpath, value in _walk_json_strings(data):
            bad = _hits(value, death_words)
            if bad:
                problems.append("%s :: %s = %r 命中 %s" % (fn, jpath, value, bad))

    assert not problems, "数据表违反 L1：\n" + "\n".join(problems)


def test_hints_are_all_neutral_or_positive():
    """`hints.*` 是最容易滑向催促的分区，逐条确认语气中性或正向。"""
    with open(_UI_TEXT, "r", encoding="utf-8") as f:
        hints = json.load(f)["hints"]

    problems = []
    for k, v in hints.items():
        bad = _hits(v, GUILT_WORDS)
        if bad:
            problems.append("hints.%s = %r 命中 %s" % (k, v, bad))
        # 感叹号密度：超过 1 个说明在制造紧迫感
        if v.count("！") + v.count("!") > 1:
            problems.append("hints.%s 感叹号过多：%r" % (k, v))

    assert not problems, "hints 违反 L6：\n" + "\n".join(problems)
