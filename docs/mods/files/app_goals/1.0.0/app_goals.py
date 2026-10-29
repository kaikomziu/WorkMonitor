"""アプリ別の目標

「VS Code を2時間」のように、アプリごとに1日の目標を決めて進み具合を表示します。
"""

from datetime import date
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "アプリ別の目標",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "アプリ（表示名）ごとに1日の目標時間を決めて、プログレスバーで表示します。達成したら通知します。",
    "api": 1,
}

EXAMPLE = "VS Code=120; Chrome=30"


def setup(api):
    api.data.setdefault("goals", {})        # 表示名 → 目標（分）
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "done": []})
    s = {"by_app": {}, "n": 0}
    w = {}

    def build(frame):
        w["frame"] = frame
        w["rows"] = {}
        if not api.data["goals"]:
            ttk.Label(frame, text="設定 → Mods の「目標を設定」でアプリを登録してください").pack(anchor="w")
        for name, mins in api.data["goals"].items():
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=name, width=14).pack(side="left")
            bar = ttk.Progressbar(row, maximum=mins * 60)
            bar.pack(side="left", fill="x", expand=True, padx=6)
            lab = ttk.Label(row, width=12, foreground=api.colors["sub"])
            lab.pack(side="left")
            w["rows"][name] = (bar, lab)
        render()

    def render():
        if not (w.get("frame") and w["frame"].winfo_exists()):
            return
        for name, (bar, lab) in w["rows"].items():
            sec = s["by_app"].get(name, 0)
            goal = api.data["goals"].get(name, 1) * 60
            bar["value"] = min(sec, goal)
            lab.configure(text="✅ 達成" if sec >= goal else f"{sec // 60}/{goal // 60}分")

    @api.on("tick")
    def tick(status):
        s["by_app"] = status["today_by_app"]
        for name, mins in api.data["goals"].items():
            if s["by_app"].get(name, 0) >= mins * 60 and name not in api.data["done"]:
                api.data["done"].append(name)
                api.save_data()
                api.notify(f"✅ {name} の目標 {mins} 分を達成しました！")
        s["n"] += 1
        if s["n"] % 5 == 0:
            render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "done": []})
        api.save_data()

    def edit():
        cur = "; ".join(f"{k}={v}" for k, v in api.data["goals"].items())
        names = ", ".join(list(s["by_app"])[:8])
        v = simpledialog.askstring("アプリ別の目標",
                                   f"「アプリの表示名=分」を ; で区切って入力\n例: {EXAMPLE}\n今日使ったアプリ: {names}",
                                   parent=api.root, initialvalue=cur or EXAMPLE)
        if v is None:
            return
        goals = {}
        for part in v.split(";"):
            if "=" in part:
                k, m = part.split("=", 1)
                if m.strip().isdigit():
                    goals[k.strip()] = int(m.strip())
        api.data["goals"] = goals
        api.save_data()
        api.refresh_panels()

    api.add_panel(build, title="アプリ別の目標")
    api.add_action("目標を設定", edit)
