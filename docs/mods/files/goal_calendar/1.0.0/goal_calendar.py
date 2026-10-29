"""目標カレンダー

月のカレンダーで、目標を達成した日に色を付けます。作業時間が多い日ほど濃くなります。
"""

import calendar
from datetime import date
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "目標カレンダー",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "月のカレンダーに、目標達成した日を緑、作業した日を青で表示します。前後の月も見られます。",
    "api": 1,
}

CELL = 30


def setup(api):
    api.data.setdefault("days", {})     # 日付 → [作業秒数, 目標秒数]
    view = {"y": date.today().year, "m": date.today().month}
    s = {"n": 0}
    w = {}

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Button(top, text="◀", width=3, command=lambda: move(-1)).pack(side="left")
        w["title"] = ttk.Label(top, font=("Segoe UI", 10, "bold"))
        w["title"].pack(side="left", padx=8)
        ttk.Button(top, text="▶", width=3, command=lambda: move(1)).pack(side="left")
        w["c"] = tk.Canvas(frame, width=CELL * 7, height=CELL * 7, bg=api.colors["bg"], highlightthickness=0)
        w["c"].pack(anchor="w", pady=4)
        render()

    def move(d):
        m = view["m"] + d
        view["y"] += (m - 1) // 12
        view["m"] = (m - 1) % 12 + 1
        render()

    def render():
        c = w.get("c")
        if not (c and c.winfo_exists()):
            return
        w["title"].configure(text=f"{view['y']}年 {view['m']}月")
        c.delete("all")
        for i, name in enumerate("月火水木金土日"):
            c.create_text(i * CELL + CELL / 2, CELL / 2, text=name, fill=api.colors["sub"], font=("Segoe UI", 8))
        weeks = calendar.Calendar().monthdayscalendar(view["y"], view["m"])
        empty = "#2a2f3a" if api.dark else "#eef0f4"
        for r, week in enumerate(weeks):
            for col, d in enumerate(week):
                if not d:
                    continue
                key = f"{view['y']}-{view['m']:02d}-{d:02d}"
                sec, goal = api.data["days"].get(key, [0, 0])
                if goal and sec >= goal:
                    color = api.colors["green"]
                elif sec >= 600:
                    color = api.colors["accent"]
                else:
                    color = empty
                x, y = col * CELL + 2, (r + 1) * CELL + 2
                c.create_rectangle(x, y, x + CELL - 4, y + CELL - 4, fill=color, outline="")
                fg = "#ffffff" if color != empty else api.colors["text"]
                bold = "bold" if key == date.today().isoformat() else "normal"
                c.create_text(x + (CELL - 4) / 2, y + (CELL - 4) / 2, text=str(d), fill=fg,
                              font=("Segoe UI", 8, bold))

    @api.on("tick")
    def tick(status):
        api.data["days"][date.today().isoformat()] = [status["today_sec"], status["goal_min"] * 60]
        s["n"] += 1
        if s["n"] % 60 == 1:
            api.save_data()
            render()

    api.add_panel(build, title="目標カレンダー")


def teardown(api):
    api.save_data()
