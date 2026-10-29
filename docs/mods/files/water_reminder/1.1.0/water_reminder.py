"""水分補給リマインダー

作業1時間ごとに水を飲むように知らせ、今日飲んだ杯数を記録します。

1.1.0: 目標杯数と間隔を変更可能に・取り消しボタン・量（ml）表示・7日間の記録を追加
"""

from datetime import date, timedelta
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "水分補給リマインダー",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "作業1時間（変更可）ごとに💧水分補給を知らせます。ボタンで飲んだ杯数を記録（目標は変更可）。"
                   "直近7日の杯数も表示します。",
    "api": 1,
}

ML_PER_CUP = 200


def setup(api):
    api.data.setdefault("goal", 8)
    api.data.setdefault("interval_min", 60)
    api.data.setdefault("history", {})        # 日付 → 杯数
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "cups": 0})
    s = {"sec": 0, "last": None}
    w = {}

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        w["l"] = ttk.Label(top, font=("Segoe UI Emoji", 12))
        w["l"].pack(side="left")
        ttk.Button(top, text="取り消し", command=undo).pack(side="right")
        ttk.Button(top, text="1杯飲んだ", command=drink).pack(side="right", padx=4)
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        n, goal = api.data["cups"], api.data["goal"]
        w["l"].configure(text="💧" * min(n, goal) + "◦" * max(0, goal - n) + f"  {n}/{goal} 杯")
        days = [(date.today() - timedelta(days=6 - i)).isoformat() for i in range(6)]
        week = " ".join(str(api.data["history"].get(d, 0)) for d in days) + f" {n}"
        left = max(0, api.data["interval_min"] * 60 - s["sec"]) // 60
        w["sub"].configure(text=f"約 {n * ML_PER_CUP} ml · 次のお知らせまで {left}分 · 直近7日: {week}")

    def drink():
        api.data["cups"] += 1
        s["sec"] = 0
        api.save_data()
        render()
        if api.data["cups"] == api.data["goal"]:
            api.notify("💧 今日の水分補給の目標を達成しました！")

    def undo():
        if api.data["cups"] > 0:
            api.data["cups"] -= 1
            api.save_data()
            render()

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= api.data["interval_min"] * 60:
            s["sec"] = 0
            api.notify(f"💧 水分補給の時間です（今日 {api.data['cups']}/{api.data['goal']} 杯）")
        if status["today_sec"] % 60 == 0:
            render()

    @api.on("day_change")
    def new_day(day):
        api.data["history"][api.data["day"]] = api.data["cups"]
        keep = sorted(api.data["history"])[-30:]
        api.data["history"] = {k: api.data["history"][k] for k in keep}
        api.data.update({"day": day, "cups": 0})
        s["last"] = None
        api.save_data()
        render()

    def settings():
        v = simpledialog.askinteger("水分補給", "1日の目標（杯）", parent=api.root,
                                    initialvalue=api.data["goal"], minvalue=1, maxvalue=30)
        if v:
            api.data["goal"] = v
        v = simpledialog.askinteger("水分補給", "何分作業したら知らせる？", parent=api.root,
                                    initialvalue=api.data["interval_min"], minvalue=10, maxvalue=240)
        if v:
            api.data["interval_min"] = v
        api.save_data()
        render()

    api.add_panel(build, title="水分補給")
    api.add_action("1杯飲んだ", drink)
    api.add_action("目標・間隔を変える", settings)
