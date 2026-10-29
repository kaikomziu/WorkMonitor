"""応援メッセージ

メイン画面に、状況に合わせた応援メッセージを出します（10分ごとに変わります）。
"""

import random
from datetime import datetime
from tkinter import ttk

MOD_INFO = {
    "name": "応援メッセージ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "メイン画面に応援メッセージを表示します。作業時間や時間帯に合わせて10分ごとに変わります。",
    "api": 1,
}

START = ["今日もいっしょにがんばろう！", "まずは小さく始めよう 🌱", "準備OK？ 深呼吸してスタート！"]
WORKING = ["いい集中だね！", "その調子 👍", "一歩ずつ確実に進んでるよ", "えらい！ 続けてる自分をほめよう",
           "水分補給も忘れずにね 💧", "あなたならできる！", "コツコツが最強 💪"]
LATE = ["もう遅いよ、無理しすぎないでね 🌙", "今日はここまででも十分えらい"]
GOAL = ["目標達成おめでとう！ 🎉", "今日のノルマクリア！ あとはご褒美タイム？", "すばらしい一日だね ✨"]


def setup(api):
    s = {"text": random.choice(START)}
    w = {}

    def pick():
        st = api.status()
        if st["goal_done"]:
            pool = GOAL
        elif datetime.now().hour >= 23 or datetime.now().hour < 4:
            pool = LATE
        elif st["today_sec"] < 300:
            pool = START
        else:
            pool = WORKING
        s["text"] = random.choice(pool)
        render()
        api.after(10 * 60 * 1000, pick)

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 12), foreground=api.colors["accent"])
        w["l"].pack(anchor="w")
        render()

    def render():
        if w.get("l") and w["l"].winfo_exists():
            w["l"].configure(text=f"📣 {s['text']}")

    api.add_panel(build, title="応援")
    api.after(3000, pick)
