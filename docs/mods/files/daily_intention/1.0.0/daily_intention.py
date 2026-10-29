"""作業開始の宣言

その日に初めて作業を始めたとき「今日やること」を聞いて、メイン画面に出しておきます。
"""

from datetime import date
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "作業開始の宣言",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "その日最初の作業開始時に「今日やること」を入力し、メイン画面に表示します。過去の宣言も保存されます。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("history", {})
    w = {}

    def today():
        return date.today().isoformat()

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 12, "bold"), wraplength=380, justify="left")
        w["l"].pack(side="left", anchor="w")
        ttk.Button(frame, text="書きかえ", command=ask).pack(side="right")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        text = api.data["history"].get(today())
        w["l"].configure(text=f"🎯 {text}" if text else "（まだ宣言していません）")

    def ask():
        v = simpledialog.askstring("作業開始の宣言", "今日やることは？", parent=api.root,
                                   initialvalue=api.data["history"].get(today(), ""))
        if v:
            api.data["history"][today()] = v.strip()
            api.save_data()
            render()

    @api.on("state_change")
    def changed(old, new, status):
        # その日まだ聞いていなければ、最初の作業開始で1回だけ聞く
        if new == "working" and today() not in api.data["history"] and api.data.get("asked") != today():
            api.data["asked"] = today()
            api.save_data()
            api.after(500, ask)

    @api.on("day_change")
    def new_day(day):
        render()

    api.add_panel(build, title="今日やること")
    api.add_action("今日やることを入力", ask)
