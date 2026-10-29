"""作業の森

作業30分ごとに木が1本ずつ生えて、森ができていきます。休まず続けるほど大きな木に。
"""

import random
from datetime import date
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "作業の森",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業30分ごとに木が1本生えます。休憩なしで続けた分は大きな木に。今日の森と、累計の本数を表示します。",
    "api": 1,
}

TREE_SEC = 30 * 60
SMALL = ["🌱", "🌿", "🌷", "🍀"]
BIG = ["🌲", "🌳", "🌴", "🎄"]


def setup(api):
    api.data.setdefault("total", 0)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "trees": []})
    s = {"sec": 0, "streak": 0, "last": None}
    w = {}

    def build(frame):
        w["t"] = tk.Text(frame, height=3, width=40, font=("Segoe UI Emoji", 14), relief="flat",
                         bg=api.colors["bg"], fg=api.colors["text"], wrap="char", cursor="arrow")
        w["t"].pack(fill="x")
        w["l"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["l"].pack(anchor="w")
        render()

    def render():
        if not (w.get("t") and w["t"].winfo_exists()):
            return
        w["t"].configure(state="normal")
        w["t"].delete("1.0", "end")
        w["t"].insert("end", "".join(api.data["trees"]) or "（まだ木がありません）")
        w["t"].configure(state="disabled")
        left = (TREE_SEC - s["sec"]) // 60
        w["l"].configure(text=f"今日 {len(api.data['trees'])} 本 · 累計 {api.data['total']} 本 · 次の木まで {left}分")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= TREE_SEC:
            s["sec"] -= TREE_SEC
            s["streak"] += 1
            tree = random.choice(BIG if s["streak"] >= 2 else SMALL)
            api.data["trees"].append(tree)
            api.data["total"] += 1
            api.save_data()
            api.notify(f"{tree} 木が生えました！（今日 {len(api.data['trees'])} 本目）")
            render()
        elif status["today_sec"] % 60 == 0:
            render()

    @api.on("state_change")
    def changed(old, new, status):
        if new == "idle":
            s["streak"] = 0

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "trees": []})
        s.update({"sec": 0, "streak": 0, "last": None})
        api.save_data()
        render()

    api.add_panel(build, title="作業の森")
