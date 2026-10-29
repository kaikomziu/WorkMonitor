"""水分補給リマインダー

作業1時間ごとに水を飲むように知らせ、今日飲んだ杯数を記録します。
"""

from datetime import date
from tkinter import ttk

MOD_INFO = {
    "name": "水分補給リマインダー",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業1時間ごとに💧水分補給を知らせます。メイン画面のボタンで飲んだ杯数を記録できます（目標8杯）。",
    "api": 1,
}

INTERVAL = 60 * 60
GOAL = 8


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "cups": 0})
    s = {"sec": 0, "last": None}
    w = {}

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI Emoji", 12))
        w["l"].pack(side="left")
        ttk.Button(frame, text="1杯飲んだ", command=drink).pack(side="right")
        render()

    def render():
        if w.get("l") and w["l"].winfo_exists():
            n = api.data["cups"]
            w["l"].configure(text="💧" * min(n, GOAL) + "◦" * max(0, GOAL - n) + f"  {n}/{GOAL} 杯")

    def drink():
        api.data["cups"] += 1
        s["sec"] = 0
        api.save_data()
        render()
        if api.data["cups"] == GOAL:
            api.notify("💧 今日の水分補給の目標を達成しました！")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= INTERVAL:
            s["sec"] = 0
            api.notify(f"💧 水分補給の時間です（今日 {api.data['cups']} 杯）")

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "cups": 0})
        s["last"] = None
        api.save_data()
        render()

    api.add_panel(build, title="水分補給")
    api.add_action("1杯飲んだ", drink)
