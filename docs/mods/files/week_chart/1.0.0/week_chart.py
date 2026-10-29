"""7日間グラフ

直近1週間の作業時間を棒グラフで表示します。
"""

from datetime import date, timedelta
import tkinter as tk

MOD_INFO = {
    "name": "7日間グラフ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "直近7日間の作業時間を棒グラフで表示します。目標の線も引きます。（記録はこの MOD を入れた日から）",
    "api": 1,
}

W, H, BOTTOM = 380, 120, 18
WEEKDAYS = "月火水木金土日"


def setup(api):
    api.data.setdefault("days", {})
    s = {"n": 0, "goal": 0}
    w = {}

    def build(frame):
        w["c"] = tk.Canvas(frame, width=W, height=H, bg=api.colors["bg"], highlightthickness=0)
        w["c"].pack(anchor="w")
        render()

    def render():
        c = w.get("c")
        if not (c and c.winfo_exists()):
            return
        c.delete("all")
        days = [date.today() - timedelta(days=6 - i) for i in range(7)]
        vals = [api.data["days"].get(d.isoformat(), 0) for d in days]
        top = max(vals + [s["goal"], 3600])
        bw = W / 7
        for i, (d, v) in enumerate(zip(days, vals)):
            x = i * bw + bw * 0.2
            bh = (H - BOTTOM - 14) * v / top
            color = api.colors["green"] if s["goal"] and v >= s["goal"] else api.colors["accent"]
            c.create_rectangle(x, H - BOTTOM - bh, x + bw * 0.6, H - BOTTOM, fill=color, outline="")
            c.create_text(x + bw * 0.3, H - BOTTOM - bh - 7, text=f"{v / 3600:.1f}h",
                          fill=api.colors["sub"], font=("Segoe UI", 7))
            c.create_text(x + bw * 0.3, H - BOTTOM / 2, text=WEEKDAYS[d.weekday()],
                          fill=api.colors["text"], font=("Segoe UI", 8, "bold" if i == 6 else "normal"))
        if s["goal"]:
            gy = H - BOTTOM - (H - BOTTOM - 14) * s["goal"] / top
            c.create_line(0, gy, W, gy, fill=api.colors["orange"], dash=(4, 3))

    @api.on("tick")
    def tick(status):
        api.data["days"][date.today().isoformat()] = status["today_sec"]
        s["goal"] = status["goal_min"] * 60
        s["n"] += 1
        if s["n"] % 60 == 1:
            api.save_data()
            render()

    api.add_panel(build, title="7日間の作業時間")


def teardown(api):
    api.save_data()
