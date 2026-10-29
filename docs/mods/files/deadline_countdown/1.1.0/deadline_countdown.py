"""締め切りカウントダウン

締め切りを登録すると、あと何日かをメイン画面に表示します。近づくと色が変わり、前日と当日に通知します。

1.1.0: 時刻つきの締め切り（当日は残り時間を表示）・3日前と7日前の通知・オーバーレイに直近の締め切りを追加
"""

from datetime import date, datetime
from tkinter import messagebox, simpledialog, ttk

MOD_INFO = {
    "name": "締め切りカウントダウン",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "締め切りを登録すると残り日数を表示します。時刻を入れると当日は残り時間も出ます。"
                   "7日前・3日前・前日・当日に通知し、オーバーレイに直近の締め切りを出します。",
    "api": 1,
}

NOTIFY_DAYS = (7, 3, 1, 0)


def setup(api):
    api.data.setdefault("items", [])        # [{"name", "date": "YYYY-MM-DD", "time": "HH:MM" or ""}]
    api.data.setdefault("notified", [])     # 通知ずみの "名前|日付|残り日数"
    api.data.setdefault("overlay", True)
    s = {"n": 0}
    w = {}

    def days_left(item):
        return (date.fromisoformat(item["date"]) - date.today()).days

    def due(item):
        t = item.get("time") or "23:59"
        return datetime.fromisoformat(f"{item['date']} {t}")

    def build(frame):
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
        items = sorted(api.data["items"], key=due)
        if not items:
            ttk.Label(w["list"], text="締め切りはありません", foreground=api.colors["sub"]).pack(anchor="w")
        for it in items:
            n = days_left(it)
            at = f" {it['time']}" if it.get("time") else ""
            rest = (due(it) - datetime.now()).total_seconds()
            if rest < 0:
                text, color = f"✔ {it['name']}（終了）", api.colors["sub"]
            elif n == 0:
                h, m = divmod(int(rest) // 60, 60)
                text, color = f"🔥 {it['name']} … 今日{at}！ あと {h}時間{m:02d}分", api.colors["red"]
            else:
                text = f"📅 {it['name']} … あと {n} 日（{it['date']}{at}）"
                color = api.colors["red"] if n <= 3 else api.colors["orange"] if n <= 7 else api.colors["text"]
            row = ttk.Frame(w["list"])
            row.pack(fill="x")
            ttk.Label(row, text=text, foreground=color).pack(side="left")
            ttk.Button(row, text="×", width=2, command=lambda it=it: remove(it)).pack(side="right")

    def check():
        for it in api.data["items"]:
            n = days_left(it)
            key = f"{it['name']}|{it['date']}|{n}"
            if n in NOTIFY_DAYS and key not in api.data["notified"]:
                api.data["notified"].append(key)
                api.data["notified"] = api.data["notified"][-200:]
                api.save_data()
                if n == 0:
                    api.notify(f"🔥 今日が「{it['name']}」の締め切りです！")
                elif n == 1:
                    api.notify(f"⏰ 明日は「{it['name']}」の締め切りです")
                else:
                    api.notify(f"📅 「{it['name']}」の締め切りまで あと {n} 日")

    def add():
        name = simpledialog.askstring("締め切り", "なんの締め切り？", parent=api.root)
        if not name:
            return
        d = simpledialog.askstring("締め切り", "日付（YYYY-MM-DD）", parent=api.root, initialvalue=date.today().isoformat())
        t = simpledialog.askstring("締め切り", "時刻（HH:MM、なければ空のまま）", parent=api.root) or ""
        try:
            date.fromisoformat((d or "").strip())
            if t.strip():
                datetime.strptime(t.strip(), "%H:%M")
        except ValueError:
            messagebox.showerror("締め切り", "日付は 2026-12-31、時刻は 18:00 のように入力してください", parent=api.root)
            return
        api.data["items"].append({"name": name.strip(), "date": d.strip(), "time": t.strip().zfill(5) if t.strip() else ""})
        api.save_data()
        render()
        check()

    def remove(it):
        api.data["items"].remove(it)
        api.save_data()
        render()

    def clean():
        api.data["items"] = [it for it in api.data["items"] if due(it) >= datetime.now()]
        api.save_data()
        render()

    @api.on("tick")
    def tick(status):
        s["n"] += 1
        if s["n"] % 60 == 0:
            render()

    @api.on("day_change")
    def new_day(day):
        render()
        check()

    @api.filter("overlay_text")
    def overlay(text):
        if not api.data["overlay"]:
            return text
        future = [it for it in api.data["items"] if due(it) >= datetime.now()]
        if not future:
            return text
        it = min(future, key=due)
        n = days_left(it)
        return f"{text} · 📅{it['name'][:8]} {'今日' if n == 0 else f'あと{n}日'}"

    def toggle_overlay():
        api.data["overlay"] = not api.data["overlay"]
        api.save_data()

    api.add_panel(build, title="締め切り")
    api.add_action("締め切りを追加", add)
    api.add_action("オーバーレイ表示のオン／オフ", toggle_overlay)
    check()
