"""連続日数バッジ

目標を達成した連続日数に応じて称号を付けます。
"""

from tkinter import ttk

MOD_INFO = {
    "name": "連続日数バッジ",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "目標達成の連続日数に応じて 🥉🥈🥇👑 の称号を表示し、ランクが上がったら通知します。",
    "api": 1,
}

# (必要な連続日数, バッジ, 称号)
RANKS = [
    (0, "🌱", "はじまり"),
    (3, "🥉", "ブロンズ"),
    (7, "🥈", "シルバー"),
    (14, "🥇", "ゴールド"),
    (30, "💎", "ダイヤ"),
    (100, "👑", "レジェンド"),
]


def rank(streak):
    cur = RANKS[0]
    for r in RANKS:
        if streak >= r[0]:
            cur = r
    return cur


def setup(api):
    api.data.setdefault("streak", 0)
    api.data.setdefault("best", 0)
    w = {}

    def build(frame):
        w["badge"] = ttk.Label(frame, font=("Segoe UI Emoji", 26))
        w["badge"].pack(side="left")
        w["l"] = ttk.Label(frame)
        w["l"].pack(side="left", padx=10)
        render()

    def render():
        if not (w.get("badge") and w["badge"].winfo_exists()):
            return
        st = api.data["streak"]
        need, badge, title = rank(st)
        nxt = next((r for r in RANKS if r[0] > st), None)
        w["badge"].configure(text=badge)
        tail = f"\n次の「{nxt[2]}」まであと {nxt[0] - st} 日" if nxt else "\n最高ランクです！"
        w["l"].configure(text=f"{title}（{st} 日連続 · 最高 {api.data['best']} 日）{tail}")

    @api.on("goal_reached")
    def goal(goal_min, streak):
        before = rank(api.data["streak"])
        api.data["streak"] = streak
        api.data["best"] = max(api.data["best"], streak)
        api.save_data()
        after = rank(streak)
        if after[0] > before[0]:
            api.notify(f"{after[1]} ランクアップ！「{after[2]}」になりました（{streak} 日連続）")
        render()

    api.add_panel(build, title="連続日数バッジ")
