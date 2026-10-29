"""ToDo リスト

メイン画面に小さな ToDo リストを置きます。チェックすると完了、完了したものはまとめて消せます。

1.1.0: 1件ずつの削除・★で重要マーク（上に並ぶ）・ダブルクリックで書きかえ・今日完了した数を追加
"""

from datetime import date
import tkinter as tk
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "ToDo リスト",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "メイン画面に ToDo リストを置きます。入力して Enter で追加、チェックで完了、★で重要、"
                   "ダブルクリックで書きかえ。今日完了した数も出ます。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("items", [])       # [{"text", "done", "star"}]
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "done_today": 0})
    w = {}

    def ordered():
        # 未完了の★ → 未完了 → 完了 の順
        return sorted(api.data["items"], key=lambda it: (it["done"], not it.get("star")))

    def build(frame):
        entry = ttk.Entry(frame)
        entry.pack(fill="x")
        entry.bind("<Return>", lambda e: add(entry))
        w["list"] = ttk.Frame(frame)
        w["list"].pack(fill="x", pady=4)
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x")
        w["count"] = ttk.Label(bottom, foreground=api.colors["sub"])
        w["count"].pack(side="left")
        ttk.Button(bottom, text="完了したものを消す", command=clear_done).pack(side="right")
        render()

    def render():
        if not (w.get("list") and w["list"].winfo_exists()):
            return
        for child in w["list"].winfo_children():
            child.destroy()
        for item in ordered():
            row = ttk.Frame(w["list"])
            row.pack(fill="x")
            var = tk.BooleanVar(value=item["done"])
            text = ("✓ " if item["done"] else "") + item["text"]
            cb = ttk.Checkbutton(row, text=text, variable=var, command=lambda it=item, v=var: toggle(it, v.get()))
            cb.pack(side="left")
            cb.bind("<Double-Button-1>", lambda e, it=item: edit(it))
            ttk.Button(row, text="×", width=2, command=lambda it=item: remove(it)).pack(side="right")
            ttk.Button(row, text="★" if item.get("star") else "☆", width=2,
                       command=lambda it=item: star(it)).pack(side="right")
        left = sum(1 for it in api.data["items"] if not it["done"])
        if api.data["items"]:
            w["count"].configure(text=f"残り {left} 件 · 今日 {api.data['done_today']} 件完了")
        else:
            w["count"].configure(text="上の欄に入力して Enter で追加")

    def add(entry):
        text = entry.get().strip()
        if text:
            api.data["items"].append({"text": text, "done": False, "star": False})
            api.save_data()
            entry.delete(0, "end")
            render()

    def toggle(item, done):
        item["done"] = done
        api.data["done_today"] += 1 if done else -1
        api.data["done_today"] = max(0, api.data["done_today"])
        api.save_data()
        render()
        if done and all(it["done"] for it in api.data["items"]):
            api.notify("🎉 ToDo をぜんぶ終わらせました！")

    def star(item):
        item["star"] = not item.get("star")
        api.save_data()
        render()

    def edit(item):
        v = simpledialog.askstring("ToDo", "書きかえ", parent=api.root, initialvalue=item["text"])
        if v and v.strip():
            item["text"] = v.strip()
            api.save_data()
            render()

    def remove(item):
        api.data["items"].remove(item)
        api.save_data()
        render()

    def clear_done():
        api.data["items"] = [it for it in api.data["items"] if not it["done"]]
        api.save_data()
        render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "done_today": 0})
        api.save_data()
        render()

    api.add_panel(build, title="ToDo")
