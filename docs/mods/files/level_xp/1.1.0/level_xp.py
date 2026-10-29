"""レベル＆経験値

作業1分ごとに 1 XP。たまるとレベルが上がる、RPG 風の MOD です。

1.1.0: カテゴリ別のスキルレベル・連続達成でXP倍率アップ・オーバーレイに Lv 表示・今日のXPを追加
"""

from datetime import date
from tkinter import messagebox, ttk

MOD_INFO = {
    "name": "レベル＆経験値",
    "version": "1.1.0",
    "author": "かるわか",
    "description": "作業1分で1XP、目標達成でボーナス30XP。連続達成日数でXP倍率アップ。カテゴリ別のスキルレベルも育ちます。",
    "api": 1,
}

TITLES = [(1, "見習い"), (5, "駆け出し"), (10, "一人前"), (20, "ベテラン"), (35, "達人"), (50, "仙人"), (80, "伝説")]


def need(level):
    """そのレベルから次のレベルに上がるのに必要な XP"""
    return 30 + level * 10


def title(level):
    t = TITLES[0][1]
    for lv, name in TITLES:
        if level >= lv:
            t = name
    return t


def skill_level(xp):
    """スキルは 60XP（1時間）ごとに 1 レベル"""
    return xp // 60 + 1


def setup(api):
    api.data.setdefault("level", 1)
    api.data.setdefault("xp", 0)
    api.data.setdefault("total", 0)
    api.data.setdefault("streak", 0)
    api.data.setdefault("skills", {})      # カテゴリ → XP
    api.data.setdefault("overlay", True)
    if api.data.get("day") != date.today().isoformat():
        api.data.update({"day": date.today().isoformat(), "today": 0})
    s = {"sec": 0, "last": None, "carry": 0.0}
    w = {}

    def mult():
        # 連続達成3日ごとに +10%（最大 2倍）
        return min(2.0, 1 + (api.data["streak"] // 3) * 0.1)

    def build(frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        w["l"] = ttk.Label(top, font=("Segoe UI", 14, "bold"))
        w["l"].pack(side="left")
        ttk.Button(top, text="スキル", command=skills).pack(side="right")
        w["bar"] = ttk.Progressbar(frame)
        w["bar"].pack(fill="x", pady=3)
        w["sub"] = ttk.Label(frame, foreground=api.colors["sub"])
        w["sub"].pack(anchor="w")
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        lv = api.data["level"]
        w["l"].configure(text=f"⚔ Lv.{lv}  {title(lv)}")
        w["bar"].configure(maximum=need(lv), value=api.data["xp"])
        w["sub"].configure(text=f"XP {api.data['xp']} / {need(lv)} · 今日 +{api.data['today']} XP"
                                f" · 倍率 ×{mult():.1f} · 累計 {api.data['total']} XP")

    def gain(xp, category=None):
        api.data["xp"] += xp
        api.data["total"] += xp
        api.data["today"] += xp
        if category:
            before = skill_level(api.data["skills"].get(category, 0))
            api.data["skills"][category] = api.data["skills"].get(category, 0) + xp
            after = skill_level(api.data["skills"][category])
            if after > before and after % 5 == 0:
                api.notify(f"📘 スキル「{category}」が Lv.{after} になりました")
        while api.data["xp"] >= need(api.data["level"]):
            api.data["xp"] -= need(api.data["level"])
            api.data["level"] += 1
            lv = api.data["level"]
            api.notify(f"🎉 レベルアップ！ Lv.{lv}「{title(lv)}」になりました")
        api.save_data()
        render()

    def skills():
        items = sorted(api.data["skills"].items(), key=lambda kv: -kv[1])
        lines = [f"{k}  Lv.{skill_level(v)}（{v} XP）" for k, v in items]
        messagebox.showinfo("スキル", "\n".join(lines) or "まだスキルがありません", parent=api.root)

    @api.on("tick")
    def tick(status):
        last, s["last"] = s["last"], status["today_sec"]
        if last is not None and status["today_sec"] > last:
            s["sec"] += status["today_sec"] - last
        if s["sec"] >= 60:
            s["sec"] -= 60
            s["carry"] += mult()
            xp = int(s["carry"])
            s["carry"] -= xp
            gain(xp, status["category"] or "その他")

    @api.on("goal_reached")
    def goal(goal_min, streak):
        api.data["streak"] = streak
        gain(30)
        api.notify(f"✨ 目標達成ボーナス +30 XP（XP倍率 ×{mult():.1f}）")

    @api.on("day_change")
    def new_day(day):
        api.data.update({"day": day, "today": 0})
        api.save_data()
        s["last"] = None

    @api.filter("overlay_text")
    def overlay(text):
        return f"Lv.{api.data['level']} {text}" if api.data["overlay"] else text

    def toggle_overlay():
        api.data["overlay"] = not api.data["overlay"]
        api.save_data()

    api.add_panel(build, title="レベル")
    api.add_action("スキルを見る", skills)
    api.add_action("オーバーレイの Lv 表示のオン／オフ", toggle_overlay)
