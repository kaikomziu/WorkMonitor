"""自己ベスト記録

1日の作業時間の自己ベストを記録し、今日それを超えたら通知します。
"""

from datetime import date
from tkinter import ttk

MOD_INFO = {
    "name": "自己ベスト記録",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "1日の作業時間の自己ベストを記録します。今日の作業がベストを超えた瞬間に通知します。",
    "api": 1,
}


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分"


def setup(api):
    api.data.setdefault("best", 0)
    api.data.setdefault("best_day", "")
    s = {"beat": False, "n": 0, "old": api.data["best"]}
    w = {}

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(anchor="w")
        render(api.status())

    def render(status):
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        gap = s["old"] - status["today_sec"]
        if s["beat"]:
            tail = "🔥 今日が新記録！"
        elif s["old"]:
            tail = f"ベストまであと {fmt(gap)}"
        else:
            tail = "まだ記録がありません"
        w["l"].configure(text=f"🏆 自己ベスト {fmt(api.data['best'])}（{api.data['best_day'] or '-'}） · {tail}")

    @api.on("tick")
    def tick(status):
        t = status["today_sec"]
        if t > api.data["best"]:
            api.data["best"] = t
            api.data["best_day"] = date.today().isoformat()
            if not s["beat"] and s["old"] > 0:
                s["beat"] = True
                api.notify(f"🏆 自己ベスト更新！ これまでの記録 {fmt(s['old'])} を超えました")
        s["n"] += 1
        if s["n"] % 60 == 0:
            api.save_data()
        if s["n"] % 10 == 0:
            render(status)

    @api.on("day_change")
    def new_day(day):
        s.update({"beat": False, "old": api.data["best"]})
        api.save_data()

    api.add_panel(build, title="自己ベスト")


def teardown(api):
    api.save_data()
