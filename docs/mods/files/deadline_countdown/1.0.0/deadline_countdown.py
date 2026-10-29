"""締め切りカウントダウン

締め切りを登録すると、あと何日かをメイン画面に表示します。近づくと色が変わり、前日と当日に通知します。
"""

from datetime import date
from tkinter import messagebox, simpledialog, ttk

MOD_INFO = {
    "name": "締め切りカウントダウン",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "締め切りを登録すると残り日数を表示します。3日前から赤くなり、前日・当日の朝に通知します。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("items", [])        # [{"name", "date": "YYYY-MM-DD"}]
    api.data.setdefault("notified", [])     # 通知ずみの "名前|日付|残り日数"
    w = {}

    def days_left(item):
        return (date.fromisoformat(item["date"]) - date.today()).days

    def build(frame):
        w["frame"] = frame
        w["list"] = ttk.Frame(frame)
        w["list"].pack(fill="x")
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(4, 0))
        ttk.Button(bottom, text="追加", command=add).pack(side="left")
        ttk.Button(bottom, text="過ぎたものを消す", command=clean).pack(side="left", padx=6)
        render()

    def render():
        if not (w.get("list") and w["list"].winfo_exists()):
            return
        for c in w["list"].winfo_children():
            c.destroy()
        items = sorted(api.data["items"], key=lambda it: it["date"])
        if not items:
            ttk.Label(w["list"], text="締め切りはありません", foreground=api.colors["sub"]).pack(anchor="w")
        for it in items:
            n = days_left(it)
            if n < 0:
                text, color = f"✔ {it['name']}（{-n}日前に終了）", api.colors["sub"]
            elif n == 0:
                text, color = f"🔥 {it['name']} … 今日が締め切り！", api.colors["red"]
            else:
                text = f"📅 {it['name']} … あと {n} 日（{it['date']}）"
                color = api.colors["red"] if n <= 3 else api.colors["orange"] if n <= 7 else api.colors["text"]
            row = ttk.Frame(w["list"])
            row.pack(fill="x")
            ttk.Label(row, text=text, foreground=color).pack(side="left")
            ttk.Button(row, text="×", width=2, command=lambda it=it: remove(it)).pack(side="right")

    def check():
        for it in api.data["items"]:
            n = days_left(it)
            key = f"{it['name']}|{it['date']}|{n}"
            if n in (0, 1) and key not in api.data["notified"]:
                api.data["notified"].append(key)
                api.save_data()
                api.notify(f"🔥 今日が「{it['name']}」の締め切りです！" if n == 0 else f"⏰ 明日は「{it['name']}」の締め切りです")

    def add():
        name = simpledialog.askstring("締め切り", "なんの締め切り？", parent=api.root)
        if not name:
            return
        d = simpledialog.askstring("締め切り", "日付（YYYY-MM-DD）", parent=api.root, initialvalue=date.today().isoformat())
        try:
            date.fromisoformat((d or "").strip())
        except ValueError:
            messagebox.showerror("締め切り", "日付は 2026-12-31 のように入力してください", parent=api.root)
            return
        api.data["items"].append({"name": name.strip(), "date": d.strip()})
        api.save_data()
        render()
        check()

    def remove(it):
        api.data["items"].remove(it)
        api.save_data()
        render()

    def clean():
        api.data["items"] = [it for it in api.data["items"] if days_left(it) >= 0]
        api.save_data()
        render()

    @api.on("day_change")
    def new_day(day):
        render()
        check()

    api.add_panel(build, title="締め切り")
    api.add_action("締め切りを追加", add)
    check()
