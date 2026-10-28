"""ポモドーロタイマーの MOD の例

作業中（WorkMonitor が数えている時間）だけ進むタイマーです。
メイン画面に枠を足し、オーバーレイにも残り時間を出します。
"""

from datetime import date
from tkinter import ttk

MOD_INFO = {
    "name": "作業ポモドーロ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業している時間だけ進むポモドーロタイマーです。25分たまると通知して休憩をすすめます。"
                   "メイン画面とオーバーレイに残り時間を表示します。",
}

WORK_MIN = 25


def setup(api):
    today = date.today().isoformat()
    if api.data.get("day") != today:          # 日付が変わっていたら回数を 0 に
        api.data.update({"day": today, "done": 0})
    s = {"sec": 0, "running": True, "last": None}
    w = {}

    def fmt(sec):
        m, sec = divmod(int(sec), 60)
        return f"{m:02d}:{sec:02d}"

    def left():
        return WORK_MIN * 60 - s["sec"]

    # メイン画面の枠（テーマを変えると作り直されるので、状態は s に持っておく）
    def build(frame):
        w["time"] = ttk.Label(frame, font=("Segoe UI", 16, "bold"))
        w["time"].pack(side="left")
        w["count"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["count"].pack(side="left", padx=10)
        ttk.Button(frame, text="リセット", command=reset).pack(side="right")
        w["btn"] = ttk.Button(frame, command=toggle)
        w["btn"].pack(side="right", padx=6)
        render()

    def render():
        if "time" not in w or not w["time"].winfo_exists():
            return
        w["time"].configure(text=f"🍅 {fmt(left())}")
        w["count"].configure(text=f"今日 {api.data['done']} 回")
        w["btn"].configure(text="一時停止" if s["running"] else "再開")

    def toggle():
        s["running"] = not s["running"]
        render()

    def reset():
        s["sec"] = 0
        render()

    @api.on("tick")
    def tick(status):
        # 前回からの作業時間の増え方だけ進める（休憩中・数えないアプリでは増えない）
        last, s["last"] = s["last"], status["today_sec"]
        if s["running"] and last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
            if s["sec"] >= WORK_MIN * 60:
                s["sec"] = 0
                api.data["done"] += 1
                api.save_data()
                api.notify(f"{WORK_MIN}分 作業しました！ 5分くらい休憩しましょう。（今日 {api.data['done']} 回目）")
        render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "done": 0})
        api.save_data()
        s["last"] = None

    @api.filter("overlay_text")
    def overlay(text):
        return f"{text} · 🍅{fmt(left())}" if s["running"] else text

    api.add_panel(build, title="ポモドーロ（作業中だけ進む）")
    api.add_action("タイマーをリセット", reset)
