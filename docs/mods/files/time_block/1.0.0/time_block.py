"""時間帯ブロック

「9:00-12:00 は開発」のように時間帯ごとにやるカテゴリを決めておき、
ちがうカテゴリのアプリで作業していたら知らせます。
"""

import time
from datetime import datetime
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "時間帯ブロック",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "時間帯ごとにやるカテゴリを決め、ちがうカテゴリで1分以上作業すると知らせます（10分に1回まで）。",
    "api": 1,
}

EXAMPLE = "09:00-12:00=開発; 13:00-15:00=デザイン"


def parse(text):
    blocks = []
    for part in text.split(";"):
        part = part.strip()
        if "=" not in part or "-" not in part:
            continue
        span, cat = part.split("=", 1)
        start, end = span.split("-", 1)
        blocks.append({"start": start.strip().zfill(5), "end": end.strip().zfill(5), "category": cat.strip()})
    return blocks


def setup(api):
    api.data.setdefault("blocks", [])
    s = {"miss": 0, "last_warn": 0, "n": 0}
    w = {}

    def current():
        now = datetime.now().strftime("%H:%M")
        for b in api.data["blocks"]:
            if b["start"] <= now < b["end"]:
                return b
        return None

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        b = current()
        if not api.data["blocks"]:
            w["l"].configure(text="設定 → Mods の「ブロックを設定」で時間帯を決めてください")
        elif b:
            w["l"].configure(text=f"⏰ 今は「{b['category']}」の時間（{b['start']}〜{b['end']}）")
        else:
            w["l"].configure(text="今は自由時間です")

    @api.on("tick")
    def tick(status):
        b = current()
        if b and status["state"] == "working" and status["category"] != b["category"]:
            s["miss"] += 1
            if s["miss"] >= 60 and time.time() - s["last_warn"] > 600:
                s["last_warn"] = time.time()
                api.notify(f"⏰ 今は「{b['category']}」の時間です（いまは {status['category']}：{status['app_name']}）")
        else:
            s["miss"] = 0
        s["n"] += 1
        if s["n"] % 30 == 0:
            render()

    def edit():
        cur = "; ".join(f"{b['start']}-{b['end']}={b['category']}" for b in api.data["blocks"])
        v = simpledialog.askstring("時間帯ブロック", f"「開始-終了=カテゴリ」を ; で区切って入力\n例: {EXAMPLE}",
                                   parent=api.root, initialvalue=cur or EXAMPLE)
        if v is not None:
            api.data["blocks"] = parse(v)
            api.save_data()
            render()

    api.add_panel(build, title="時間帯ブロック")
    api.add_action("ブロックを設定", edit)
