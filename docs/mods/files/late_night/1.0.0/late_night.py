"""深夜作業の警告

夜遅く（初期は0時以降）に作業していたら「そろそろ寝よう」と知らせます。
"""

import time
from datetime import datetime
from tkinter import simpledialog

MOD_INFO = {
    "name": "深夜作業の警告",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "決めた時刻（初期 0時）〜朝5時に作業していると、30分ごとに寝るようすすめます。オーバーレイに🌙も出します。",
    "api": 1,
}

MESSAGES = ["🌙 もう遅い時間です。そろそろ寝ませんか？", "😴 睡眠も大事な作業のうち。明日の自分に任せよう",
            "🛏 今日はもう十分がんばりました", "🌙 夜ふかしは明日の集中力を下げちゃいます"]


def setup(api):
    api.data.setdefault("hour", 0)
    s = {"last": 0, "i": 0}

    def late():
        h = datetime.now().hour
        start = api.data["hour"]
        if start == 0:
            return h < 5
        return h >= start or h < 5

    @api.on("tick")
    def tick(status):
        if status["state"] == "working" and late() and time.time() - s["last"] > 30 * 60:
            s["last"] = time.time()
            api.notify(MESSAGES[s["i"] % len(MESSAGES)])
            s["i"] += 1

    @api.filter("overlay_text")
    def overlay(text):
        return f"🌙 {text}" if late() else text

    def set_hour():
        v = simpledialog.askinteger("深夜作業の警告", "何時から知らせる？（0〜23。0 なら0時）", parent=api.root,
                                    initialvalue=api.data["hour"], minvalue=0, maxvalue=23)
        if v is not None:
            api.data["hour"] = v
            api.save_data()

    api.add_action("知らせる時刻を変える", set_hour)
