"""タイムボックス

「このタスクは45分だけ」と時間を区切って取り組むためのタイマーです（実時間で進みます）。
"""

import time
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "タイムボックス",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "タスク名と分数を決めてタイマーを開始。メイン画面とオーバーレイに残り時間を出し、時間切れで通知します。",
    "api": 1,
}


def setup(api):
    s = {"end": None, "task": "", "timer": None}
    w = {}

    def left():
        return max(0, int(s["end"] - time.time())) if s["end"] else 0

    def fmt(sec):
        m, sec = divmod(sec, 60)
        return f"{m:02d}:{sec:02d}"

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 13, "bold"))
        w["l"].pack(side="left")
        ttk.Button(frame, text="止める", command=stop).pack(side="right")
        ttk.Button(frame, text="開始", command=start).pack(side="right", padx=6)
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        w["l"].configure(text=f"⏳ {s['task']}  {fmt(left())}" if s["end"] else "⏳ タイムボックスなし")

    def loop():
        if not s["end"]:
            return
        if left() <= 0:
            api.notify(f"⏰ タイムボックス終了：「{s['task']}」")
            s.update({"end": None, "timer": None})
        else:
            s["timer"] = api.after(1000, loop)
        render()

    def start():
        task = simpledialog.askstring("タイムボックス", "取り組むタスクは？", parent=api.root)
        if not task:
            return
        mins = simpledialog.askinteger("タイムボックス", "何分？", parent=api.root,
                                       initialvalue=45, minvalue=1, maxvalue=600)
        if not mins:
            return
        stop()
        s.update({"task": task, "end": time.time() + mins * 60})
        loop()

    def stop():
        if s["timer"]:
            api.cancel(s["timer"])
        s.update({"end": None, "timer": None})
        render()

    @api.filter("overlay_text")
    def overlay(text):
        return f"{text} · ⏳{fmt(left())}" if s["end"] else text

    api.add_panel(build, title="タイムボックス")
    api.add_action("タイムボックスを始める", start)
    api.add_action("止める", stop)
