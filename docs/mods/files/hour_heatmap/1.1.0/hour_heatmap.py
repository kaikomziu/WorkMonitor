"""時間帯ヒートマップ

何時台に作業が多いかを、24本のマスの濃さで表示します（今日と、これまでの合計）。

1.1.0: 曜日別の段・ゴールデンタイム（いちばん作業している時間帯）の表示・マスにマウスを乗せると時間が出る機能を追加
"""

from datetime import date, datetime
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "時間帯ヒートマップ",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "0〜23時のどの時間帯に作業しているかを色の濃さで表示します。今日・累計・曜日別の段があり、"
                   "いちばん作業できている時間帯も教えてくれます。",
    "api": 1,
}

CELL, GAP, LEFT = 14, 2, 34
WEEKDAYS = "月火水木金土日"


def mix(c1, c2, t):
    """2つの色 #rrggbb を t（0〜1）で混ぜる"""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def setup(api):
    api.data.setdefault("total", [0] * 24)
    api.data.setdefault("weekday", [[0] * 24 for _ in range(7)])
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "today": [0] * 24})
    s = {"last": None, "n": 0}
    w = {}

    def rows():
        return [("今日", api.data["today"]), ("累計", api.data["total"])] + \
               [(WEEKDAYS[i], api.data["weekday"][i]) for i in range(7)]

    def build(frame):
        width = LEFT + 24 * (CELL + GAP)
        w["c"] = tk.Canvas(frame, width=width, height=9 * (CELL + GAP) + 20, bg=api.colors["bg"],
                           highlightthickness=0)
        w["c"].pack(anchor="w")
        w["tip"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["tip"].pack(anchor="w")
        w["c"].bind("<Motion>", hover)
        render()

    def golden():
        t = api.data["total"]
        if not any(t):
            return "まだデータがありません"
        # 3時間の幅でいちばん多いところ
        best = max(range(24), key=lambda h: t[h] + t[(h + 1) % 24] + t[(h + 2) % 24])
        return f"✨ ゴールデンタイムは {best}時〜{(best + 3) % 24}時"

    def hover(e):
        h = int((e.x - LEFT) // (CELL + GAP))
        r = int(e.y // (CELL + GAP))
        r = -1 if r == 2 else r - 1 if r > 2 else r      # 2段目のあとはすき間が1段ある
        all_rows = rows()
        if 0 <= h < 24 and 0 <= r < len(all_rows):
            name, vals = all_rows[r]
            w["tip"].configure(text=f"{name} {h}時台: {vals[h] // 60}分")
        else:
            w["tip"].configure(text=golden())

    def row(c, y, values, label):
        top = max(values) or 1
        base = "#2a2f3a" if api.dark else "#e9ecf2"
        c.create_text(0, y + CELL / 2, text=label, anchor="w", fill=api.colors["sub"], font=("Segoe UI", 8))
        for h, v in enumerate(values):
            x = LEFT + h * (CELL + GAP)
            color = mix(base, api.colors["accent"], v / top) if v else base
            c.create_rectangle(x, y, x + CELL, y + CELL, fill=color, outline="")

    def render():
        c = w.get("c")
        if not (c and c.winfo_exists()):
            return
        c.delete("all")
        y = 0
        for i, (name, vals) in enumerate(rows()):
            if i == 2:
                y += CELL + GAP      # 曜日の段の前にすき間
            row(c, y, vals, name)
            y += CELL + GAP
        for h in range(0, 24, 3):
            c.create_text(LEFT + h * (CELL + GAP), y + 7, text=str(h), anchor="w",
                          fill=api.colors["sub"], font=("Segoe UI", 7))
        w["tip"].configure(text=golden())

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            d = status["today_sec"] - last
            now = datetime.now()
            api.data["today"][now.hour] += d
            api.data["total"][now.hour] += d
            api.data["weekday"][now.weekday()][now.hour] += d
        s["n"] += 1
        if s["n"] % 60 == 0:
            api.save_data()
            render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "today": [0] * 24})
        s["last"] = None
        api.save_data()
        render()

    api.add_panel(build, title="時間帯ヒートマップ")


def teardown(api):
    api.save_data()
