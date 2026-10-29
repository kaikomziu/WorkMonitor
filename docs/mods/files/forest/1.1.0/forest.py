"""作業の森

作業30分ごとに木が1本ずつ生えて、森ができていきます。休まず続けるほど大きな木に。

1.1.0: めずらしい木（低確率）・森の図鑑・森のレベル（累計本数で称号）・過去の森の記録を追加
"""

import random
from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk

MOD_INFO = {
    "name": "作業の森",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "作業30分ごとに木が1本生えます。休憩なしで続けた分は大きな木に、たまにめずらしい木も。"
                   "図鑑・森の称号・過去の森の記録つき。",
    "api": 1,
}

TREE_SEC = 30 * 60
SMALL = ["🌱", "🌿", "🌷", "🍀"]
BIG = ["🌲", "🌳", "🌴", "🎄"]
RARE = ["🌸", "🍄", "🌵", "🎋", "🌻", "🍁"]          # 5% で生える
LEVELS = [(0, "草むら"), (10, "雑木林"), (50, "小さな森"), (150, "深い森"), (400, "大森林"), (1000, "世界樹の森")]


def level(total):
    name = LEVELS[0][1]
    for need, n in LEVELS:
        if total >= need:
            name = n
    return name


def setup(api):
    api.data.setdefault("total", 0)
    api.data.setdefault("dex", {})         # 木 → 本数
    api.data.setdefault("past", {})        # 日付 → その日の森（文字列）
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "trees": []})
    s = {"sec": 0, "streak": 0, "last": None}
    w = {}

    def build(frame):
        w["t"] = tk.Text(frame, height=3, width=40, font=("Segoe UI Emoji", 14), relief="flat",
                         bg=api.colors["bg"], fg=api.colors["text"], wrap="char", cursor="arrow")
        w["t"].pack(fill="x")
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x")
        w["l"] = ttk.Label(bottom, foreground=api.colors["sub"])
        w["l"].pack(side="left")
        ttk.Button(bottom, text="記録", command=history).pack(side="right")
        ttk.Button(bottom, text="図鑑", command=dex).pack(side="right", padx=4)
        render()

    def render():
        if not (w.get("t") and w["t"].winfo_exists()):
            return
        w["t"].configure(state="normal")
        w["t"].delete("1.0", "end")
        w["t"].insert("end", "".join(api.data["trees"]) or "（まだ木がありません）")
        w["t"].configure(state="disabled")
        left = (TREE_SEC - s["sec"]) // 60
        w["l"].configure(text=f"今日 {len(api.data['trees'])} 本 · 累計 {api.data['total']} 本"
                              f"「{level(api.data['total'])}」 · 次の木まで {left}分")

    def dex():
        lines = []
        for group, trees in (("ふつうの木", SMALL + BIG), ("めずらしい木", RARE)):
            lines.append(f"―― {group} ――")
            lines += [f"  {t} ×{api.data['dex'][t]}" if t in api.data["dex"] else "  ？" for t in trees]
        messagebox.showinfo("森の図鑑", "\n".join(lines), parent=api.root)

    def history():
        days = sorted(api.data["past"], reverse=True)[:14]
        lines = [f"{d}  {api.data['past'][d]}" for d in days]
        messagebox.showinfo("過去の森", "\n".join(lines) or "まだ記録がありません", parent=api.root)

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= TREE_SEC:
            s["sec"] -= TREE_SEC
            s["streak"] += 1
            if random.random() < 0.05:
                tree = random.choice(RARE)
            else:
                tree = random.choice(BIG if s["streak"] >= 2 else SMALL)
            before = level(api.data["total"])
            api.data["trees"].append(tree)
            api.data["total"] += 1
            new = tree not in api.data["dex"]
            api.data["dex"][tree] = api.data["dex"].get(tree, 0) + 1
            api.save_data()
            msg = f"{tree} 木が生えました！（今日 {len(api.data['trees'])} 本目）"
            if tree in RARE:
                msg = f"✨ めずらしい木 {tree} が生えました！" + ("（図鑑に登録）" if new else "")
            api.notify(msg)
            if level(api.data["total"]) != before:
                api.notify(f"🌳 森が「{level(api.data['total'])}」に育ちました！")
            render()
        elif status["today_sec"] % 60 == 0:
            render()

    @api.on("state_change")
    def changed(old, new, status):
        if new == "idle":
            s["streak"] = 0

    @api.on("day_change")
    def new_day(day):
        if api.data["trees"]:
            api.data["past"][api.data["day"]] = "".join(api.data["trees"])
            keep = sorted(api.data["past"])[-60:]
            api.data["past"] = {k: api.data["past"][k] for k in keep}
        api.data.update({"day": day, "trees": []})
        s.update({"sec": 0, "streak": 0, "last": None})
        api.save_data()
        render()

    api.add_panel(build, title="作業の森")
    api.add_action("森の図鑑", dex)
    api.add_action("過去の森", history)
