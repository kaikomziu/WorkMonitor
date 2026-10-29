"""レベル＆経験値

作業1分ごとに 1 XP。たまるとレベルが上がる、RPG 風の MOD です。
"""

from tkinter import ttk

MOD_INFO = {
    "name": "レベル＆経験値",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業1分で1XP、目標達成でボーナス30XP。レベルが上がると通知します。称号つき。",
    "api": 1,
}

TITLES = [(1, "見習い"), (5, "駆け出し"), (10, "一人前"), (20, "ベテラン"), (35, "達人"), (50, "仙人"), (80, "伝説")]


def need(level):
    """そのレベルから次のレベルに上がるのに必要な XP"""
    return 30 + level * 10


def title(level):
    t = TITLES[0][1]
    for lv, name in TITLES:
        if level >= lv:
            t = name
    return t


def setup(api):
    api.data.setdefault("level", 1)
    api.data.setdefault("xp", 0)
    api.data.setdefault("total", 0)
    s = {"sec": 0, "last": None}
    w = {}

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 14, "bold"))
        w["l"].pack(anchor="w")
        w["bar"] = ttk.Progressbar(frame)
        w["bar"].pack(fill="x", pady=3)
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        lv = api.data["level"]
        w["l"].configure(text=f"⚔ Lv.{lv}  {title(lv)}")
        w["bar"].configure(maximum=need(lv), value=api.data["xp"])
        w["sub"].configure(text=f"XP {api.data['xp']} / {need(lv)} · 累計 {api.data['total']} XP")

    def gain(xp):
        api.data["xp"] += xp
        api.data["total"] += xp
        while api.data["xp"] >= need(api.data["level"]):
            api.data["xp"] -= need(api.data["level"])
            api.data["level"] += 1
            lv = api.data["level"]
            api.notify(f"🎉 レベルアップ！ Lv.{lv}「{title(lv)}」になりました")
        api.save_data()
        render()

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= 60:
            s["sec"] -= 60
            gain(1)

    @api.on("goal_reached")
    def goal(goal_min, streak):
        gain(30)
        api.notify("✨ 目標達成ボーナス +30 XP")

    @api.on("day_change")
    def new_day(day):
        s["last"] = None

    api.add_panel(build, title="レベル")
