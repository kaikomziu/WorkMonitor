"""作業時間グラフ

直近の作業時間を棒グラフで表示します。

1.1.0: 7日・14日・30日の切り替え・平均の線・合計と平均の表示を追加
"""

from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "7日間グラフ",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "直近7日・14日・30日の作業時間を棒グラフで表示します。目標と平均の線も引きます。（記録はこの MOD を入れた日から）",
    "api": 1,
}

W, H, BOTTOM = 380, 120, 18
WEEKDAYS = "月火水木金土日"


def setup(api):
    api.data.setdefault("days", {})
    api.data.setdefault("span", 7)
    s = {"n": 0, "goal": 0}
    w = {}

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        for n in (7, 14, 30):
            ttk.Button(top, text=f"{n}日", width=5, command=lambda n=n: switch(n)).pack(side="left", padx=1)
        w["sum"] = ttk.Label(top, foreground=api.colors["sub"])
        w["sum"].pack(side="right")
        w["c"] = tk.Canvas(frame, width=W, height=H, bg=api.colors["bg"], highlightthickness=0)
        w["c"].pack(anchor="w", pady=(4, 0))
        render()

    def switch(n):
        api.data["span"] = n
        api.save_data()
        render()

    def render():
        c = w.get("c")
        if not (c and c.winfo_exists()):
            return
        c.delete("all")
        span = api.data["span"]
        days = [date.today() - timedelta(days=span - 1 - i) for i in range(span)]
        vals = [api.data["days"].get(d.isoformat(), 0) for d in days]
        worked = [v for v in vals if v >= 60]
        avg = sum(worked) / len(worked) if worked else 0
        w["sum"].configure(text=f"合計 {sum(vals) / 3600:.1f}h · 平均 {avg / 3600:.1f}h")
        top = max(vals + [s["goal"], 3600])
        bw = W / span
        for i, (d, v) in enumerate(zip(days, vals)):
            x = i * bw + bw * 0.15
            bh = (H - BOTTOM - 14) * v / top
            color = api.colors["green"] if s["goal"] and v >= s["goal"] else api.colors["accent"]
            c.create_rectangle(x, H - BOTTOM - bh, x + bw * 0.7, H - BOTTOM, fill=color, outline="")
            if span == 7:
                c.create_text(x + bw * 0.35, H - BOTTOM - bh - 7, text=f"{v / 3600:.1f}h",
                              fill=api.colors["sub"], font=("Segoe UI", 7))
            if span == 7 or d.weekday() == 0 or i == span - 1:
                label = WEEKDAYS[d.weekday()] if span == 7 else f"{d.month}/{d.day}"
                c.create_text(x + bw * 0.35, H - BOTTOM / 2, text=label, fill=api.colors["text"],
                              font=("Segoe UI", 8 if span == 7 else 7, "bold" if i == span - 1 else "normal"))
        for value, color in ((s["goal"], api.colors["orange"]), (avg, api.colors["sub"])):
            if value:
                y = H - BOTTOM - (H - BOTTOM - 14) * value / top
                c.create_line(0, y, W, y, fill=color, dash=(4, 3))

    @api.on("tick")
    def tick(status):
        api.data["days"][date.today().isoformat()] = status["today_sec"]
        s["goal"] = status["goal_min"] * 60
        s["n"] += 1
        if s["n"] % 60 == 1:
            api.save_data()
            render()

    api.add_panel(build, title="作業時間グラフ")


def teardown(api):
    api.save_data()
