"""残り時間予測

今日のペースが続いたら、何時ごろ目標を達成しそうかを予測して表示します。
"""

import time
from datetime import date, datetime
from tkinter import ttk

MOD_INFO = {
    "name": "残り時間予測",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "最初に作業を始めた時刻からのペースで、目標を達成しそうな時刻を予測します。",
    "api": 1,
}


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "start": None})
    s = {"n": 0}
    w = {}

    def predict(status):
        goal = status["goal_min"] * 60
        if not goal:
            return "目標が設定されていません"
        if status["today_sec"] >= goal:
            return "🎉 目標達成ずみ！"
        start = api.data["start"]
        if not start or status["today_sec"] < 300:
            return "まだ予測できません（5分以上作業すると出ます）"
        elapsed = time.time() - start
        rate = status["today_sec"] / elapsed            # 実時間1秒あたりの作業秒数
        eta = time.time() + (goal - status["today_sec"]) / max(rate, 0.01)
        when = datetime.fromtimestamp(eta)
        day = "" if when.date() == date.today() else "（明日以降）"
        return f"⏰ このペースなら {when:%H:%M}{day} に達成 · 作業率 {rate * 100:.0f}%"

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(anchor="w")
        render(api.status())

    def render(status):
        if w.get("l") and w["l"].winfo_exists():
            w["l"].configure(text=predict(status))

    @api.on("tick")
    def tick(status):
        if status["state"] == "working" and not api.data["start"]:
            api.data["start"] = time.time() - status["today_sec"]
            api.save_data()
        s["n"] += 1
        if s["n"] % 10 == 0:
            render(status)

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "start": None})
        api.save_data()

    api.add_panel(build, title="達成予測")
