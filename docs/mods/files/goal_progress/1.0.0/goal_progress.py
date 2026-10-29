"""目標の進捗バー

1日の目標に対して、今どこまで来ているかをメイン画面のプログレスバーで表示します。
"""

from tkinter import ttk

MOD_INFO = {
    "name": "目標の進捗バー",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "1日の目標に対する達成度をプログレスバーと残り時間で表示します。",
    "api": 1,
}


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    w = {}

    def build(frame):
        w["bar"] = ttk.Progressbar(frame, maximum=100)
        w["bar"].pack(fill="x")
        w["l"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["l"].pack(anchor="w", pady=(4, 0))
        render(api.status())

    def render(status):
        if not (w.get("bar") and w["bar"].winfo_exists()):
            return
        goal = status["goal_min"] * 60
        if not goal:
            w["bar"]["value"] = 0
            w["l"].configure(text="目標が設定されていません（WorkMonitor の設定で決められます）")
            return
        pct = min(100, status["today_sec"] * 100 / goal)
        w["bar"]["value"] = pct
        if status["goal_done"] or status["today_sec"] >= goal:
            w["l"].configure(text=f"🎉 達成！ {fmt(status['today_sec'])} / {fmt(goal)}")
        else:
            w["l"].configure(text=f"{pct:.0f}% · あと {fmt(goal - status['today_sec'])}")

    api.on("tick", render)
    api.add_panel(build, title="目標の進捗")
