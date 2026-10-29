"""週間目標

1週間（月曜はじまり）の合計作業時間に目標を決めて、進み具合を表示します。
"""

from datetime import date, timedelta
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "週間目標",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "月曜〜日曜の合計作業時間に目標を設定し、プログレスバーで表示します。達成したら通知します。",
    "api": 1,
}


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分"


def setup(api):
    api.data.setdefault("goal_h", 20)
    api.data.setdefault("days", {})       # 日付 → その日の作業秒数
    s = {"n": 0}
    w = {}

    def week_sec():
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        return sum(api.data["days"].get((monday + timedelta(days=i)).isoformat(), 0) for i in range(7))

    def build(frame):
        w["bar"] = ttk.Progressbar(frame, maximum=100)
        w["bar"].pack(fill="x")
        w["l"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["l"].pack(anchor="w", pady=(4, 0))
        render()

    def render():
        if not (w.get("bar") and w["bar"].winfo_exists()):
            return
        total, goal = week_sec(), api.data["goal_h"] * 3600
        w["bar"]["value"] = min(100, total * 100 / goal)
        left = date.today().weekday()
        w["l"].configure(text=f"今週 {fmt(total)} / 目標 {api.data['goal_h']} 時間"
                              f"（{total * 100 // goal}% · 残り {6 - left} 日）")

    @api.on("tick")
    def tick(status):
        d = date.today().isoformat()
        before = week_sec()
        api.data["days"][d] = status["today_sec"]
        goal = api.data["goal_h"] * 3600
        if before < goal <= week_sec():
            api.notify(f"🏁 週間目標 {api.data['goal_h']} 時間を達成しました！")
        s["n"] += 1
        if s["n"] % 60 == 0:
            # 古い記録は消して、ファイルを小さく保つ
            old = (date.today() - timedelta(days=60)).isoformat()
            for k in [k for k in api.data["days"] if k < old]:
                del api.data["days"][k]
            api.save_data()
        if s["n"] % 5 == 0:
            render()

    def set_goal():
        v = simpledialog.askinteger("週間目標", "1週間の目標（時間）", parent=api.root,
                                    initialvalue=api.data["goal_h"], minvalue=1, maxvalue=168)
        if v:
            api.data["goal_h"] = v
            api.save_data()
            render()

    api.add_panel(build, title="週間目標")
    api.add_action("目標を変える", set_goal)


def teardown(api):
    api.save_data()
