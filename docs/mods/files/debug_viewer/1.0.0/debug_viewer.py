"""MOD デバッグビューア

MOD を作るときのために、api.status() の中身と、最近のイベントをリアルタイムで表示します。
"""

import json
import time
from collections import deque
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "MOD デバッグビューア",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "status の中身と、最近のイベント（state_change・app_change など）をメイン画面に表示します。MOD 作りに便利。",
    "api": 1,
}


def setup(api):
    events = deque(maxlen=8)
    s = {"status": {}}
    w = {}

    def build(frame):
        mono = ("Consolas", 9)
        bg = "#1b1f29" if api.dark else "#f4f5f8"
        w["st"] = tk.Text(frame, height=11, font=mono, relief="flat", bg=bg, fg=api.colors["text"])
        w["st"].pack(fill="x")
        ttk.Label(frame, text="最近のイベント", foreground=api.colors["sub"]).pack(anchor="w", pady=(4, 0))
        w["ev"] = tk.Text(frame, height=6, font=mono, relief="flat", bg=bg, fg=api.colors["text"])
        w["ev"].pack(fill="x")
        render()

    def put(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def render():
        if not (w.get("st") and w["st"].winfo_exists()):
            return
        put(w["st"], json.dumps(s["status"], ensure_ascii=False, indent=1))
        put(w["ev"], "\n".join(events) or "（まだありません）")

    def add(text):
        events.appendleft(f"{time.strftime('%H:%M:%S')}  {text}")
        render()

    @api.on("tick")
    def tick(status):
        s["status"] = status
        render()

    @api.on("state_change")
    def st(old, new, status):
        add(f"state_change  {old} → {new}")

    @api.on("app_change")
    def ap(old_app, new_app, status):
        add(f"app_change    {old_app} → {new_app}")

    @api.on("goal_reached")
    def gl(goal_min, streak):
        add(f"goal_reached  goal_min={goal_min} streak={streak}")

    @api.on("day_change")
    def dc(day):
        add(f"day_change    {day}")

    def dump():
        api.log(json.dumps(api.status(), ensure_ascii=False))
        api.log("config:", json.dumps(api.config(), ensure_ascii=False)[:2000])

    api.add_panel(build, title="デバッグ")
    api.add_action("status と設定をログに出す", dump)
