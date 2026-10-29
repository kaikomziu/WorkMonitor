"""実績（アチーブメント）

いろいろな条件を満たすと実績が解除されます。
"""

from datetime import datetime
from tkinter import messagebox, ttk

MOD_INFO = {
    "name": "実績",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "「朝6時前に作業」「1日8時間」などの実績を解除して集めます。解除すると通知します。",
    "api": 1,
}

# ID → (名前, 説明)
ACHIEVEMENTS = {
    "first":     ("はじめの一歩", "はじめて作業した"),
    "h1":        ("1時間の壁", "1日に1時間作業した"),
    "h3":        ("3時間コース", "1日に3時間作業した"),
    "h5":        ("ハードワーカー", "1日に5時間作業した"),
    "h8":        ("フルタイム", "1日に8時間作業した"),
    "h12":       ("鉄人", "1日に12時間作業した"),
    "early":     ("早起きは三文の徳", "朝6時前に作業した"),
    "night":     ("夜ふかし職人", "深夜2時以降に作業した"),
    "goal1":     ("目標クリア", "1日の目標をはじめて達成した"),
    "streak3":   ("三日坊主卒業", "3日連続で目標を達成した"),
    "streak7":   ("1週間の習慣", "7日連続で目標を達成した"),
    "streak30":  ("習慣の達人", "30日連続で目標を達成した"),
    "apps5":     ("マルチタスカー", "1日に5種類のアプリで作業した"),
    "apps10":    ("なんでも屋", "1日に10種類のアプリで作業した"),
    "weekend":   ("休日出勤", "土日に2時間以上作業した"),
    "days10":    ("10日の積み重ね", "作業した日が10日になった"),
    "days100":   ("100日の積み重ね", "作業した日が100日になった"),
}


def setup(api):
    api.data.setdefault("unlocked", {})      # ID → 解除した日時
    api.data.setdefault("work_days", [])
    w = {}

    def unlock(key):
        if key in api.data["unlocked"]:
            return
        api.data["unlocked"][key] = datetime.now().strftime("%Y-%m-%d %H:%M")
        api.save_data()
        name, desc = ACHIEVEMENTS[key]
        api.notify(f"🏅 実績解除「{name}」 — {desc}")
        render()

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(side="left")
        ttk.Button(frame, text="一覧", command=show).pack(side="right")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        n = len(api.data["unlocked"])
        w["l"].configure(text=f"🏅 {n} / {len(ACHIEVEMENTS)} 解除")

    def show():
        lines = []
        for key, (name, desc) in ACHIEVEMENTS.items():
            when = api.data["unlocked"].get(key)
            lines.append(f"🏅 {name}（{when}）" if when else f"🔒 ？？？ — {desc}")
        messagebox.showinfo("実績", "\n".join(lines), parent=api.root)

    @api.on("tick")
    def tick(status):
        if status["state"] != "working":
            return
        now = datetime.now()
        h = status["today_sec"] / 3600
        unlock("first")
        for need, key in ((1, "h1"), (3, "h3"), (5, "h5"), (8, "h8"), (12, "h12")):
            if h >= need:
                unlock(key)
        if 4 <= now.hour < 6:
            unlock("early")
        if 2 <= now.hour < 4:
            unlock("night")
        apps = len([v for v in status["today_by_app"].values() if v >= 60])
        if apps >= 5:
            unlock("apps5")
        if apps >= 10:
            unlock("apps10")
        if now.weekday() >= 5 and h >= 2:
            unlock("weekend")
        day = now.strftime("%Y-%m-%d")
        if day not in api.data["work_days"]:
            api.data["work_days"].append(day)
            api.save_data()
        if len(api.data["work_days"]) >= 10:
            unlock("days10")
        if len(api.data["work_days"]) >= 100:
            unlock("days100")

    @api.on("goal_reached")
    def goal(goal_min, streak):
        unlock("goal1")
        for need, key in ((3, "streak3"), (7, "streak7"), (30, "streak30")):
            if streak >= need:
                unlock(key)

    api.add_panel(build, title="実績")
    api.add_action("実績の一覧を見る", show)
