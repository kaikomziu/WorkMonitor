"""カテゴリ別円グラフ

今日の作業時間をカテゴリ（開発・デザインなど）ごとに円グラフで表示します。
"""

from datetime import date
import tkinter as tk

MOD_INFO = {
    "name": "カテゴリ別円グラフ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "今日の作業時間のカテゴリ別の割合を円グラフで表示します（この MOD が動いている間の分）。",
    "api": 1,
}

PALETTE = ["#4f6bed", "#22a06b", "#e2a03f", "#d9534f", "#9b59b6", "#17a2b8", "#e83e8c", "#6c757d"]
SIZE = 110


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "cats": {}})
    s = {"last": None, "n": 0}
    w = {}

    def build(frame):
        w["c"] = tk.Canvas(frame, width=360, height=SIZE + 6, bg=api.colors["bg"], highlightthickness=0)
        w["c"].pack(anchor="w")
        render()

    def render():
        c = w.get("c")
        if not (c and c.winfo_exists()):
            return
        c.delete("all")
        cats = sorted(api.data["cats"].items(), key=lambda kv: -kv[1])
        total = sum(v for _, v in cats)
        if not total:
            c.create_text(4, SIZE / 2, text="まだデータがありません", anchor="w", fill=api.colors["sub"])
            return
        start = 90
        for i, (name, v) in enumerate(cats):
            color = PALETTE[i % len(PALETTE)]
            extent = 360 * v / total
            if len(cats) == 1:
                c.create_oval(3, 3, SIZE, SIZE, fill=color, outline="")
            else:
                c.create_arc(3, 3, SIZE, SIZE, start=start, extent=-extent, fill=color, outline=api.colors["bg"])
            start -= extent
            if i < 7:
                y = 8 + i * 15
                c.create_rectangle(SIZE + 16, y - 5, SIZE + 26, y + 5, fill=color, outline="")
                c.create_text(SIZE + 32, y, anchor="w", fill=api.colors["text"], font=("Segoe UI", 9),
                              text=f"{name}  {v * 100 / total:.0f}%（{v // 60}分）")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            cat = status["category"] or "その他"
            api.data["cats"][cat] = api.data["cats"].get(cat, 0) + status["today_sec"] - last
        s["n"] += 1
        if s["n"] % 30 == 0:
            api.save_data()
            render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "cats": {}})
        s["last"] = None
        api.save_data()
        render()

    api.add_panel(build, title="カテゴリ別")


def teardown(api):
    api.save_data()
