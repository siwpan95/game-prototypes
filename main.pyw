import tkinter as tk
from tkinter import ttk
import pyautogui
import keyboard
import threading
import time

clicking = False
interval = 0.1

def click_loop():
    global clicking, interval
    while clicking:
        pyautogui.click()
        time.sleep(interval)

def toggle_clicking():
    global clicking
    if clicking:
        clicking = False
    else:
        clicking = True
        threading.Thread(target=click_loop, daemon=True).start()

def update_interval():
    global interval
    try:
        cps = float(cps_var.get())
        interval = 1 / cps
    except ValueError:
        pass

# ---------- UI ----------
root = tk.Tk()
root.title("鼠标连点器")
root.geometry("240x140")
root.resizable(False, False)

cps_var = tk.StringVar(value="10")

ttk.Label(root, text="点击频率（次/秒）").pack(pady=8)
ttk.Entry(root, textvariable=cps_var, width=10).pack()
ttk.Button(root, text="确认频率", command=update_interval).pack(pady=8)

ttk.Label(root, text="按 空格键 开始 / 停止").pack(pady=10)

# ---------- 空格键切换 ----------
keyboard.add_hotkey("space", toggle_clicking)

root.mainloop()