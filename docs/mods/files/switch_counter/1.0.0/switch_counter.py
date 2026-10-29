"""アプリ切り替えカウンター

前面のアプリを切り替えた回数を数えて、集中が途切れていないかを見える化します。
"""

import time
from datetime import date
from tkinter import ttk

MOD_INFO = {
    "name": "アプリ切り替えカウンター",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "今日アプリを切り替えた回数と、直近1時間の回数を表示します。多すぎると集中が途切れているサインかも。",
    "api": 1,
}


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "count": 0})
    recent = []          # 直近の切り替えの時刻
    w = {}

    def level(n):
        if n < 30:
            return "🟢 集中できています"
        if n < 80:
            return "🟡 ちょっと多め"
        return "🔴 気が散っているかも"

    def build(frame):
        w["main"] = ttk.Label(frame, font=("Segoe UI", 14, "bold"))
        w["main"].pack(anchor="w")
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("main") and w["main"].winfo_exists()):
            return
        now = time.time()
        recent[:] = [t for t in recent if now - t < 3600]
        w["main"].configure(text=f"今日の切り替え {api.data['count']} 回")
        w["sub"].configure(text=f"直近1時間 {len(recent)} 回 · {level(len(recent))}")

    @api.on("app_change")
    def changed(old_app, new_app, status):
        if not old_app or not new_app:
            return
        api.data["count"] += 1
        recent.append(time.time())
        if api.data["count"] % 20 == 0:
            api.save_data()
        render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "count": 0})
        recent.clear()
        api.save_data()
        render()

    api.add_panel(build, title="アプリ切り替え")


def teardown(api):
    api.save_data()
