"""週間目標

1週間（月曜はじまり）の合計作業時間に目標を決めて、進み具合を表示します。

1.1.0: 曜日ごとのミニ棒・残りの日で必要な1日あたりの時間・先週との比較を追加
"""

from datetime import date, timedelta
import tkinter as tk
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "週間目標",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "月曜〜日曜の合計作業時間に目標を設定し、曜日ごとの棒と進み具合を表示します。必要な1日あたりの時間や"
                   "先週との比較も出します。",
    "api": 1,
}

WEEKDAYS = "月火水木金土日"


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分"


def setup(api):
    api.data.setdefault("goal_h", 20)
    api.data.setdefault("days", {})       # 日付 → その日の作業秒数
    s = {"n": 0}
    w = {}

    def monday(offset=0):
        t = date.today()
        return t - timedelta(days=t.weekday() + 7 * offset)

    def week_sec(offset=0, upto=7):
        m = monday(offset)
        return sum(api.data["days"].get((m + timedelta(days=i)).isoformat(), 0) for i in range(upto))

    def build(frame):
        w["bar"] = ttk.Progressbar(frame, maximum=100)
        w["bar"].pack(fill="x")
        w["c"] = tk.Canvas(frame, width=7 * 34, height=46, bg=api.colors["bg"], highlightthickness=0)
        w["c"].pack(anchor="w", pady=4)
        w["l"] = ttk.Label(frame, foreground=api.colors["sub"], justify="left")
        w["l"].pack(anchor="w")
        render()

    def render():
        if not (w.get("bar") and w["bar"].winfo_exists()):
            return
        total, goal = week_sec(), api.data["goal_h"] * 3600
        w["bar"]["value"] = min(100, total * 100 / goal)
        wd = date.today().weekday()
        days_left = 7 - wd                      # 今日をふくむ残り日数
        need = max(0, goal - total) / days_left
        last_same = week_sec(1, wd + 1)          # 先週の同じ曜日まで
        diff = total - last_same
        sign = "+" if diff >= 0 else "-"
        w["l"].configure(text=f"今週 {fmt(total)} / 目標 {api.data['goal_h']} 時間（{total * 100 // goal}%）\n"
                              + (f"残り {days_left} 日、1日 {fmt(need)} ずつで達成 · " if total < goal else "🏁 達成ずみ · ")
                              + f"先週の同じ曜日まで比 {sign}{fmt(abs(diff))}")
        c = w["c"]
        c.delete("all")
        m = monday()
        vals = [api.data["days"].get((m + timedelta(days=i)).isoformat(), 0) for i in range(7)]
        top = max(vals + [goal / 7, 1])
        for i, v in enumerate(vals):
            x = i * 34 + 6
            bh = 30 * v / top
            color = api.colors["accent"] if i <= wd else ("#2a2f3a" if api.dark else "#e9ecf2")
            c.create_rectangle(x, 32 - max(bh, 2), x + 22, 32, fill=color, outline="")
            c.create_text(x + 11, 40, text=WEEKDAYS[i], fill=api.colors["text"] if i == wd else api.colors["sub"],
                          font=("Segoe UI", 8, "bold" if i == wd else "normal"))
        gy = 32 - 30 * (goal / 7) / top
        c.create_line(0, gy, 7 * 34, gy, fill=api.colors["orange"], dash=(3, 3))

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
