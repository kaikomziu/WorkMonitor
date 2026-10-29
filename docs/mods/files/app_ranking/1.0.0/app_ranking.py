"""アプリのランキング

今週・今月・ぜんぶ の期間で、よく使ったアプリのトップ5を表示します。
"""

from datetime import date, timedelta
from tkinter import ttk

MOD_INFO = {
    "name": "アプリのランキング",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "今週・今月・累計でよく使ったアプリのトップ5を表示します（記録はこの MOD を入れた日から）。",
    "api": 1,
}

MEDALS = ["🥇", "🥈", "🥉", "4.", "5."]


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    api.data.setdefault("days", {})       # 日付 → {表示名: 秒}
    api.data.setdefault("range", "week")
    s = {"n": 0}
    w = {}

    def since():
        t = date.today()
        if api.data["range"] == "week":
            return (t - timedelta(days=t.weekday())).isoformat()
        if api.data["range"] == "month":
            return t.replace(day=1).isoformat()
        return ""

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        for key, name in (("week", "今週"), ("month", "今月"), ("all", "累計")):
            ttk.Button(top, text=name, width=6, command=lambda k=key: switch(k)).pack(side="left", padx=1)
        w["l"] = ttk.Label(frame, justify="left", font=("Segoe UI", 10))
        w["l"].pack(anchor="w", pady=4)
        render()

    def switch(key):
        api.data["range"] = key
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        start, total = since(), {}
        for d, apps in api.data["days"].items():
            if d >= start:
                for k, v in apps.items():
                    total[k] = total.get(k, 0) + v
        top = sorted(total.items(), key=lambda kv: -kv[1])[:5]
        name = {"week": "今週", "month": "今月", "all": "累計"}[api.data["range"]]
        lines = [f"【{name}】"] + [f"{MEDALS[i]} {k}  {fmt(v)}" for i, (k, v) in enumerate(top)]
        w["l"].configure(text="\n".join(lines) if top else f"【{name}】まだデータがありません")

    @api.on("tick")
    def tick(status):
        api.data["days"][date.today().isoformat()] = dict(status["today_by_app"])
        s["n"] += 1
        if s["n"] % 60 == 1:
            api.save_data()
            render()

    api.add_panel(build, title="アプリランキング")


def teardown(api):
    api.save_data()
