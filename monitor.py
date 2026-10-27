"""作業監視ツールのコマンドライン版（GUI 版は app.py）

使い方:
    python monitor.py            # 監視開始（Ctrl+C で終了）
    python monitor.py report     # 今日の集計を表示
    python monitor.py report 2026-10-27   # 指定日の集計
    python monitor.py dashboard  # 表・グラフをブラウザで表示

設定とログは %APPDATA%\\WorkMonitor に保存される（GUI 版と共通）。
"""

import csv
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

import core


def run_monitor():
    config = core.load_config()
    print(f"監視を開始しました（{config['idle_threshold_sec']}秒 無操作で放置扱い）。Ctrl+C で終了。")
    mon = core.Monitor(config)
    mon.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        mon.stop()
        print("監視を終了しました。")


def fmt(sec):
    sec = int(sec)
    return f"{sec // 3600:d}時間{sec % 3600 // 60:02d}分"


def run_report(date_str):
    path = core.log_path(date_str)
    if not os.path.exists(path):
        print(f"{date_str} の記録はありません。")
        return

    config = core.load_config()
    by_cat = defaultdict(float)
    by_app = defaultdict(float)
    by_title = defaultdict(float)
    by_hour = defaultdict(float)
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            info = core.app_info(config, row["app"])
            if not info["count"]:
                continue
            sec = float(row["seconds"])
            by_cat[info["category"]] += sec
            by_app[info["name"]] += sec
            by_title[(info["name"], core.window_label(row["app"], row["title"]))] += sec
            by_hour[int(row["start"][:2])] += sec

    total = sum(by_app.values())
    print(f"=== {date_str} の作業時間: {fmt(total)} ===\n")

    print("[カテゴリ別]")
    for cat, sec in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {fmt(sec):>10}  {cat}")
    print()

    print("[アプリ別]")
    for app, sec in sorted(by_app.items(), key=lambda x: -x[1]):
        pct = sec / total * 100 if total else 0
        print(f"  {fmt(sec):>10}  {pct:5.1f}%  {app}")

    print("\n[サイト・ウィンドウ別 上位10件]")
    for (app, title), sec in sorted(by_title.items(), key=lambda x: -x[1])[:10]:
        print(f"  {fmt(sec):>10}  {app} - {title[:60]}")

    print("\n[時間帯別]")
    for h in range(24):
        if by_hour[h]:
            bar = "█" * int(by_hour[h] / 60 / 2)  # 1マス = 2分
            print(f"  {h:02d}時 {int(by_hour[h] / 60):3d}分 {bar}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "dashboard":
        from dashboard import build_dashboard
        print(f"ダッシュボードを作成しました: {build_dashboard()}")
    elif len(sys.argv) >= 2 and sys.argv[1] == "report":
        d = sys.argv[2] if len(sys.argv) >= 3 else datetime.now().strftime("%Y-%m-%d")
        run_report(d)
    else:
        run_monitor()
