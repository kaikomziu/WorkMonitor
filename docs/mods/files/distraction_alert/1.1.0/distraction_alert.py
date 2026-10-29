"""脱線警告

数えないアプリ（動画・SNS など）を使い続けていたら「作業に戻ろう」と知らせます。

1.1.0: 今日の脱線時間をアプリ別にパネル表示・1日の脱線の上限を追加
"""

from datetime import date
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "脱線警告",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "数えないアプリを続けて5分（変更可）使うと作業に戻るよう通知します。今日の脱線時間をアプリ別に表示し、"
                   "1日の上限を超えたときも知らせます。",
    "api": 1,
}


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    api.data.setdefault("limit_min", 5)
    api.data.setdefault("day_limit_min", 60)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "apps": {}, "over": False})
    s = {"sec": 0, "n": 0}
    w = {}

    def total():
        return sum(api.data["apps"].values())

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(anchor="w")
        w["bar"] = ttk.Progressbar(frame)
        w["bar"].pack(fill="x", pady=2)
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        lim = api.data["day_limit_min"] * 60
        w["l"].configure(text=f"📺 今日の脱線 {fmt(total())} / 上限 {api.data['day_limit_min']}分")
        w["bar"].configure(maximum=lim, value=min(total(), lim))
        top = sorted(api.data["apps"].items(), key=lambda kv: -kv[1])[:3]
        w["sub"].configure(text="  ".join(f"{k} {fmt(v)}" for k, v in top) or "脱線なし 👍")

    @api.on("tick")
    def tick(status):
        s["n"] += 1
        if status["state"] != "excluded":
            s["sec"] = 0
            return
        s["sec"] += 1
        name = status["app_name"]
        api.data["apps"][name] = api.data["apps"].get(name, 0) + 1
        if s["sec"] % (api.data["limit_min"] * 60) == 0:
            api.notify(f"👀 {name} を {s['sec'] // 60}分 使っています。そろそろ作業に戻りませんか？")
        if total() >= api.data["day_limit_min"] * 60 and not api.data["over"]:
            api.data["over"] = True
            api.notify(f"🚨 今日の脱線が上限 {api.data['day_limit_min']}分 を超えました！")
        if s["n"] % 30 == 0:
            api.save_data()
        if s["n"] % 5 == 0:
            render()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "apps": {}, "over": False})
        api.save_data()
        render()

    def set_limit():
        v = simpledialog.askinteger("脱線警告", "続けて何分使ったら知らせる？", parent=api.root,
                                    initialvalue=api.data["limit_min"], minvalue=1, maxvalue=120)
        if v:
            api.data["limit_min"] = v
        v = simpledialog.askinteger("脱線警告", "1日の脱線の上限（分）", parent=api.root,
                                    initialvalue=api.data["day_limit_min"], minvalue=5, maxvalue=600)
        if v:
            api.data["day_limit_min"] = v
        api.save_data()
        render()

    api.add_panel(build, title="脱線")
    api.add_action("知らせる時間・上限を変える", set_limit)


def teardown(api):
    api.save_data()
