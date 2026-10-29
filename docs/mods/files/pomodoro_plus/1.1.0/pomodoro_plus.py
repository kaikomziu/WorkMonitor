"""ポモドーロ強化版

作業 → 休憩 → 作業 … のサイクルを回すタイマーです。
作業フェーズは作業中だけ進み、休憩フェーズは実時間で進みます。
長さは 設定 → Mods のボタンで変えられます。

1.1.0: 一時停止・切り替え音・今日の完了数の保存・🍅の並び表示・1日の目標回数を追加
"""

import threading
import winsound
from datetime import date
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "ポモドーロ強化版",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "作業（作業中だけ進む）と休憩（実時間で進む）を交互にくり返すタイマー。4回ごとに長い休憩。"
                   "一時停止・切り替え音・1日の目標回数つき。",
    "api": 1,
}


def beep(notes):
    threading.Thread(target=lambda: [winsound.Beep(f, ms) for f, ms in notes], daemon=True).start()


def setup(api):
    api.data.setdefault("work_min", 25)
    api.data.setdefault("break_min", 5)
    api.data.setdefault("long_min", 15)
    api.data.setdefault("goal", 8)
    api.data.setdefault("sound", True)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "done": 0})
    s = {"phase": "work", "sec": 0, "last": None, "paused": False}
    w = {}

    def length():
        if s["phase"] == "work":
            return api.data["work_min"] * 60
        return (api.data["long_min"] if api.data["done"] % 4 == 0 else api.data["break_min"]) * 60

    def fmt(sec):
        m, sec = divmod(max(0, int(sec)), 60)
        return f"{m:02d}:{sec:02d}"

    def label():
        icon = "⏸" if s["paused"] else "🍅" if s["phase"] == "work" else "☕"
        return f"{icon} {fmt(length() - s['sec'])}"

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        w["time"] = ttk.Label(top, font=("Segoe UI", 16, "bold"))
        w["time"].pack(side="left")
        w["info"] = ttk.Label(top, foreground=api.colors["sub"])
        w["info"].pack(side="left", padx=10)
        ttk.Button(top, text="スキップ", command=skip).pack(side="right")
        w["btn"] = ttk.Button(top, command=toggle)
        w["btn"].pack(side="right", padx=6)
        w["bar"] = ttk.Progressbar(frame)
        w["bar"].pack(fill="x", pady=(4, 0))
        w["row"] = ttk.Label(frame, font=("Segoe UI Emoji", 11))
        w["row"].pack(anchor="w")
        render()

    def render():
        if not (w.get("time") and w["time"].winfo_exists()):
            return
        w["time"].configure(text=label())
        phase = "作業" if s["phase"] == "work" else "休憩"
        w["info"].configure(text=f"{phase}中 · 今日 {api.data['done']}/{api.data['goal']} 回")
        w["btn"].configure(text="再開" if s["paused"] else "一時停止")
        w["bar"].configure(maximum=length(), value=s["sec"])
        n, goal = api.data["done"], api.data["goal"]
        w["row"].configure(text="🍅" * n + "◦" * max(0, goal - n))

    def next_phase():
        if s["phase"] == "work":
            api.data["done"] += 1
            api.save_data()
            s["phase"] = "break"
            kind = "長い休憩" if api.data["done"] % 4 == 0 else "休憩"
            msg = f"🍅 {api.data['work_min']}分おつかれさま！ {length() // 60}分の{kind}にしましょう。"
            if api.data["done"] == api.data["goal"]:
                msg += f"\n🎉 今日の目標 {api.data['goal']} 回を達成！"
            api.notify(msg)
            if api.data["sound"]:
                beep([(784, 120), (659, 120), (523, 200)])
        else:
            s["phase"] = "work"
            api.notify("☕ 休憩おわり！ 次のポモドーロを始めましょう。")
            if api.data["sound"]:
                beep([(523, 120), (659, 120), (784, 200)])
        s["sec"] = 0

    def skip():
        next_phase()
        render()

    def toggle():
        s["paused"] = not s["paused"]
        render()

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if not s["paused"]:
            if s["phase"] == "work":
                # 作業時間が増えた分だけ進める
                if last is not None and status["today_sec"] > last:
                    s["sec"] += status["today_sec"] - last
            else:
                s["sec"] += 1
            if s["sec"] >= length():
                next_phase()
        render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "done": 0})
        api.save_data()
        s.update({"phase": "work", "sec": 0, "last": None})

    @api.filter("overlay_text")
    def overlay(text):
        return f"{text} · {label()}"

    def set_lengths():
        for key, name, mx in (("work_min", "作業の長さ（分）", 180), ("break_min", "短い休憩（分）", 60),
                              ("long_min", "長い休憩（分）", 120), ("goal", "1日の目標回数", 30)):
            v = simpledialog.askinteger("ポモドーロ強化版", name, parent=api.root,
                                        initialvalue=api.data[key], minvalue=1, maxvalue=mx)
            if v:
                api.data[key] = v
        api.save_data()
        render()

    def toggle_sound():
        api.data["sound"] = not api.data["sound"]
        api.save_data()
        api.log("切り替え音:", "オン" if api.data["sound"] else "オフ")

    api.add_panel(build, title="ポモドーロ強化版")
    api.add_action("長さ・目標回数を変える", set_lengths)
    api.add_action("次のフェーズへ", skip)
    api.add_action("切り替え音のオン／オフ", toggle_sound)
