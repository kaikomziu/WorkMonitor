"""フロー検知

同じアプリで長く作業が続いたら「フロー状態」と判定して、オーバーレイに 🔥 を出します。

1.1.0: 判定までの時間を変更可能に。今日のフロー回数・最長フローをパネルに表示
"""

from datetime import date
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "フロー検知",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "同じアプリで30分（変更可）以上作業が続くとフロー状態と判定し、オーバーレイに🔥を表示して通知します。"
                   "今日のフロー回数と最長記録も表示します。",
    "api": 1,
}


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分" if h else f"{m}分"


def setup(api):
    api.data.setdefault("flow_min", 30)
    api.data.setdefault("best", 0)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "count": 0, "today_best": 0, "apps": {}})
    s = {"app": None, "name": "", "sec": 0, "last": None, "flow": False}
    w = {}

    def stop():
        if s["flow"]:
            api.data["today_best"] = max(api.data["today_best"], s["sec"])
            api.data["best"] = max(api.data["best"], s["sec"])
            api.data["apps"][s["name"]] = api.data["apps"].get(s["name"], 0) + 1
            api.save_data()
            api.log(f"フロー終了: {s['name']} {fmt(s['sec'])}")
        s.update({"sec": 0, "flow": False})
        render()

    def build(frame):
        w["l"] = ttk.Label(frame, font=("Segoe UI", 12, "bold"))
        w["l"].pack(anchor="w")
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        need = api.data["flow_min"] * 60
        if s["flow"]:
            w["l"].configure(text=f"🔥 フロー中！ {s['name']} {fmt(s['sec'])}")
        else:
            w["l"].configure(text=f"🧊 フローまで あと {fmt(max(0, need - s['sec']))}")
        top = max(api.data["apps"].items(), key=lambda kv: kv[1], default=None)
        fav = f" · よく入るアプリ {top[0]}" if top else ""
        w["sub"].configure(text=f"今日 {api.data['count']} 回 · 今日の最長 {fmt(api.data['today_best'])}"
                                f" · 歴代最長 {fmt(api.data['best'])}{fav}")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if status["app"] != s["app"]:
            stop()
            s["app"], s["name"] = status["app"], status["app_name"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= api.data["flow_min"] * 60 and not s["flow"]:
            s["flow"] = True
            api.data["count"] += 1
            api.save_data()
            api.notify(f"🔥 {status['app_name']} でフロー状態です！ このまま集中しよう。")
        if s["flow"]:
            api.data["today_best"] = max(api.data["today_best"], s["sec"])
        if status["today_sec"] % 10 == 0:
            render()

    @api.on("state_change")
    def changed(old, new, status):
        if new != "working":
            stop()

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "count": 0, "today_best": 0, "apps": {}})
        s["last"] = None
        api.save_data()

    @api.filter("overlay_text")
    def overlay(text):
        return f"🔥フロー {s['sec'] // 60}分 · {text}" if s["flow"] else text

    def set_min():
        v = simpledialog.askinteger("フロー検知", "何分続いたらフローと判定する？", parent=api.root,
                                    initialvalue=api.data["flow_min"], minvalue=5, maxvalue=240)
        if v:
            api.data["flow_min"] = v
            api.save_data()
            render()

    api.add_panel(build, title="フロー")
    api.add_action("判定までの時間を変える", set_min)
