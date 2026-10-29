"""作業ガチャ

作業30分ごとにガチャチケットが1枚もらえます。引いて図鑑をコンプリートしよう。
"""

import random
from datetime import datetime
from tkinter import messagebox, ttk

MOD_INFO = {
    "name": "作業ガチャ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "作業30分でガチャチケット1枚。N・R・SR・SSR のアイテムを集めて図鑑を埋めましょう。",
    "api": 1,
}

TICKET_SEC = 30 * 60

# レア度 → (出る確率 %, アイテム)
POOL = {
    "N":   (60, ["🍙 おにぎり", "☕ コーヒー", "📎 クリップ", "✏ えんぴつ", "🧦 くつした", "🍪 クッキー",
                 "📓 ノート", "🧃 ジュース"]),
    "R":   (28, ["⌨ キーボード", "🎧 ヘッドホン", "🪴 観葉植物", "🕶 サングラス", "📚 技術書", "🧸 くま"]),
    "SR":  (10, ["🖥 ウルトラワイドモニター", "🪑 ゲーミングチェア", "🎹 シンセサイザー", "🔭 望遠鏡"]),
    "SSR": (2,  ["👑 集中の王冠", "🐉 締め切りドラゴン", "🌈 虹色のマウス"]),
}


def setup(api):
    api.data.setdefault("tickets", 0)
    api.data.setdefault("owned", {})       # アイテム → 個数
    api.data.setdefault("pulls", 0)
    s = {"sec": 0, "last": None}
    w = {}

    def total_items():
        return sum(len(v[1]) for v in POOL.values())

    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(side="left")
        ttk.Button(frame, text="図鑑", command=book).pack(side="right")
        ttk.Button(frame, text="ガチャを引く", command=pull).pack(side="right", padx=6)
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        left = (TICKET_SEC - s["sec"]) // 60
        w["l"].configure(text=f"🎟 チケット {api.data['tickets']} 枚 · 図鑑 {len(api.data['owned'])}/{total_items()}"
                              f" · 次まで {left}分")

    def pull():
        if api.data["tickets"] <= 0:
            messagebox.showinfo("作業ガチャ", "チケットがありません。作業30分で1枚もらえます！", parent=api.root)
            return
        api.data["tickets"] -= 1
        api.data["pulls"] += 1
        r = random.uniform(0, 100)
        for rarity, (rate, items) in POOL.items():
            if r < rate:
                break
            r -= rate
        item = random.choice(items)
        new = item not in api.data["owned"]
        api.data["owned"][item] = api.data["owned"].get(item, 0) + 1
        api.save_data()
        render()
        star = {"N": "", "R": "✨", "SR": "🌟🌟", "SSR": "🎆🎆🎆"}[rarity]
        messagebox.showinfo("作業ガチャ", f"{star}\n【{rarity}】 {item}\n{'NEW！' if new else ''}", parent=api.root)

    def book():
        lines = []
        for rarity, (rate, items) in POOL.items():
            lines.append(f"―― {rarity}（{rate}%）――")
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

    @api.on("day_change")
    def new_day(day):
        s["last"] = None

    api.add_panel(build, title="作業ガチャ")
    api.add_action("ガチャを引く", pull)
    api.add_action("図鑑を見る", book)
