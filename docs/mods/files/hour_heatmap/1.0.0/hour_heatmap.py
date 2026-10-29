"""時間帯ヒートマップ

何時台に作業が多いかを、24本のマスの濃さで表示します（今日と、これまでの合計）。
"""

from datetime import date, datetime
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "時間帯ヒートマップ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "0〜23時のどの時間帯に作業しているかを色の濃さで表示します。今日の分と累計の2段です。",
    "api": 1,
}

CELL, GAP, LEFT = 15, 2, 34


def mix(c1, c2, t):
    """2つの色 #rrggbb を t（0〜1）で混ぜる"""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def setup(api):
    api.data.setdefault("total", [0] * 24)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "today": [0] * 24})
    s = {"last": None, "n": 0}
    w = {}

    def build(frame):
        width = LEFT + 24 * (CELL + GAP)
        w["c"] = tk.Canvas(frame, width=width, height=2 * (CELL + GAP) + 16, bg=api.colors["bg"],
                           highlightthickness=0)
        w["c"].pack(anchor="w")
        render()

    def row(c, y, values, label):
        top = max(values) or 1
        base = "#2a2f3a" if api.dark else "#e9ecf2"
        c.create_text(0, y + CELL / 2, text=label, anchor="w", fill=api.colors["sub"], font=("Segoe UI", 8))
        for h, v in enumerate(values):
            x = LEFT + h * (CELL + GAP)
            color = mix(base, api.colors["accent"], v / top) if v else base
            c.create_rectangle(x, y, x + CELL, y + CELL, fill=color, outline="")

    def render():
        c = w.get("c")
        if not (c and c.winfo_exists()):
            return
        c.delete("all")
        row(c, 0, api.data["today"], "今日")
        row(c, CELL + GAP, api.data["total"], "累計")
        for h in range(0, 24, 3):
            c.create_text(LEFT + h * (CELL + GAP), 2 * (CELL + GAP) + 7, text=str(h), anchor="w",
                          fill=api.colors["sub"], font=("Segoe UI", 7))

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            d = status["today_sec"] - last
            h = datetime.now().hour
            api.data["today"][h] += d
            api.data["total"][h] += d
        s["n"] += 1
        if s["n"] % 60 == 0:
            api.save_data()
            render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "today": [0] * 24})
        s["last"] = None
        api.save_data()
        render()

    api.add_panel(build, title="時間帯ヒートマップ")


def teardown(api):
    api.save_data()
