"""タイムボックス

「このタスクは45分だけ」と時間を区切って取り組むためのタイマーです（実時間で進みます）。

1.1.0: 15/25/45/60分のワンクリック開始・延長ボタン・残り1分の予告・今日の履歴を追加
"""

import time
from datetime import date, datetime
from tkinter import messagebox, simpledialog, ttk

MOD_INFO = {
    "name": "タイムボックス",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "タスク名と分数を決めてタイマーを開始。残り時間を画面とオーバーレイに出し、時間切れで通知。"
                   "ワンクリック開始・+5分延長・今日の履歴つき。",
    "api": 1,
}

PRESETS = [15, 25, 45, 60]


def setup(api):
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "log": []})
    s = {"end": None, "task": "", "timer": None, "start": None, "warned": False}
    w = {}

    def left():
        return max(0, int(s["end"] - time.time())) if s["end"] else 0

    def fmt(sec):
        m, sec = divmod(sec, 60)
        return f"{m:02d}:{sec:02d}"

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        w["l"] = ttk.Label(top, font=("Segoe UI", 13, "bold"))
        w["l"].pack(side="left")
        ttk.Button(top, text="止める", command=lambda: stop(True)).pack(side="right")
        ttk.Button(top, text="+5分", command=extend).pack(side="right", padx=4)
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(4, 0))
        for m in PRESETS:
            ttk.Button(row, text=f"{m}分", width=5, command=lambda m=m: start(m)).pack(side="left", padx=1)
        ttk.Button(row, text="履歴", command=history).pack(side="right")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        w["l"].configure(text=f"⏳ {s['task']}  {fmt(left())}" if s["end"] else
                         f"⏳ タイムボックスなし（今日 {len(api.data['log'])} 個）")

    def record(finished):
        mins = int((time.time() - s["start"]) // 60) if s["start"] else 0
        api.data["log"].append([datetime.now().strftime("%H:%M"), s["task"], mins, finished])
        api.save_data()

    def loop():
        if not s["end"]:
            return
        if left() <= 60 and not s["warned"]:
            s["warned"] = True
            api.notify(f"⏳ 「{s['task']}」残り1分です")
        if left() <= 0:
            api.notify(f"⏰ タイムボックス終了：「{s['task']}」")
            record(True)
            s.update({"end": None, "timer": None})
        else:
            s["timer"] = api.after(1000, loop)
        render()

    def start(mins=None):
        task = simpledialog.askstring("タイムボックス", "取り組むタスクは？", parent=api.root)
        if not task:
            return
        if mins is None:
            mins = simpledialog.askinteger("タイムボックス", "何分？", parent=api.root,
                                           initialvalue=45, minvalue=1, maxvalue=600)
            if not mins:
                return
        stop(s["end"] is not None)
        s.update({"task": task, "end": time.time() + mins * 60, "start": time.time(), "warned": False})
        loop()

    def extend():
        if s["end"]:
            s["end"] += 300
            s["warned"] = False
            render()

    def stop(log=False):
        if s["timer"]:
            api.cancel(s["timer"])
        if log and s["end"]:
            record(False)
        s.update({"end": None, "timer": None})
        render()

    def history():
        lines = [f"{t}  {'✅' if ok else '⏹'} {task}（{m}分）" for t, task, m, ok in api.data["log"]]
        messagebox.showinfo("今日のタイムボックス", "\n".join(lines) or "まだありません", parent=api.root)

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "log": []})
        api.save_data()
        render()

    @api.filter("overlay_text")
    def overlay(text):
        return f"{text} · ⏳{fmt(left())}" if s["end"] else text

    api.add_panel(build, title="タイムボックス")
    api.add_action("タイムボックスを始める", start)
    api.add_action("止める", lambda: stop(True))
    api.add_action("今日の履歴", history)
