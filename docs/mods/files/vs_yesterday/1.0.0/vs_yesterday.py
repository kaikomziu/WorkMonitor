"""自分との勝負

昨日の同じ時刻までの作業時間と比べて、今日は進んでいるか遅れているかを表示します。
"""

from datetime import date, datetime, timedelta
from tkinter import ttk

MOD_INFO = {
    "name": "自分との勝負",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "昨日の同じ時刻と今日の作業時間を比べて、リードしているか表示します。オーバーレイにも出します。",
    "api": 1,
}

STEP = 5   # 何分ごとに記録するか


def fmt(sec):
    h, m = divmod(abs(int(sec)) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    api.data.setdefault("timeline", {})     # 日付 → {その日の分(5分きざみ): 作業秒数}
    s = {"diff": None, "n": 0}
    w = {}

    def slot(now):
        return str((now.hour * 60 + now.minute) // STEP * STEP)

    def yesterday_at(now):
        y = api.data["timeline"].get((now.date() - timedelta(days=1)).isoformat())
        if not y:
            return None
        cur = int(slot(now))
        past = [int(k) for k in y if int(k) <= cur]
        return y[str(max(past))] if past else 0

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 12, "bold"))
        w["l"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        d = s["diff"]
        if d is None:
            w["l"].configure(text="昨日の記録がまだありません（明日から比べられます）")
        elif d >= 0:
            w["l"].configure(text=f"🏃 昨日の自分に {fmt(d)} リード！", foreground=api.colors["green"])
        else:
            w["l"].configure(text=f"🐢 昨日の自分より {fmt(d)} 遅れています", foreground=api.colors["orange"])

    @api.on("tick")
    def tick(status):
        now = datetime.now()
        today = api.data["timeline"].setdefault(now.date().isoformat(), {})
        today[slot(now)] = status["today_sec"]
        y = yesterday_at(now)
        s["diff"] = None if y is None else status["today_sec"] - y
        s["n"] += 1
        if s["n"] % 60 == 0:
            keep = {(date.today() - timedelta(days=i)).isoformat() for i in range(3)}
            api.data["timeline"] = {k: v for k, v in api.data["timeline"].items() if k in keep}
            api.save_data()
        if s["n"] % 5 == 0:
            render()

    @api.filter("overlay_text")
    def overlay(text):
        d = s["diff"]
        if d is None:
            return text
        return f"{text} · {'▲' if d >= 0 else '▼'}{fmt(d)}"

    api.add_panel(build, title="昨日の自分と勝負")


def teardown(api):
    api.save_data()
