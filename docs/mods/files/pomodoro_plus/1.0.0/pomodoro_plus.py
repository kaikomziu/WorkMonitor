"""ポモドーロ強化版

作業 → 休憩 → 作業 … のサイクルを回すタイマーです。
作業フェーズは作業中だけ進み、休憩フェーズは実時間で進みます。
長さは 設定 → Mods のボタンで変えられます。
"""

from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "ポモドーロ強化版",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業（作業中だけ進む）と休憩（実時間で進む）を交互にくり返すタイマー。4回ごとに長い休憩になります。",
    "api": 1,
}


def setup(api):
    api.data.setdefault("work_min", 25)
    api.data.setdefault("break_min", 5)
    api.data.setdefault("long_min", 15)
    s = {"phase": "work", "sec": 0, "last": None, "cycle": 0}
    w = {}

    def length():
        if s["phase"] == "work":
            return api.data["work_min"] * 60
        return (api.data["long_min"] if s["cycle"] % 4 == 0 else api.data["break_min"]) * 60

    def fmt(sec):
        m, sec = divmod(max(0, int(sec)), 60)
        return f"{m:02d}:{sec:02d}"

    def label():
        icon = "🍅" if s["phase"] == "work" else "☕"
        return f"{icon} {fmt(length() - s['sec'])}"

    def build(frame):
        w["time"] = ttk.Label(frame, font=("Segoe UI", 16, "bold"))
        w["time"].pack(side="left")
        w["info"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["info"].pack(side="left", padx=10)
        ttk.Button(frame, text="スキップ", command=skip).pack(side="right")
        render()

    def render():
        if not (w.get("time") and w["time"].winfo_exists()):
            return
        w["time"].configure(text=label())
        phase = "作業" if s["phase"] == "work" else "休憩"
        w["info"].configure(text=f"{phase}中 · 完了 {s['cycle']} 回")

    def next_phase():
        if s["phase"] == "work":
            s["cycle"] += 1
            s["phase"] = "break"
            kind = "長い休憩" if s["cycle"] % 4 == 0 else "休憩"
            api.notify(f"🍅 {api.data['work_min']}分おつかれさま！ {length() // 60}分の{kind}にしましょう。")
        else:
            s["phase"] = "work"
            api.notify("☕ 休憩おわり！ 次のポモドーロを始めましょう。")
        s["sec"] = 0

    def skip():
        next_phase()
        render()

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if s["phase"] == "work":
            # 作業時間が増えた分だけ進める
            if last is not None and status["today_sec"] > last:
                s["sec"] += status["today_sec"] - last
        else:
            s["sec"] += 1
        if s["sec"] >= length():
            next_phase()
        render()

    @api.on("day_change")
    def new_day(day):
        s.update({"phase": "work", "sec": 0, "last": None, "cycle": 0})

    @api.filter("overlay_text")
    def overlay(text):
        return f"{text} · {label()}"

    def set_lengths():
        for key, name in (("work_min", "作業"), ("break_min", "短い休憩"), ("long_min", "長い休憩")):
            v = simpledialog.askinteger("ポモドーロ強化版", f"{name}の長さ（分）", parent=api.root,
                                        initialvalue=api.data[key], minvalue=1, maxvalue=180)
            if v:
                api.data[key] = v
        api.save_data()
        render()

    api.add_panel(build, title="ポモドーロ強化版")
    api.add_action("長さを変える", set_lengths)
    api.add_action("次のフェーズへ", skip)
