"""バーチャルペット

作業するとごはんがもらえて元気になり、サボるとお腹がすいていくペットです。

1.1.0: ペットの種類えらび（とり・ねこ・ドラゴン）・なでる/おやつボタン・なかよし度・ひとことを追加
"""

import random
import time
from tkinter import messagebox, simpledialog, ttk

MOD_INFO = {
    "name": "バーチャルペット",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "作業するとペットが元気に育ちます。放っておくとお腹がすいてしょんぼり。種類えらび・なでる・おやつ・"
                   "なかよし度つき。",
    "api": 1,
}

# 種類 → [(成長に必要な累計作業時間（時間）, 見た目, 段階名), ...]
SPECIES = {
    "とり":     [(0, "🥚", "たまご"), (1, "🐣", "ひよこ"), (5, "🐥", "こども"), (20, "🐔", "おとな"), (60, "🦚", "伝説の鳥")],
    "ねこ":     [(0, "🧶", "毛玉"), (1, "🐱", "こねこ"), (5, "😺", "わかねこ"), (20, "🐈", "おとなねこ"), (60, "🦁", "百獣の王")],
    "ドラゴン": [(0, "🥚", "竜のたまご"), (1, "🦎", "とかげ"), (5, "🐊", "わに？"), (20, "🐲", "子竜"), (60, "🐉", "古竜")],
}
HUNGER_PER_HOUR = 12      # 実時間1時間でお腹が減る量（最大100）
SNACK_COST = 600          # おやつ1回に必要な作業秒数（作業10分で1個）

TALK = {
    "happy": ["るんるん♪", "いっしょにがんばろ！", "今日もいい日！", "作業してるとこ見るのすき"],
    "normal": ["なにしてるの？", "ふわぁ…", "ちょっとおなかすいたかも"],
    "hungry": ["おなかすいた…", "ごはん…（作業してね）", "くぅ〜"],
}


def stage(species, hours):
    stages = SPECIES.get(species, SPECIES["とり"])
    cur = stages[0]
    for st in stages:
        if hours >= st[0]:
            cur = st
    return cur


def setup(api):
    api.data.setdefault("name", "ぴよ")
    api.data.setdefault("species", "とり")
    api.data.setdefault("food", 70)       # 0〜100
    api.data.setdefault("love", 0)        # なかよし度 0〜100
    api.data.setdefault("grow_sec", 0)
    api.data.setdefault("snack_sec", 0)   # おやつのための作業秒数
    api.data.setdefault("updated", time.time())
    s = {"last": None, "n": 0, "talk": "", "pet_at": 0}
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

    def talk():
        f = api.data["food"]
        pool = TALK["happy"] if f >= 70 else TALK["normal"] if f >= 30 else TALK["hungry"]
        s["talk"] = random.choice(pool)

    def build(frame):
        w["pet"] = ttk.Label(frame, font=("Segoe UI Emoji", 34), cursor="hand2")
        w["pet"].pack(side="left")
        w["pet"].bind("<Button-1>", lambda e: pet())
        right = ttk.Frame(frame)
        right.pack(side="left", fill="x", expand=True, padx=10)
        w["name"] = ttk.Label(right, font=("Segoe UI", 11, "bold"))
        w["name"].pack(anchor="w")
        w["bar"] = ttk.Progressbar(right, maximum=100)
        w["bar"].pack(fill="x", pady=2)
        w["mood"] = ttk.Label(right, foreground=api.colors["sub"])
        w["mood"].pack(anchor="w")
        btns = ttk.Frame(right)
        btns.pack(anchor="w", pady=(2, 0))
        ttk.Button(btns, text="なでる", command=pet).pack(side="left")
        w["snack"] = ttk.Button(btns, command=snack)
        w["snack"].pack(side="left", padx=4)
        render()

    def render():
        if not (w.get("pet") and w["pet"].winfo_exists()):
            return
        hours = api.data["grow_sec"] / 3600
        need, look, name = stage(api.data["species"], hours)
        nxt = next((st for st in SPECIES[api.data["species"]] if st[0] > hours), None)
        grow = f" · 次の成長まで {nxt[0] - hours:.1f} 時間" if nxt else ""
        hearts = "♥" * (api.data["love"] // 20) + "♡" * (5 - api.data["love"] // 20)
        w["pet"].configure(text=look)
        w["name"].configure(text=f"{api.data['name']}（{name}） {hearts}" + (f"「{s['talk']}」" if s["talk"] else ""))
        w["bar"]["value"] = api.data["food"]
        w["mood"].configure(text=f"まんぷく度 {api.data['food']:.0f} · {mood()}{grow}")
        w["snack"].configure(text=f"おやつ（{api.data['snack_sec'] // SNACK_COST}個）")

    def pet():
        if time.time() - s["pet_at"] < 30:
            s["talk"] = "もうなでなでいっぱい〜"
        else:
            s["pet_at"] = time.time()
            api.data["love"] = min(100, api.data["love"] + 2)
            s["talk"] = random.choice(["えへへ", "♪", "もっと〜", "すりすり"])
            api.save_data()
        render()

    def snack():
        if api.data["snack_sec"] < SNACK_COST:
            s["talk"] = "おやつは作業10分で1個もらえるよ"
        else:
            api.data["snack_sec"] -= SNACK_COST
            api.data["food"] = min(100, api.data["food"] + 15)
            api.data["love"] = min(100, api.data["love"] + 5)
            s["talk"] = "おいしい！ ありがと！"
            api.save_data()
        render()

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        before = stage(api.data["species"], api.data["grow_sec"] / 3600)
        if last is not None and status["today_sec"] > last:
            d = status["today_sec"] - last
            api.data["grow_sec"] += d
            api.data["snack_sec"] = min(api.data["snack_sec"] + d, SNACK_COST * 10)
            api.data["food"] = min(100, api.data["food"] + d * 30 / 3600)   # 作業1時間で +30
        api.data["food"] = max(0, api.data["food"] - HUNGER_PER_HOUR / 3600)
        after = stage(api.data["species"], api.data["grow_sec"] / 3600)
        if after != before:
            api.notify(f"{after[1]} {api.data['name']} が「{after[2]}」に成長しました！")
        s["n"] += 1
        if s["n"] % 300 == 0:
            talk()
        if s["n"] % 60 == 0:
            api.data["updated"] = time.time()
            api.save_data()
        if s["n"] % 5 == 0:
            render()

    @api.on("goal_reached")
    def goal(goal_min, streak):
        api.data["love"] = min(100, api.data["love"] + 10)
        s["talk"] = "目標たっせい！ すごいすごい！"
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

    def choose():
        names = "・".join(SPECIES)
        v = simpledialog.askstring("バーチャルペット", f"種類をえらんでください（{names}）\n※成長はそのまま引きつぎます",
                                   parent=api.root, initialvalue=api.data["species"])
        if v and v.strip() in SPECIES:
            api.data["species"] = v.strip()
            api.save_data()
            render()
        elif v:
            messagebox.showerror("バーチャルペット", f"{names} のどれかを入力してください", parent=api.root)

    api.add_panel(build, title="ペット")
    api.add_action("名前を変える", rename)
    api.add_action("種類を変える", choose)


def teardown(api):
    api.data["updated"] = time.time()
    api.save_data()
