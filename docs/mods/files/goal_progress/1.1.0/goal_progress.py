"""目標の進捗バー

1日の目標に対して、今どこまで来ているかをメイン画面のプログレスバーで表示します。

1.1.0: 色つきのバー・25%ごとの区切り通知・「今日の残り時間で必要なペース」を追加
"""

from datetime import date, datetime
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "目標の進捗バー",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "1日の目標に対する達成度を色つきのバーで表示します。25%ごとに通知し、寝るまで（24時）に必要なペースも出します。",
    "api": 1,
}

H = 16


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "quarter": None})
    w = {}

    def build(frame):
        w["c"] = tk.Canvas(frame, height=H, bg=api.colors["bg"], highlightthickness=0)
        w["c"].pack(fill="x")
        w["l"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["l"].pack(anchor="w", pady=(4, 0))
        w["c"].bind("<Configure>", lambda e: render(api.status()))
        render(api.status())

    def render(status):
        c = w.get("c")
        if not (c and c.winfo_exists()):
            return
        c.delete("all")
        width = max(c.winfo_width(), 50)
        goal = status["goal_min"] * 60
        c.create_rectangle(0, 0, width, H, fill="#2a2f3a" if api.dark else "#e9ecf2", outline="")
        if not goal:
            w["l"].configure(text="目標が設定されていません（WorkMonitor の設定で決められます）")
            return
        pct = min(1, status["today_sec"] / goal)
        color = api.colors["green"] if pct >= 1 else api.colors["accent"] if pct >= 0.5 else api.colors["orange"]
        c.create_rectangle(0, 0, width * pct, H, fill=color, outline="")
        for q in (0.25, 0.5, 0.75):
            c.create_line(width * q, 0, width * q, H, fill=api.colors["bg"])
        c.create_text(width / 2, H / 2, text=f"{pct * 100:.0f}%", fill="#ffffff" if pct > 0.55 else api.colors["text"],
                      font=("Segoe UI", 8, "bold"))
        if pct >= 1:
            w["l"].configure(text=f"🎉 達成！ {fmt(status['today_sec'])} / {fmt(goal)}")
            return
        rest = goal - status["today_sec"]
        now = datetime.now()
        left_today = (24 - now.hour) * 3600 - now.minute * 60
        pace = rest / max(left_today, 1) * 60       # 1時間あたり何分の作業が必要か
        w["l"].configure(text=f"あと {fmt(rest)} · 24時までに達成するには 1時間あたり {pace:.0f}分のペース")

    @api.on("tick")
    def tick(status):
        goal = status["goal_min"] * 60
        if goal:
            q = min(4, status["today_sec"] * 4 // goal)
            if api.data["quarter"] is None:       # 起動直後は今の値から
                api.data["quarter"] = q
            if 0 < q < 4 and q > api.data["quarter"]:
                api.notify(f"📈 目標の {q * 25}% まで来ました！")
            if q != api.data["quarter"]:
                api.data["quarter"] = q
                api.save_data()
        render(status)

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "quarter": 0})
        api.save_data()

    api.add_panel(build, title="目標の進捗")
