"""実績（アチーブメント）

いろいろな条件を満たすと実績が解除されます。
"""

from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk

MOD_INFO = {
    "name": "実績",
    "version": "2.0.0",
    "author": "かるわか",
    "description": "作業時間・時間帯・連続達成・集中・季節など、60以上の実績を解除して集めます。解除すると通知します。",
    "api": 1,
}

# ID → (名前, 説明, グループ)
ACHIEVEMENTS = {
    # 1日の作業時間
    "first":      ("はじめの一歩", "はじめて作業した", "1日の作業時間"),
    "m10":        ("ウォームアップ", "1日に10分作業した", "1日の作業時間"),
    "h1":         ("1時間の壁", "1日に1時間作業した", "1日の作業時間"),
    "h3":         ("3時間コース", "1日に3時間作業した", "1日の作業時間"),
    "h5":         ("ハードワーカー", "1日に5時間作業した", "1日の作業時間"),
    "h8":         ("フルタイム", "1日に8時間作業した", "1日の作業時間"),
    "h10":        ("10時間の壁", "1日に10時間作業した", "1日の作業時間"),
    "h12":        ("鉄人", "1日に12時間作業した", "1日の作業時間"),
    "h15":        ("限界突破", "1日に15時間作業した", "1日の作業時間"),
    # 累計
    "t10":        ("積み重ね 10時間", "累計で10時間作業した", "累計"),
    "t50":        ("積み重ね 50時間", "累計で50時間作業した", "累計"),
    "t100":       ("百時間の旅人", "累計で100時間作業した", "累計"),
    "t300":       ("三百時間の職人", "累計で300時間作業した", "累計"),
    "t500":       ("五百時間の達人", "累計で500時間作業した", "累計"),
    "t1000":      ("千時間の求道者", "累計で1000時間作業した", "累計"),
    "days3":      ("三日目の朝", "作業した日が3日になった", "累計"),
    "days10":     ("10日の積み重ね", "作業した日が10日になった", "累計"),
    "days30":     ("1か月の積み重ね", "作業した日が30日になった", "累計"),
    "days100":    ("100日の積み重ね", "作業した日が100日になった", "累計"),
    "days365":    ("1年の積み重ね", "作業した日が365日になった", "累計"),
    # 時間帯
    "early":      ("早起きは三文の徳", "朝6時前に作業した", "時間帯"),
    "early5":     ("朝型人間", "朝6時前に作業した日が5日になった", "時間帯"),
    "morning":    ("朝活マスター", "朝8時までに1時間作業した", "時間帯"),
    "lunch":      ("昼休み返上", "12時台に作業した", "時間帯"),
    "night":      ("夜ふかし職人", "深夜2時以降に作業した", "時間帯"),
    "night5":     ("夜の住人", "深夜2時以降に作業した日が5日になった", "時間帯"),
    "midnight":   ("日付またぎ", "作業中に日付が変わった", "時間帯"),
    "zorome":     ("ゾロ目の奇跡", "11:11 か 22:22 に作業していた", "時間帯"),
    # 目標・連続
    "goal1":      ("目標クリア", "1日の目標をはじめて達成した", "目標・連続"),
    "goals10":    ("達成グセ", "目標を10回達成した", "目標・連続"),
    "goals50":    ("達成のプロ", "目標を50回達成した", "目標・連続"),
    "goals100":   ("百戦錬磨", "目標を100回達成した", "目標・連続"),
    "goal_am":    ("午前中で完了", "正午までに目標を達成した", "目標・連続"),
    "double":     ("ダブルスコア", "目標の2倍の時間作業した", "目標・連続"),
    "streak3":    ("三日坊主卒業", "3日連続で目標を達成した", "目標・連続"),
    "streak7":    ("1週間の習慣", "7日連続で目標を達成した", "目標・連続"),
    "streak14":   ("2週間の習慣", "14日連続で目標を達成した", "目標・連続"),
    "streak30":   ("習慣の達人", "30日連続で目標を達成した", "目標・連続"),
    "streak60":   ("習慣の鬼", "60日連続で目標を達成した", "目標・連続"),
    "streak100":  ("百日行", "100日連続で目標を達成した", "目標・連続"),
    "streak365":  ("一年皆勤", "365日連続で目標を達成した", "目標・連続"),
    # 集中
    "s30":        ("集中モード", "休憩なしで30分作業した", "集中"),
    "s60":        ("ゾーン突入", "休憩なしで1時間作業した", "集中"),
    "s120":       ("深い集中", "休憩なしで2時間作業した", "集中"),
    "s180":       ("無我の境地", "休憩なしで3時間作業した", "集中"),
    "same2h":     ("一点集中", "同じアプリで2時間続けて作業した", "集中"),
    "steady":     ("ブレない心", "3時間以上作業して、切り替えが20回未満だった", "集中"),
    "pure":       ("脇目もふらず", "3時間以上作業して、数えないアプリは5分未満だった", "集中"),
    # アプリ・休憩
    "apps5":      ("マルチタスカー", "1日に5種類のアプリで作業した", "アプリ・休憩"),
    "apps10":     ("なんでも屋", "1日に10種類のアプリで作業した", "アプリ・休憩"),
    "cats3":      ("多才", "1日に3つのカテゴリで作業した", "アプリ・休憩"),
    "switch100":  ("ザッピング王", "1日にアプリを100回切り替えた", "アプリ・休憩"),
    "breaks10":   ("こまめな休憩", "1日に10回休憩した", "アプリ・休憩"),
    "detour":     ("ちょっと寄り道", "1日に数えないアプリを1時間使った", "アプリ・休憩"),
    # 曜日・季節
    "weekend":    ("休日出勤", "土日に2時間以上作業した", "曜日・季節"),
    "weekend10":  ("休日の求道者", "土日に作業した日が10日になった", "曜日・季節"),
    "monday":     ("月曜日に勝つ", "月曜の朝9時前に作業した", "曜日・季節"),
    "friday":     ("華金の前に", "金曜日に目標を達成した", "曜日・季節"),
    "allweek":    ("皆勤賞", "月曜から日曜まで毎日作業した", "曜日・季節"),
    "newyear":    ("書き初め", "1月1日に作業した", "曜日・季節"),
    "xmas":       ("聖夜の作業", "12月24日か25日に作業した", "曜日・季節"),
    "halloween":  ("いたずらより作業", "10月31日に作業した", "曜日・季節"),
    # その他
    "comeback":   ("おかえりなさい", "7日以上あいだをあけて作業を再開した", "その他"),
    "half":       ("コレクター", "実績を半分解除した", "その他"),
    "complete":   ("実績マスター", "ほかの実績をすべて解除した", "その他"),
}

GROUPS = ["1日の作業時間", "累計", "時間帯", "目標・連続", "集中", "アプリ・休憩", "曜日・季節", "その他"]


def setup(api):
    d = api.data
    d.setdefault("unlocked", {})        # ID → 解除した日時
    d.setdefault("work_days", [])       # 作業した日
    d.setdefault("early_days", [])
    d.setdefault("night_days", [])
    d.setdefault("weekend_days", [])
    d.setdefault("total_sec", 0)
    d.setdefault("goal_count", 0)
    if d.get("day") != date.today().isoformat():
        d.update({"day": date.today().isoformat(), "switches": 0, "breaks": 0, "excluded": 0, "cats": []})
    # セッション中だけの値（保存しない）
    s = {"last": None, "session": 0, "app": None, "same": 0, "n": 0, "working": False}
    w = {}

    def unlock(key):
        if key in d["unlocked"]:
            return
        d["unlocked"][key] = datetime.now().strftime("%Y-%m-%d %H:%M")
        api.save_data()
        name, desc, _ = ACHIEVEMENTS[key]
        api.notify(f"🏅 実績解除「{name}」 — {desc}")
        n = len(d["unlocked"])
        if n >= len(ACHIEVEMENTS) // 2:
            unlock("half")
        if n >= len(ACHIEVEMENTS) - 1:
            unlock("complete")
        render()

    def add_day(name, day):
        if day not in d[name]:
            d[name].append(day)
            api.save_data()
        return len(d[name])

    # ---- 画面 ----
    def build(frame):
        w["l"] = ttk.Label(frame)
        w["l"].pack(side="left")
        ttk.Button(frame, text="一覧", command=show).pack(side="right")
        w["bar"] = ttk.Progressbar(frame, maximum=len(ACHIEVEMENTS), length=120)
        w["bar"].pack(side="right", padx=8)
        render()

    def render():
        if not (w.get("l") and w["l"].winfo_exists()):
            return
        n = len(d["unlocked"])
        latest = max(d["unlocked"].items(), key=lambda kv: kv[1], default=None)
        tail = f" · 最新「{ACHIEVEMENTS[latest[0]][0]}」" if latest and latest[0] in ACHIEVEMENTS else ""
        w["l"].configure(text=f"🏅 {n} / {len(ACHIEVEMENTS)} 解除{tail}")
        w["bar"]["value"] = n

    def show():
        win = tk.Toplevel(api.root)
        win.title(f"実績（{len(d['unlocked'])} / {len(ACHIEVEMENTS)}）")
        win.geometry("460x560")
        bg = "#1b1f29" if api.dark else "#ffffff"
        t = tk.Text(win, wrap="word", font=("Segoe UI", 10), relief="flat", bg=bg, fg=api.colors["text"],
                    padx=12, pady=8)
        sb = ttk.Scrollbar(win, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.tag_configure("h", font=("Segoe UI", 11, "bold"), spacing1=8, spacing3=2)
        t.tag_configure("lock", foreground=api.colors["sub"])
        for g in GROUPS:
            keys = [k for k, v in ACHIEVEMENTS.items() if v[2] == g]
            got = sum(1 for k in keys if k in d["unlocked"])
            t.insert("end", f"{g}（{got}/{len(keys)}）\n", "h")
            for k in keys:
                name, desc, _ = ACHIEVEMENTS[k]
                when = d["unlocked"].get(k)
                if when:
                    t.insert("end", f"🏅 {name} — {desc}（{when}）\n")
                else:
                    t.insert("end", f"🔒 ？？？ — {desc}\n", "lock")
        t.configure(state="disabled")

    # ---- 判定 ----
    @api.on("tick")
    def tick(status):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        last, s["last"] = s["last"], status["today_sec"]
        delta = status["today_sec"] - last if last is not None and status["today_sec"] > last else 0

        if status["state"] == "excluded":
            d["excluded"] += 1
            if d["excluded"] >= 3600:
                unlock("detour")
        if delta:
            d["total_sec"] += delta
            s["session"] += delta
            if status["app"] != s["app"]:
                s.update({"app": status["app"], "same": 0})
            s["same"] += delta
            if status["category"] and status["category"] not in d["cats"]:
                d["cats"].append(status["category"])
        s["working"] = status["state"] == "working"

        if status["state"] == "working":
            first_today = today not in d["work_days"]
            if first_today and d["work_days"]:
                gap = (date.today() - date.fromisoformat(max(d["work_days"]))).days
                if gap >= 7:
                    unlock("comeback")
            days = add_day("work_days", today)
            unlock("first")
            for need, key in ((3, "days3"), (10, "days10"), (30, "days30"), (100, "days100"), (365, "days365")):
                if days >= need:
                    unlock(key)
            # 時間帯
            if 4 <= now.hour < 6:
                unlock("early")
                if add_day("early_days", today) >= 5:
                    unlock("early5")
            if 2 <= now.hour < 4:
                unlock("night")
                if add_day("night_days", today) >= 5:
                    unlock("night5")
            if now.hour < 8 and status["today_sec"] >= 3600:
                unlock("morning")
            if now.hour == 12:
                unlock("lunch")
            if now.strftime("%H:%M") in ("11:11", "22:22"):
                unlock("zorome")
            # 曜日・季節
            if now.weekday() == 0 and now.hour < 9:
                unlock("monday")
            if now.weekday() >= 5:
                if add_day("weekend_days", today) >= 10:
                    unlock("weekend10")
                if status["today_sec"] >= 7200:
                    unlock("weekend")
            if now.weekday() == 6:
                monday = date.today() - timedelta(days=6)
                if all((monday + timedelta(days=i)).isoformat() in d["work_days"] for i in range(7)):
                    unlock("allweek")
            md = (now.month, now.day)
            if md == (1, 1):
                unlock("newyear")
            if md in ((12, 24), (12, 25)):
                unlock("xmas")
            if md == (10, 31):
                unlock("halloween")

        # 1日の作業時間
        sec = status["today_sec"]
        for need, key in ((600, "m10"), (3600, "h1"), (3 * 3600, "h3"), (5 * 3600, "h5"), (8 * 3600, "h8"),
                          (10 * 3600, "h10"), (12 * 3600, "h12"), (15 * 3600, "h15")):
            if sec >= need:
                unlock(key)
        # 累計
        total_h = d["total_sec"] / 3600
        for need, key in ((10, "t10"), (50, "t50"), (100, "t100"), (300, "t300"), (500, "t500"), (1000, "t1000")):
            if total_h >= need:
                unlock(key)
        # 集中
        for need, key in ((30, "s30"), (60, "s60"), (120, "s120"), (180, "s180")):
            if s["session"] >= need * 60:
                unlock(key)
        if s["same"] >= 7200:
            unlock("same2h")
        if sec >= 3 * 3600:
            if d["switches"] < 20:
                unlock("steady")
            if d["excluded"] < 300:
                unlock("pure")
        if status["goal_min"] and sec >= status["goal_min"] * 120:
            unlock("double")
        # アプリ
        apps = len([v for v in status["today_by_app"].values() if v >= 60])
        if apps >= 5:
            unlock("apps5")
        if apps >= 10:
            unlock("apps10")
        if len(d["cats"]) >= 3:
            unlock("cats3")

        s["n"] += 1
        if s["n"] % 60 == 0:
            api.save_data()

    @api.on("state_change")
    def changed(old, new, status):
        if new == "idle" and old == "working":
            s["session"] = 0
            s["same"] = 0
            d["breaks"] += 1
            if d["breaks"] >= 10:
                unlock("breaks10")

    @api.on("app_change")
    def app_changed(old_app, new_app, status):
        if old_app and new_app:
            d["switches"] += 1
            if d["switches"] >= 100:
                unlock("switch100")

    @api.on("goal_reached")
    def goal(goal_min, streak):
        d["goal_count"] += 1
        api.save_data()
        unlock("goal1")
        for need, key in ((10, "goals10"), (50, "goals50"), (100, "goals100")):
            if d["goal_count"] >= need:
                unlock(key)
        for need, key in ((3, "streak3"), (7, "streak7"), (14, "streak14"), (30, "streak30"),
                          (60, "streak60"), (100, "streak100"), (365, "streak365")):
            if streak >= need:
                unlock(key)
        now = datetime.now()
        if now.hour < 12:
            unlock("goal_am")
        if now.weekday() == 4:
            unlock("friday")

    @api.on("day_change")
    def new_day(day):
        if s["working"]:
            unlock("midnight")
        d.update({"day": day, "switches": 0, "breaks": 0, "excluded": 0, "cats": []})
        s["last"] = None
        api.save_data()

    api.add_panel(build, title="実績")
    api.add_action("実績の一覧を見る", show)


def teardown(api):
    api.save_data()
