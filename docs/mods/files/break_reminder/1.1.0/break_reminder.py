"""休憩リマインダー

休まずに作業が続いたら、休憩をすすめる通知を出します。

1.1.0: 連続作業時間のパネル表示・休憩回数の記録・オーバーレイの警告表示を追加
"""

from datetime import date
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "休憩リマインダー",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "連続で作業した時間が一定（初期60分）を超えると休憩をすすめます。休憩中が3分続くとリセット。"
                   "連続作業時間をメイン画面に表示します。",
    "api": 1,
}

RESET_IDLE_SEC = 180   # この秒数だけ休憩が続いたら「休んだ」とみなす
REPEAT_MIN = 15        # 休まなかったときに、もう一度知らせるまでの分


def setup(api):
    api.data.setdefault("limit_min", 60)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "breaks": 0})
    s = {"work": 0, "idle": 0, "next": 0, "last": None, "rested": True}
    w = {}

    def reset():
        s["work"] = 0
        s["next"] = api.data["limit_min"] * 60

    reset()

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(anchor="w")
        w["bar"] = ttk.Progressbar(frame)
        w["bar"].pack(fill="x", pady=(3, 0))
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        limit = api.data["limit_min"] * 60
        m = s["work"] // 60
        mark = "🔴" if s["work"] >= limit else "🟡" if s["work"] >= limit * 0.75 else "🟢"
        w["l"].configure(text=f"{mark} 連続作業 {m}分 / {api.data['limit_min']}分 · 今日の休憩 {api.data['breaks']} 回")
        w["bar"].configure(maximum=limit, value=min(s["work"], limit))

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if status["state"] == "working":
            s["idle"] = 0
            s["rested"] = False
            if last is not None and status["today_sec"] > last:
                s["work"] += status["today_sec"] - last
        else:
            s["idle"] += 1
            if s["idle"] >= RESET_IDLE_SEC and not s["rested"]:
                s["rested"] = True
                if s["work"] >= 600:
                    api.data["breaks"] += 1
                    api.save_data()
                reset()
        if s["work"] >= s["next"]:
            api.notify(f"⏸ {s['work'] // 60}分 休まず作業しています。少し休憩しませんか？")
            s["next"] += REPEAT_MIN * 60
        if status["today_sec"] % 5 == 0 or status["state"] != "working":
            render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "breaks": 0})
        api.save_data()

    @api.filter("overlay_text")
    def overlay(text):
        return f"⏸休憩して · {text}" if s["work"] >= api.data["limit_min"] * 60 else text

    def set_limit():
        v = simpledialog.askinteger("休憩リマインダー", "何分続けて作業したら知らせる？", parent=api.root,
                                    initialvalue=api.data["limit_min"], minvalue=5, maxvalue=600)
        if v:
            api.data["limit_min"] = v
            api.save_data()
            reset()
            render()

    def rested():
        reset()
        render()

    api.add_panel(build, title="休憩リマインダー")
    api.add_action("知らせる時間を変える", set_limit)
    api.add_action("いま休んだことにする", rested)
