"""日報の自動作成

日付が変わったら、前の日の作業時間とアプリ別の内訳を Markdown の日報にして保存します。
保存先: ドキュメント\\WorkMonitor日報\\2026-10-28.md
"""

import os
from datetime import date

MOD_INFO = {
    "name": "日報の自動作成",
    "version": "1.0.0",
    "author": "かるわか",
    "description": "日付が変わると前日の内訳を Markdown の日報にして「ドキュメント\\WorkMonitor日報」に保存します。",
    "api": 2,   # api.open_path を使う（WorkMonitor 1.7.0 以降）
}

OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "WorkMonitor日報")


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}時間{m:02d}分"


def write_report(day, status):
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = [f"# 日報 {day}", "", f"- 作業時間: **{fmt(status['today_sec'])}**"]
    if status["goal_min"]:
        mark = "✅ 達成" if status["today_sec"] >= status["goal_min"] * 60 else "未達成"
        lines.append(f"- 目標: {status['goal_min']} 分（{mark}）")
    lines += ["", "## アプリ別", "", "| アプリ | 時間 | 割合 |", "|---|---|---|"]
    total = sum(status["today_by_app"].values()) or 1
    for name, sec in sorted(status["today_by_app"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {fmt(sec)} | {sec * 100 / total:.0f}% |")
    path = os.path.join(OUT_DIR, f"{day}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def setup(api):
    s = {"status": None, "day": date.today().isoformat()}

    @api.on("tick")
    def tick(status):
        if status["today_sec"] > 0:
            s["status"] = dict(status, today_by_app=dict(status["today_by_app"]))

    @api.on("day_change")
    def new_day(day):
        # 日付が変わる直前の状態で、前の日の日報を書く
        if s["status"]:
            path = write_report(s["day"], s["status"])
            api.notify(f"📝 {s['day']} の日報を保存しました")
            api.log("保存:", path)
        s.update({"status": None, "day": day})

    def now():
        path = write_report(date.today().isoformat(), api.status())
        api.log("保存:", path)
        api.open_path(path)

    def open_dir():
        os.makedirs(OUT_DIR, exist_ok=True)
        api.open_path(OUT_DIR)

    api.add_action("今日の分を今すぐ書き出す", now)
    api.add_action("日報フォルダを開く", open_dir)
