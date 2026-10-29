"""メモ帳

メイン画面にメモ欄を置きます。日付ごとに自動で保存され、前の日のメモも見返せます。
"""

from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "メモ帳",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "メイン画面のメモ欄。書いた内容は日付ごとに自動保存され、◀ ▶ で前の日のメモを見られます。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("memos", {})       # 日付 → 本文
    s = {"day": date.today(), "timer": None}
    w = {}

    def key():
        return s["day"].isoformat()

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Button(top, text="◀", width=3, command=lambda: move(-1)).pack(side="left")
        w["title"] = ttk.Label(top)
        w["title"].pack(side="left", padx=8)
        ttk.Button(top, text="▶", width=3, command=lambda: move(1)).pack(side="left")
        w["t"] = tk.Text(frame, height=5, wrap="word", font=("Segoe UI", 10), relief="flat",
                         bg="#2a2f3a" if api.dark else "#ffffff", fg=api.colors["text"],
                         insertbackground=api.colors["text"])
        w["t"].pack(fill="x", pady=4)
        w["t"].bind("<KeyRelease>", lambda e: schedule_save())
        load()

    def load():
        if not (w.get("t") and w["t"].winfo_exists()):
            return
        w["title"].configure(text=f"{s['day']:%Y/%m/%d}" + ("（今日）" if s["day"] == date.today() else ""))
        w["t"].delete("1.0", "end")
        w["t"].insert("1.0", api.data["memos"].get(key(), ""))

    def save():
        s["timer"] = None
        if not (w.get("t") and w["t"].winfo_exists()):
            return
        text = w["t"].get("1.0", "end-1c")
        if text.strip():
            api.data["memos"][key()] = text
        else:
            api.data["memos"].pop(key(), None)
        api.save_data()

    def schedule_save():
        # 打つたびに保存しないよう、手が止まって1秒後に保存
        if s["timer"]:
            api.cancel(s["timer"])
        s["timer"] = api.after(1000, save)

    def move(d):
        if s["timer"]:
            api.cancel(s["timer"])
            save()
        if s["day"] + timedelta(days=d) <= date.today():
            s["day"] += timedelta(days=d)
        load()

    @api.on("day_change")
    def new_day(day):
        if s["timer"]:
            api.cancel(s["timer"])
            save()
        s["day"] = date.today()
        load()

    api.add_panel(build, title="メモ")


def teardown(api):
    api.save_data()
