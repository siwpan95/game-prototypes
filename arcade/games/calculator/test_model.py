"""Unit tests for CalculatorModel (MVVM version) — no GUI needed."""
import sys
import os

# 指向 cal/ 目录，使 model 和 utils 可被 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import CalculatorModel


def push_str(model, s):
    for ch in s:
        model.push(ch)


def eq(model):
    model.push("=")
    return model.display_text


# Test 1: basic arithmetic
m = CalculatorModel()
push_str(m, "2+3")
r = eq(m)
assert r == "5", f"Test1 failed: {r}"
print("Test1 PASS: 2+3=5")

# Test 2: division by zero => fool
m = CalculatorModel()
push_str(m, "1÷0")
r = eq(m)
assert r == "fool", f"Test2 failed: {r}"
print("Test2 PASS: 1÷0=fool")

# Test 3: 520=1314 (easter egg)
m = CalculatorModel()
push_str(m, "520")
r = eq(m)
assert r == "1314", f"Test3 failed: {r}"
print("Test3 PASS: 520=1314")

# Test 4: 520+0=520 (no easter egg, normal calc)
m = CalculatorModel()
push_str(m, "520+0")
r = eq(m)
assert r == "520", f"Test4 failed: {r}"
print("Test4 PASS: 520+0=520")

# Test 5: triple-same digit triggers reset
m = CalculatorModel()
push_str(m, "11")
m.push("1")
assert m.last_action == "reset", f"Test5 failed: {m.last_action}"
print("Test5 PASS: 111 -> reset")

# Test 6: three backspaces -> quit
m = CalculatorModel()
m.push("←"); m.push("←")
m.push("←")
assert m.last_action == "quit", f"Test6 failed: {m.last_action}"
print("Test6 PASS: <<< -> quit")

# Test 7: triple consecutive equals -> shuffle
m = CalculatorModel()
m.push("="); m.push("=")
m.push("=")
assert m.last_action == "shuffle", f"Test7 failed: {m.last_action}"
print("Test7 PASS: === -> shuffle")

# Test 8: max 4 digit-key presses total
m = CalculatorModel()
push_str(m, "1+2+34")   # digit presses: 1,2,3,4 = 4 total, at limit
before = m.expression
m.push("5")             # 5th digit press -> blocked
assert m.expression == before, f"Test8 failed, expr={m.expression}"
print("Test8 PASS: 5th digit keypress blocked")

# Test 9: max 13 chars
m = CalculatorModel()
expr12 = "(1+2)×(3-4)+"   # 12 chars
push_str(m, expr12)
assert len(m.expression) == 12
m.push("+")   # 13th char -> allowed
assert len(m.expression) == 13
m.push("-")   # 14th -> blocked
assert len(m.expression) == 13, f"Test9 failed: len={len(m.expression)}"
print(f"Test9 PASS: expression capped at 13 chars ({m.expression!r})")

# Test 10: 911=fbi warning
m = CalculatorModel()
push_str(m, "911")
r = eq(m)
assert r == "fbi warning", f"Test10 failed: {r}"
print("Test10 PASS: 911=fbi warning")

# Test 11: 1÷3 decimal <= 6 places
m = CalculatorModel()
push_str(m, "1÷3")
r = eq(m)
if "." in r:
    assert len(r.split(".")[1]) <= 6, f"Test11 failed: {r}"
print(f"Test11 PASS: 1/3={r} (<=6 decimals)")

# Test 12: triple-same then = gives 0
m = CalculatorModel()
push_str(m, "333")   # reset triggered
r = eq(m)
assert r == "0", f"Test12 failed: {r}"
print("Test12 PASS: after reset, =0")

# Test 13: 1314=520
m = CalculatorModel()
push_str(m, "1314")
r = eq(m)
assert r == "520", f"Test13 failed: {r}"
print("Test13 PASS: 1314=520")

# Test 14: 520+= is fool (incomplete expression)
m = CalculatorModel()
push_str(m, "520+")
r = eq(m)
assert r == "fool", f"Test14 failed: {r}"
print("Test14 PASS: 520+= is fool")

# Test 15: backspace streak resets on non-backspace input
m = CalculatorModel()
m.push("←"); m.push("←")   # streak=2
m.push("1")                  # non-backspace resets streak
m.push("←"); m.push("←")   # streak=2 again
m.push("←")                  # streak=3 -> quit
assert m.last_action == "quit", f"Test15 failed: {m.last_action}"
print("Test15 PASS: backspace streak resets on other input")

# Test 16: three consecutive = triggers shuffle
m = CalculatorModel()
push_str(m, "1")
m.push("=")   # streak=1
m.push("=")   # streak=2
m.push("=")   # streak=3 -> shuffle
assert m.last_action == "shuffle", f"Test16 failed: {m.last_action}"
print("Test16 PASS: three consecutive = triggers shuffle")

# Test 17: Model notifies observers on every push
m = CalculatorModel()
calls = []
m.add_observer(lambda: calls.append(m.last_action))
push_str(m, "1+2")
assert len(calls) == 3, f"Test17 failed: calls={calls}"
print("Test17 PASS: observer called on every push")

# Test 18: digit_limit flag set correctly
m = CalculatorModel()
push_str(m, "1+234")   # 4 digit presses
assert m.digit_limit is True, f"Test18 failed: digit_limit={m.digit_limit}"
m.push("←")            # delete one digit, recalc
assert m.digit_limit is False, f"Test18b failed: digit_limit={m.digit_limit}"
print("Test18 PASS: digit_limit flag toggles correctly")

print("\nAll 18 tests passed!")
