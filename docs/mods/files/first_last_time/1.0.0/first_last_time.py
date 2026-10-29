"""始業・終業時刻

今日最初に作業を始めた時刻と、最後に作業した時刻を記録して表示します。
"""

from datetime import date, datetime
from tkinter import ttk

MOD_INFO = {
    "name": "始業・終業時刻",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "今日の最初の作業開始時刻と最後に作業した時刻、その間の長さを表示します。過去30日分を保存します。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("days", {})       # 日付 → [最初, 最後]（"HH:MM"）
    s = {"n": 0}
    w = {}

    def today():
        return api.data["days"].get(date.today().isoformat())

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 12))
        w["l"].pack(anchor="w")
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        t = today()
        if not t:
            w["l"].configure(text="今日はまだ作業していません")
            w["sub"].configure(text="")
            return
        a, b = (datetime.strptime(x, "%H:%M") for x in t)
        h, m = divmod(int((b - a).total_seconds()) // 60, 60)
        w["l"].configure(text=f"🌅 {t[0]} 〜 🌙 {t[1]}")
        w["sub"].configure(text=f"始業から {h}時間{m:02d}分")

    @api.on("tick")
    def tick(status):
        if status["state"] != "working":
            return
        now = datetime.now().strftime("%H:%M")
        rec = api.data["days"].setdefault(date.today().isoformat(), [now, now])
        rec[1] = now
        s["n"] += 1
        if s["n"] % 60 == 1:
            keys = sorted(api.data["days"])[-30:]
            api.data["days"] = {k: api.data["days"][k] for k in keys}
            api.save_data()
            render()

    @api.on("day_change")
    def new_day(day):
        render()

    api.add_panel(build, title="始業・終業")


def teardown(api):
    api.save_data()
