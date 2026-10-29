"""
test/test_command.py — 命令系统单元测试

测试 CommandParser (别名解析/命令解析) 和 CommandHandler (分发/上下文)。

运行：
    cd D:/allin && python -m allin_engine.test.test_command
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.systems.command import (
    CommandParser, CommandHandler, CommandResult, DEFAULT_ALIASES,
)


# ══════════════════════════════════════════════════════════
# CommandResult 测试
# ══════════════════════════════════════════════════════════

def test_command_result_ok():
    """测试 ok() 快捷创建"""
    r = CommandResult.ok("成功")
    assert r.success is True
    assert r.message == "成功"
    assert bool(r) is True


def test_command_result_fail():
    """测试 fail() 快捷创建"""
    r = CommandResult.fail("失败")
    assert r.success is False
    assert r.message == "失败"
    assert bool(r) is False


def test_command_result_to_dict():
    """测试序列化为字典"""
    r = CommandResult(True, "msg", data={"k": "v"}, next_action="look")
    d = r.to_dict()
    assert d["success"] is True
    assert d["message"] == "msg"
    assert d["data"] == {"k": "v"}
    assert d["next_action"] == "look"


def test_command_result_repr():
    """测试 repr"""
    r = CommandResult.ok("hello")
    assert "OK" in repr(r)
    assert "hello" in repr(r)


# ══════════════════════════════════════════════════════════
# CommandParser 测试
# ══════════════════════════════════════════════════════════

def test_parser_basic():
    """测试基本命令解析"""
    parser = CommandParser()
    cmd, args = parser.parse("look north")
    assert cmd == "look"
    assert args == ["north"]


def test_parser_empty_input():
    """测试空输入"""
    parser = CommandParser()
    cmd, args = parser.parse("")
    assert cmd == ""
    assert args == []


def test_parser_whitespace_only():
    """测试纯空白输入"""
    parser = CommandParser()
    cmd, args = parser.parse("   ")
    assert cmd == ""
    assert args == []


def test_parser_no_args():
    """测试无参数命令"""
    parser = CommandParser()
    cmd, args = parser.parse("look")
    assert cmd == "look"
    assert args == []


def test_parser_multiple_args():
    """测试多参数"""
    parser = CommandParser()
    cmd, args = parser.parse("go north fast")
    assert cmd == "go"
    assert args == ["north", "fast"]


def test_parser_alias_q():
    """测试退出别名 q"""
    parser = CommandParser()
    cmd, _ = parser.parse("q")
    assert cmd == "quit"


def test_parser_alias_exit():
    """测试退出别名 exit"""
    parser = CommandParser()
    cmd, _ = parser.parse("exit")
    assert cmd == "quit"


def test_parser_alias_l():
    """测试 look 别名 l"""
    parser = CommandParser()
    cmd, _ = parser.parse("l")
    assert cmd == "look"


def test_parser_alias_direction():
    """测试方向别名（north → go）"""
    parser = CommandParser()
    cmd, args = parser.parse("north")
    assert cmd == "go"
    assert args == []


def test_parser_direction_with_modifier():
    """测试带修饰词的方向"""
    parser = CommandParser()
    cmd, args = parser.parse("north fast")
    assert cmd == "go"
    assert args == ["fast"]


def test_parser_case_insensitive():
    """测试命令不区分大小写"""
    parser = CommandParser()
    cmd, _ = parser.parse("LOOK")
    assert cmd == "look"
    cmd, _ = parser.parse("Look")
    assert cmd == "look"


def test_parser_unknown_command():
    """测试未识别命令保留原样"""
    parser = CommandParser()
    cmd, args = parser.parse("xyzzy abc")
    assert cmd == "xyzzy"
    assert args == ["abc"]


def test_parser_add_alias():
    """测试动态添加别名"""
    parser = CommandParser()
    parser.add_alias("zz", "sleep")
    cmd, _ = parser.parse("zz")
    assert cmd == "sleep"


def test_parser_remove_alias():
    """测试移除别名"""
    parser = CommandParser()
    assert parser.remove_alias("q") is True
    cmd, _ = parser.parse("q")
    assert cmd == "q"  # 不再被解析为 quit

    assert parser.remove_alias("nonexistent") is False


def test_parser_get_alias():
    """测试查询别名"""
    parser = CommandParser()
    assert parser.get_alias("q") == "quit"
    assert parser.get_alias("nonexistent") is None


def test_parser_aliases_property():
    """测试 aliases 属性返回副本"""
    parser = CommandParser()
    aliases = parser.aliases
    assert "q" in aliases
    # 修改副本不影响内部
    aliases["test"] = "test_cmd"
    assert parser.get_alias("test") is None


def test_parser_parse_with_raw():
    """测试 parse_with_raw 保留原始命令词"""
    parser = CommandParser()
    resolved, args, raw = parser.parse_with_raw("l north")
    assert resolved == "look"
    assert args == ["north"]
    assert raw == "l"


def test_parser_is_quit():
    """测试 is_quit"""
    parser = CommandParser()
    assert parser.is_quit("q") is True
    assert parser.is_quit("exit") is True
    assert parser.is_quit("quit") is True
    assert parser.is_quit("look") is False


def test_parser_custom_aliases():
    """测试构造时传入自定义别名"""
    parser = CommandParser(aliases={"xx": "explode"})
    cmd, _ = parser.parse("xx")
    assert cmd == "explode"
    # 默认别名仍在
    cmd, _ = parser.parse("q")
    assert cmd == "quit"


# ══════════════════════════════════════════════════════════
# CommandHandler 测试
# ══════════════════════════════════════════════════════════

def test_handler_register_and_execute():
    """测试注册并执行命令"""
    handler = CommandHandler()
    handler.register("look", lambda args, ctx: "你看到了一片森林")
    result = handler.execute("look")
    assert result.success is True
    assert result.message == "你看到了一片森林"


def test_handler_unknown_command():
    """测试执行未注册命令"""
    handler = CommandHandler()
    result = handler.execute("unknown_cmd")
    assert result.success is False
    assert "未知命令" in result.message


def test_handler_str_return():
    """测试处理器返回字符串自动包装"""
    handler = CommandHandler()
    handler.register("say", lambda args, ctx: "hello")
    result = handler.execute("say")
    assert result.success is True
    assert result.message == "hello"


def test_handler_none_return():
    """测试处理器返回 None"""
    handler = CommandHandler()
    handler.register("noop", lambda args, ctx: None)
    result = handler.execute("noop")
    assert result.success is True
    assert result.message == ""


def test_handler_command_result_return():
    """测试处理器直接返回 CommandResult"""
    handler = CommandHandler()
    handler.register("custom", lambda args, ctx: CommandResult(False, "故意失败"))
    result = handler.execute("custom")
    assert result.success is False
    assert result.message == "故意失败"


def test_handler_exception_handling():
    """测试处理器异常被捕获"""
    handler = CommandHandler()

    def bad_handler(args, ctx):
        raise ValueError("boom")

    handler.register("bad", bad_handler)
    result = handler.execute("bad")
    assert result.success is False
    assert "ValueError" in result.message
    assert "boom" in result.message


def test_handler_context():
    """测试上下文注入"""
    handler = CommandHandler()
    handler.set_context(world="earth", level=3)

    def look_handler(args, ctx):
        return f"世界: {ctx['world']}, 等级: {ctx['level']}"

    handler.register("look", look_handler)
    result = handler.execute("look")
    assert result.success is True
    assert "earth" in result.message
    assert "3" in result.message


def test_handler_get_context():
    """测试获取上下文值"""
    handler = CommandHandler()
    handler.set_context(key="value")
    assert handler.get_context("key") == "value"
    assert handler.get_context("nonexistent") is None


def test_handler_clear_context():
    """测试清空上下文"""
    handler = CommandHandler()
    handler.set_context(a=1)
    handler.clear_context()
    assert handler.get_context("a") is None


def test_handler_unregister():
    """测试移除处理器"""
    handler = CommandHandler()
    handler.register("look", lambda args, ctx: "ok")
    assert handler.has_handler("look") is True

    assert handler.unregister("look") is True
    assert handler.has_handler("look") is False
    assert handler.unregister("nonexistent") is False


def test_handler_case_insensitive():
    """测试命令名不区分大小写"""
    handler = CommandHandler()
    handler.register("look", lambda args, ctx: "ok")
    result = handler.execute("LOOK")
    assert result.success is True


def test_handler_get_all_commands():
    """测试列出所有命令"""
    handler = CommandHandler()
    handler.register("look", lambda a, c: "")
    handler.register("go", lambda a, c: "")
    cmds = handler.get_all_commands()
    assert "look" in cmds
    assert "go" in cmds


def test_handler_last_result():
    """测试获取最近结果"""
    handler = CommandHandler()
    handler.register("look", lambda a, c: "first")
    handler.execute("look")
    assert handler.last_result is not None
    assert handler.last_result.message == "first"


def test_handler_result_history():
    """测试结果历史"""
    handler = CommandHandler()
    handler.register("a", lambda args, ctx: "1")
    handler.register("b", lambda args, ctx: "2")
    handler.execute("a")
    handler.execute("b")
    assert len(handler.result_history) == 2
