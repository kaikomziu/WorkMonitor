"""アプリ切り替えカウンター

前面のアプリを切り替えた回数を数えて、集中が途切れていないかを見える化します。

1.1.0: よくある切り替えの組み合わせトップ3・直近7日の回数・多すぎるときの通知を追加
"""

import time
from datetime import date, timedelta
from tkinter import ttk

MOD_INFO = {
    "name": "アプリ切り替えカウンター",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "今日アプリを切り替えた回数と直近1時間の回数、よくある切り替えの組み合わせを表示します。"
                   "1時間に80回を超えると通知します。",
    "api": 1,
}

WARN_PER_HOUR = 80


def short(exe):
    return (exe or "").replace(".exe", "")


def setup(api):
    api.data.setdefault("history", {})      # 日付 → 回数
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "count": 0, "pairs": {}})
    recent = []          # 直近の切り替えの時刻
    s = {"warned": 0}
    w = {}

    def level(n):
        if n < 30:
            return "🟢 集中できています"
        if n < WARN_PER_HOUR:
            return "🟡 ちょっと多め"
        return "🔴 気が散っているかも"

    def build(frame):
        w["main"] = ttk.Label(frame, font=("Segoe UI", 14, "bold"))
        w["main"].pack(anchor="w")
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"], justify="left")
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("main") and w["main"].winfo_exists()):
            return
        now = time.time()
        recent[:] = [t for t in recent if now - t < 3600]
        w["main"].configure(text=f"今日の切り替え {api.data['count']} 回")
        pairs = sorted(api.data["pairs"].items(), key=lambda kv: -kv[1])[:3]
        pair_text = "  ".join(f"{k} ×{v}" for k, v in pairs)
        days = [(date.today() - timedelta(days=6 - i)).isoformat() for i in range(6)]
        week = " ".join(str(api.data["history"].get(d, 0)) for d in days) + f" {api.data['count']}"
        w["sub"].configure(text=f"直近1時間 {len(recent)} 回 · {level(len(recent))}\n"
                                f"よくある切り替え: {pair_text or 'まだありません'}\n直近7日: {week}")

    @api.on("app_change")
    def changed(old_app, new_app, status):
        if not old_app or not new_app:
            return
        api.data["count"] += 1
        a, b = sorted((short(old_app), short(new_app)))
        key = f"{a}⇄{b}"
        api.data["pairs"][key] = api.data["pairs"].get(key, 0) + 1
        recent.append(time.time())
        if len(recent) >= WARN_PER_HOUR and time.time() - s["warned"] > 3600:
            s["warned"] = time.time()
            api.notify(f"🔀 この1時間で {len(recent)} 回もアプリを切り替えています。1つのことに絞ってみませんか？")
        if api.data["count"] % 20 == 0:
            api.save_data()
        render()

    @api.on("day_change")
    def new_day(day):
        api.data["history"][api.data["day"]] = api.data["count"]
        keep = sorted(api.data["history"])[-30:]
        api.data["history"] = {k: api.data["history"][k] for k in keep}
        api.data.update({"day": day, "count": 0, "pairs": {}})
        recent.clear()
        api.save_data()
        render()

    api.add_panel(build, title="アプリ切り替え")


def teardown(api):
    api.save_data()
