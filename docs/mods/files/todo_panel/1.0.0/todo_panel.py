"""ToDo リスト

メイン画面に小さな ToDo リストを置きます。チェックすると完了、完了したものはまとめて消せます。
"""

import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "ToDo リスト",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "メイン画面に ToDo リストを置きます。入力して Enter で追加、チェックで完了。内容は保存されます。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("items", [])       # [{"text": ..., "done": bool}]
    w = {}

    def build(frame):
        w["frame"] = frame
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
        for i, item in enumerate(api.data["items"]):
            var = tk.BooleanVar(value=item["done"])
            text = ("✓ " if item["done"] else "") + item["text"]
            ttk.Checkbutton(w["list"], text=text, variable=var,
                            command=lambda i=i, v=var: toggle(i, v.get())).pack(anchor="w")
        left = sum(1 for it in api.data["items"] if not it["done"])
        w["count"].configure(text=f"残り {left} 件" if api.data["items"] else "上の欄に入力して Enter で追加")

    def add(entry):
        text = entry.get().strip()
        if text:
            api.data["items"].append({"text": text, "done": False})
            api.save_data()
            entry.delete(0, "end")
            render()

    def toggle(i, done):
        api.data["items"][i]["done"] = done
        api.save_data()
        render()
        if done and all(it["done"] for it in api.data["items"]):
            api.notify("🎉 ToDo をぜんぶ終わらせました！")

    def clear_done():
        api.data["items"] = [it for it in api.data["items"] if not it["done"]]
        api.save_data()
        render()

    api.add_panel(build, title="ToDo")
