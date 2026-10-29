"""作業ガチャ

作業30分ごとにガチャチケットが1枚もらえます。引いて図鑑をコンプリートしよう。

1.1.0: 10連ガチャ（SR以上1つ確定）・天井（50回で SSR 確定）・アイテム追加・レア度別のコンプ報酬を追加
"""

import random
from datetime import datetime
from tkinter import messagebox, ttk

MOD_INFO = {
    "name": "作業ガチャ",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "作業30分でガチャチケット1枚。N・R・SR・SSR・UR のアイテムを集めて図鑑を埋めましょう。"
                   "10連はSR以上確定、50回で SSR 確定の天井つき。",
    "api": 1,
}

TICKET_SEC = 30 * 60
PITY = 50

# レア度 → (出る確率 %, アイテム)
POOL = {
    "N":   (58, ["🍙 おにぎり", "☕ コーヒー", "📎 クリップ", "✏ えんぴつ", "🧦 くつした", "🍪 クッキー",
                 "📓 ノート", "🧃 ジュース", "🧻 ティッシュ", "🍬 あめ", "📌 画びょう", "🥤 炭酸水"]),
    "R":   (28, ["⌨ キーボード", "🎧 ヘッドホン", "🪴 観葉植物", "🕶 サングラス", "📚 技術書", "🧸 くま",
                 "🖱 マウス", "🕯 アロマキャンドル", "⏰ 目覚まし時計"]),
    "SR":  (11, ["🖥 ウルトラワイドモニター", "🪑 ゲーミングチェア", "🎹 シンセサイザー", "🔭 望遠鏡",
                 "🛋 ふかふかソファ", "🎮 ゲーム機"]),
    "SSR": (2.5, ["👑 集中の王冠", "🐉 締め切りドラゴン", "🌈 虹色のマウス", "🧙 時間の魔法使い"]),
    "UR":  (0.5, ["🌌 無限の集中力", "⏳ 止まった砂時計"]),
}
STARS = {"N": "", "R": "✨", "SR": "🌟🌟", "SSR": "🎆🎆🎆", "UR": "🌌🌌🌌🌌"}
ORDER = list(POOL)


def roll(min_rarity=None):
    """1回引く。min_rarity を指定すると、それ以上のレア度だけから引く"""
    pool = {k: v for k, v in POOL.items() if not min_rarity or ORDER.index(k) >= ORDER.index(min_rarity)}
    r = random.uniform(0, sum(v[0] for v in pool.values()))
    for rarity, (rate, items) in pool.items():
        if r < rate:
            return rarity, random.choice(items)
        r -= rate
    rarity = list(pool)[-1]
    return rarity, random.choice(pool[rarity][1])


def setup(api):
    api.data.setdefault("tickets", 0)
    api.data.setdefault("owned", {})       # アイテム → 個数
    api.data.setdefault("pulls", 0)
    api.data.setdefault("pity", 0)         # SSR 以上が出ていない回数
    api.data.setdefault("complete", [])    # コンプしたレア度
    s = {"sec": 0, "last": None}
    w = {}

    def total_items():
        return sum(len(v[1]) for v in POOL.values())

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(side="left")
        ttk.Button(frame, text="図鑑", command=book).pack(side="right")
        ttk.Button(frame, text="10連", command=lambda: pull(10)).pack(side="right", padx=4)
        ttk.Button(frame, text="1回引く", command=lambda: pull(1)).pack(side="right")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        left = (TICKET_SEC - s["sec"]) // 60
        w["l"].configure(text=f"🎟 {api.data['tickets']} 枚 · 図鑑 {len(api.data['owned'])}/{total_items()}"
                              f" · 天井まで {PITY - api.data['pity']} · 次まで {left}分")

    def get_one(min_rarity=None):
        if api.data["pity"] >= PITY - 1:
            min_rarity = "SSR"
        rarity, item = roll(min_rarity)
        api.data["pity"] = 0 if ORDER.index(rarity) >= ORDER.index("SSR") else api.data["pity"] + 1
        new = item not in api.data["owned"]
        api.data["owned"][item] = api.data["owned"].get(item, 0) + 1
        api.data["pulls"] += 1
        return rarity, item, new

    def check_complete():
        for rarity, (rate, items) in POOL.items():
            if rarity not in api.data["complete"] and all(it in api.data["owned"] for it in items):
                api.data["complete"].append(rarity)
                bonus = ORDER.index(rarity) + 1
                api.data["tickets"] += bonus
                api.notify(f"📖 {rarity} をコンプリート！ ごほうびチケット +{bonus} 枚")

    def pull(n):
        if api.data["tickets"] < n:
            messagebox.showinfo("作業ガチャ", f"チケットが足りません（{api.data['tickets']} / {n} 枚）。"
                                              "作業30分で1枚もらえます！", parent=api.root)
            return
        api.data["tickets"] -= n
        results = [get_one() for _ in range(n)]
        if n == 10 and all(ORDER.index(r) < ORDER.index("SR") for r, _, _ in results):
            results[-1] = get_one("SR")          # 10連は SR 以上を1つ確定
            api.data["pulls"] -= 1
        check_complete()
        api.save_data()
        render()
        lines = [f"{STARS[r]}【{r}】 {it}{'  NEW！' if new else ''}" for r, it, new in results]
        messagebox.showinfo("作業ガチャ", "\n".join(lines), parent=api.root)

    def book():
        lines = []
        for rarity, (rate, items) in POOL.items():
            got = sum(1 for it in items if it in api.data["owned"])
            mark = " 👑COMP" if rarity in api.data["complete"] else ""
            lines.append(f"―― {rarity}（{rate}%） {got}/{len(items)}{mark} ――")
            for it in items:
                n = api.data["owned"].get(it)
                lines.append(f"  {it} ×{n}" if n else "  ？？？")
        lines.append(f"\n合計 {api.data['pulls']} 回 引きました")
        messagebox.showinfo("ガチャ図鑑", "\n".join(lines), parent=api.root)

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= TICKET_SEC:
            s["sec"] -= TICKET_SEC
            api.data["tickets"] += 1
            api.save_data()
            api.notify(f"🎟 ガチャチケットをゲット！（{api.data['tickets']} 枚）")
        if datetime.now().second == 0:
            render()

    @api.on("goal_reached")
    def goal(goal_min, streak):
        api.data["tickets"] += 2
        api.save_data()
        api.notify("🎟 目標達成ボーナス！ チケット +2 枚")
        render()

    @api.on("day_change")
    def new_day(day):
        s["last"] = None

    api.add_panel(build, title="作業ガチャ")
    api.add_action("ガチャを引く", lambda: pull(1))
    api.add_action("10連ガチャ", lambda: pull(10))
    api.add_action("図鑑を見る", book)
