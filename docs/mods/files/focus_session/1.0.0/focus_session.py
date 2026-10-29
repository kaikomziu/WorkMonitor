"""集中セッション計測

休憩をはさまずに続いた作業（セッション）の長さを測り、最長記録を残します。
"""

from datetime import date
from tkinter import ttk

MOD_INFO = {
    "name": "集中セッション計測",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "休憩なしで続いた作業の長さを測ります。今日と歴代の最長記録を表示し、更新したら通知します。",
    "api": 1,
}


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    api.data.setdefault("best", 0)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "today_best": 0, "count": 0})
    s = {"cur": 0, "last": None, "notified": False}
    w = {}

    def build(frame):
        w["cur"] = ttk.Label(frame, font=("Segoe UI", 14, "bold"))
        w["cur"].pack(anchor="w")
        w["rec"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["rec"].pack(anchor="w")
        render()

    def render():
        if not (w.get("cur") and w["cur"].winfo_exists()):
            return
        w["cur"].configure(text=f"今のセッション: {fmt(s['cur'])}")
        w["rec"].configure(text=f"今日の最長 {fmt(api.data['today_best'])} · 歴代最長 {fmt(api.data['best'])}"
                                f" · 今日のセッション {api.data['count']} 回")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["cur"] += status["today_sec"] - last
        if s["cur"] > api.data["today_best"]:
            api.data["today_best"] = s["cur"]
        if s["cur"] > api.data["best"] and s["cur"] >= 600:
            api.data["best"] = s["cur"]
            if not s["notified"]:
                s["notified"] = True
                api.notify("🏆 集中セッションの歴代最長記録を更新中！")
        render()

    @api.on("state_change")
    def changed(old, new, status):
        if new == "idle" and s["cur"] > 0:
            if s["cur"] >= 60:
                api.data["count"] += 1
                api.log(f"セッション終了: {fmt(s['cur'])}")
            s["cur"] = 0
            s["notified"] = False
            api.save_data()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "today_best": 0, "count": 0})
        s.update({"cur": 0, "last": None})
        api.save_data()

    api.add_panel(build, title="集中セッション")


def teardown(api):
    api.save_data()
