"""メモ帳

メイン画面にメモ欄を置きます。日付ごとに自動で保存され、前の日のメモも見返せます。

1.1.0: 時刻を入れるボタン・文字数の表示・「今日」ボタン・全メモの検索を追加
"""

from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

MOD_INFO = {
    "name": "メモ帳",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "メイン画面のメモ欄。書いた内容は日付ごとに自動保存され、◀ ▶ で前の日のメモを見られます。"
                   "時刻の挿入・文字数・検索つき。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("memos", {})       # 日付 → 本文
    s = {"day": date.today(), "timer": None}
    w = {}

    def key():
        return s["day"].isoformat()

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Button(top, text="◀", width=3, command=lambda: move(-1)).pack(side="left")
        w["title"] = ttk.Label(top)
        w["title"].pack(side="left", padx=8)
        ttk.Button(top, text="▶", width=3, command=lambda: move(1)).pack(side="left")
        ttk.Button(top, text="今日", width=5, command=go_today).pack(side="left", padx=4)
        ttk.Button(top, text="🔍", width=3, command=search).pack(side="right")
        ttk.Button(top, text="🕒時刻", command=stamp).pack(side="right", padx=4)
        w["t"] = tk.Text(frame, height=5, wrap="word", font=("Segoe UI", 10), relief="flat",
                         bg="#2a2f3a" if api.dark else "#ffffff", fg=api.colors["text"],
                         insertbackground=api.colors["text"])
        w["t"].pack(fill="x", pady=4)
        w["t"].bind("<KeyRelease>", lambda e: changed())
        w["n"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["n"].pack(anchor="e")
        load()

    def count():
        if w.get("n") and w["n"].winfo_exists():
            text = w["t"].get("1.0", "end-1c")
            w["n"].configure(text=f"{len(text)} 文字 · {len(api.data['memos'])} 日分のメモ")

    def load():
        if not (w.get("t") and w["t"].winfo_exists()):
            return
        w["title"].configure(text=f"{s['day']:%Y/%m/%d}" + ("（今日）" if s["day"] == date.today() else ""))
        w["t"].delete("1.0", "end")
        w["t"].insert("1.0", api.data["memos"].get(key(), ""))
        count()

    def save():
        s["timer"] = None
        if not (w.get("t") and w["t"].winfo_exists()):
            return
        text = w["t"].get("1.0", "end-1c")
        if text.strip():
            api.data["memos"][key()] = text
        else:
            api.data["memos"].pop(key(), None)
        api.save_data()
        count()

    def changed():
        # 打つたびに保存しないよう、手が止まって1秒後に保存
        if s["timer"]:
            api.cancel(s["timer"])
        s["timer"] = api.after(1000, save)
        count()

    def flush():
        if s["timer"]:
            api.cancel(s["timer"])
            save()

    def move(d):
        flush()
        if s["day"] + timedelta(days=d) <= date.today():
            s["day"] += timedelta(days=d)
        load()

    def go_today():
        flush()
        s["day"] = date.today()
        load()

    def stamp():
        if w.get("t") and w["t"].winfo_exists():
            w["t"].insert("insert", f"[{datetime.now():%H:%M}] ")
            w["t"].focus_set()
            changed()

    def search():
        flush()
        q = simpledialog.askstring("メモの検索", "さがす言葉", parent=api.root)
        if not q:
            return
        hits = []
        for day in sorted(api.data["memos"], reverse=True):
            for line in api.data["memos"][day].splitlines():
                if q.lower() in line.lower():
                    hits.append(f"{day}  {line.strip()[:60]}")
        messagebox.showinfo("メモの検索", "\n".join(hits[:30]) or "見つかりませんでした", parent=api.root)

    @api.on("day_change")
    def new_day(day):
        flush()
        s["day"] = date.today()
        load()

    api.add_panel(build, title="メモ")
    api.add_action("メモを検索", search)


def teardown(api):
    api.save_data()
