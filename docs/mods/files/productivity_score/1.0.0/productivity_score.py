"""生産性スコア

作業時間・アプリの切り替え回数・脱線の少なさから、今日の生産性を 100 点満点で採点します。
"""

from datetime import date
from tkinter import ttk

MOD_INFO = {
    "name": "生産性スコア",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業時間（60点）・集中度（切り替えの少なさ 20点）・脱線の少なさ（20点）で今日を採点します。",
    "api": 1,
}


def grade(score):
    for need, g in ((90, "S"), (75, "A"), (60, "B"), (40, "C")):
        if score >= need:
            return g
    return "D"


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "switches": 0, "excluded": 0})
    s = {"score": 0, "parts": (0, 0, 0), "n": 0}
    w = {}

    def calc(status):
        goal = (status["goal_min"] or 240) * 60
        work = status["today_sec"]
        p1 = min(60, 60 * work / goal)
        hours = max(work / 3600, 0.5)
        per_hour = api.data["switches"] / hours        # 1時間あたりの切り替え回数
        p2 = max(0, 20 - max(0, per_hour - 20) * 0.4)
        ratio = api.data["excluded"] / max(work + api.data["excluded"], 1)
        p3 = max(0, 20 * (1 - ratio * 2))
        s["parts"] = (p1, p2, p3)
        s["score"] = round(p1 + p2 + p3) if work >= 60 else 0

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 16, "bold"))
        w["l"].pack(side="left")
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"], justify="left")
        w["sub"].pack(side="left", padx=12)
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        p1, p2, p3 = s["parts"]
        w["l"].configure(text=f"{grade(s['score'])}  {s['score']}点")
        w["sub"].configure(text=f"作業 {p1:.0f}/60 · 集中 {p2:.0f}/20 · 脱線なし {p3:.0f}/20")

    @api.on("app_change")
    def app_changed(old_app, new_app, status):
        if old_app and new_app:
            api.data["switches"] += 1

    @api.on("tick")
    def tick(status):
        if status["state"] == "excluded":
            api.data["excluded"] += 1
        s["n"] += 1
        if s["n"] % 10 == 0:
            calc(status)
            render()
        if s["n"] % 120 == 0:
            api.save_data()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "switches": 0, "excluded": 0})
        api.save_data()

    api.add_panel(build, title="生産性スコア")


def teardown(api):
    api.save_data()
