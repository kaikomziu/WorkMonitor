"""バーチャルペット

作業するとごはんがもらえて元気になり、サボるとお腹がすいていくペットです。
"""

import time
from tkinter import simpledialog, ttk

MOD_INFO = {
    "name": "バーチャルペット",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業するとペットが元気に育ちます。放っておくとお腹がすいてしょんぼり。作業時間で成長もします。",
    "api": 1,
}

# (成長に必要な累計作業時間（時間）, 見た目, 段階名)
STAGES = [(0, "🥚", "たまご"), (1, "🐣", "ひよこ"), (5, "🐥", "こども"), (20, "🐔", "おとな"), (60, "🦚", "伝説の鳥")]
HUNGER_PER_HOUR = 12      # 実時間1時間でお腹が減る量（最大100）


def stage(hours):
    cur = STAGES[0]
    for st in STAGES:
        if hours >= st[0]:
            cur = st
    return cur


def setup(api):
    api.data.setdefault("name", "ぴよ")
    api.data.setdefault("food", 70)       # 0〜100
    api.data.setdefault("grow_sec", 0)
    api.data.setdefault("updated", time.time())
    s = {"last": None, "n": 0}
    w = {}

    # 閉じていた間にお腹が減った分を反映（ただし 0 より下にはしない）
    away_h = (time.time() - api.data["updated"]) / 3600
    api.data["food"] = max(0, api.data["food"] - away_h * HUNGER_PER_HOUR)

    def mood():
        f = api.data["food"]
        if f >= 70:
            return "ごきげん♪"
        if f >= 40:
            return "ふつう"
        if f >= 15:
            return "おなかすいた…"
        return "😢 ぐったり…作業してごはんを！"

    def build(frame):
        w["pet"] = ttk.Label(frame, font=("Segoe UI Emoji", 34))
        w["pet"].pack(side="left")
        right = ttk.Frame(frame)
        right.pack(side="left", fill="x", expand=True, padx=10)
        w["name"] = ttk.Label(right, font=("Segoe UI", 11, "bold"))
        w["name"].pack(anchor="w")
        w["bar"] = ttk.Progressbar(right, maximum=100)
        w["bar"].pack(fill="x", pady=2)
        w["mood"] = ttk.Label(right, foreground=api.colors["sub"])
        w["mood"].pack(anchor="w")
        render()

    def render():
        if not (w.get("pet") and w["pet"].winfo_exists()):
            return
        hours = api.data["grow_sec"] / 3600
        need, look, name = stage(hours)
        nxt = next((st for st in STAGES if st[0] > hours), None)
        grow = f" · 次の成長まで {nxt[0] - hours:.1f} 時間" if nxt else ""
        w["pet"].configure(text=look)
        w["name"].configure(text=f"{api.data['name']}（{name}）")
        w["bar"]["value"] = api.data["food"]
        w["mood"].configure(text=f"まんぷく度 {api.data['food']:.0f} · {mood()}{grow}")

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        before = stage(api.data["grow_sec"] / 3600)
        if last is not None and status["today_sec"] > last:
            d = status["today_sec"] - last
            api.data["grow_sec"] += d
            api.data["food"] = min(100, api.data["food"] + d * 30 / 3600)   # 作業1時間で +30
        api.data["food"] = max(0, api.data["food"] - HUNGER_PER_HOUR / 3600)
        after = stage(api.data["grow_sec"] / 3600)
        if after != before:
            api.notify(f"{after[1]} {api.data['name']} が「{after[2]}」に成長しました！")
        s["n"] += 1
        if s["n"] % 60 == 0:
            api.data["updated"] = time.time()
            api.save_data()
        if s["n"] % 5 == 0:
            render()

    @api.on("day_change")
    def new_day(day):
        s["last"] = None

    def rename():
        v = simpledialog.askstring("バーチャルペット", "ペットの名前", parent=api.root, initialvalue=api.data["name"])
        if v:
            api.data["name"] = v
            api.save_data()
            render()

    api.add_panel(build, title="ペット")
    api.add_action("名前を変える", rename)


def teardown(api):
    api.data["updated"] = time.time()
    api.save_data()
